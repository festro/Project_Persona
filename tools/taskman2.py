#!/usr/bin/env python3
import argparse, json, os, re, shutil, subprocess, hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

def run_cmd(cmd: List[str], cwd: Path, timeout: int = 300) -> Dict[str, Any]:
    try:
        p = subprocess.run(
            cmd, cwd=str(cwd),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=timeout
        )
        return {"cmd": cmd, "returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    except Exception as e:
        return {"cmd": cmd, "returncode": 999, "stdout": "", "stderr": f"Exception: {e}"}

def have_cmd(name: str) -> bool:
    return shutil.which(name) is not None

def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)

def normalize_repo_root(repo: str) -> Path:
    p = Path(os.path.expanduser(repo)).resolve()
    if not p.exists():
        raise SystemExit(f"Repo root does not exist: {p}")
    return p

def is_under_repo(repo: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(repo.resolve())
        return True
    except Exception:
        return False

def prompt_yes_no(msg: str, default_no: bool = True) -> bool:
    suffix = " [y/N]: " if default_no else " [Y/n]: "
    ans = input(msg + suffix).strip().lower()
    if ans == "":
        return not default_no
    return ans in ("y", "yes")

ANCHOR_PATTERNS = [
    r"FastAPI\s*\(",
    r"APIRouter\s*\(",
    r"app\s*=\s*FastAPI\s*\(",
    r"router\s*=\s*APIRouter\s*\(",
    r"@app\.(get|post|put|delete|patch)\(",
    r"@router\.(get|post|put|delete|patch)\(",
    r"include_router\s*\(",
    r"add_api_route\s*\(",
]

def find_anchors_in_file(path: Path, max_hits: int = 12) -> List[Dict[str, Any]]:
    try:
        lines = read_text(path).splitlines()
    except Exception:
        return []
    hits: List[Dict[str, Any]] = []
    for i, line in enumerate(lines, start=1):
        for pat in ANCHOR_PATTERNS:
            if re.search(pat, line):
                hits.append({"line": i, "pattern": pat, "snippet": line.strip()[:200]})
                if len(hits) >= max_hits:
                    return hits
    return hits

def suggest_for_steps(repo: Path, steps: List[str]) -> Dict[str, Any]:
    suggestions: Dict[str, Any] = {"anchors": {}, "missing_steps": []}
    mentioned_paths: List[Path] = []

    for s in steps:
        for m in re.findall(r"([A-Za-z0-9_\-./]+?\.(py|sh|js|ts|json|yaml|yml))", s):
            rel = m[0]
            p = (repo / rel).resolve()
            if is_under_repo(repo, p) and p.exists():
                mentioned_paths.append(p)

    wiring_keywords = ("wire", "route", "endpoint", "api", "server", "fastapi", "router", "mount", "include_router")
    if any(any(k in s.lower() for k in wiring_keywords) for s in steps):
        for candidate in [repo / "services/api/server.py", repo / "app/server.py", repo / "server.py", repo / "main.py"]:
            if candidate.exists():
                mentioned_paths.append(candidate.resolve())

    uniq, seen = [], set()
    for p in mentioned_paths:
        sp = str(p)
        if sp not in seen:
            seen.add(sp)
            uniq.append(p)

    for p in uniq:
        rel = str(p.relative_to(repo))
        suggestions["anchors"][rel] = find_anchors_in_file(p)

    if not any("test" in st.lower() or "smoke" in st.lower() for st in steps):
        suggestions["missing_steps"].append("Consider adding a smoke test step (curl/script) to validate changes quickly.")

    return suggestions

def apply_unified_diff(repo: Path, diff_text: str) -> Tuple[bool, str]:
    if diff_text.lstrip().startswith("*** Begin Patch"):
        return False, 'Unsupported patch format ("*** Begin Patch"). Use a real unified diff (git diff style).'
    if have_cmd("git") and (repo / ".git").exists():
        try:
            sp = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", "-"],
                cwd=str(repo),
                input=diff_text,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
            ok = (sp.returncode == 0)
            return ok, (sp.stderr or sp.stdout)
        except Exception as e:
            return False, f"Exception running git apply: {e}"
    if have_cmd("patch"):
        try:
            sp = subprocess.run(
                ["patch", "-p1", "--forward", "--batch"],
                cwd=str(repo),
                input=diff_text,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
            ok = (sp.returncode == 0)
            out = (sp.stdout or "") + (("\n" + sp.stderr) if sp.stderr else "")
            return ok, out.strip()
        except Exception as e:
            return False, f"Exception running patch: {e}"
    return False, "No patch tool available (need git or patch)."

@dataclass
class Edit:
    action: str  # write | patch | insert_after | replace_regex
    path: str = ""
    content: str = ""
    pattern: str = ""
    text: str = ""
    repl: str = ""
    flags: str = ""  # e.g. "MULTILINE,DOTALL"

def load_job(path: Path) -> Dict[str, Any]:
    data = json.loads(read_text(path))
    if not isinstance(data, dict):
        raise SystemExit("Job file must be a JSON object.")
    return data

def parse_edits(job: Dict[str, Any]) -> List[Edit]:
    edits: List[Edit] = []
    for e in job.get("edits", []) or []:
        if not isinstance(e, dict):
            continue
        action = e.get("action")
        if action == "patch":
            edits.append(Edit(action="patch", content=e.get("content", "")))
        elif action == "write":
            p = e.get("path")
            if p:
                edits.append(Edit(action="write", path=p, content=e.get("content", "")))
        elif action == "insert_after":
            p, pat = e.get("path"), e.get("pattern")
            if p and pat:
                edits.append(Edit(action="insert_after", path=p, pattern=pat, text=e.get("text", "")))
        elif action == "replace_regex":
            p, pat = e.get("path"), e.get("pattern")
            repl = e.get("repl")
            if p and pat is not None and repl is not None:
                edits.append(Edit(action="replace_regex", path=p, pattern=pat, repl=repl, flags=e.get("flags", "")))
    return edits

def preview_write(repo: Path, rel_path: str, new_content: str) -> Dict[str, Any]:
    p = (repo / rel_path).resolve()
    if not is_under_repo(repo, p):
        return {"ok": False, "error": f"Refusing to write outside repo: {rel_path}"}
    old = read_text(p) if p.exists() else ""
    return {
        "ok": True,
        "path": rel_path,
        "exists": p.exists(),
        "old_sha256": sha256_text(old),
        "new_sha256": sha256_text(new_content),
        "old_bytes": len(old.encode("utf-8", errors="ignore")),
        "new_bytes": len(new_content.encode("utf-8", errors="ignore")),
    }

def do_write(repo: Path, rel_path: str, new_content: str) -> Tuple[bool, str]:
    p = (repo / rel_path).resolve()
    if not is_under_repo(repo, p):
        return False, f"Refusing to write outside repo: {rel_path}"
    try:
        write_text_atomic(p, new_content)
        return True, "wrote file"
    except Exception as e:
        return False, f"write failed: {e}"

def _rx_flags(flags: str) -> int:
    f = 0
    if not flags:
        return f
    parts = [x.strip().upper() for x in flags.split(",") if x.strip()]
    if "MULTILINE" in parts:
        f |= re.MULTILINE
    if "DOTALL" in parts:
        f |= re.DOTALL
    return f

def preview_insert_after(repo: Path, rel_path: str, pattern: str, text: str) -> Dict[str, Any]:
    p = (repo / rel_path).resolve()
    if not is_under_repo(repo, p):
        return {"ok": False, "error": f"Refusing to edit outside repo: {rel_path}"}
    if not p.exists():
        return {"ok": False, "error": f"Target file does not exist: {rel_path}"}
    src = read_text(p)
    lines = src.splitlines()
    rx = re.compile(pattern)
    for idx, line in enumerate(lines):
        if rx.search(line):
            ctx = lines[max(0, idx-2):idx+3]
            return {"ok": True, "path": rel_path, "match_line": idx+1, "match_snippet": line.strip()[:200], "context": ctx}
    return {"ok": False, "error": f"Pattern not found in {rel_path}: {pattern}"}

def do_insert_after(repo: Path, rel_path: str, pattern: str, text: str) -> Tuple[bool, str]:
    p = (repo / rel_path).resolve()
    if not is_under_repo(repo, p):
        return False, f"Refusing to edit outside repo: {rel_path}"
    if not p.exists():
        return False, f"Target file does not exist: {rel_path}"
    lines = read_text(p).splitlines(keepends=True)
    rx = re.compile(pattern)
    for idx, line in enumerate(lines):
        if rx.search(line):
            ins = text
            if ins and not ins.endswith("\n"):
                ins += "\n"
            lines.insert(idx + 1, ins)
            write_text_atomic(p, "".join(lines))
            return True, f"inserted after line {idx+1}"
    return False, f"Pattern not found: {pattern}"

def preview_replace_regex(repo: Path, rel_path: str, pattern: str, repl: str, flags: str) -> Dict[str, Any]:
    p = (repo / rel_path).resolve()
    if not is_under_repo(repo, p):
        return {"ok": False, "error": f"Refusing to edit outside repo: {rel_path}"}
    if not p.exists():
        return {"ok": False, "error": f"Target file does not exist: {rel_path}"}
    src = read_text(p)
    rx = re.compile(pattern, _rx_flags(flags))
    m = rx.search(src)
    if not m:
        return {"ok": False, "error": f"No match for replace_regex in {rel_path}: {pattern}"}
    before = src[m.start():m.end()]
    after = rx.sub(repl, before, count=1)
    return {
        "ok": True,
        "path": rel_path,
        "match_span": [m.start(), m.end()],
        "before_preview": before[:600],
        "after_preview": after[:600],
    }

def do_replace_regex(repo: Path, rel_path: str, pattern: str, repl: str, flags: str) -> Tuple[bool, str]:
    p = (repo / rel_path).resolve()
    if not is_under_repo(repo, p):
        return False, f"Refusing to edit outside repo: {rel_path}"
    if not p.exists():
        return False, f"Target file does not exist: {rel_path}"
    src = read_text(p)
    rx = re.compile(pattern, _rx_flags(flags))
    if not rx.search(src):
        return False, "pattern not found"
    out = rx.sub(repl, src, count=1)
    write_text_atomic(p, out)
    return True, "replaced first match"

def collect_context(repo: Path, extra_rg: Optional[List[str]] = None) -> Dict[str, Any]:
    ctx: Dict[str, Any] = {"repo": str(repo)}
    if have_cmd("git") and (repo / ".git").exists():
        ctx["git_status"] = run_cmd(["git", "status", "--porcelain"], cwd=repo, timeout=60)
        ctx["git_diff"] = run_cmd(["git", "diff"], cwd=repo, timeout=60)
    else:
        ctx["git_status"] = {"returncode": 999, "stdout": "", "stderr": "Not a git repo or git not installed."}
        ctx["git_diff"] = {"returncode": 999, "stdout": "", "stderr": "Not a git repo or git not installed."}
    if extra_rg and have_cmd("rg"):
        ctx["rg"] = [run_cmd(["rg", "-n", q], cwd=repo, timeout=60) for q in extra_rg[:10]]
    return ctx

def run_job(repo: Path, job: Dict[str, Any], assume_yes: bool = False) -> Dict[str, Any]:
    task_id = job.get("task_id") or "unknown"
    steps = job.get("steps") or []
    cmds = job.get("commands") or []
    extra_rg = job.get("rg_queries") or []

    res: Dict[str, Any] = {
        "task_id": task_id,
        "status": "running",
        "repo_root": str(repo),
        "suggestions": {},
        "pre_context": {},
        "edits": [],
        "commands_run": [],
        "post_context": {},
        "errors": [],
    }

    res["pre_context"] = collect_context(repo, extra_rg=extra_rg)
    if isinstance(steps, list) and steps:
        res["suggestions"] = suggest_for_steps(repo, [str(s) for s in steps])

    edits = parse_edits(job)

    for ed in edits:
        if ed.action == "write":
            preview = preview_write(repo, ed.path, ed.content)
            if not preview.get("ok"):
                res["errors"].append(preview.get("error", "preview failed"))
                res["edits"].append({"path": ed.path, "action": "write", "applied": False, "error": preview.get("error")})
                continue
            if not assume_yes and not prompt_yes_no(f"\nApply WRITE to {ed.path}?", default_no=True):
                res["edits"].append({"path": ed.path, "action": "write", "applied": False, "reason": "user_skipped", "preview": preview})
                continue
            ok, info = do_write(repo, ed.path, ed.content)
            res["edits"].append({"path": ed.path, "action": "write", "applied": ok, "info": info, "preview": preview})
            if not ok:
                res["errors"].append(info)

        elif ed.action == "patch":
            if not assume_yes and not prompt_yes_no(f"\nApply PATCH (unified diff) to repo? (task {task_id})", default_no=True):
                res["edits"].append({"path": "(patch)", "action": "patch", "applied": False, "reason": "user_skipped"})
                continue
            ok, out = apply_unified_diff(repo, ed.content)
            res["edits"].append({"path": "(patch)", "action": "patch", "applied": ok, "output": (out or "")[:8000]})
            if not ok:
                res["errors"].append("patch failed")

        elif ed.action == "insert_after":
            preview = preview_insert_after(repo, ed.path, ed.pattern, ed.text)
            if not preview.get("ok"):
                res["errors"].append(preview.get("error", "insert preview failed"))
                res["edits"].append({"path": ed.path, "action": "insert_after", "applied": False, "error": preview.get("error")})
                continue
            if not assume_yes and not prompt_yes_no(f"\nApply INSERT_AFTER to {ed.path}? (line {preview.get('match_line')})", default_no=True):
                res["edits"].append({"path": ed.path, "action": "insert_after", "applied": False, "reason": "user_skipped", "preview": preview})
                continue
            ok, info = do_insert_after(repo, ed.path, ed.pattern, ed.text)
            res["edits"].append({"path": ed.path, "action": "insert_after", "applied": ok, "info": info, "preview": preview})
            if not ok:
                res["errors"].append(info)

        elif ed.action == "replace_regex":
            preview = preview_replace_regex(repo, ed.path, ed.pattern, ed.repl, ed.flags)
            if not preview.get("ok"):
                res["errors"].append(preview.get("error", "replace preview failed"))
                res["edits"].append({"path": ed.path, "action": "replace_regex", "applied": False, "error": preview.get("error")})
                continue
            if not assume_yes and not prompt_yes_no(f"\nApply REPLACE_REGEX to {ed.path}? (span {preview.get('match_span')})", default_no=True):
                res["edits"].append({"path": ed.path, "action": "replace_regex", "applied": False, "reason": "user_skipped", "preview": preview})
                continue
            ok, info = do_replace_regex(repo, ed.path, ed.pattern, ed.repl, ed.flags)
            res["edits"].append({"path": ed.path, "action": "replace_regex", "applied": ok, "info": info, "preview": preview})
            if not ok:
                res["errors"].append(info)

    for c in cmds:
        if isinstance(c, str):
            res["commands_run"].append(run_cmd(["bash", "-lc", c], cwd=repo, timeout=int(job.get("command_timeout_sec", 300))))
        elif isinstance(c, list) and c:
            res["commands_run"].append(run_cmd([str(x) for x in c], cwd=repo, timeout=int(job.get("command_timeout_sec", 300))))

    res["post_context"] = collect_context(repo, extra_rg=extra_rg)

    failed_cmds = [x for x in res["commands_run"] if x.get("returncode", 0) != 0]
    res["status"] = "needs_attention" if (res["errors"] or failed_cmds) else "done"

    return res

def main():
    ap = argparse.ArgumentParser(description="Taskman2 v3: Option B repo helper with insert_after and replace_regex.")
    ap.add_argument("job", help="Path to job JSON file.")
    ap.add_argument("--repo", default=".", help="Repo root (default: current directory).")
    ap.add_argument("--yes", action="store_true", help="Assume yes for all prompts (DANGEROUS).")
    ap.add_argument("--out", default="", help="Write result JSON to this file (also prints).")
    args = ap.parse_args()

    repo = normalize_repo_root(args.repo)
    job_path = Path(os.path.expanduser(args.job)).resolve()
    job = load_job(job_path)

    res = run_job(repo, job, assume_yes=args.yes)
    out_json = json.dumps(res, indent=2, ensure_ascii=False)
    print(out_json)
    if args.out:
        outp = Path(os.path.expanduser(args.out)).resolve()
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(out_json, encoding="utf-8")

if __name__ == "__main__":
    main()
