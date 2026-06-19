#!/usr/bin/env python3
"""Model provisioner -- download + preflight + config wiring (P3).

Consumes a pick dict from scripts/provision_match.match() and:
  - gates on license (default catalog is OSI-open/ungated; gated needs HF_TOKEN),
  - checks free disk space (file size + margin),
  - builds a download plan (base GGUF + matching mmproj when vision),
  - downloads via huggingface_hub (resumable; network branch only),
  - renders + non-destructively wires the pick into run/config.toml (or the
    active per-host override config.<host>.toml) under the [<os>] table.

Everything except the actual network download is pure stdlib and unit-tested
offline (tests/test_provision_fetch.py). See
docs/model_provisioner_design_20260607_2158.md (section 5/6, phase P3).
"""
from __future__ import annotations

import shutil
import struct
from pathlib import Path

OPEN_LICENSES = {"apache-2.0", "mit", "bsd-3-clause", "bsd-2-clause"}

# ggml type sizes in BYTES PER ELEMENT (block byte size / block element count).
# These are the real ggml block layouts, NOT tuning constants -- used to size the
# KV cache for a given --cache-type-k/-v. Unknown types fall back to f16 (2.0), the
# safe over-estimate (bigger per-token cost -> smaller ctx -> we never over-allocate).
_GGML_BYTES_PER_ELEM = {
    "f32": 4.0, "f16": 2.0, "bf16": 2.0,
    "q8_0": 34.0 / 32.0, "q8_1": 36.0 / 32.0,
    "q5_0": 22.0 / 32.0, "q5_1": 24.0 / 32.0,
    "q4_0": 18.0 / 32.0, "q4_1": 20.0 / 32.0,
    "iq4_nl": 18.0 / 32.0,
}


def kv_dtype_bytes(name):
    """Bytes/element for a llama.cpp --cache-type-{k,v} value; f16 if unknown."""
    return _GGML_BYTES_PER_ELEM.get((name or "").strip().lower(), 2.0)


# --- minimal GGUF metadata reader (stdlib; header only) ---------------------
_GGUF_MAGIC = b"GGUF"
# GGUF metadata value-type enum -> (struct format, byte width) for scalars.
_GGUF_SCALAR = {
    0: ("B", 1), 1: ("b", 1), 2: ("H", 2), 3: ("h", 2),
    4: ("I", 4), 5: ("i", 4), 6: ("f", 4), 7: ("?", 1),
    10: ("Q", 8), 11: ("q", 8), 12: ("d", 8),
}
_GGUF_STRING = 8
_GGUF_ARRAY = 9


def _gguf_scalar(f, fmt, width):
    data = f.read(width)
    if len(data) != width:
        raise ValueError("truncated GGUF header")
    return struct.unpack("<" + fmt, data)[0]


def _gguf_string(f):
    n = _gguf_scalar(f, "Q", 8)
    s = f.read(n)
    if len(s) != n:
        raise ValueError("truncated GGUF string")
    return s.decode("utf-8", "replace")


def _gguf_value(f, vtype):
    if vtype in _GGUF_SCALAR:
        fmt, width = _GGUF_SCALAR[vtype]
        return _gguf_scalar(f, fmt, width)
    if vtype == _GGUF_STRING:
        return _gguf_string(f)
    if vtype == _GGUF_ARRAY:
        elem_t = _gguf_scalar(f, "I", 4)
        count = _gguf_scalar(f, "Q", 8)
        return [_gguf_value(f, elem_t) for _ in range(count)]
    raise ValueError("unknown GGUF value type %r" % vtype)


