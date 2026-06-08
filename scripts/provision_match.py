#!/usr/bin/env python3
"""Model provisioner matcher -- pick the best-fit model for a host envelope.

Pure stdlib (tomllib, Python 3.11+). Given a profiled host
(run/node_capabilities.json) and the catalog (run/model_playbook.toml), return the
model + quant + runtime settings the first-run provisioner should download and wire
into config.toml. See docs/model_provisioner_design_20260607_2158.md.

Run standalone:  python scripts/provision_match.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None


def load_playbook(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def envelope_from_caps(caps):
    """Normalize node_capabilities.json into the matcher's resource envelope."""
    accels = caps.get("accel_present") or []
    usable = [a for a in accels if a.get("usable_for_llm")]
    mem_model = caps.get("memory_model") or ("discrete" if usable else "cpu")
    return {
        "arch": caps.get("arch"),
        "os": caps.get("os"),
        "ram_mb": caps.get("ram_mb") or 0,
        "vram_mb": caps.get("vram_mb") or 0,
        "memory_model": mem_model,
        "camera_present": bool(caps.get("camera_present")),
        "has_gpu": bool(usable),
    }


def compute_budget(env, meta):
    """Largest model file (MiB) the host can load, plus the VRAM-only budget.

    A model can occupy system RAM (CPU / partial offload) OR VRAM (full offload),
    so the load budget is the max of the two pools after reserves. On unified
    memory the VRAM is carved from RAM, so RAM total is the single pool."""
    reserve = meta.get("reserve_mb", 4096)
    vram_reserve = meta.get("vram_reserve_mb", 1024)
    ram_budget = max(0, (env.get("ram_mb") or 0) - reserve)
    vram_budget = max(0, (env.get("vram_mb") or 0) - vram_reserve)
    if env.get("memory_model") == "unified":
        budget = ram_budget
    else:
        budget = max(ram_budget, vram_budget)
    return budget, vram_budget


def _largest_fitting_quant(model, budget_mb, cpu_only, cpu_max_file_mb):
    """Biggest quant whose size <= budget (and <= the CPU cap on CPU-only hosts)."""
    best = None
    for q in model.get("quants", []):
        size = q.get("size_mb")
        if size is None or size > budget_mb:
            continue
        if cpu_only and size > cpu_max_file_mb:
            continue
        if best is None or size > best["size_mb"]:
            best = q
    return best


def match(env, playbook):
    """Return the best pick dict, or None if nothing fits."""
    meta = playbook.get("meta", {})
    budget_mb, vram_budget = compute_budget(env, meta)
    cpu_only = not env.get("has_gpu")
    cpu_max = meta.get("cpu_max_file_mb", 9000)
    vboost = meta.get("vision_boost", 5)
    vsoft = meta.get("vision_soft_boost", 2)

    candidates = []
    for model in playbook.get("model", []):
        quant = _largest_fitting_quant(model, budget_mb, cpu_only, cpu_max)
        if not quant:
            continue
        score = model.get("rank", 0)
        if model.get("vision"):
            score += vsoft
            if env.get("camera_present"):
                score += vboost
        candidates.append((score, quant["size_mb"], model, quant))

    if not candidates:
        return None
    # highest score; tiebreak by larger quant (more capable), then id (determinism)
    candidates.sort(key=lambda c: (c[0], c[1], c[2]["id"]), reverse=True)
    score, _, model, quant = candidates[0]

    full_offload = bool(env.get("has_gpu")) and quant["size_mb"] <= vram_budget
    vision_enabled = bool(model.get("vision") and env.get("camera_present"))
    ctx = model.get("ctx_default", 8192)
    if quant["size_mb"] > budget_mb * 0.85:   # tight budget -> conservative ctx
        ctx = model.get("min_ctx", ctx)

    return {
        "model_id": model["id"],
        "family": model.get("family"),
        "license": model.get("license"),
        "repo": model.get("repo"),
        "quant": quant["name"],
        "file": quant["file"],
        "size_mb": quant["size_mb"],
        "mmproj": model.get("mmproj"),
        "vision": bool(model.get("vision")),
        "vision_enabled": vision_enabled,
        "ctx": ctx,
        "full_gpu_offload": full_offload,
        "budget_mb": budget_mb,
        "score": score,
    }


def explain(pick):
    if not pick:
        return "No compatible model fits this host's memory budget."
    off = "full GPU offload" if pick["full_gpu_offload"] else "partial offload / CPU"
    if pick["vision_enabled"]:
        vis = "vision ON (camera detected)"
    elif pick["vision"]:
        vis = "vision available (opt-in; no camera)"
    else:
        vis = "text-only"
    return (f"{pick['model_id']} {pick['quant']} ({pick['size_mb']} MiB) -> {off}, "
            f"ctx {pick['ctx']}, {vis}. repo={pick['repo']} "
            f"budget={pick['budget_mb']} MiB")


def main(argv):
    if tomllib is None:
        print("ERROR: tomllib requires Python 3.11+", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parent.parent
    caps = json.loads((root / "run" / "node_capabilities.json").read_text("utf-8"))
    playbook = load_playbook(root / "run" / "model_playbook.toml")
    pick = match(envelope_from_caps(caps), playbook)
    print(json.dumps(pick, indent=2) if pick else "null")
    print(explain(pick), file=sys.stderr)
    return 0 if pick else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
