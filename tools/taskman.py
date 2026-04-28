#!/usr/bin/env python3
import argparse, json, os, re, shutil, subprocess, sys, textwrap, hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ----------------------------
# Utilities
# ----------------------------

def run_cmd(cmd: List[str], cwd: Path, timeout: int = 300) -> Dict[str, Any]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        return {
            "cmd": cmd,
            "returncode": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
        }
    except Exception as e:
        return {
            "cmd": cmd,
            "returncode": 999,
            "stdout": "",
            "stderr": f"Exception: {e}",
        }

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

# ----------------------------
# Suggestion engine (Option B)
# ----------------------------

ANCHOR_PATTERNS = [
    # common web server / routing anchors
    r"FastAPI\s*\(",
    r"APIRouter\s*\(",
    r"app\s*=\s*FastAPI\s*\(",
    r"router\s*=\s*APIRouter\s*\(",
    r"@app\.(get|post|put|delete|patch)\(",
    r"@router\.(get|post|put|delete|patch)\(",
    r"def\s+main\s*\(",
    r"if\s+__name__\s*==\s*['\"]__main__['\"]\s*:",
    # config/env anchors
    r"os\.environ",
    r"dotenv",
    r"load_dotenv",
    r"argparse",
    # registry / wiring patterns
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
                hits.append({
                    "line": i,
                    "pattern": pat,
                    "snippet": line.strip()[:200],
                })
                if len(hits) >= max_hits:
                    return hits
    return hits

def suggest_for_steps(repo: Path, steps: List[str]) -> Dict[str, Any]:
    """
    Heuristics:
    - If a step mentions a file path, scan it for anchors.
    - If a step says "wire into X" or "add route" and we can guess a file, scan common server files.
    """
    suggestions: Dict[str, Any] = {"anchors": {}, "missing_steps": []}

    mentioned_paths: List[Path] = []
    # crude path detector: contains "/" and ends with typical extensions
    for s in steps:
        for m in re.findall(r"([A-Za-z0-9_\-./]+?\.(py|sh|js|ts|json|yaml|yml))", s):
            rel = m[0]
            p = (repo / rel).resolve()
            if is_under_repo(repo, p) and p.exists():
                mentioned_paths.append(p)

    # Add common "wiring" candidates if steps hint at server wiring
    wiring_keywords = ("wire", "route", "endpoint", "api", "server", "fastapi", "router", "mount", "include_router")
    if any(any(k in s.lower() for k in wiring_keywords) for s in steps):
        for candidate in [
            repo / "services/api/server.py",
            repo / "app/server.py",
            repo / "server.py",
            repo / "main.py",
        ]:
            if candidate.exists():
                mentioned_paths.append(candidate.resolve())

    # de-dupe
    uniq: List[Path] = []
    seen = set()
    for p in mentioned_paths:
        if str(p) not in seen:
            seen.add(str(p))
            uniq.append(p)

    for p in uniq:
        rel = str(p.relative_to(repo))
        suggestions["anchors"][rel] = find_anchors_in_file(p)

    # Missing-steps suggestions (lightweight, non-invasive)
    for s in steps:
        sl = s.lower()
        if "create file" in sl and "chmod" not in sl and (".sh" in sl):
            suggestions["missing_steps"].append("Consider adding: chmod +x <script> (if not already handled).")
        if ("add" in sl or "wire" in sl) and ("test" not in " ".join(steps).lower()):
            # only suggest once
            pass

    if not any("test" in st.lower() or "smoke" in st.lower() for st in steps):
        suggestions["missing_steps"].append("Consider adding a smoke test step (even a simple curl/script) to validate changes quickly.")

    return suggestions

# ----------------------------
# Patch apply (unified diff)
# ----------------------------

def apply_unified_diff(repo: Path, diff_text: str) -> Tuple[bool, str]:
    """
    Uses system `git apply` if available and repo is a git repo; falls back to `patch`.
    Safer than trying to parse diffs ourselves.
    """
    # Prefer git apply for reliability
    git_dir = repo / ".git"
    if have_cmd("git") and git_dir.exists():
        # --whitespace=nowarn to reduce false negatives
        p = run_cmd(["git", "apply", "--whitespace=nowarn", "-"], cwd=repo, timeout=60)
        # but we need to feed stdin; so run directly with subprocess for stdin
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

# ----------------------------
# Job execution
# ----------------------------

@dataclass
class Edit:
    path: str
    action: str  # "write" or "patch"
    content: str

def load_job(path: Path) -> Dict[str, Any]:
    data = json.loads(read_text(path))
    if not isinstance(data, dict):
        raise SystemExit("Job file must be a JSON object.")
    return data

def collect_context(repo: Path, extra_rg: Optional[List[str]] = None) -> Dict[str, Any]:
    ctx: Dict[str, Any] = {"repo": str(repo)}
    if have_cmd("git") and (repo / ".git").exists():
        ctx["git_status"] = run_cmd(["git", "status", "--porcelain"], cwd=repo, timeout=60)
        ctx["git_diff"] = run_cmd(["git", "diff"], cwd=repo, timeout=60)
    else:
        ctx["git_status"] = {"returncode": 999, "stdout": "", "stderr": "Not a git repo or git not installed."}
        ctx["git_diff"] = {"returncode": 999, "stdout": "", "stderr": "Not a git repo or git not installed."}

    # lightweight tree
    if have_cmd("tree"):
        ctx["tree"] = run_cmd(["tree", "-L", "3", "-a"], cwd=repo, timeout=60)
    else:
        # fallback: ls -R is too big; do a small directory listing
        ctx["tree"] = run_cmd(["bash", "-lc", "ls -la && echo '---' && find . -maxdepth 3 -type d -print"], cwd=repo, timeout=60)

    # optional rg
    if extra_rg and have_cmd("rg"):
        ctx["rg"] = []
        for q in extra_rg[:10]:
            ctx["rg"].append(run_cmd(["rg", "-n", q], cwd=repo, timeout=60))
    return ctx

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

def parse_edits(job: Dict[str, Any]) -> List[Edit]:
    edits = []
    for e in job.get("edits", []) or []:
        if not isinstance(e, dict):
            continue
        path = e.get("path")
        action = e.get("action")
        content = e.get("content", "")
        if not path or action not in ("write", "patch"):
            continue
        edits.append(Edit(path=path, action=action, content=content))
    return edits

def run_job(repo: Path, job: Dict[str, Any], assume_yes: bool = False) -> Dict[str, Any]:
    task_id = job.get("task_id") or "unknown"
    steps = job.get("steps") or []
    cmds = job.get("commands") or []
    extra_rg = job.get("rg_queries") or []

    result: Dict[str, Any] = {
        "task_id": task_id,
        "status": "running",
        "repo_root": str(repo),
        "suggestions": {},
        "pre_context": {},
        "edits": [],
        "commands_run": [],
        "post_context": {},
        "notes": "",
        "errors": [],
    }

    # Pre context + suggestions
    result["pre_context"] = collect_context(repo, extra_rg=extra_rg)
    if isinstance(steps, list) and steps:
        result["suggestions"] = suggest_for_steps(repo, [str(s) for s in steps])

    edits = parse_edits(job)
    applied_files: List[str] = []

    # Apply edits with per-file confirmation
    for ed in edits:
        if ed.action == "write":
            preview = preview_write(repo, ed.path, ed.content)
            if not preview.get("ok"):
                result["errors"].append(preview.get("error", "preview failed"))
                continue

            if not assume_yes:
                msg = f"\nApply WRITE to {ed.path}? (exists={preview['exists']}, old_bytes={preview['old_bytes']} -> new_bytes={preview['new_bytes']})"
                if not prompt_yes_no(msg, default_no=True):
                    result["edits"].append({"path": ed.path, "action": "write", "applied": False, "reason": "user_skipped", "preview": preview})
                    continue

            ok, info = do_write(repo, ed.path, ed.content)
            result["edits"].append({"path": ed.path, "action": "write", "applied": ok, "info": info, "preview": preview})
            if ok:
                applied_files.append(ed.path)

        elif ed.action == "patch":
            if not assume_yes:
                msg = f"\nApply PATCH (unified diff) to repo? (task {task_id})"
                if not prompt_yes_no(msg, default_no=True):
                    result["edits"].append({"path": "(patch)", "action": "patch", "applied": False, "reason": "user_skipped"})
                    continue
            ok, out = apply_unified_diff(repo, ed.content)
            result["edits"].append({"path": "(patch)", "action": "patch", "applied": ok, "output": out[:8000]})
            if not ok:
                result["errors"].append("patch failed")
            else:
                applied_files.append("(patch-applied)")

    # Run commands
    for c in cmds:
        if isinstance(c, str):
            # shell mode
            r = run_cmd(["bash", "-lc", c], cwd=repo, timeout=int(job.get("command_timeout_sec", 300)))
            result["commands_run"].append(r)
        elif isinstance(c, list) and c:
            r = run_cmd([str(x) for x in c], cwd=repo, timeout=int(job.get("command_timeout_sec", 300)))
            result["commands_run"].append(r)

    # Post context
    result["post_context"] = collect_context(repo, extra_rg=extra_rg)

    # Determine status
    failed_cmds = [x for x in result["commands_run"] if x.get("returncode", 0) != 0]
    if result["errors"] or failed_cmds:
        result["status"] = "needs_attention"
    else:
        result["status"] = "done"

    # Helpful summary note
    changed_files = []
    if have_cmd("git") and (repo / ".git").exists():
        st = result["post_context"]["git_status"]["stdout"]
        for line in st.splitlines():
            # " M path" or "?? path"
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                changed_files.append(parts[1])
    result["changed_files_guess"] = sorted(set(changed_files))

    return result

# ----------------------------
# CLI
# ----------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Local Task Manager Agent (Option B): scans repo, suggests anchors, applies edits w/ per-file confirmation."
    )
    ap.add_argument("job", help="Path to job JSON file.")
    ap.add_argument("--repo", default=".", help="Repo root (default: current directory).")
    ap.add_argument("--yes", action="store_true", help="Assume yes for all edit prompts (DANGEROUS).")
    ap.add_argument("--out", default="", help="Write result JSON to this file (also prints to stdout).")
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