def read_gguf_meta(path):
    """Parse the GGUF metadata header (stdlib, header only) and return the fields
    needed to size the KV cache: arch, n_layers, n_head, n_head_kv, n_embd, head_dim.
    Returns None if the file is not GGUF or the required fields are missing."""
    try:
        with open(path, "rb") as f:
            if f.read(4) != _GGUF_MAGIC:
                return None
            _gguf_scalar(f, "I", 4)   # version
            _gguf_scalar(f, "Q", 8)   # tensor count
            n_kv = _gguf_scalar(f, "Q", 8)
            md = {}
            for _ in range(n_kv):
                key = _gguf_string(f)
                vtype = _gguf_scalar(f, "I", 4)
                md[key] = _gguf_value(f, vtype)
    except (OSError, ValueError, struct.error):
        return None

    arch = md.get("general.architecture")
    if not arch:
        return None

    def a(suffix):
        return md.get("%s.%s" % (arch, suffix))

    n_layers = a("block_count")
    n_head = a("attention.head_count")
    n_head_kv = a("attention.head_count_kv")
    n_embd = a("embedding_length")
    if n_layers is None or n_head_kv is None:
        return None
    # head_dim: explicit attention.key_length when present, else n_embd / n_head.
    head_dim = a("attention.key_length")
    if head_dim is None and n_embd and n_head:
        head_dim = n_embd // n_head
    if not head_dim:
        return None
    return {
        "arch": arch,
        "n_layers": int(n_layers),
        "n_head": int(n_head) if n_head else None,
        "n_head_kv": int(n_head_kv),
        "n_embd": int(n_embd) if n_embd else None,
        "head_dim": int(head_dim),
    }


def kv_bytes_per_token(meta, ck="q8_0", cv="q8_0"):
    """KV-cache bytes per token of context = K + V, each layer holding
    n_head_kv * head_dim elements across n_layers. ck/cv = --cache-type-k/-v."""
    per_layer = meta["n_layers"] * meta["n_head_kv"] * meta["head_dim"]
    return per_layer * kv_dtype_bytes(ck) + per_layer * kv_dtype_bytes(cv)


