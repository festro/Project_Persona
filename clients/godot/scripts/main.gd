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
var speak_chk: CheckBox
var reply_lbl: Label
var state_lbl: Label

const PANEL_H: float = 196.0


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

	reply_lbl = Label.new()
	reply_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	reply_lbl.custom_minimum_size = Vector2(0, 78)
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
	if speak_chk.button_pressed:
		_speak_aloud(text)


func _on_failed(message: String) -> void:
	send_btn.disabled = false
	_set_status("error: " + message)


func _set_status(msg: String) -> void:
	if state_lbl != null:
		state_lbl.text = msg


## Scripted exchange -> wait for the reply -> let the avatar animate -> save a PNG of
## the viewport -> quit. Capture happens mid-animation so the saved frame shows the
## emotion color + an open (speaking) mouth.
func _run_demo() -> void:
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
	await get_tree().create_timer(0.4).timeout
	get_tree().quit()


func _speak_seconds(text: String) -> float:
	var words: int = text.split(" ", false).size()
	return clampf(float(words) * 0.34 + 0.6, 0.8, 14.0)


## Optional: fire the local Piper voice client to speak the reply aloud. Best-effort
## and non-blocking; the mouth animation above runs on the word-count estimate, so a
## visual demo works even without audio. Phase 5's tts_speaking will tighten this.
func _speak_aloud(text: String) -> void:
	var base: String = ProjectSettings.globalize_path("res://")  # .../clients/godot/
	var py: String = base.path_join("../../portable/python/python.exe").simplify_path()
	var script: String = base.path_join("../voice/persona_voice.py").simplify_path()
	if not FileAccess.file_exists(py):
		py = "python"  # fall back to PATH
	if not FileAccess.file_exists(script):
		_set_status("voice client not found at " + script)
		return
	OS.create_process(py, [script, "say", text])
