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

from datetime import datetime


def _pacific_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Los_Angeles"))
    except Exception:
        return datetime.now().astimezone()


class _Tee:
    def __init__(self, *streams):
        self._streams = streams

    def write(self, s):
        for st in self._streams:
            st.write(s)
        return len(s)

    def flush(self):
        for st in self._streams:
            st.flush()


_log_fh = None
if not os.getenv("RUN_LOGGED"):
    LOG_DIR = os.path.join(REPO, "logs")
    os.makedirs(LOG_DIR, exist_ok=True)
    _log_fh = open(os.path.join(LOG_DIR, "test_api_offline.log"), "w", encoding="utf-8", newline="\n")
    sys.stdout = _Tee(sys.__stdout__, _log_fh)
    _now = _pacific_now()
    print("=" * 72)
    print("Project_Persona offline self-test log")
    print("started  : " + _now.strftime("%Y-%m-%d %H%M ") + (_now.tzname() or "local"))
    print("python   : " + sys.version.split()[0] + "  (" + sys.executable + ")")
    print("platform : " + sys.platform)
    print("=" * 72)
    print()

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
checks_run = 0


def check(name, cond):
    global checks_run
    checks_run += 1
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

# H2 bridge: /agent/delegate writes a "delegated" row WITHOUT running taskman2.
r = client.post("/agent/delegate", json={"job_id": "delgA", "title": "Summarize the design doc",
                                          "body": "Read docs/ and summarize.", "assignee": "default"})
dj = r.json()
check("/agent/delegate returns delegated", dj.get("status") == "delegated" and dj.get("job_id") == "delgA")
check("/agent/delegate row kind hermes_delegate", dj["job"].get("kind") == "hermes_delegate")
check("/agent/delegate did NOT run taskman2", "returncode" not in dj["job"] and "result_file" not in dj["job"])
check("/agent/delegate carries no hermes_task_id yet", "hermes_task_id" not in dj["job"])
check("/agent/delegate has delegated_at + assignee + tenant",
      isinstance(dj["job"].get("delegated_at"), int) and dj["job"].get("assignee") == "default"
      and dj["job"].get("tenant") == "persona")
r = client.get("/jobs/delgA")
check("/jobs/<delegate> round-trips status=delegated", r.json().get("status") == "delegated")
r = client.post("/agent/delegate", json={"body": "no title"})
check("/agent/delegate without title -> 400", r.status_code == 400)
r = client.post("/agent/delegate", json={"job_id": "delgA", "title": "dup"})
check("/agent/delegate duplicate job_id -> 409", r.status_code == 409)

# New bridge statuses (delegated/blocked) round-trip through /jobs additively.
tb.task_set("delgB", {"status": "blocked", "kind": "hermes_delegate",
                      "block_reason": "review-required: confirm scope"})
r = client.get("/jobs/delgB")
check("/jobs/<id> blocked status round-trips", r.json().get("status") == "blocked")
check("/jobs/<id> block_reason surfaced", "review-required" in (r.json().get("block_reason") or ""))
h = client.get("/health").json()
check("health delegate block present", isinstance(h.get("delegate"), dict)
      and h["delegate"].get("default_tenant") == "persona")

check("collection_name global when off", server._collection_name("alice") == server.RAG_GLOBAL_COLLECTION)
_saved_pp = server.RAG_PER_PROFILE
server.RAG_PER_PROFILE = True
check("collection_name per-profile when on", server._collection_name("alice") == "mem_alice")
check("collection_name None -> global", server._collection_name(None) == server.RAG_GLOBAL_COLLECTION)
check("collection_name sanitizes unsafe", server._collection_name("a/b c") == "mem_a_b_c")
server.RAG_PER_PROFILE = _saved_pp
h = client.get("/health").json()
check("health rag_per_profile present", "rag_per_profile" in h)
check("health rag_collections is list", isinstance(h.get("rag_collections"), list))

check("classify_topic coding", server.classify_topic("why does my python function throw an exception") == "coding")
check("classify_topic chat fallback", server.classify_topic("hey how are you") == "chat")
check("resolve_topic explicit non-chat respected", server.resolve_topic("biology", "python code") == "biology")

r = client.post("/chat", json={"text": "compute the derivative of this polynomial equation", "topic": "auto", "debug": True})
tr = r.json()["debug"]["topic_routing"]
check("auto routes to math", tr["resolved"] == "math")
check("auto routed topic drives think preset", r.json()["debug"]["sampling_preset"] == "think")

r = client.post("/chat", json={"text": "debug this python stack trace", "topic": "chat", "debug": True})
check("routing off -> chat stays chat", r.json()["debug"]["topic_routing"]["resolved"] == "chat")

