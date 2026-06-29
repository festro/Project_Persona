extends Control
## Wires the UI to the PersonaClient + AvatarFace. Type a line (or use the
## suggestion buttons), POST it to the EVO-X2 /chat endpoint, then animate the
## avatar from the returned STATE and (optionally) speak the reply via the local
## Piper voice client. Proves the Phase 4 Exit Gate: avatar reflects STATE in
## sync with the RESPONSE for a scripted exchange.

# Preloaded explicitly (not referenced by class_name) so main.gd never depends on
# the global class registry being populated -- that cache is only written on a full
# editor import, and a fresh `-s`/run-scene launch can parse this before it exists.
const AvatarFaceScript := preload("res://scripts/avatar.gd")
const PersonaClientScript := preload("res://scripts/persona_client.gd")

var client: Node          # PersonaClientScript instance (dynamic access, no class_name dep)
var avatar: Node2D        # AvatarFaceScript instance

var input: LineEdit
var send_btn: Button
var talk_btn: Button
var speak_chk: CheckBox
var reply_lbl: RichTextLabel
var state_lbl: Label
var _rec_thread: Thread = null
var _voice_turn: bool = false           # set for mic-initiated turns -> always speak the reply

const PANEL_H: float = 280.0


func _ready() -> void:
	avatar = AvatarFaceScript.new()
	add_child(avatar)

	client = PersonaClientScript.new()
	add_child(client)
	client.reply.connect(_on_reply)
	client.failed.connect(_on_failed)

	_build_ui()
	resized.connect(_layout)
	_layout.call_deferred()  # deferred: the window size is not applied until after _ready
	_set_status("Connected to " + client.api_base + " -- type a message and press Enter")

	# One-shot self-demo: scripted exchange + viewport screenshot, then quit. Lets a
	# headless-less host capture proof of the STATE-driven face without screen control.
	if OS.get_environment("PERSONA_AVATAR_DEMO") == "1":
		_run_demo()


func _build_ui() -> void:
	var panel: PanelContainer = PanelContainer.new()
	panel.name = "Panel"
	panel.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	panel.offset_top = -PANEL_H
	add_child(panel)

	var vbox: VBoxContainer = VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 8)
	panel.add_child(vbox)

	reply_lbl = RichTextLabel.new()
	reply_lbl.bbcode_enabled = false
	reply_lbl.scroll_active = true                      # long replies scroll, not push controls off-screen
	reply_lbl.size_flags_vertical = Control.SIZE_EXPAND_FILL
	reply_lbl.text = "..."
	vbox.add_child(reply_lbl)

	state_lbl = Label.new()
	state_lbl.add_theme_color_override("font_color", Color(0.6, 0.7, 0.85))
	vbox.add_child(state_lbl)

	# scripted-exchange suggestion buttons (each exercises a different emotion/gesture)
	var chips: HBoxContainer = HBoxContainer.new()
	chips.add_theme_constant_override("separation", 6)
	vbox.add_child(chips)
	for prompt in ["Greet me warmly!", "I got an error in my code.",
			"Tell me a fun fact.", "What is 17 times 23?"]:
		var b: Button = Button.new()
		b.text = prompt
		b.pressed.connect(_send.bind(prompt))
		chips.add_child(b)

	var row: HBoxContainer = HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	vbox.add_child(row)

	input = LineEdit.new()
	input.placeholder_text = "Say something to the persona..."
	input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	input.text_submitted.connect(_on_submit)
	row.add_child(input)

	send_btn = Button.new()
	send_btn.text = "Send"
	send_btn.pressed.connect(_on_send_pressed)
	row.add_child(send_btn)

	talk_btn = Button.new()
	talk_btn.text = "Talk (mic)"
	talk_btn.tooltip_text = "Speak one message; a pause ends your turn (Whisper STT)"
	talk_btn.pressed.connect(_on_talk_pressed)
	row.add_child(talk_btn)

	speak_chk = CheckBox.new()
	speak_chk.text = "Speak (Piper)"
	speak_chk.tooltip_text = "Also synthesize the reply aloud via the local voice client"
	row.add_child(speak_chk)


func _layout() -> void:
	var vp: Vector2 = get_viewport_rect().size  # actual window size (Control.size lags at _ready)
	avatar.set_anchor(Vector2(vp.x * 0.5, (vp.y - PANEL_H) * 0.5 + 28.0))


func _on_submit(text: String) -> void:
	_send(text)


func _on_send_pressed() -> void:
	_send(input.text)


func _send(text: String) -> void:
	text = text.strip_edges()
	if text == "" or client.busy:
		return
	input.text = ""
	reply_lbl.text = "..."
	_set_status("thinking...")
	send_btn.disabled = true
	client.ask(text)


