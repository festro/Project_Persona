#!/usr/bin/env python3
"""Drive OpenWebUI's chat API from the command line -- end-to-end smoke testing over SSH.

The persona API (:8000) can be probed directly, but that BYPASSES OpenWebUI, so it can't
exercise web search (which lives in OpenWebUI's chat middleware). This drives OpenWebUI's
`/api/chat/completions` (:3000) instead, so the WHOLE pipeline runs: web-search necessity
check -> search -> scrape -> embed -> retrieve -> inject -> persona API -> reply. That lets the
stack be validated headless, without the browser.

Auth: mints the same HS256 JWT OpenWebUI issues, signed with `.webui_secret_key` (read at
runtime, never printed or committed; the file is gitignored). User id is auto-detected from
openwebui/webui.db unless given.

Examples (run with the webui venv, which has PyJWT):
  env_webui/bin/python tools/webui_probe.py --web --expect-sources "what did Anthropic announce recently?"
  env_webui/bin/python tools/webui_probe.py --no-web --expect-absent "Next actions" \
      "Give me 6 focus tips as a numbered list. No intro, no Next actions section."
  env_webui/bin/python tools/webui_probe.py --json "explain async/await in two sentences"

Exit code: 0 = all assertions passed (or none given), 1 = an assertion failed, 2 = setup error.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent  # repo root (tools/ is under it)


def mint_token(secret_file: Path, user_id: str) -> str:
    import jwt  # PyJWT, shipped with OpenWebUI's venv

    secret = Path(secret_file).read_text(encoding="utf-8").strip()
    tok = jwt.encode({"id": user_id}, secret, algorithm="HS256")
    return tok.decode() if isinstance(tok, (bytes, bytearray)) else tok


def detect_user_id(db_path: Path) -> str | None:
    try:
        cur = sqlite3.connect(str(db_path)).cursor()
        cur.execute("SELECT id FROM user ORDER BY created_at LIMIT 1")
        row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Drive OpenWebUI's chat API for headless smoke tests.")
    ap.add_argument("prompt", help="the user message to send")
    ap.add_argument("--base-url", default="http://127.0.0.1:3000")
    ap.add_argument("--secret-file", default=str(DEFAULT_ROOT / ".webui_secret_key"))
    ap.add_argument("--db", default=str(DEFAULT_ROOT / "openwebui" / "webui.db"))
    ap.add_argument("--user-id", default=None, help="OpenWebUI user id (auto-detected from the DB if omitted)")
    ap.add_argument("--model", default=None, help="model id (auto-detected, first non-arena, if omitted)")
    web = ap.add_mutually_exclusive_group()
    web.add_argument("--web", dest="web", action="store_true", help="force web_search ON")
    web.add_argument("--no-web", dest="web", action="store_false", help="force web_search OFF")
    ap.set_defaults(web=None)  # None -> omit the feature, let the server default decide
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--json", action="store_true", help="emit one JSON result line instead of text")
    ap.add_argument("--expect-contains", action="append", default=[], metavar="TEXT",
                    help="assert the answer contains TEXT (case-insensitive; repeatable)")
    ap.add_argument("--expect-absent", action="append", default=[], metavar="TEXT",
                    help="assert the answer does NOT contain TEXT (repeatable)")
    ap.add_argument("--expect-sources", action="store_true", help="assert web sources were attached")
    args = ap.parse_args(argv)

    user_id = args.user_id or detect_user_id(Path(args.db))
    if not user_id:
        print("ERROR: could not resolve an OpenWebUI user id (set --user-id)", file=sys.stderr)
        return 2
    try:
        token = mint_token(Path(args.secret_file), user_id)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: could not mint token: {e!r}", file=sys.stderr)
        return 2

    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}

    def call(path: str, body=None):
        req = urllib.request.Request(
            args.base_url + path,
            data=(json.dumps(body).encode("utf-8") if body is not None else None),
            headers=headers,
        )
        return json.loads(urllib.request.urlopen(req, timeout=args.timeout).read())

    model = args.model
    if not model:
        try:
            ids = [m.get("id") for m in (call("/api/models").get("data") or [])]
            model = next((i for i in ids if i and "arena" not in i), ids[0] if ids else "project_persona")
        except Exception as e:  # noqa: BLE001
            print(f"ERROR: could not list models: {e!r}", file=sys.stderr)
            return 2

    body = {"model": model, "messages": [{"role": "user", "content": args.prompt}], "stream": False}
    if args.web is not None:
        body["features"] = {"web_search": args.web}

    t0 = time.time()
    try:
        resp = call("/api/chat/completions", body)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read()[:400].decode('utf-8', 'replace')}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: request failed: {e!r}", file=sys.stderr)
        return 2
    elapsed = round(time.time() - t0, 1)

    answer = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
    sources = resp.get("sources") or []
    src_names = []
    for s in sources:
        meta = s.get("source") or {}
        name = meta.get("name") or meta.get("id") or ""
        if name:
            src_names.append(name)

    fails = []
    low = answer.lower()
    for needle in args.expect_contains:
        if needle.lower() not in low:
            fails.append(f"missing:{needle!r}")
    for needle in args.expect_absent:
        if needle.lower() in low:
            fails.append(f"present:{needle!r}")
    if args.expect_sources and not sources:
        fails.append("no-sources")

    if args.json:
        print(json.dumps({
            "model": model, "web": args.web, "elapsed_s": elapsed,
            "sources": len(sources), "source_names": src_names[:8],
            "answer": answer, "fails": fails,
        }, ensure_ascii=False))
    else:
        print(f"model={model} web={args.web} elapsed={elapsed}s sources={len(sources)}")
        if src_names:
            print("sources: " + ", ".join(src_names[:8]))
        print("--- answer ---")
        print(answer)
        if args.expect_contains or args.expect_absent or args.expect_sources:
            print("--- validation: " + ("FAILED " + str(fails) if fails else "OK"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