def max_ctx_for_budget(free_mb, kv_per_token_bytes, min_ctx, ctx_default, step=1024):
    """Largest context that fits free_mb of KV headroom, clamped to
    [min_ctx, ctx_default] and floored to `step`. Never exceeds ctx_default (the
    model's designed max) nor drops below min_ctx (its floor)."""
    if kv_per_token_bytes <= 0:
        return int(ctx_default)
    raw = int((free_mb * 1024 * 1024) / kv_per_token_bytes)
    raw = (raw // step) * step
    return max(int(min_ctx), min(int(ctx_default), raw))


def disk_free_mb(path):
    """Free space (MiB) on the filesystem that holds path, walking up to the
    nearest existing ancestor so a not-yet-created models/ dir still measures."""
    probe = Path(path)
    while not probe.exists():
        if probe.parent == probe:
            break
        probe = probe.parent
    return shutil.disk_usage(str(probe)).free / (1024 * 1024)


def preflight_disk(dest_dir, size_mb, margin=0.20):
    """Free space must cover the download size plus a margin (default 20%)."""
    need = (size_mb or 0) * (1.0 + margin)
    free = disk_free_mb(dest_dir)
    return {
        "ok": free >= need,
        "free_mb": round(free),
        "need_mb": round(need),
        "size_mb": size_mb,
        "margin": margin,
    }


def license_gate(pick, hf_token=None):
    """The default catalog is Apache-2.0/MIT + ungated -> happy path, no token.
    A non-open (gated) license is allowed only with an explicit HF_TOKEN; never
    auto-accept on the user's behalf."""
    lic = (pick.get("license") or "").strip().lower()
    if lic in OPEN_LICENSES:
        return {"allowed": True, "gated": False, "license": lic,
                "reason": "OSI-open + ungated (%s)" % (lic or "unknown")}
    if hf_token:
        return {"allowed": True, "gated": True, "license": lic,
                "reason": "gated license accepted via HF_TOKEN"}
    return {"allowed": False, "gated": True, "license": lic,
            "reason": "gated/restrictive license '%s' needs HF_TOKEN + explicit "
                      "acceptance" % (lic or "unknown")}


def build_plan(pick, models_dir):
    """List the files to fetch (base GGUF, plus mmproj for vision models),
    marking ones already on disk, and the total bytes still to download."""
    models_dir = Path(models_dir)
    files = [{
        "repo": pick["repo"], "filename": pick["file"],
        "dest": models_dir / pick["file"], "role": "weights",
        "size_mb": pick.get("size_mb"),
    }]
    if pick.get("vision") and pick.get("mmproj"):
        files.append({
            "repo": pick["repo"], "filename": pick["mmproj"],
            "dest": models_dir / pick["mmproj"], "role": "mmproj",
            "size_mb": None,
        })
    for f in files:
        f["present"] = Path(f["dest"]).is_file()
    download_mb = sum((f["size_mb"] or 0) for f in files if not f["present"])
    return {"files": files, "download_mb": download_mb}


def _toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    return '"%s"' % v


def resolve_ctx(pick_ctx, existing_ctx=None, gguf_ctx=None):
    """Choose PERSONA_CTX. Precedence (under-setting is the safe direction):
      1. an existing host-validated PERSONA_CTX wins, but is CAPPED to the
         GGUF-derived fit when that is known (never serve a ctx that won't fit);
      2. else the GGUF-derived KV-aware fit -- the authoritative fresh-host value;
      3. else the matcher's conservative pre-download guess (pick_ctx)."""
    existing = None
    if existing_ctx is not None and str(existing_ctx).strip() != "":
        try:
            existing = int(existing_ctx)
        except (TypeError, ValueError):
            existing = None
    if existing is not None:
        return min(existing, int(gguf_ctx)) if gguf_ctx else existing
    if gguf_ctx:
        return int(gguf_ctx)
    return int(pick_ctx)


def config_kv(pick, existing_ctx=None, gguf_ctx=None):
    """The keys the pick wires into the [<os>] config table. PERSONA_CTX is resolved
    by resolve_ctx (existing host-validated value, else the GGUF-derived KV-aware fit,
    else the matcher guess). MMPROJ_PATH and VISION_ENABLED are forward-looking -- the
    mmproj is fetched regardless so vision can flip on without a re-download."""
    kv = {"PERSONA_MODEL": pick["file"],
          "PERSONA_CTX": resolve_ctx(pick["ctx"], existing_ctx, gguf_ctx)}
    if pick.get("vision") and pick.get("mmproj"):
        kv["MMPROJ_PATH"] = pick["mmproj"]
        kv["VISION_ENABLED"] = 1 if pick.get("vision_enabled") else 0
    return kv


def config_block(os_tag, kv):
    """Render the [<os>] block the wiring would write (for --dry-run display)."""
    out = ["[%s]" % os_tag]
    for k, v in kv.items():
        out.append("%s = %s" % (k, _toml_value(v)))
    return "\n".join(out) + "\n"


def target_config_path(root, host_tag, os_tag=None):
    """Write target: the committed per-host override run/config.<host>.toml when
    it exists (it is that host's source of truth), else run/config.toml."""
    root = Path(root)
    host = root / "run" / ("config.%s.toml" % host_tag)
    if host.is_file():
        return host
    return root / "run" / "config.toml"


def model_resolvable(models_dir, configured):
    """True if the stack can serve a model WITHOUT provisioning -- a configured
    PERSONA_MODEL that exists on disk, or exactly one GGUF present (the unambiguous
    fallback). Mirrors manage.resolve_model()'s usable cases (quiet; no logging) so
    cmd_up can decide whether to trigger first-run provisioning."""
    models_dir = Path(models_dir)
    if configured and (models_dir / configured).is_file():
        return True
    present = sorted(models_dir.glob("*.gguf")) if models_dir.is_dir() else []
    return len(present) == 1


def wire_config(path, os_tag, kv, dry_run=True):
    """Non-destructively set kv inside the [<os>] table of a TOML file. Existing
    keys are replaced in place (a changed PERSONA_MODEL leaves the old line as a
    '# was:' rollback breadcrumb); missing keys are appended to the section;
    a missing section is appended at EOF. Returns the new text + a change list."""
    path = Path(path)
    section = "[%s]" % os_tag
    orig = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = orig.splitlines()
    changes = []

    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == section:
            start = i
            break

    if start is None:
        block = []
        if lines and lines[-1].strip() != "":
            block.append("")
        block.append(section)
        for k, v in kv.items():
            block.append("%s = %s" % (k, _toml_value(v)))
            changes.append("added %s" % k)
        changes.append("added section %s" % section)
        new_lines = lines + block
    else:
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j][:1] == "[":
                end = j
                break
        body = lines[start + 1:end]
        remaining = dict(kv)
        new_body = []
        for ln in body:
            stripped = ln.strip()
            key = None
            if "=" in stripped and not stripped.startswith("#"):
                key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                v = remaining.pop(key)
                old_val = stripped.split("=", 1)[1].strip().strip('"')
                if key == "PERSONA_MODEL" and old_val != str(v):
                    new_body.append("# was: %s   (provision rollback)" % stripped)
                    changes.append("commented prior PERSONA_MODEL")
                new_body.append("%s = %s" % (key, _toml_value(v)))
                changes.append("set %s" % key)
            else:
                new_body.append(ln)
        tail_blanks = []
        while new_body and new_body[-1].strip() == "":
            tail_blanks.insert(0, new_body.pop())
        for k, v in remaining.items():
            new_body.append("%s = %s" % (k, _toml_value(v)))
            changes.append("added %s" % k)
        new_body.extend(tail_blanks)
        new_lines = lines[:start + 1] + new_body + lines[end:]

    new_text = "\n".join(new_lines)
    if orig.endswith("\n") or not orig:
        if not new_text.endswith("\n"):
            new_text += "\n"
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return {"path": str(path), "changes": changes, "text": new_text,
            "dry_run": dry_run}


