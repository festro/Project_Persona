"""Phase 4 -- the persona side of the two-channel embodiment protocol.

The persona answers on two channels: RESPONSE (the text, later spoken by Phase 5 TTS) and
STATE (a small JSON of avatar directives -- emotion, gesture, mouth state). A Godot/VR client
consumes STATE to animate an avatar in sync with RESPONSE (docs/avatar_protocol.md). This module
is the pure deriver: deterministic, dependency-free, so the STATE channel works with or without
a client attached and is unit-testable.

STATE vocabulary (the contract a client animates against):
  emotion   : one of EMOTIONS
  intensity : 0.0..1.0 strength of the emotion
  gesture   : one of GESTURES (a one-shot body cue)
  speaking  : bool -- is TTS audio playing (driven by Phase 5 tts_speaking; False until then)
  viseme    : coarse mouth shape ("sil" when not speaking, else a neutral "aa")
"""
import re
from typing import Any, Dict, Optional

EMOTIONS = ("neutral", "happy", "excited", "thinking", "concerned", "confused", "amused")
GESTURES = ("idle", "nod", "shrug", "wave", "point", "tilt_head", "lean_in")

# Ordered cue table: the first emotion whose keywords hit wins (most specific first). Each entry
# is (emotion, default_gesture, base_intensity, [keywords]).
_CUES = (
    ("concerned", "lean_in", 0.6, ["sorry", "unfortunately", "error", "failed", "fail ",
                                   "cannot", "can't", "unable", "warning", "issue", "problem"]),
    ("confused", "tilt_head", 0.5, ["not sure", "unclear", "confus", "i don't know",
                                    "ambiguous", "unsure"]),
    ("excited", "nod", 0.8, ["awesome", "amazing", "fantastic", "let's go", "great news",
                             "congratulations", "congrats", "love it"]),
    ("happy", "nod", 0.6, ["glad", "great", "happy", "thanks", "thank you", "welcome",
                           "perfect", "nice", "good to"]),
    ("amused", "shrug", 0.5, ["haha", "lol", "funny", "joke", ":)", "fair enough"]),
)


def derive_state(text: str, *, speaking: bool = False, topic: Optional[str] = None) -> Dict[str, Any]:
    """Derive avatar STATE directives from a reply. Deterministic + cheap. `speaking` is supplied
    by the voice pipeline (Phase 5); until then it is False."""
    t = (text or "").strip()
    low = t.lower()
    emotion, gesture, intensity = "neutral", "idle", 0.4

    for emo, gst, base, kws in _CUES:
        if any(kw in low for kw in kws):
            emotion, gesture, intensity = emo, gst, base
            break
    else:
        # no keyword cue: questions read as "thinking", otherwise neutral
        if t.endswith("?") or re.search(r"\?\s*$", t) or " ? " in t:
            emotion, gesture, intensity = "thinking", "tilt_head", 0.5

    # exclamation amplifies whatever we have (and nudges neutral -> excited)
    excl = t.count("!")
    if excl:
        if emotion in ("neutral", "happy"):
            emotion, gesture = ("excited", "nod")
        intensity = min(1.0, intensity + 0.15 * excl)

    return {
        "emotion": emotion,
        "intensity": round(float(intensity), 2),
        "gesture": gesture,
        "speaking": bool(speaking),
        "viseme": "aa" if speaking else "sil",
    }
