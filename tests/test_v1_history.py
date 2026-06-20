#!/usr/bin/env python3
"""Offline tests for the /v1 (OpenAI-compatible) conversation wiring in server.py.

Covers the Phase 2 hybrid conversation keying + history handoff that brings
`/v1/chat/completions` to parity with `/chat`:

  - _v1_conversation_id   : explicit id / `user` / stable system+first-user hash
  - _v1_latest_user_text  : the trailing user message is the new input
  - _v1_prior_turns       : user/assistant before the trailing user msg (system dropped)
  - _v1_prepare_conversation : cold-thread seeding, windowing, no double-seed on warm
  - full endpoint via TestClient (generation monkeypatched -> no llama-server/network):
    turns persist in conversations.db and conversation_id is returned

Uses a temp CONVERSATIONS_DB (set before importing server). Stdlib + the pinned
FastAPI test chain only; no live server, no network.

    python tests/test_v1_history.py     # exit 0 = pass, 1 = a failure
"""
import os
import sys
import tempfile
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
API = ROOT / "services" / "api"
sys.path.insert(0, str(API))

# Point the conversation store at a throwaway DB BEFORE importing server (server
# calls convo.init_db(CONVERSATIONS_DB) at import time).
_TMPDB = Path(tempfile.mkdtemp(prefix="v1hist_")) / "conversations.db"
os.environ["CONVERSATIONS_DB"] = str(_TMPDB)

warnings.filterwarnings("ignore", message=r"Using .*starlette\.testclient.* is deprecated")

import server  # noqa: E402
import conversations as cv  # noqa: E402

checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def msg(role, content):
    return server.OA_Message(role=role, content=content)


def req(messages, **kw):
    return server.OA_ChatCompletionsReq(messages=messages, **kw)


