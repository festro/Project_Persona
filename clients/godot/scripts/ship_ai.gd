extends Node
## The persona as a classic OMNIPRESENT SHIP'S COMPUTER -- a disembodied voice + a HUD
## presence, standing in until the embodied 3D avatar is built. Press T to talk: your
## speech is transcribed (Whisper, via clients/voice/persona_voice.py off the main
## thread), sent to the persona API (/chat), and the reply is spoken aloud (Piper) and
## shown as a subtitle. A small status orb pulses through idle / listening / thinking /
## speaking so the ship always feels "present".
##
## Voice I/O needs the host engines (clients/install.ps1: Whisper + Piper). If they are
## missing the ship still answers in text (subtitle), just silently -- and the status
## line says so.

const PersonaClientScript := preload("res://scripts/persona_client.gd")

const STATE_COLORS := {
	"idle":      Color(0.35, 0.62, 0.85),
	"listening": Color(0.35, 1.00, 0.55),
	"thinking":  Color(1.00, 0.72, 0.25),
	"speaking":  Color(0.40, 0.90, 1.00),
	"error":     Color(1.00, 0.45, 0.40),
}
const PULSE_SPEED := {"idle": 1.6, "listening": 4.5, "thinking": 6.5, "speaking": 8.5, "error": 3.0}

var _rig: Node
var _client: Node
var _orb: Label
var _status: Label
var _subtitle: RichTextLabel

var _state: String = "idle"
var _t: float = 0.0
var _busy: bool = false
var _rec_thread: Thread = null
var _speak_until: float = 0.0


func setup(rig: Node) -> void:
	_rig = rig


func _ready() -> void:
	_client = PersonaClientScript.new()
	add_child(_client)
	_client.reply.connect(_on_reply)
	_client.failed.connect(_on_failed)
	_build_hud()
	_set_state("idle")
	var voice: String = "voice ready" if not _voice_py().is_empty() else "text-only (no voice engines)"
	_say_subtitle("[i]Ship AI online. Press T to speak with me.[/i]")
	_status.text = "online  -  %s  -  %s" % [_client.api_base, voice]
	set_process(true)


func _build_hud() -> void:
	var layer := CanvasLayer.new()
	layer.name = "ShipAIHUD"
	add_child(layer)

	var top := HBoxContainer.new()
	top.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	top.offset_top = 12
	top.alignment = BoxContainer.ALIGNMENT_CENTER
	top.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(top)

	_orb = Label.new()
	_orb.text = "●"
	_orb.add_theme_font_size_override("font_size", 30)
	_orb.mouse_filter = Control.MOUSE_FILTER_IGNORE
	top.add_child(_orb)

	var name_lbl := Label.new()
	name_lbl.text = "  SHIP AI"
	name_lbl.add_theme_font_size_override("font_size", 22)
	name_lbl.add_theme_color_override("font_color", Color(0.75, 0.88, 1.0))
	name_lbl.add_theme_constant_override("outline_size", 4)
	name_lbl.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
	name_lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	top.add_child(name_lbl)

	_status = Label.new()
	_status.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	_status.offset_top = 50
	_status.add_theme_font_size_override("font_size", 15)
	_status.add_theme_color_override("font_color", Color(0.6, 0.75, 0.9, 0.8))
	_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_status.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(_status)

	_subtitle = RichTextLabel.new()
	_subtitle.bbcode_enabled = true
	_subtitle.fit_content = true
	_subtitle.scroll_active = false
	_subtitle.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	_subtitle.offset_left = 180
	_subtitle.offset_right = -180
	_subtitle.offset_top = -150
	_subtitle.offset_bottom = -64
	_subtitle.add_theme_font_size_override("normal_font_size", 24)
	_subtitle.add_theme_color_override("default_color", Color(0.92, 0.97, 1.0))
	_subtitle.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(_subtitle)


func _process(delta: float) -> void:
	_t += delta
	var spd: float = PULSE_SPEED.get(_state, 2.0)
	_orb.modulate.a = 0.45 + 0.55 * absf(sin(_t * spd))
	if _state == "speaking" and _t >= _speak_until:
		_set_state("idle")
		_status.text = "online"


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_T:
		# ignore when a console panel is focused (T is being typed into it)
		if _rig != null and _rig.has_method("is_movement_enabled") and not _rig.is_movement_enabled():
			return
		_start_talk()


# --- voice turn ------------------------------------------------------------
func _start_talk() -> void:
	if _busy or (_rec_thread != null and _rec_thread.is_alive()):
		return
	if _voice_py().is_empty():
		_status.text = "no voice engines -- run clients\\install.ps1 (text mode only)"
		return
	_busy = true
	_set_state("listening")
	_status.text = "listening...  speak, then pause"
	_say_subtitle("")
	_rec_thread = Thread.new()
	_rec_thread.start(_talk_worker)


func _talk_worker() -> void:
	var text: String = ""
	var v: Array = _voice_py()
	if not v.is_empty():
		var out: Array = []
		OS.execute(v[0], [v[1], "record-text", "--seconds", "15"], out, false)
		if out.size() > 0:
			text = String(out[0]).strip_edges()
	call_deferred("_on_transcript", text)


func _on_transcript(text: String) -> void:
	if _rec_thread != null:
		_rec_thread.wait_to_finish()
		_rec_thread = null
	if text == "":
		_busy = false
		_set_state("idle")
		_status.text = "online  -  (no speech heard; press T to retry)"
		return
	_say_subtitle("[color=#8fd0ff]you:[/color] " + text)
	_set_state("thinking")
	_status.text = "thinking..."
	_client.ask(text)


func _on_reply(text: String, _state: Dictionary, _cid: String) -> void:
	_busy = false
	var clean: String = text.strip_edges()
	_say_subtitle(clean)
	_set_state("speaking")
	_speak_until = _t + _speak_seconds(clean)
	_status.text = "speaking..."
	_speak_aloud(clean)


func _on_failed(message: String) -> void:
	_busy = false
	_set_state("error")
	_status.text = "error: " + message


func _set_state(s: String) -> void:
	_state = s
	_orb.add_theme_color_override("font_color", STATE_COLORS.get(s, STATE_COLORS["idle"]))


func _say_subtitle(text: String) -> void:
	_subtitle.text = text


func _speak_seconds(text: String) -> float:
	return clampf(float(text.split(" ", false).size()) * 0.34 + 0.6, 0.8, 16.0)


# --- local voice client (Whisper STT in, Piper TTS out) --------------------
## Resolve [python_exe, persona_voice.py] for the local voice client, or [] if missing.
func _voice_py() -> Array:
	var base: String = ProjectSettings.globalize_path("res://")          # .../clients/godot/
	var py: String = base.path_join("../../portable/python/python.exe").simplify_path()
	var script: String = base.path_join("../voice/persona_voice.py").simplify_path()
	if not FileAccess.file_exists(py):
		py = "python"
	if not FileAccess.file_exists(script):
		return []
	return [py, script]


## Speak the reply aloud via the local Piper voice client (best-effort, non-blocking).
func _speak_aloud(text: String) -> void:
	var v: Array = _voice_py()
	if not v.is_empty():
		OS.create_process(v[0], [v[1], "say", text])
