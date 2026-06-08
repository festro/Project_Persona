#!/usr/bin/env python3
"""Offline tests for the model provisioner matcher (scripts/provision_match.py).

Exercises envelope_from_caps + match against the real run/model_playbook.toml with
synthetic host profiles. Pure stdlib; needs Python 3.11+ (tomllib).

Run:  python tests/test_provision_match.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import provision_match as pm  # noqa: E402

PLAYBOOK = pm.load_playbook(ROOT / "run" / "model_playbook.toml")


def caps(ram, vram, mem_model, gpu, camera, arch="x86_64", os_="linux"):
    """Build a node_capabilities.json-shaped dict."""
    accel = ([{"vendor": "amd", "device": "GPU", "tier": 1,
               "backends": ["vulkan"], "usable_for_llm": True}] if gpu else [])
    return {
        "arch": arch, "os": os_, "ram_mb": ram, "vram_mb": vram,
        "memory_model": mem_model, "camera_present": camera,
        "accel_present": accel,
    }


def pick_for(**kw):
    return pm.match(pm.envelope_from_caps(caps(**kw)), PLAYBOOK)


CASES = [
    # name, kwargs, expected_model_id, expected_vision_enabled, expected_full_offload
    ("brandon_no_cam (16GB VRAM / 32GB RAM discrete)",
     dict(ram=31858, vram=16304, mem_model="discrete", gpu=True, camera=False),
     "qwen3.6-35b-a3b", False, False),
    ("brandon_cam (same + webcam)",
     dict(ram=31858, vram=16304, mem_model="discrete", gpu=True, camera=True),
     "qwen3.6-35b-a3b", True, False),
    ("evo_x2 (96GB unified APU)",
     dict(ram=96000, vram=49152, mem_model="unified", gpu=True, camera=False),
     "qwen3.6-35b-a3b", False, True),
    ("mid_discrete_cam (16GB RAM / 8GB VRAM + webcam)",
     dict(ram=16000, vram=8192, mem_model="discrete", gpu=True, camera=True),
     "pixtral-12b", True, False),
    ("pi_headless (8GB ARM CPU, no camera)",
     dict(ram=8000, vram=0, mem_model="cpu", gpu=False, camera=False, arch="arm64"),
     "qwen3-4b", False, False),
    ("pi_camera (8GB ARM CPU + camera)",
     dict(ram=8000, vram=0, mem_model="cpu", gpu=False, camera=True, arch="arm64"),
     "smolvlm2-2.2b", True, False),
]


def main():
    failures = 0
    for name, kw, exp_id, exp_vis, exp_off in CASES:
        p = pick_for(**kw)
        got_id = p["model_id"] if p else None
        got_vis = p["vision_enabled"] if p else None
        got_off = p["full_gpu_offload"] if p else None
        ok = (got_id == exp_id and got_vis == exp_vis and got_off == exp_off)
        flag = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        line = pm.explain(p) if p else "None"
        print(f"[{flag}] {name}")
        print(f"        -> {line}")
        if not ok:
            print(f"        EXPECTED id={exp_id} vision_enabled={exp_vis} "
                  f"full_offload={exp_off}")

    # edge: 4GB host is below the 8GB floor -> nothing should fit
    tiny = pick_for(ram=4000, vram=0, mem_model="cpu", gpu=False, camera=False)
    ok = tiny is None
    print(f"[{'PASS' if ok else 'FAIL'}] tiny_4gb -> {'None (unsupported)' if ok else tiny}")
    if not ok:
        failures += 1

    total = len(CASES) + 1
    print(f"\n{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
