# Project_Persona -- Clients (voice + avatar)

Host-side clients that give the persona a **voice** (Phase 5) and an **embodied
face** (Phase 4). They run on a desktop with a display + audio device and talk to
the persona API over HTTP.

## Topology (chosen 2026-06-29)

This Windows box is a **client**. The 35B model and the persona API live on the
**EVO-X2 anchor node**; the engines + mic/speaker + avatar run here, next to the
hardware that needs them, and call the API over the LAN.

```
  Windows desktop (this box)                         EVO-X2 anchor (LAN)
  -------------------------                          -------------------
  [mic] -> Whisper.cpp STT --text-->  POST /chat  -->  persona API + Qwen3.6-35B
                                      <--text+STATE--
  reply text -> Piper TTS --wav--> [speaker]
  STATE ----------------------> Godot avatar (emotion / gesture / mouth)
```

Default API target: `http://192.168.8.114:8000` (override with `PERSONA_API`).
Federated noding (Phases 9-10) will relocate pieces; the HTTP seams above do not
change -- the client only ever speaks `/chat`.

## Install

```powershell
clients\install.ps1          # fetch engines + models + Godot, then run the selftest
clients\install.ps1 -Force   # refetch everything
```

Pinned, idempotent. Lays down (all **gitignored** -- host-provided, not committed):

| Component | License | Path |
|---|---|---|
| Whisper.cpp v1.9.1 (STT) | MIT | `tools\whisper\Release\whisper-cli.exe` |
| Piper 2023.11.14 (TTS) | GPL-3.0 | `tools\piper\piper\piper.exe` |
| Godot 4.7 (avatar) | MIT | `tools\godot\Godot_v4.7-stable_win64.exe` |
| ggml-base.en (STT model) | MIT | `models\ggml-base.en.bin` |
| en_US-lessac-medium (TTS voice) | MIT | `models\en_US-lessac-medium.onnx` |

**Piper is GPL-3.0** and is used only as a **separate process** (subprocess /
stdin->wav), never linked or imported -- so it does not propagate its license into
this AGPL repo. Same boundary as the daemon's `--with-voice` wiring.

## Voice client (Phase 5)

`voice\persona_voice.py` -- stdlib-only core (urllib + wave + subprocess +
winsound); only the live-mic verbs need `sounddevice`.

```powershell
clients\voice\run_voice.ps1 selftest                 # headless end-to-end proof (no mic)
clients\voice\run_voice.ps1 say "Hello there"        # TTS only -> speaker
clients\voice\run_voice.ps1 transcribe .\clip.wav    # STT only
clients\voice\run_voice.ps1 ask "What is 2+2?"       # chat only (prints text + STATE)
clients\voice\run_voice.ps1 turn .\speech.wav        # STT -> chat -> TTS -> speaker
clients\voice\run_voice.ps1 listen                   # mic -> turn; auto-stops on a pause (VAD)
clients\voice\run_voice.ps1 listen --fixed --seconds 5  # fixed-window capture instead of VAD
clients\voice\run_voice.ps1 converse                 # spoken conversation; pauses end each turn
clients\voice\run_voice.ps1 converse --brief         # short 1-2 sentence spoken replies
```

TTS strips Markdown before speaking, so `*`, `#`, backticks, and list markers are never read aloud.
Replies are **full/detailed by default**; add `--brief` (on ask/turn/listen/converse) for short
1-2 sentence spoken answers.

`listen`/`converse` auto-stop on a pause (VAD-lite: calibrates the room noise floor, starts on
speech, ends after ~1s of silence, capped by `--seconds`). Live mic capture needs `sounddevice`
(installed on this box 2026-06-29; on a fresh host):

```powershell
portable\python\python.exe -m pip install sounddevice numpy
```

`selftest` is the reproducible end-to-end check: it synthesizes a prompt (Piper),
transcribes it back (Whisper), round-trips the transcript through the persona API,
and speaks the reply -- proving the whole loop without a microphone.

## Avatar client (Phase 4)

`godot/` -- a Godot 4.7 project. A minimal procedural face animates against the
inline `state` field returned by `/chat` (`docs/avatar_protocol.md`): emotion
drives color + mouth curve + eye shape, intensity drives strength, gesture fires a
one-shot cue (nod / shrug / tilt_head / lean_in / ...), and the mouth animates while
the reply is "spoken". Tick **Speak (Piper)** to also hear a *typed* reply via the
voice client.

Click **Talk (mic)** to speak *to* the avatar: it records one utterance off the main
thread (Whisper VAD, via the voice client's `record-text` verb), shows the transcript,
then answers and speaks the reply aloud -- a mic turn is always voice-in -> voice-out.

```powershell
clients\godot\run_avatar.ps1            # run the avatar app
clients\godot\run_avatar.ps1 -Editor    # open the project in the Godot editor
```

Headless smoke test (no display; verifies the HTTP + STATE-parse path):

```powershell
tools\godot\Godot_v4.7-stable_win64_console.exe --headless --path clients\godot -s res://tools/headless_check.gd
```

On-screen self-demo (runs a scripted `/chat` exchange, animates from STATE, saves a
viewport screenshot, then quits -- the reusable proof path):

```powershell
$env:PERSONA_AVATAR_DEMO=1; $env:PERSONA_AVATAR_SHOT="$PWD\avatar_demo.png"
clients\godot\run_avatar.ps1
```

The procedural face is intentionally simple; a rigged 3D blend-shape head is the
natural next step and consumes the **same** STATE contract unchanged.

## Configuration (env)

| Var | Default | Used by |
|---|---|---|
| `PERSONA_API` | `http://192.168.8.114:8000` | voice + avatar |
| `PERSONA_PROFILE` | `default` | voice + avatar |
| `WHISPER_BIN` / `WHISPER_MODEL` | `tools\whisper\...` / `models\ggml-base.en.bin` | voice |
| `PIPER_BIN` / `PIPER_MODEL` | `tools\piper\...` / `models\en_US-lessac-medium.onnx` | voice |

## Status

- Phase 5 voice: end-to-end **PROVEN** on this box (selftest: STT 0.8s / chat 2.3s /
  TTS sub-second). Live mic/speaker is `sounddevice` + `winsound` away.
- Phase 4 avatar: client **PROVEN** headlessly (HTTP + STATE parse); on-screen
  animation runs when launched with a display.
