"""PROJECT_PERSONA: fetch URLs the user pastes into chat directly.

OpenWebUI's web_search feature paraphrases the conversation into keyword queries and
searches -- so a pasted link like "explain https://github.com/festro/Project_Persona"
never gets visited; the model just searches for "Project_Persona" and lands on
lookalike repos. This helper detects URLs in the latest user message and loads THOSE
pages directly (via OpenWebUI's own /process/web loader), attaching them as
web_search-style sources so the proven retrieval path injects them.

Deploy: scripts/start_webui.sh copies this file into open_webui/utils/ and inserts a
call into open_webui/utils/middleware.py (both steps marker-guarded + idempotent).

Only the stdlib is imported at module load (re, logging) so extract_urls() is unit
testable offline; the OpenWebUI imports are deferred into fetch_inline_urls().
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

# http(s) URL. Stop at whitespace, angle brackets, any quote (straight, single, or the
# curly quotes a copy-paste produces), backtick, and the bracket closers that wrap URLs
# in markdown / prose -- so "(https://x)" and the smart-quoted "https://x" both clip clean.
_URL_RE = re.compile(
    r"https?://[^\s<>\"'`\)\]\}‘’“”]+",
    re.IGNORECASE,
)
# Sentence punctuation that is a valid URL char but is almost always a trailing artifact.
_TRAILING = ".,;:!?…"


def extract_urls(text, limit: int = 4):
    """Return up to `limit` de-duplicated, cleaned URLs from `text` (order preserved)."""
    if not text:
        return []
    out = []
    for m in _URL_RE.finditer(text):
        url = m.group(0).rstrip(_TRAILING)
        if url and url not in out:
            out.append(url)
        if len(out) >= limit:
            break
    return out


async def fetch_inline_urls(request, form_data, extra_params, user):
    """Load any URLs in the latest user message into web_search-style collections on
    form_data['files']. Returns the list of URLs successfully fetched (empty if none)."""
    try:
        from open_webui.utils.misc import get_last_user_message
        from open_webui.routers.retrieval import ProcessUrlForm, process_web
    except Exception as e:  # pragma: no cover - only hit inside OpenWebUI
        log.warning("persona inline-url: import failed: %s", e)
        return []

    urls = extract_urls(get_last_user_message(form_data.get("messages") or []))
    if not urls:
        return []

    event_emitter = extra_params.get("__event_emitter__")

    async def _status(desc, done, error=False, found=None):
        if not event_emitter:
            return
        data = {"action": "web_search", "description": desc, "done": done}
        if error:
            data["error"] = True
        if found:
            data["urls"] = found
        await event_emitter({"type": "status", "data": data})

    files = form_data.get("files", [])
    fetched = []
    for url in urls:
        try:
            await _status(f"Reading {url}", done=False)
            res = await process_web(
                request, ProcessUrlForm(url=url), process=True, overwrite=True, user=user
            )
            collection_name = res.get("collection_name") if isinstance(res, dict) else None
            if collection_name:
                files.append(
                    {
                        "collection_name": collection_name,
                        "name": url,
                        "type": "web_search",
                        "urls": [url],
                        "queries": [url],
                    }
                )
                fetched.append(url)
            else:
                log.warning("persona inline-url: no collection for %s", url)
        except Exception as e:
            log.warning("persona inline-url: fetch failed for %s: %s", url, e)
            await _status(f"Could not read {url}", done=True, error=True)

    if fetched:
        form_data["files"] = files
        await _status("Read {{count}} link(s)", done=True, found=fetched)
    return fetched
