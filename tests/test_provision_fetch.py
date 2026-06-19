#!/usr/bin/env python3
"""Offline tests for the provisioner P3 module (scripts/provision_fetch.py).

Covers disk preflight, license gate, plan building, config-block render, the
non-destructive TOML wiring, per-host target selection, and the dry-run/verify
helpers. Pure stdlib (no tomllib, no network) so it runs anywhere 3.8+.

    python tests/test_provision_fetch.py
Exit 0 = all pass, 1 = a failure.
"""
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))

import provision_fetch as pf  # noqa: E402

checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


VISION_PICK = {
    "model_id": "qwen3.6-35b-a3b", "repo": "unsloth/Qwen3.6-35B-A3B-GGUF",
    "file": "Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf", "size_mb": 26000,
    "mmproj": "mmproj-Qwen3.6-35B-A3B-F16.gguf", "vision": True,
    "vision_enabled": True, "ctx": 16384, "license": "apache-2.0",
}
TEXT_PICK = {
    "model_id": "qwen3-4b", "repo": "Qwen/Qwen3-4B-GGUF",
    "file": "Qwen3-4B-Q4_K_M.gguf", "size_mb": 2500, "mmproj": None,
    "vision": False, "vision_enabled": False, "ctx": 8192, "license": "apache-2.0",
}
GATED_PICK = dict(TEXT_PICK, license="gemma", model_id="gemma-x")


def test_preflight():
    orig = pf.disk_free_mb
    pf.disk_free_mb = lambda p: 40000.0
    try:
        r = pf.preflight_disk("/whatever", 26000)
        check("preflight ok when free >= size*1.2", r["ok"] and r["need_mb"] == 31200)
        pf.disk_free_mb = lambda p: 30000.0
        r2 = pf.preflight_disk("/whatever", 26000)
        check("preflight fails when free < size+20%", not r2["ok"])
    finally:
        pf.disk_free_mb = orig


def test_license():
    a = pf.license_gate(VISION_PICK)
    check("apache allowed ungated", a["allowed"] and not a["gated"])
    g = pf.license_gate(GATED_PICK)
    check("gated denied without token", (not g["allowed"]) and g["gated"])
    gt = pf.license_gate(GATED_PICK, hf_token="hf_xxx")
    check("gated allowed with token", gt["allowed"] and gt["gated"])


def test_plan():
    with tempfile.TemporaryDirectory() as d:
        models = Path(d) / "models"
        models.mkdir()
        p = pf.build_plan(VISION_PICK, models)
        roles = [f["role"] for f in p["files"]]
        check("vision plan has weights + mmproj", roles == ["weights", "mmproj"])
        check("plan download_mb counts unpresent weights", p["download_mb"] == 26000)
        (models / VISION_PICK["file"]).write_text("x")
        p2 = pf.build_plan(VISION_PICK, models)
        check("present weights skipped in download_mb", p2["download_mb"] == 0
              and p2["files"][0]["present"])
        pt = pf.build_plan(TEXT_PICK, models)
        check("text plan has no mmproj", [f["role"] for f in pt["files"]] == ["weights"])


def test_kv_block():
    kv = pf.config_kv(VISION_PICK)
    check("vision kv has model/ctx/mmproj/vision", set(kv) ==
          {"PERSONA_MODEL", "PERSONA_CTX", "MMPROJ_PATH", "VISION_ENABLED"})
    check("vision_enabled int 1", kv["VISION_ENABLED"] == 1)
    kt = pf.config_kv(TEXT_PICK)
    check("text kv is model/ctx only", set(kt) == {"PERSONA_MODEL", "PERSONA_CTX"})
    blk = pf.config_block("linux", kv)
    check("block has header + quoted model + bare ctx",
          blk.startswith("[linux]") and '"Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf"' in blk
          and "PERSONA_CTX = 16384" in blk)


SAMPLE = """[base]
HOST = "127.0.0.1"

[linux]
PERSONA_MODEL = "OLD-MODEL.gguf"
PERSONA_CTX = 32768
GPU_LAYERS_PERSONA = 999

[runtime]
RAG_ENABLED = 1
"""


