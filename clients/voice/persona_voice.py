#!/usr/bin/env python3
"""Project_Persona -- Windows voice client (Phase 5).

Topology (chosen 2026-06-29): this box is a CLIENT. The persona API (and the 35B
model) live on the EVO-X2 anchor node; voice I/O + the engines run here, next to
the mic/speaker, and talk to the API over the LAN. Federated noding may relocate
pieces later; the HTTP seams below do not change.

Pipeline:
    [mic / wav] --> Whisper.cpp STT --> POST {API}/chat --> reply text + STATE
                                                |
                         reply text --> Piper TTS --> wav --> [speaker]

Engines are host-provided, separate processes (Piper is GPL-3.0 -> never linked,
only invoked as a subprocess). Paths are env-overridable; defaults point at the
in-repo tools/ install laid down by install_voice.ps1.

Dependency posture: the core verbs (say / transcribe / ask / turn / selftest) use
only the Python stdlib (urllib, wave, subprocess, winsound). Live-mic verbs
(listen / converse) additionally need `sounddevice` (pip install sounddevice).

Usage:
    python persona_voice.py selftest            # headless end-to-end proof (no mic)
    python persona_voice.py say "Hello there"   # TTS only
    python persona_voice.py transcribe a.wav    # STT only
    python persona_voice.py ask "What is 2+2?"  # chat only (prints text + STATE)
    python persona_voice.py turn speech.wav     # STT -> chat -> TTS -> speaker
    python persona_voice.py listen              # mic -> turn (needs sounddevice)
    python persona_voice.py converse            # continuous mic loop (needs sounddevice)
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # clients/voice/ -> repo root
SCRATCH = Path(os.getenv("TEMP", str(ROOT))) / "persona_voice"
SCRATCH.mkdir(parents=True, exist_ok=True)

API = os.getenv("PERSONA_API", "http://192.168.8.114:8000").rstrip("/")
PROFILE = os.getenv("PERSONA_PROFILE", "default")

# Appended to the user's text in voice/brief mode so the persona replies in short
# spoken prose. The persona honors explicit brevity requests (its server-side default
# is "thorough"), so this keeps a voice turn from becoming a minute-long essay.
BRIEF_SUFFIX = (" [Voice mode: reply in 1 to 2 short sentences of plain spoken prose"
                " -- no markdown, no lists, no headings.]")


def _first_existing(env, *candidates):
    v = os.getenv(env)
    if v:
        return Path(v)
    for c in candidates:
        p = Path(c)
        if p.is_file():
            return p
    return Path(candidates[0])  # report the canonical default even if absent


WHISPER_BIN = _first_existing(
    "WHISPER_BIN",
    ROOT / "tools" / "whisper" / "Release" / "whisper-cli.exe",
    ROOT / "tools" / "whisper" / "whisper-cli.exe",
    ROOT / "tools" / "whisper" / "main.exe",
)
WHISPER_MODEL = _first_existing("WHISPER_MODEL", ROOT / "models" / "ggml-base.en.bin")
PIPER_BIN = _first_existing(
    "PIPER_BIN",
    ROOT / "tools" / "piper" / "piper" / "piper.exe",
    ROOT / "tools" / "piper" / "piper.exe",
)
PIPER_MODEL = _first_existing("PIPER_MODEL", ROOT / "models" / "en_US-lessac-medium.onnx")


# --------------------------------------------------------------------------
# Engines (subprocess) + API (stdlib http)
# --------------------------------------------------------------------------
def stt(wav_path):
    """Transcribe a WAV/MP3/OGG/FLAC file to text via whisper-cli. whisper.cpp's
    decoder resamples to 16 kHz internally, so any sample rate is accepted."""
    if not Path(WHISPER_BIN).is_file():
        raise FileNotFoundError(f"whisper binary not found: {WHISPER_BIN} (run install_voice.ps1)")
    cmd = [str(WHISPER_BIN), "-m", str(WHISPER_MODEL), "-f", str(wav_path),
           "-nt", "-np", "-l", "en"]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                         errors="replace")
    if out.returncode != 0:
        raise RuntimeError(f"whisper failed ({out.returncode}): {out.stderr.strip()[:300]}")
    lines = []
    for ln in out.stdout.splitlines():
        s = ln.strip()
        if not s or s.startswith("[") or s.startswith("whisper_") \
                or "load_backend" in s or s.startswith("ggml_"):
            continue
        lines.append(s)
    return " ".join(lines).strip()


# Markdown -> speech normalizer (Piper would otherwise read '*', '#', backticks aloud)
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_RULE = re.compile(r"(?m)^\s*([-*_]\s*){3,}$")
_MD_HEADING = re.compile(r"(?m)^\s{0,3}#{1,6}\s*")
_MD_QUOTE = re.compile(r"(?m)^\s*>\s?")
_MD_BULLET = re.compile(r"(?m)^\s*[\*\-\+]\s+")
_MD_NUMBERED = re.compile(r"(?m)^\s*\d+[.)]\s+")
_MD_EMPH = re.compile(r"(\*\*|\*|__|_|~~|`)")
_WS_SPACES = re.compile(r"[ \t]{2,}")
_WS_NL = re.compile(r"\n{2,}")


def clean_for_speech(text):
    """Strip Markdown so the TTS engine speaks the words, not '*', '#', or backticks."""
    t = (text or "").replace("```", " ")
    t = _MD_LINK.sub(r"\1", t)       # [label](url) -> label
    t = _MD_RULE.sub("", t)          # --- *** ___ horizontal rules
    t = _MD_HEADING.sub("", t)       # ## Heading -> Heading
    t = _MD_QUOTE.sub("", t)         # > blockquote
    t = _MD_BULLET.sub("", t)        # "* item" / "- item" -> "item"
    t = _MD_NUMBERED.sub("", t)      # "1. item" -> "item"
    t = _MD_EMPH.sub("", t)          # ** * __ _ ~~ ` emphasis markers
    t = _WS_SPACES.sub(" ", t)
    t = _WS_NL.sub("\n", t)
    return t.strip()


def tts(text, out_wav=None):
    """Synthesize text to a WAV with Piper (separate process; text on stdin).
    Markdown is stripped first so symbols are not read aloud."""
    if not Path(PIPER_BIN).is_file():
        raise FileNotFoundError(f"piper binary not found: {PIPER_BIN} (run install_voice.ps1)")
    out_wav = Path(out_wav) if out_wav else (SCRATCH / "tts_out.wav")
    speech = clean_for_speech(text) or text
    cmd = [str(PIPER_BIN), "-m", str(PIPER_MODEL), "-f", str(out_wav)]
    proc = subprocess.run(cmd, input=speech.encode("utf-8"),
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if proc.returncode != 0 or not out_wav.is_file():
        raise RuntimeError(f"piper failed ({proc.returncode}): {proc.stderr.decode('utf-8','replace')[:300]}")
    return out_wav


def chat(text, conversation_id=None, profile=PROFILE, timeout=120):
    """POST {API}/chat -> dict with text + state + conversation_id (Phase 4 STATE)."""
    payload = {"text": text, "profile": profile}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    req = urllib.request.Request(
        f"{API}/chat", data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def wav_seconds(path):
    try:
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except Exception:
        return 0.0


def play(wav_path):
    """Blocking playback (blocks for the TTS duration -> natural mouth-gate)."""
    if sys.platform.startswith("win"):
        import winsound
        winsound.PlaySound(str(wav_path), winsound.SND_FILENAME)
        return True
    for player in ("aplay", "afplay", "paplay"):
        try:
            subprocess.run([player, str(wav_path)], check=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    print(f"  (no audio player; wrote {wav_path})")
    return False


def _fmt_state(state):
    if not state:
        return "(no state)"
    return (f"emotion={state.get('emotion')} intensity={state.get('intensity')} "
            f"gesture={state.get('gesture')} speaking={state.get('speaking')} "
            f"viseme={state.get('viseme')}")


# --------------------------------------------------------------------------
# Verbs
# --------------------------------------------------------------------------
def cmd_say(args):
    out = tts(args.text, args.out)
    print(f"[tts] {wav_seconds(out):.1f}s -> {out}")
    if not args.no_play:
        play(out)


def cmd_transcribe(args):
    t0 = time.time()
    text = stt(args.wav)
    print(f"[stt {time.time()-t0:.1f}s] {text}")


def cmd_ask(args):
    t0 = time.time()
    query = args.text + BRIEF_SUFFIX if getattr(args, "brief", False) else args.text
    resp = chat(query, conversation_id=args.cid, profile=args.profile)
    print(f"[chat {time.time()-t0:.1f}s] {resp.get('text','').strip()}")
    print(f"[state] {_fmt_state(resp.get('state'))}")
    print(f"[cid] {resp.get('conversation_id')}")


def cmd_turn(args):
    """Full pipeline on a pre-recorded WAV: STT -> chat -> TTS -> speaker."""
    t0 = time.time()
    heard = stt(args.wav)
    t1 = time.time()
    print(f"[stt {t1-t0:.1f}s] heard: {heard!r}")
    if not heard:
        print("[turn] empty transcript; aborting")
        return 2
    query = heard + BRIEF_SUFFIX if getattr(args, "brief", False) else heard
    resp = chat(query, conversation_id=args.cid, profile=args.profile)
    t2 = time.time()
    reply = resp.get("text", "").strip()
    print(f"[chat {t2-t1:.1f}s] reply: {reply}")
    print(f"[state] {_fmt_state(resp.get('state'))}")
    out = tts(reply, args.out)
    print(f"[tts {time.time()-t2:.1f}s] {wav_seconds(out):.1f}s -> {out}")
    if not args.no_play:
        play(out)
    print(f"[turn] total {time.time()-t0:.1f}s  cid={resp.get('conversation_id')}")
    return 0


def cmd_selftest(args):
    """Headless end-to-end proof, no mic needed: synthesize a prompt, transcribe it
    back (proves STT+TTS), round-trip the transcript through the persona API
    (proves the LAN chat seam), then speak the reply (proves the full loop)."""
    prompt = args.prompt
    print(f"== selftest ==\nAPI={API} profile={PROFILE}")
    print(f"whisper={WHISPER_BIN}\npiper  ={PIPER_BIN}")
    ok = True

    print(f"\n[1/4] TTS synth prompt: {prompt!r}")
    spoken = tts(prompt, SCRATCH / "selftest_prompt.wav")
    print(f"      -> {spoken} ({wav_seconds(spoken):.1f}s)")

    print("\n[2/4] STT transcribe it back")
    t0 = time.time()
    heard = stt(spoken)
    print(f"      heard ({time.time()-t0:.1f}s): {heard!r}")
    if not heard:
        print("      FAIL: empty transcript"); ok = False

    print("\n[3/4] chat round-trip to persona API")
    try:
        t0 = time.time()
        resp = chat(heard or prompt, profile=PROFILE)
        reply = resp.get("text", "").strip()
        print(f"      reply ({time.time()-t0:.1f}s): {reply[:200]}")
        print(f"      STATE: {_fmt_state(resp.get('state'))}")
        if not reply:
            print("      FAIL: empty reply"); ok = False
    except Exception as e:
        print(f"      FAIL: API error: {e}"); ok = False; reply = ""

    print("\n[4/4] TTS synth the reply")
    if reply:
        out = tts(reply, SCRATCH / "selftest_reply.wav")
        print(f"      -> {out} ({wav_seconds(out):.1f}s)")
        if not args.no_play:
            play(out)
    else:
        print("      skipped (no reply)")

    print(f"\n== selftest {'PASS' if ok else 'FAIL'} ==")
    return 0 if ok else 1


def _record(seconds, out_wav):
    """Capture mono 16 kHz s16 from the default mic. Needs sounddevice."""
    try:
        import sounddevice as sd
    except ImportError:
        raise SystemExit("live mic needs sounddevice: pip install sounddevice")
    sr = 16000
    print(f"[mic] recording {seconds:.0f}s ...")
    audio = sd.rec(int(seconds * sr), samplerate=sr, channels=1, dtype="int16")
    sd.wait()
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(audio.tobytes())
    return out_wav


def _record_vad(max_seconds=15.0, silence_tail=1.0, start_timeout=8.0, out_wav=None):
    """Record from the default mic until ~silence_tail s of quiet follow speech (natural
    turn end), capped at max_seconds. Calibrates a noise floor from the first blocks so it
    adapts to the room. Returns (wav_path, spoke). Needs sounddevice + numpy."""
    try:
        import sounddevice as sd
        import numpy as np
    except ImportError:
        raise SystemExit("live mic needs sounddevice + numpy: pip install sounddevice numpy")
    sr = 16000
    block = int(0.03 * sr)  # 30 ms frames
    out_wav = Path(out_wav) if out_wav else (SCRATCH / "mic_in.wav")
    frames = []
    with sd.InputStream(samplerate=sr, channels=1, dtype="int16", blocksize=block) as stream:
        cal = [float(np.abs(stream.read(block)[0]).mean()) for _ in range(10)]  # ~0.3s
        floor = float(np.median(cal)) if cal else 50.0
        thresh = max(floor * 3.5, 120.0)
        print(f"[mic] listening (noise floor {floor:.0f}; speak now -- a pause ends your turn)...")
        speech = False
        silence = 0.0
        pre = 0.0
        elapsed = 0.0
        while True:
            b = stream.read(block)[0]
            frames.append(b.copy())
            amp = float(np.abs(b).mean())
            dt = block / sr
            elapsed += dt
            if amp > thresh:
                speech = True
                silence = 0.0
            elif speech:
                silence += dt
            else:
                pre += dt
            if speech and silence >= silence_tail:
                break
            if not speech and pre >= start_timeout:
                print(f"[mic] (no speech detected within {start_timeout:.0f}s)")
                break
            if elapsed >= max_seconds:
                break
        audio = np.concatenate(frames) if frames else np.zeros((0, 1), dtype="int16")
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(audio.tobytes())
    return out_wav, speech


def cmd_listen(args):
    if args.fixed:
        wav = _record(args.seconds, SCRATCH / "mic_in.wav")
    else:
        wav, spoke = _record_vad(max_seconds=args.seconds, out_wav=SCRATCH / "mic_in.wav")
        if not spoke:
            print("[listen] no speech detected; nothing sent")
            return 0
    a = argparse.Namespace(wav=str(wav), out=None, no_play=args.no_play,
                           cid=args.cid, profile=args.profile,
                           brief=getattr(args, "brief", False))
    return cmd_turn(a)


def cmd_converse(args):
    cid = args.cid
    print("[converse] speak; a pause ends each turn. Ctrl+C to stop.")
    try:
        while True:
            if args.fixed:
                wav = _record(args.seconds, SCRATCH / "mic_in.wav")
                spoke = True
            else:
                wav, spoke = _record_vad(max_seconds=args.seconds, out_wav=SCRATCH / "mic_in.wav")
            if not spoke:
                continue
            heard = stt(wav)
            print(f"\n> {heard!r}")
            if not heard:
                continue
            query = heard + BRIEF_SUFFIX if getattr(args, "brief", False) else heard
            resp = chat(query, conversation_id=cid, profile=args.profile)
            cid = resp.get("conversation_id", cid)
            reply = resp.get("text", "").strip()
            print(f"< {reply}\n  [state] {_fmt_state(resp.get('state'))}")
            play(tts(reply))
    except KeyboardInterrupt:
        print("\n[converse] stopped")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Project_Persona voice client (Windows -> EVO-X2 API)")
    p.add_argument("--profile", default=PROFILE, help="persona profile (default: %(default)s)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("say"); s.add_argument("text"); s.add_argument("--out")
    s.add_argument("--no-play", action="store_true"); s.set_defaults(fn=cmd_say)

    s = sub.add_parser("transcribe"); s.add_argument("wav"); s.set_defaults(fn=cmd_transcribe)

    s = sub.add_parser("ask"); s.add_argument("text"); s.add_argument("--cid")
    s.add_argument("--brief", action="store_true", help="ask for a short 1-2 sentence reply")
    s.set_defaults(fn=cmd_ask)

    s = sub.add_parser("turn"); s.add_argument("wav"); s.add_argument("--out")
    s.add_argument("--cid"); s.add_argument("--no-play", action="store_true")
    s.add_argument("--brief", action="store_true", help="ask for a short spoken reply")
    s.set_defaults(fn=cmd_turn)

    s = sub.add_parser("selftest")
    s.add_argument("--prompt", default="What is the capital of France? Answer in one short sentence.")
    s.add_argument("--no-play", action="store_true"); s.set_defaults(fn=cmd_selftest)

    s = sub.add_parser("listen"); s.add_argument("--seconds", type=float, default=15.0,
                                                 help="max capture seconds (VAD ends earlier on a pause)")
    s.add_argument("--fixed", action="store_true", help="record a fixed --seconds instead of VAD auto-stop")
    s.add_argument("--brief", action="store_true", help="short 1-2 sentence spoken reply (default: full)")
    s.add_argument("--cid"); s.add_argument("--no-play", action="store_true")
    s.set_defaults(fn=cmd_listen)

    s = sub.add_parser("converse"); s.add_argument("--seconds", type=float, default=15.0,
                                                   help="per-turn max capture seconds (VAD ends earlier on a pause)")
    s.add_argument("--fixed", action="store_true", help="record fixed --seconds per turn instead of VAD")
    s.add_argument("--brief", action="store_true", help="short 1-2 sentence spoken replies (default: full)")
    s.add_argument("--cid"); s.set_defaults(fn=cmd_converse)

    args = p.parse_args(argv)
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
