#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "${HERE}/.." && pwd)"
SRC="${ROOT}/HANDOFF.md"
OUT="${ROOT}/HANDOFF.html"
CSS_EMBED="$(mktemp /tmp/handoff_styles.XXXXXX.css)"
trap 'rm -f "${CSS_EMBED}"' EXIT
if [[ ! -f "${SRC}" ]]; then
    echo "ERROR: HANDOFF.md not found at ${SRC}" >&2
    exit 1
fi
if ! command -v pandoc >/dev/null 2>&1; then
    echo "ERROR: pandoc not installed (apt install pandoc)" >&2
    exit 1
fi
cat > "${CSS_EMBED}" <<'CSS_EOF'
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 1100px;
    margin: 2em auto;
    padding: 0 2em;
    line-height: 1.55;
    color: #1a1a1a;
    background: #ffffff;
}
h1, h2, h3 { color: #0f1419; }
h1 { border-bottom: 2px solid #2c3e50; padding-bottom: 0.3em; }
h2 { border-bottom: 1px solid #d0d7de; padding-bottom: 0.2em; margin-top: 2em; }
code { background: #f5f5f5; padding: 0.1em 0.4em; border-radius: 3px; font-size: 0.9em; }
pre { background: #f5f5f5; padding: 1em; border-radius: 5px; overflow-x: auto; }
pre code { background: transparent; padding: 0; }
table { border-collapse: collapse; margin: 1em 0; width: 100%; }
th, td { border: 1px solid #d0d7de; padding: 0.5em 0.8em; text-align: left; vertical-align: top; }
th { background: #f5f5f5; }
details { border: 1px solid #d0d7de; border-radius: 5px; padding: 0.5em 1em; margin: 1em 0; background: #fafbfc; }
details[open] { background: #ffffff; }
summary { cursor: pointer; font-weight: 600; padding: 0.3em 0; user-select: none; }
summary:hover { color: #0969da; }
blockquote { border-left: 4px solid #d0d7de; margin: 1em 0; padding: 0.3em 1em; background: #f8f9fa; color: #444; }
a { color: #0969da; text-decoration: none; }
a:hover { text-decoration: underline; }
hr { border: 0; border-top: 1px solid #d0d7de; margin: 2em 0; }
#TOC { background: #f8f9fa; border: 1px solid #d0d7de; border-radius: 5px; padding: 1em 2em; margin: 1em 0 2em; }
#TOC ul { padding-left: 1.5em; }
@media (prefers-color-scheme: dark) {
    body { background: #0d1117; color: #c9d1d9; }
    h1, h2, h3 { color: #f0f6fc; }
    h1 { border-bottom-color: #30363d; }
    h2 { border-bottom-color: #21262d; }
    code, pre { background: #161b22; color: #c9d1d9; }
    th, td { border-color: #30363d; }
    th { background: #161b22; }
    details { background: #0d1117; border-color: #30363d; }
    details[open] { background: #0d1117; }
    summary:hover { color: #58a6ff; }
    blockquote { background: #161b22; border-left-color: #30363d; color: #8b949e; }
    a { color: #58a6ff; }
    hr { border-top-color: #30363d; }
    #TOC { background: #161b22; border-color: #30363d; }
}
CSS_EOF
PANDOC_VER="$(pandoc --version | head -1 | awk '{print $2}')"
PANDOC_MAJOR="${PANDOC_VER%%.*}"
if [[ "${PANDOC_MAJOR}" -ge 3 ]]; then
    EMBED_FLAG="--embed-resources"
else
    EMBED_FLAG="--self-contained"
fi
pandoc "${SRC}" -o "${OUT}" \
    --standalone "${EMBED_FLAG}" \
    --toc --toc-depth=2 \
    --metadata title="Project_Persona Living Handoff" \
    --css="${CSS_EMBED}"
SIZE="$(stat -c%s "${OUT}" 2>/dev/null || stat -f%z "${OUT}")"
echo "Generated ${OUT} (${SIZE} bytes)"
