"""Offline smoke test for services/api/server.py.

Runs the FastAPI app via TestClient with query_llama monkeypatched, so it needs
no llama-server and no network. Run from the repo root with the portable
interpreter:

    .\\portable\\python\\python.exe tests\\test_api_offline.py

Exit code 0 = all pass, 1 = one or more failures.
"""
import os
import sys
import json
import tempfile
import warnings

# Cosmetic: Starlette's TestClient emits a deprecation notice about httpx/httpx2
# (httpx >=0.27 Client-init change). Test-harness only, not the serving path; we
# suppress it here rather than bump a pinned FastAPI-chain dependency. Must run
# before the starlette.testclient import below.
warnings.filterwarnings(
    "ignore",
    message=r"Using .*starlette\.testclient.* is deprecated",
)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
API = os.path.join(REPO, "services", "api")
sys.path.insert(0, API)

TMP = tempfile.mkdtemp(prefix="persona_apitest_")
os.environ.update({
    "AI_ROOT": TMP,
    "PERSONA_ROOT": os.path.join(TMP, "persona"),
    "PROFILES_DIR": os.path.join(TMP, "persona", "profiles"),
    "GLOBAL_MEMORY_DIR": os.path.join(TMP, "persona", "global_memory"),
    "RAG_ENABLED": "0",
    "MEMORY_DISTILL_ENABLED": "0",
    "PERSONA_WRITEBACK_ENABLED": "0",
    "CHAT_LOG_WRITEBACK_ENABLED": "0",
})

import server


async def fake_query_llama(url, prompt, tokens, temperature, timeout_s, extra=None):
    return (
        "This is a sanitized persona reply long enough to survive writeback filters.",
        {"tokens_generated": 11, "tokens_evaluated": 42},
    )


server.query_llama = fake_query_llama

from fastapi.testclient import TestClient

client = TestClient(server.app)
failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


r = client.get("/")
check("GET / -> 200", r.status_code == 200)
check("GET / -> service json", r.json().get("service") == "project_persona")

r = client.get("/favicon.ico")
check("GET /favicon.ico -> 204", r.status_code == 204)

r = client.get("/health")
check("GET /health -> 200", r.status_code == 200)

r = client.get("/v1/models")
check("GET /v1/models -> 200", r.status_code == 200)

r = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
usage = r.json().get("usage", {})
check("usage.prompt_tokens == 42", usage.get("prompt_tokens") == 42)
check("usage.completion_tokens == 11", usage.get("completion_tokens") == 11)
check("usage.total_tokens == 53", usage.get("total_tokens") == 53)

r = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}], "stream": True})
check("stream -> 200", r.status_code == 200)
check("stream content-type", r.headers.get("content-type", "").startswith("text/event-stream"))
body = r.text
check("stream emits chunk objects", "chat.completion.chunk" in body)
check("stream ends with [DONE]", "data: [DONE]" in body)
content = "".join(
    json.loads(line[len("data: "):])["choices"][0]["delta"].get("content", "")
    for line in body.splitlines()
    if line.startswith("data: ") and line.strip() != "data: [DONE]"
)
check("stream reconstructs non-empty content", len(content) > 0)

r = client.post("/chat_submit", json={"text": "hi"})
check("/chat_submit removed -> 404", r.status_code == 404)

check("classify_triviality trivial 'hi'", server.classify_triviality("hi") == (False, ["short"]))
check(
    "classify_triviality non-trivial 'why'",
    server.classify_triviality("Explain why the sky is blue and how Rayleigh scattering works")[0] is True,
)

server.THINKING_AUTO_GATE = False
r = client.post("/chat", json={"text": "Explain why and how this works in detail", "topic": "chat", "debug": True})
gate = r.json().get("debug", {}).get("thinking_gate", {})
check("gate off -> reports disabled", gate.get("enabled") is False)
check("gate off -> chat resolves no_think", r.json()["debug"]["thinking_mode_resolved"] == "/no_think")
check("gate classifies non-trivial regardless", gate.get("is_nontrivial") is True)