def verify_download(path, min_mb=1):
    """hf_hub_download verifies the blob hash against HF metadata on its own; this
    is a light post-check that the file landed and is not a stub."""
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "reason": "missing after download"}
    mb = p.stat().st_size / (1024 * 1024)
    return {"ok": mb >= min_mb, "size_mb": round(mb),
            "reason": "ok" if mb >= min_mb else "suspiciously small (%d MiB)" % mb}


def download(plan, hf_token=None, dry_run=False, revision=None, log=print):
    """Fetch any not-present files in the plan via huggingface_hub (resumable).
    dry_run reports intent without touching the network."""
    results = []
    if dry_run:
        for f in plan["files"]:
            results.append({
                "filename": f["filename"], "role": f["role"],
                "status": "present" if f["present"] else "would download",
            })
        return {"ok": True, "dry_run": True, "results": results}

    try:
        from huggingface_hub import hf_hub_download
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "dry_run": False, "results": [],
                "error": "huggingface_hub not installed (%s); pip install "
                         "huggingface_hub" % e}

    ok_all = True
    for f in plan["files"]:
        if f["present"]:
            results.append({"filename": f["filename"], "role": f["role"],
                            "status": "present"})
            continue
        dest_dir = Path(f["dest"]).parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        log("downloading %s (%s) from %s" % (f["filename"], f["role"], f["repo"]))
        try:
            local = hf_hub_download(
                repo_id=f["repo"], filename=f["filename"],
                local_dir=str(dest_dir), token=hf_token, revision=revision,
            )
        except Exception as e:  # noqa: BLE001
            ok_all = False
            results.append({"filename": f["filename"], "role": f["role"],
                            "status": "error", "error": str(e)})
            continue
        v = verify_download(local, min_mb=(1 if f["role"] == "mmproj" else 50))
        ok_all = ok_all and v["ok"]
        results.append({"filename": f["filename"], "role": f["role"],
                        "status": "ok" if v["ok"] else "verify-failed",
                        "path": str(local), "verify": v})
    return {"ok": ok_all, "dry_run": False, "results": results}
