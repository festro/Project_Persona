#!/usr/bin/env python3
"""Offline test for the always-on self-identity block (server.self_identity_section +
its injection into the persona system prompt).

    python tests/test_self_identity.py     # exit 0 = pass, 1 = a failure
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
# Point the loader at the repo's real SELF_IDENTITY.md and root before importing server.
os.environ["SELF_IDENTITY_PATH"] = str(ROOT / "SELF_IDENTITY.md")
os.environ.setdefault("AI_ROOT", str(ROOT))
sys.path.insert(0, str(ROOT / "services" / "api"))

import server  # noqa: E402

checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


sec = server.self_identity_section()
check("self-identity section loads", bool(sec))
check("identifies as Project_Persona", "Project_Persona" in sec)
check("marked authoritative", "AUTHORITATIVE" in sec)
check("carries real architecture facts", "Qwen3.6-35B" in sec and "Qdrant" in sec)

# It must be injected into the actual persona system prompt.
msgs = server.build_persona_messages("hello", [], profile="default", topic="chat")
sys_msg = msgs[0]["content"]
check("system prompt is the first message", msgs and msgs[0]["role"] == "system")
check("self-identity injected into system prompt", "you ARE this system" in sys_msg and "Project_Persona" in sys_msg)
check("still has the Output format block after it", "Output format:" in sys_msg)

# The legacy raw-prompt builder gets it too.
prompt = server.build_persona_prompt("hello", [], profile="default", topic="chat")
check("raw prompt builder also injects identity", "Project_Persona" in prompt and "you ARE this system" in prompt)

print(f"\n{checks - len(failures)}/{checks} checks passed")
sys.exit(1 if failures else 0)
