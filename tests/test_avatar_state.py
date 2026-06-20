#!/usr/bin/env python3
"""Offline tests for the Phase 4 avatar STATE deriver (services/api/avatar_state.py).

Pure + deterministic: maps a reply to {emotion, intensity, gesture, speaking, viseme} in the
documented vocabulary. No model, no network.

    python tests/test_avatar_state.py     # exit 0 = pass, 1 = a failure
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "api"))

import avatar_state as av  # noqa: E402

checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def main():
    neutral = av.derive_state("Here is the information you asked for.")
    check("neutral statement -> neutral/idle", neutral["emotion"] == "neutral" and neutral["gesture"] == "idle")
    check("state has the full vocabulary keys",
          set(neutral) == {"emotion", "intensity", "gesture", "speaking", "viseme"})
    check("emotion is in EMOTIONS", neutral["emotion"] in av.EMOTIONS)
    check("gesture is in GESTURES", neutral["gesture"] in av.GESTURES)

    q = av.derive_state("What would you like to do next?")
    check("question -> thinking/tilt_head", q["emotion"] == "thinking" and q["gesture"] == "tilt_head")

    concern = av.derive_state("Sorry, that failed with an error.")
    check("error text -> concerned", concern["emotion"] == "concerned")

    happy = av.derive_state("Great, thanks -- that worked perfectly.")
    check("thanks/great -> happy", happy["emotion"] == "happy")

    excited = av.derive_state("Awesome, let's go!!!")
    check("exclamation+awesome -> excited", excited["emotion"] == "excited")
    check("exclamation raises intensity", excited["intensity"] > happy["intensity"])
    check("intensity clamped <= 1.0", av.derive_state("yes!!!!!!!!!!")["intensity"] <= 1.0)

    confused = av.derive_state("I'm not sure what you mean by that.")
    check("not sure -> confused", confused["emotion"] == "confused")

    # speaking flag drives the mouth/viseme channel
    sil = av.derive_state("hello", speaking=False)
    spk = av.derive_state("hello", speaking=True)
    check("not speaking -> viseme sil", sil["speaking"] is False and sil["viseme"] == "sil")
    check("speaking -> viseme aa", spk["speaking"] is True and spk["viseme"] == "aa")

    check("empty text is safe", av.derive_state("")["emotion"] == "neutral")

    print()
    print(f"RESULT: {checks - len(failures)}/{checks} checks passed")
    if failures:
        print("FAILURES:", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
