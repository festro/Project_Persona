# Project_Persona -- Avatar Protocol (Phase 4, two-channel embodiment)

Status: SCAFFOLDED 2026-06-20 (persona side). The Godot/VR client is the optional consumer.
Keep ASCII (see `WORKFLOW.md`).

## 1. The two channels

The persona answers on two parallel channels:

- RESPONSE -- the assistant text (and, with Phase 5, the spoken TTS audio of that text).
- STATE -- a small JSON of avatar directives the client animates against, in sync with
  RESPONSE. STATE is advisory: a text-only or audio-only client ignores it; an embodied
  client (Godot/VR) drives an avatar from it.

STATE is derived deterministically from the reply by `services/api/avatar_state.py`
(`derive_state`), so it is available with or without a client attached and needs no model call.

## 2. Transport

Today: `POST /chat` returns STATE inline as a `state` object alongside `text`:

```json
{
  "text": "Great, that worked perfectly.",
  "persona": true,
  "conversation_id": "owui-...",
  "state": {"emotion": "happy", "intensity": 0.6, "gesture": "nod",
            "speaking": false, "viseme": "sil"}
}
```

Gated by `AVATAR_STATE_ENABLED` (default on). The field is additive -- existing text clients
ignore it. `/health.avatar_state` advertises `{enabled, emotions, gestures}`.

A streaming STATE channel (SSE/WebSocket, frame-aligned to TTS visemes) is the natural Phase 5
upgrade once audio timing exists; the vocabulary below does not change.

## 3. STATE vocabulary (the client contract)

| field      | type        | values |
|------------|-------------|--------|
| emotion    | string      | neutral, happy, excited, thinking, concerned, confused, amused |
| intensity  | float 0..1  | strength of the emotion (drives blend-shape weight) |
| gesture    | string      | idle, nod, shrug, wave, point, tilt_head, lean_in (a one-shot body cue) |
| speaking   | bool        | is TTS audio currently playing (driven by Phase 5 `tts_speaking`; false until then) |
| viseme     | string      | coarse mouth shape: `sil` when not speaking, else `aa` (a viseme stream lands with Phase 5) |

The authoritative enum lists are `avatar_state.EMOTIONS` / `GESTURES` and are mirrored in
`/health`. A client should treat an unknown value as `neutral` / `idle`.

## 4. How STATE is derived (current heuristic)

`derive_state(text, speaking=False)` runs an ordered keyword-cue table (concerned -> confused ->
excited -> happy -> amused), falls back to `thinking` for questions and `neutral` otherwise, then
lets `!` amplify intensity (and nudge neutral/happy -> excited). It is intentionally simple and
deterministic; a model-scored affect pass can replace the heuristic later without changing the
wire format. The per-profile `.hermes.md` is the place to pin a profile-specific STATE style.

## 5. Godot client (optional, not in this repo)

The client: poll/stream `/chat`, speak RESPONSE (Phase 5 TTS), and on each reply set the avatar's
emotion blend-shape (weight = intensity), trigger the one-shot `gesture`, and gate the mouth on
`speaking`/`viseme`. Phase 4 Exit Gate: the avatar reflects STATE directives in sync with RESPONSE
for a scripted exchange -- exercised against this `/chat` `state` field.