server.THINKING_AUTO_GATE = True
r = client.post("/chat", json={"text": "Explain why and how this works in detail", "topic": "chat", "debug": True})
check("gate on -> non-trivial chat promotes to think", r.json()["debug"]["thinking_mode_resolved"] == "/think")
check("gate on -> non-trivial chat uses think preset", r.json()["debug"]["sampling_preset"] == "think")
r = client.post("/chat", json={"text": "hi", "topic": "chat", "debug": True})
check("gate on -> trivial chat stays no_think", r.json()["debug"]["thinking_mode_resolved"] == "/no_think")
r = client.post("/chat", json={"text": "hi", "topic": "science", "debug": True})
check("gate on -> thinking topic still deterministic think", r.json()["debug"]["thinking_mode_resolved"] == "/think")
server.THINKING_AUTO_GATE = False

check("split_reasoning wrapped", server.split_reasoning("<think>r</think>a") == ("r", "a"))
check("split_reasoning none", server.split_reasoning("plain answer") == ("", "plain answer"))
check("split_reasoning unclosed", server.split_reasoning("<think>partial only") == ("partial only", ""))


async def fake_query_llama_think(url, prompt, tokens, temperature, timeout_s, extra=None):
    return (
        "<think>weigh the options step by step</think>"
        "Here is the actual answer, long enough to survive the writeback filters fine.",
        {"tokens_generated": 9, "tokens_evaluated": 40},
    )


server.query_llama = fake_query_llama_think

r = client.post("/chat", json={"text": "plan something", "topic": "chat", "debug": True})
body = r.json()
check("/chat default strips think from text", "<think>" not in body["text"] and "weigh the options" not in body["text"])
check("/chat default reasoning empty", body["reasoning"] == "")
check("/chat default preserve resolved false", body["debug"]["preserve_thinking"]["resolved"] is False)

r = client.post("/chat", json={"text": "plan something", "topic": "chat", "preserve_thinking": True, "debug": True})
body = r.json()
check("/chat preserve returns reasoning", body["reasoning"] == "weigh the options step by step")
check("/chat preserve answer un-sanitized", body["text"].startswith("Here is the actual answer"))
check("/chat preserve no forced Next actions", "Next actions:" not in body["text"])

r = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "plan"}], "preserve_thinking": True})
msg = r.json()["choices"][0]["message"]
check("/v1 preserve emits reasoning_content", msg.get("reasoning_content") == "weigh the options step by step")
check("/v1 preserve content is the answer", msg["content"].startswith("Here is the actual answer"))

r = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "plan"}]})
msg = r.json()["choices"][0]["message"]
check("/v1 default has no reasoning_content", "reasoning_content" not in msg)

server.query_llama = fake_query_llama

tb = server.taskboard
check("health task_store present", "task_store" in client.get("/health").json())

r = client.get("/jobs/does-not-exist")
check("/jobs/<missing> -> not_found", r.json().get("status") == "not_found")

tb.task_set("jobA", {"status": "running", "kind": "agent_run"})
tb.task_set("jobA", {"status": "ok", "returncode": 0})
r = client.get("/jobs/jobA")
jb = r.json()
check("/jobs/<id> upsert-merged", jb.get("status") == "ok" and jb.get("kind") == "agent_run")
check("/jobs/<id> has timestamps", "_created_at" in jb and "_updated_at" in jb)

r = client.get("/jobs?limit=10")
ids = [j["job_id"] for j in r.json().get("jobs", [])]
check("/jobs list includes jobA", "jobA" in ids)
check("/jobs list carries status", any(j["job_id"] == "jobA" and j["status"] == "ok" for j in r.json()["jobs"]))

print()
print("RESULT:", "ALL PASS" if not failures else ("FAILURES: " + ", ".join(failures)))
sys.exit(1 if failures else 0)