_saved_tr = server.TOPIC_ROUTING_DEFAULT
server.TOPIC_ROUTING_DEFAULT = True
r = client.post("/chat", json={"text": "debug this python stack trace", "topic": "chat", "debug": True})
check("routing on -> chat classified to coding", r.json()["debug"]["topic_routing"]["resolved"] == "coding")
server.TOPIC_ROUTING_DEFAULT = _saved_tr

h = client.get("/health").json()
check("health topic_routing present", "topic_routing" in h and "topic_routing_topics" in h)

msgs = server.build_persona_messages("hello world here", [], profile="default", topic="chat")
check("messages: two parts", len(msgs) == 2)
check("messages: system + user roles", msgs[0]["role"] == "system" and msgs[1]["role"] == "user")
check("messages: user carries text + topic", "hello world here" in msgs[1]["content"] and "Topic:" in msgs[1]["content"])
check("messages: no think prefix", "/think" not in msgs[1]["content"] and "/no_think" not in msgs[0]["content"])


async def fake_query_llama_messages(url, messages, max_tokens, temperature, timeout_s, *, enable_thinking, extra=None):
    return (
        "The answer here is long enough to pass the writeback filters easily.",
        "server-side reasoning block",
        {"tokens_generated": 7, "tokens_evaluated": 30},
    )


server.query_llama_messages = fake_query_llama_messages
_saved_msgs = server.PERSONA_USE_MESSAGES
_saved_san = server.PERSONA_SANITIZE_MESSAGES
server.PERSONA_USE_MESSAGES = True
server.PERSONA_SANITIZE_MESSAGES = False
r = client.post("/chat", json={"text": "explain the idea", "topic": "science", "preserve_thinking": True, "debug": True})
body = r.json()
check("messages path: preserve surfaces server reasoning", body["reasoning"] == "server-side reasoning block")
check("messages path: content is the answer", body["text"].startswith("The answer here"))
r = client.post("/chat", json={"text": "explain the idea", "topic": "science", "debug": True})
check("messages path: default does not leak reasoning", "server-side reasoning" not in r.json()["text"])
r = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}], "preserve_thinking": True})
m = r.json()["choices"][0]["message"]
check("messages path: /v1 reasoning_content", m.get("reasoning_content") == "server-side reasoning block")

r = client.post("/chat", json={"text": "explain the idea", "topic": "science", "debug": True})
body = r.json()
check("T2.4: messages path returns server content verbatim",
      body["text"] == "The answer here is long enough to pass the writeback filters easily.")
check("T2.4: messages path skips forced Next actions", "Next actions:" not in body["text"])
check("T2.4: debug reports sanitizer not applied", body["debug"]["sanitizer_applied"] is False)

r = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
mc = r.json()["choices"][0]["message"]["content"]
check("T2.4: /v1 messages path content verbatim",
      mc == "The answer here is long enough to pass the writeback filters easily.")

server.PERSONA_SANITIZE_MESSAGES = True
r = client.post("/chat", json={"text": "explain the idea", "topic": "science", "debug": True})
body = r.json()
check("T2.4: escape hatch re-sanitizes messages path", "Next actions:" in body["text"])
check("T2.4: debug reports sanitizer applied under hatch", body["debug"]["sanitizer_applied"] is True)

server.PERSONA_USE_MESSAGES = _saved_msgs
server.PERSONA_SANITIZE_MESSAGES = _saved_san
server.query_llama_messages = None

r = client.post("/chat", json={"text": "plan something", "topic": "chat", "debug": True})
body = r.json()
check("T2.4: raw /completion path still sanitizes", "Next actions:" in body["text"])
check("T2.4: raw path debug reports sanitizer applied", body["debug"]["sanitizer_applied"] is True)

check("health persona_use_messages present", "persona_use_messages" in client.get("/health").json())
check("health persona_sanitize_messages present", "persona_sanitize_messages" in client.get("/health").json())

print()
print("RESULT:", "ALL PASS" if not failures else ("FAILURES: " + ", ".join(failures)))

if _log_fh is not None:
    _end = _pacific_now()
    print("=" * 72)
    print("finished : " + _end.strftime("%Y-%m-%d %H%M ") + (_end.tzname() or "local"))
    print("scan     : checks={} PASS={} FAIL={}".format(checks_run, checks_run - len(failures), len(failures)))
    print("log file : " + _log_fh.name)
    print("=" * 72)
    sys.stdout.flush()
    sys.stdout = sys.__stdout__
    _log_fh.close()

sys.exit(1 if failures else 0)