def main():
    check("server points at temp conversations DB", server.CONVERSATIONS_DB == str(_TMPDB))
    check("conversations store initialized", server._convo_ok)

    # --- _v1_conversation_id: hybrid keying ---------------------------------
    r_explicit = req([msg("user", "hi")], conversation_id="cid-explicit")
    check("explicit conversation_id wins", server._v1_conversation_id(r_explicit) == "cid-explicit")

    # the `user` field must NOT be used as the thread id directly (it is per-USER, not
    # per-conversation) -- it namespaces the hash, so it never collapses distinct threads.
    r_user = req([msg("user", "hi")], user="user-abc")
    check("user field is NOT the raw conversation id", server._v1_conversation_id(r_user) != "user-abc")
    check("user-namespaced id still has owui- prefix", server._v1_conversation_id(r_user).startswith("owui-"))

    # REGRESSION: same user, two different threads -> DIFFERENT ids (the merge bug)
    u_cats = req([msg("system", "S"), msg("user", "tell me about cats")], user="brandon")
    u_paris = req([msg("system", "S"), msg("user", "capital of france?")], user="brandon")
    check("same user, different threads -> different ids",
          server._v1_conversation_id(u_cats) != server._v1_conversation_id(u_paris))
    # same user, same thread -> stable
    check("same user, same thread -> stable id",
          server._v1_conversation_id(u_cats) == server._v1_conversation_id(
              req([msg("system", "S"), msg("user", "tell me about cats"),
                   msg("assistant", "meow"), msg("user", "more?")], user="brandon")))
    # different users, identical message -> different ids (user namespacing)
    check("different users, same first message -> different ids",
          server._v1_conversation_id(req([msg("user", "hello")], user="alice"))
          != server._v1_conversation_id(req([msg("user", "hello")], user="bob")))

    r_a1 = req([msg("system", "you are P"), msg("user", "first message")])
    r_a2 = req([msg("system", "you are P"), msg("user", "first message"),
                msg("assistant", "ok"), msg("user", "second message")])
    id_a1 = server._v1_conversation_id(r_a1)
    id_a2 = server._v1_conversation_id(r_a2)
    check("derived id has owui- prefix", id_a1.startswith("owui-"))
    check("derived id stable across turns of same thread", id_a1 == id_a2)

    r_b = req([msg("system", "you are P"), msg("user", "a DIFFERENT first message")])
    check("different first user -> different id", server._v1_conversation_id(r_b) != id_a1)

    r_sys = req([msg("system", "system A"), msg("user", "same first")])
    r_sys2 = req([msg("system", "system B"), msg("user", "same first")])
    check("system prompt participates in the key",
          server._v1_conversation_id(r_sys) != server._v1_conversation_id(r_sys2))

    # --- _v1_latest_user_text / _v1_prior_turns -----------------------------
    convo_msgs = [msg("system", "S"), msg("user", "u1"), msg("assistant", "a1"), msg("user", "u2")]
    check("latest user text = trailing user msg", server._v1_latest_user_text(convo_msgs) == "u2")
    prior = server._v1_prior_turns(convo_msgs)
    check("prior turns drop system + trailing user", prior == [("user", "u1"), ("assistant", "a1")])
    check("prior turns empty on first turn",
          server._v1_prior_turns([msg("system", "S"), msg("user", "only")]) == [])

    # --- _v1_prepare_conversation: warm thread, no double-seed --------------
    t1 = req([msg("system", "S"), msg("user", "warm thread start")])
    cid1, hist1 = server._v1_prepare_conversation(t1, "default", "chat")
    check("turn 1 has no prior history", hist1 is None)
    check("turn 1 persisted the user turn", cv.count_turns(cid1) == 1)
    server._persist_turn(cid1, "assistant", "reply-1", profile="default", topic="chat")

    t2 = req([msg("system", "S"), msg("user", "warm thread start"),
              msg("assistant", "reply-1"), msg("user", "warm follow-up")])
    cid2, hist2 = server._v1_prepare_conversation(t2, "default", "chat")
    check("turn 2 maps to same thread", cid2 == cid1)
    check("turn 2 sees windowed prior history", isinstance(hist2, dict) and len(hist2.get("recent") or []) >= 1)
    # DB now: user1, assistant1, user2 == 3 (NOT re-seeded from the client array)
    check("warm thread not re-seeded (count == 3)", cv.count_turns(cid1) == 3)

    # --- _v1_prepare_conversation: cold-thread seeding from client array ----
    cold = req([msg("system", "S"),
                msg("user", "cold u1"), msg("assistant", "cold a1"),
                msg("user", "cold u2"), msg("assistant", "cold a2"),
                msg("user", "cold u3")])
    cid_cold, hist_cold = server._v1_prepare_conversation(cold, "default", "chat")
    # seeded 4 prior (u1,a1,u2,a2) + persisted u3 == 5
    check("cold thread seeded from client array (count == 5)", cv.count_turns(cid_cold) == 5)
    check("cold thread produced history", isinstance(hist_cold, dict))
    turns = cv.get_turns(cid_cold)
    check("seeded turns are in order", [t["content"] for t in turns[:3]] == ["cold u1", "cold a1", "cold u2"])

    # --- full endpoint via TestClient (generation monkeypatched) ------------
    async def fake_persona_generate(**kw):
        return ("", "a fake persona reply long enough to look real", {"tokens_generated": 9, "tokens_evaluated": 21})

    async def fake_distill(*a, **k):
        return {}

    orig_gen, orig_distill, orig_rag = server.persona_generate, server.distill_and_store_facts, server.RAG_ENABLED
    server.persona_generate = fake_persona_generate
    server.distill_and_store_facts = fake_distill
    server.RAG_ENABLED = False
    try:
        from fastapi.testclient import TestClient
        client = TestClient(server.app)
        body = {"messages": [{"role": "system", "content": "S"},
                             {"role": "user", "content": "endpoint hello"}]}
        resp = client.post("/v1/chat/completions", json=body)
        check("endpoint returns 200", resp.status_code == 200)
        data = resp.json()
        cid = data.get("conversation_id")
        check("response carries conversation_id", isinstance(cid, str) and cid.startswith("owui-"))
        check("response is OpenAI-shaped", data["choices"][0]["message"]["content"].startswith("a fake persona reply"))
        check("endpoint persisted user+assistant", cv.count_turns(cid) == 2)

        # second turn on the same thread reloads + extends history
        body2 = {"messages": [{"role": "system", "content": "S"},
                              {"role": "user", "content": "endpoint hello"},
                              {"role": "assistant", "content": "a fake persona reply long enough to look real"},
                              {"role": "user", "content": "endpoint follow-up"}]}
        resp2 = client.post("/v1/chat/completions", json=body2)
        check("turn 2 maps to same thread id", resp2.json().get("conversation_id") == cid)
        check("turn 2 extended the thread (count == 4)", cv.count_turns(cid) == 4)
    finally:
        server.persona_generate = orig_gen
        server.distill_and_store_facts = orig_distill
        server.RAG_ENABLED = orig_rag

    print()
    print(f"RESULT: {checks - len(failures)}/{checks} checks passed")
    if failures:
        print("FAILURES:", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