func _on_reply(text: String, state: Dictionary, _cid: String) -> void:
	send_btn.disabled = false
	reply_lbl.text = text.strip_edges()
	state_lbl.text = "STATE  emotion=%s  intensity=%.2f  gesture=%s  speaking=%s  viseme=%s" % [
		state.get("emotion", "?"), float(state.get("intensity", 0.0)),
		state.get("gesture", "?"), str(state.get("speaking", false)),
		state.get("viseme", "?")]
	avatar.apply_state(state)
	var secs: float = _speak_seconds(text)
	avatar.speak_for(secs)
	# Voice-in -> voice-out: a mic turn always speaks; typed turns speak only if Speak is ticked.
	if speak_chk.button_pressed or _voice_turn:
		_speak_aloud(text)
	_voice_turn = false


func _on_failed(message: String) -> void:
	send_btn.disabled = false
	_voice_turn = false
	_set_status("error: " + message)


func _set_status(msg: String) -> void:
	if state_lbl != null:
		state_lbl.text = msg


## Scripted exchange -> wait for the reply -> let the avatar animate -> save a PNG of
## the viewport -> quit. Capture happens mid-animation so the saved frame shows the
## emotion color + an open (speaking) mouth.
func _run_demo() -> void:
	var speak: bool = OS.get_environment("PERSONA_AVATAR_SPEAK") == "1"
	if speak:
		speak_chk.button_pressed = true  # _on_reply will then fire _speak_aloud()
	await get_tree().create_timer(0.8).timeout
	_send("Greet me warmly and tell me you are excited to meet me!")
	await client.reply  # (text, state, cid) -- _on_reply also runs and animates
	await get_tree().create_timer(0.7).timeout
	await RenderingServer.frame_post_draw
	var img: Image = get_viewport().get_texture().get_image()
	var path: String = OS.get_environment("PERSONA_AVATAR_SHOT")
	if path == "":
		path = ProjectSettings.globalize_path("user://avatar_demo.png")
	var err: int = img.save_png(path)
	print("[demo] screenshot %s -> %s" % ["OK" if err == OK else "ERR %d" % err, path])
	# When speaking, hold the window open so the detached Piper process has time to
	# synthesize + start playing (it survives quit, but this lets the audio begin).
	await get_tree().create_timer(6.0 if speak else 0.4).timeout
	get_tree().quit()


func _speak_seconds(text: String) -> float:
	var words: int = text.split(" ", false).size()
	return clampf(float(words) * 0.34 + 0.6, 0.8, 14.0)


## Resolve [python_exe, persona_voice.py] for the local voice client, or [] if missing.
func _voice_py() -> Array:
	var base: String = ProjectSettings.globalize_path("res://")  # .../clients/godot/
	var py: String = base.path_join("../../portable/python/python.exe").simplify_path()
	var script: String = base.path_join("../voice/persona_voice.py").simplify_path()
	if not FileAccess.file_exists(py):
		py = "python"  # fall back to PATH
	if not FileAccess.file_exists(script):
		return []
	return [py, script]


## Optional: fire the local Piper voice client to speak the reply aloud. Best-effort,
## non-blocking; the mouth animation runs on the word-count estimate, so a visual demo
## works even without audio. Phase 5's tts_speaking will tighten this.
func _speak_aloud(text: String) -> void:
	var v: Array = _voice_py()
	if v.is_empty():
		_set_status("voice client not found")
		return
	OS.create_process(v[0], [v[1], "say", text])


## Voice INPUT: record one spoken utterance off the main thread (so the UI stays
## responsive), transcribe it with the local Whisper client, then send it like a typed
## message -- the avatar animates from STATE and (if Speak is ticked) replies aloud.
func _on_talk_pressed() -> void:
	if client.busy or (_rec_thread != null and _rec_thread.is_alive()):
		return
	if _voice_py().is_empty():
		_set_status("voice client not found -- run clients\\install.ps1")
		return
	talk_btn.disabled = true
	send_btn.disabled = true
	_set_status("listening... speak now, then pause")
	_rec_thread = Thread.new()
	_rec_thread.start(_talk_worker)


func _talk_worker() -> void:
	var text: String = ""
	var v: Array = _voice_py()
	if not v.is_empty():
		var out: Array = []
		# record-text: VAD-records one utterance and prints ONLY the transcript to stdout
		OS.execute(v[0], [v[1], "record-text", "--seconds", "15"], out, false)
		if out.size() > 0:
			text = String(out[0]).strip_edges()
	call_deferred("_on_transcript", text)


func _on_transcript(text: String) -> void:
	if _rec_thread != null:
		_rec_thread.wait_to_finish()
		_rec_thread = null
	talk_btn.disabled = false
	send_btn.disabled = false
	if text == "":
		_set_status("(no speech heard -- click Talk and try again)")
		return
	_voice_turn = true        # spoke to it -> speak the reply back
	_send(text)
