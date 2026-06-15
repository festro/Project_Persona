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
from pathlib import Path

OPEN_LICENSES = {"apache-2.0", "mit", "bsd-3-clause", "bsd-2-clause"}


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


def resolve_ctx(pick_ctx, existing_ctx=None):
    """Prefer a context the host already validated (an existing effective config
    PERSONA_CTX) over the matcher's conservative tight-budget guess; fall back to
    the matcher value on a fresh host (under-setting is the safe direction)."""
    if existing_ctx is not None and str(existing_ctx).strip() != "":
        try:
            return int(existing_ctx)
        except (TypeError, ValueError):
            pass
    return int(pick_ctx)


def config_kv(pick, existing_ctx=None):
    """The keys the pick wires into the [<os>] config table. PERSONA_CTX prefers an
    existing host-validated value (see resolve_ctx). MMPROJ_PATH and VISION_ENABLED
    are forward-looking (serving-side vision wiring still owed) -- the mmproj is
    fetched regardless so vision can flip on without a re-download."""
    kv = {"PERSONA_MODEL": pick["file"],
          "PERSONA_CTX": resolve_ctx(pick["ctx"], existing_ctx)}
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
