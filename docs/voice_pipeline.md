# Project_Persona -- Voice Pipeline (Phase 5, optional)

Status: SCAFFOLDED 2026-06-20 (daemon wiring). The engines are host-provided compute; this repo
only supervises them as children when present. Keep ASCII (see `WORKFLOW.md`).

## 1. Goal

Local, fully-offline speech in/out as supervised daemon children:

  microphone --> Whisper.cpp STT --> /chat (persona) --> Piper TTS --> speaker

No cloud, host-side compute only. STT + TTS run as HTTP servers the API/client calls; the daemon
supervises them with the same three-strike policy as llama-server (daemon.py).

## 2. What is wired (this repo)

`daemon.py` gains guarded child specs, opt-in via `daemon.py --with-voice` or
`VOICE_DAEMON_ENABLED=1`:

- `whisper_stt_spec(root)` -> `whisper-stt` child: `whisper-server --model <m> --host 127.0.0.1
  --port 8120`. Built only when `stt_present(root)` (binary + model exist).
- `piper_tts_spec(root)` -> `piper-tts` child: `piper --model <voice.onnx> --http --port 8121`.
  Built only when `tts_present(root)`.

All paths are env-overridable: `WHISPER_SERVER_BIN`, `WHISPER_MODEL`, `WHISPER_PORT`,
`PIPER_BIN`, `PIPER_MODEL`, `PIPER_PORT`. If a binary/model is missing the spec is `None` and the
daemon logs "engine not found; skipping" -- so `--with-voice` is safe on a box without the engines.

## 3. What is host-provided (not in this repo)

- Whisper.cpp: build `whisper-server` (it lives alongside the llama.cpp build) + fetch a ggml model
  (e.g. `ggml-base.en.bin`) into `models/`.
- Piper (GPL-3.0): the `piper` binary + an ONNX voice into `models/`. Used as a SEPARATE PROCESS
  (HTTP), never linked, to respect GPL-3.0 (see knowledge.md licensing).
- Audio I/O (mic capture / speaker playback): the client/host -- headless WSL has no audio device,
  so end-to-end audio is validated on a host with sound (or EVO-X2).

The exact server flags are pinned when the engine is installed; the argv above is the conventional
shape and the seam the daemon supervises.

## 4. Integration with the rest of the stack

- The `tts_speaking` EventBus event (Phase 3 vocabulary) is published while Piper is emitting audio,
  which drives the Phase 4 avatar STATE `speaking`/`viseme` channel (docs/avatar_protocol.md) so the
  mouth animates in sync.
- A future `/speak` API endpoint (TTS synth to WAV) and a `/listen` (STT) are the natural thin
  wrappers over the two servers once they are installed on a host with audio.

## 5. Exit Gate

Spoken input is transcribed, answered, and spoken back end-to-end, fully offline -- exercised on a
host with the engines + an audio device (the daemon-child wiring + guarded specs are done here).