def test_wire_replace_and_comment():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "config.toml"
        f.write_text(SAMPLE)
        kv = pf.config_kv(VISION_PICK)
        pf.wire_config(f, "linux", kv, dry_run=False)
        t = f.read_text()
        check("old PERSONA_MODEL commented as breadcrumb",
              "# was: PERSONA_MODEL = \"OLD-MODEL.gguf\"" in t)
        check("new PERSONA_MODEL set",
              'PERSONA_MODEL = "Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf"' in t)
        check("PERSONA_CTX updated in place", "PERSONA_CTX = 16384" in t
              and "PERSONA_CTX = 32768" not in t)
        check("MMPROJ_PATH appended to section", "MMPROJ_PATH =" in t)
        check("untouched key GPU_LAYERS_PERSONA preserved",
              "GPU_LAYERS_PERSONA = 999" in t)
        check("other sections preserved (base/runtime)",
              "[base]" in t and "[runtime]" in t and "RAG_ENABLED = 1" in t)
        pf.wire_config(f, "linux", kv, dry_run=False)
        t2 = f.read_text()
        check("rerun is idempotent (one breadcrumb, value unchanged)",
              t2.count("# was: PERSONA_MODEL") == 1
              and t2.count('PERSONA_MODEL = "Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf"') == 1)


def test_wire_missing_section():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "config.toml"
        f.write_text("[base]\nHOST = \"127.0.0.1\"\n")
        pf.wire_config(f, "windows", pf.config_kv(TEXT_PICK), dry_run=False)
        t = f.read_text()
        check("missing [windows] section appended", "[windows]" in t)
        check("appended section carries the model", "Qwen3-4B-Q4_K_M.gguf" in t)
        check("base section intact", t.startswith("[base]"))


def test_wire_dry_run():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "config.toml"
        f.write_text(SAMPLE)
        r = pf.wire_config(f, "linux", pf.config_kv(VISION_PICK), dry_run=True)
        check("dry_run leaves file unchanged", f.read_text() == SAMPLE)
        check("dry_run still returns the new text", "16384" in r["text"])


def test_target_path():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "run").mkdir()
        (root / "run" / "config.toml").write_text("[base]\n")
        p = pf.target_config_path(root, "daemonic-pc")
        check("no per-host file -> config.toml", p.name == "config.toml")
        (root / "run" / "config.daemonic-pc.toml").write_text("[base]\n")
        p2 = pf.target_config_path(root, "daemonic-pc")
        check("per-host file present -> override path",
              p2.name == "config.daemonic-pc.toml")


def test_download_dry_and_verify():
    with tempfile.TemporaryDirectory() as d:
        models = Path(d) / "models"
        models.mkdir()
        plan = pf.build_plan(TEXT_PICK, models)
        r = pf.download(plan, dry_run=True)
        check("download dry_run ok + would-download",
              r["ok"] and r["results"][0]["status"] == "would download")
        big = models / "x.gguf"
        big.write_bytes(b"0" * (2 * 1024 * 1024))
        v = pf.verify_download(big, min_mb=1)
        check("verify_download ok for >=min file", v["ok"])
        v2 = pf.verify_download(big, min_mb=50)
        check("verify_download flags too-small file", not v2["ok"])


def test_resolve_ctx():
    check("resolve_ctx prefers existing config ctx", pf.resolve_ctx(8192, 16384) == 16384)
    check("resolve_ctx falls back to matcher ctx when none", pf.resolve_ctx(8192, None) == 8192)
    check("resolve_ctx ignores empty existing", pf.resolve_ctx(8192, "") == 8192)
    check("resolve_ctx coerces stringy existing", pf.resolve_ctx(8192, "16384") == 16384)
    kv = pf.config_kv(VISION_PICK, existing_ctx=16384)
    check("config_kv honors existing ctx", kv["PERSONA_CTX"] == 16384)
    kv2 = pf.config_kv(VISION_PICK)
    check("config_kv default uses pick ctx",
          kv2["PERSONA_CTX"] == 16384 and VISION_PICK["ctx"] == 16384)


def test_model_resolvable():
    with tempfile.TemporaryDirectory() as d:
        models = Path(d) / "models"
        models.mkdir()
        check("no gguf -> not resolvable", not pf.model_resolvable(models, ""))
        (models / "a.gguf").write_text("x")
        check("exactly one gguf -> resolvable (fallback)", pf.model_resolvable(models, ""))
        (models / "b.gguf").write_text("x")
        check("two gguf + no configured -> not resolvable", not pf.model_resolvable(models, ""))
        check("configured present -> resolvable", pf.model_resolvable(models, "b.gguf"))
        check("configured missing -> not resolvable", not pf.model_resolvable(models, "z.gguf"))
        check("missing dir -> not resolvable", not pf.model_resolvable(Path(d) / "nope", ""))


for fn in [test_preflight, test_license, test_plan, test_kv_block,
           test_wire_replace_and_comment, test_wire_missing_section,
           test_wire_dry_run, test_target_path, test_download_dry_and_verify,
           test_resolve_ctx, test_model_resolvable]:
    fn()

print("\n%d checks, %d failures" % (checks, len(failures)))
sys.exit(1 if failures else 0)
