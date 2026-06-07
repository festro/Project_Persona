"""Phase 1 Exit Gate -- LIVE validation against a running stack.

Unlike tests/test_api_offline.py (which fakes query_llama), this hits the real
companion API and the live llama-server, so it must be run with the stack UP:

    portable\\python\\python.exe manage.py up
    portable\\python\\python.exe tests\\exit_gate_live.py

Stdlib only (urllib) -- no extra deps. Exit code 0 = all required checks pass.

Checks (roadmap Phase 1 Exit Gate):
  - /health green: status ok, embedder_ok, chroma_ok
  - thinking resolution: chat -> no_think; science/coding/math/research -> think
  - T2.3 preserve_thinking: reasoning surfaced under preserve, stripped by default
  - /v1: stream=true yields SSE chunks + [DONE]; non-stream reports prompt_tokens>0
  - /v1 preserve: reasoning_content present under preserve

Model-dependent checks (need a thinking model, e.g. Qwen3.6) are SOFT: they WARN
rather than fail if no reasoning is produced, so the suite still passes on a
non-thinking model (e.g. Instruct-2507) while telling you what was skipped.

Env:
  API_BASE   default http://127.0.0.1:8000
  THINK_TOPIC default science   (a topic in THINKING_MODE_TOPICS)
"""
import os
import sys
import json
import urllib.request

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000").rstrip("/")
THINK_TOPIC = os.getenv("THINK_TOPIC", "science")

failures = []
warnings = []


def _req(method, path, payload=None, stream=False, timeout=180):
    url = API_BASE + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    resp = urllib.request.urlopen(req, timeout=timeout)
    if stream:
        return resp
    return resp.status, json.loads(resp.read().decode("utf-8"))


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def soft(name, cond, why):
    if cond:
        print("PASS", name)
    else:
        print("WARN", name, "--", why)
        warnings.append(name)


def chat(text, topic="chat", preserve=None):
    payload = {"text": text, "topic": topic, "debug": True}
    if preserve is not None:
        payload["preserve_thinking"] = preserve
    _, body = _req("POST", "/chat", payload)
    return body


print("Exit Gate live check against", API_BASE)
print("-" * 60)

status, health = _req("GET", "/health")
check("/health -> 200", status == 200)
check("/health status ok", health.get("status") == "ok")
check("/health embedder_ok", health.get("embedder_ok") is True)
check("/health chroma_ok", health.get("chroma_ok") is True)
print("  thinking_auto_gate:", health.get("thinking_auto_gate"),
      "| preserve_thinking_default:", health.get("preserve_thinking_default"))

b = chat("hello there", topic="chat")
check("chat topic -> no_think", b["debug"]["thinking_mode_resolved"] == "/no_think")
check("chat topic -> no_think preset", b["debug"]["sampling_preset"] == "no_think")

for tp in ("science", "coding", "math", "research"):
    b = chat("Work through this carefully.", topic=tp)
    check(tp + " topic -> think", b["debug"]["thinking_mode_resolved"] == "/think")
    check(tp + " topic -> think preset", b["debug"]["sampling_preset"] == "think")

b = chat("Plan a small experiment and reason it out.", topic=THINK_TOPIC, preserve=False)
check("preserve off: no <think> in text", "<think>" not in b["text"])
check("preserve off: reasoning empty", b.get("reasoning", "") == "")

b = chat("Plan a small experiment and reason it out.", topic=THINK_TOPIC, preserve=True)
check("preserve on: no <think> in text", "<think>" not in b["text"])
soft("preserve on: reasoning surfaced",
     b["debug"]["preserve_thinking"]["reasoning_chars"] > 0,
     "served model produced no <think> (non-thinking model?)")

_, v = _req("POST", "/v1/chat/completions", {"messages": [{"role": "user", "content": "Say hi."}]})
usage = v.get("usage", {})
check("/v1 non-stream prompt_tokens > 0", int(usage.get("prompt_tokens", 0)) > 0)

resp = _req("POST", "/v1/chat/completions",
            {"messages": [{"role": "user", "content": "Say hi."}], "stream": True}, stream=True)
raw = resp.read().decode("utf-8")
check("/v1 stream emits chunks", "chat.completion.chunk" in raw)
check("/v1 stream ends with [DONE]", "data: [DONE]" in raw)

_, v = _req("POST", "/v1/chat/completions",
            {"messages": [{"role": "user", "content": "Plan and reason it out."}],
             "topic": THINK_TOPIC, "preserve_thinking": True})
msg = v["choices"][0]["message"]
soft("/v1 preserve -> reasoning_content",
     bool(msg.get("reasoning_content")),
     "served model produced no <think> (non-thinking model?)")

# ---- adaptive sections: validate whichever flags are enabled on the server ----
# Re-read /health so the script reflects the running config and only asserts the
# flag-gated behavior that is actually turned on (skips the rest with a note).
flags = _req("GET", "/health")[1]
print("-" * 60)
print("flags: persona_use_messages=%s | rag_per_profile=%s | topic_routing=%s | thinking_auto_gate=%s"
      % (flags.get("persona_use_messages"), flags.get("rag_per_profile"),
         flags.get("topic_routing"), flags.get("thinking_auto_gate")))

# T2.4 messages path (PERSONA_USE_MESSAGES=1). Confirms reasoning arrives from the
# server's reasoning_content under --jinja and the user channel stays <think>-free.
if flags.get("persona_use_messages"):
    b = chat("Plan a small experiment and reason it through.", topic=THINK_TOPIC, preserve=True)
    check("[messages] no <think> in text", "<think>" not in b["text"])
    soft("[messages] reasoning from server reasoning_content",
         b["debug"]["preserve_thinking"]["reasoning_chars"] > 0,
         "server returned no reasoning_content (check --reasoning-format deepseek / non-thinking model)")
    _, v = _req("POST", "/v1/chat/completions",
                {"messages": [{"role": "user", "content": "Plan and reason it through."}],
                 "topic": THINK_TOPIC, "preserve_thinking": True})
    soft("[messages] /v1 reasoning_content present",
         bool(v["choices"][0]["message"].get("reasoning_content")),
         "server returned no reasoning_content")
else:
    print("SKIP [messages] T2.4 -- PERSONA_USE_MESSAGES off (set =1 + restart to validate)")

# Per-profile Chroma (RAG_PER_PROFILE=1 AND RAG_ENABLED). Posts under throwaway
# profiles and confirms mem_<profile> collections appear in /health.rag_collections.
if flags.get("rag_per_profile") and flags.get("rag_enabled"):
    _req("POST", "/chat", {"text": "hello from alice, remember this", "topic": "chat", "profile": "alice"})
    _req("POST", "/chat", {"text": "hello from bob, remember this", "topic": "chat", "profile": "bob"})
    cols = _req("GET", "/health")[1].get("rag_collections", [])
    check("[per-profile] mem_alice collection created", "mem_alice" in cols)
    check("[per-profile] mem_bob collection created", "mem_bob" in cols)
else:
    print("SKIP [per-profile] -- needs RAG_PER_PROFILE=1 and RAG_ENABLED (set + restart)")

print("-" * 60)
if warnings:
    print("WARNINGS (model-dependent, not failures):", ", ".join(warnings))
print("RESULT:", "ALL REQUIRED PASS" if not failures else ("FAILURES: " + ", ".join(failures)))
sys.exit(1 if failures else 0)
