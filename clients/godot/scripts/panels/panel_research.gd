extends Control
## RESEARCH terminal panel (Stage B), mounted on a Panel3D in the command seat.
## Two modes via a toggle:
##   Persona -- POST <PERSONA_API>/chat {text} and show the reply (web-sourced
##              server-side by the researcher role). Same API the voice/avatar use.
##   Web     -- fetch a URL directly (HTTPRequest) and show the stripped readable text.
## Interact through scripts/screen_interactor.gd: click the field, type, Enter to send.

var _api: String = "http://192.168.8.114:8000"
var _persona_mode: bool = true
var _busy: bool = false

var _http: HTTPRequest
var _input: LineEdit
var _out: RichTextLabel
var _status: Label
var _persona_btn: Button
var _web_btn: Button


func _ready() -> void:
	var env: String = OS.get_environment("PERSONA_API")
	if env != "":
		_api = env.rstrip("/")
	_build()
	_http = HTTPRequest.new()
	add_child(_http)
	_http.request_completed.connect(_on_completed)
	_refresh_mode()


func _build() -> void:
	var bg := ColorRect.new()
	bg.color = Color(0.03, 0.06, 0.09)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	var col := VBoxContainer.new()
	col.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	col.offset_left = 22; col.offset_top = 18; col.offset_right = -22; col.offset_bottom = -18
	col.add_theme_constant_override("separation", 12)
	add_child(col)

	col.add_child(_title("RESEARCH TERMINAL", Color(0.45, 0.85, 1.0)))

	var modes := HBoxContainer.new()
	modes.add_theme_constant_override("separation", 10)
	col.add_child(modes)
	_persona_btn = _mode_button("Persona", true)
	_web_btn = _mode_button("Web", false)
	modes.add_child(_persona_btn)
	modes.add_child(_web_btn)

	_out = RichTextLabel.new()
	_out.bbcode_enabled = true
	_out.scroll_following = true
	_out.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_out.add_theme_font_size_override("normal_font_size", 22)
	_out.add_theme_color_override("default_color", Color(0.82, 0.92, 1.0))
	_out.text = "[i]Ask the persona, or switch to Web and paste a URL.[/i]"
	col.add_child(_out)

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	col.add_child(row)
	_input = LineEdit.new()
	_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_input.add_theme_font_size_override("font_size", 24)
	_input.text_submitted.connect(func(_t): _send())
	row.add_child(_input)
	var send := Button.new()
	send.text = "Send"
	send.add_theme_font_size_override("font_size", 24)
	send.pressed.connect(_send)
	row.add_child(send)

	_status = Label.new()
	_status.add_theme_font_size_override("font_size", 18)
	_status.add_theme_color_override("font_color", Color(0.5, 0.7, 0.9))
	col.add_child(_status)


func _title(text: String, c: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", 40)
	l.add_theme_color_override("font_color", c)
	return l


func _mode_button(text: String, persona: bool) -> Button:
	var b := Button.new()
	b.text = text
	b.toggle_mode = true
	b.add_theme_font_size_override("font_size", 22)
	b.pressed.connect(func():
		_persona_mode = persona
		_refresh_mode())
	return b


func _refresh_mode() -> void:
	_persona_btn.button_pressed = _persona_mode
	_web_btn.button_pressed = not _persona_mode
	if _persona_mode:
		_input.placeholder_text = "Ask the persona anything..."
		_status.text = "mode: Persona  ->  %s/chat" % _api
	else:
		_input.placeholder_text = "Paste a URL (https://...)"
		_status.text = "mode: Web  ->  direct fetch"


func _send() -> void:
	var text: String = _input.text.strip_edges()
	if text == "" or _busy:
		return
	_busy = true
	_input.text = ""
	_out.text = "[i]...working...[/i]"
	if _persona_mode:
		_status.text = "asking persona..."
		var body := {"text": text, "profile": "default"}
		var err := _http.request(_api + "/chat",
			PackedStringArray(["Content-Type: application/json"]),
			HTTPClient.METHOD_POST, JSON.stringify(body))
		if err != OK:
			_fail("request error %d" % err)
	else:
		var url: String = text
		if not url.begins_with("http"):
			url = "https://" + url
		_status.text = "fetching " + url
		var err := _http.request(url, PackedStringArray(["User-Agent: Project_Persona/1.0"]))
		if err != OK:
			_fail("request error %d" % err)


func _on_completed(result: int, code: int, _headers: PackedStringArray, raw: PackedByteArray) -> void:
	_busy = false
	if result != HTTPRequest.RESULT_SUCCESS:
		_fail("transport result %d" % result)
		return
	var text: String = raw.get_string_from_utf8()
	if _persona_mode:
		var data: Variant = JSON.parse_string(text)
		if typeof(data) == TYPE_DICTIONARY and data.has("text"):
			_out.text = String(data["text"]).strip_edges()
			_status.text = "persona replied (HTTP %d)" % code
		else:
			_fail("unexpected reply (HTTP %d)" % code)
	else:
		_out.text = _readable(text)
		_status.text = "fetched (HTTP %d, %d bytes)" % [code, raw.size()]


## Crude HTML -> readable text: drop script/style, strip tags, collapse whitespace.
func _readable(html: String) -> String:
	var re := RegEx.new()
	re.compile("(?is)<(script|style|head)[^>]*>.*?</\\1>")
	var s: String = re.sub(html, " ", true)
	var re2 := RegEx.new()
	re2.compile("<[^>]+>")
	s = re2.sub(s, " ", true)
	s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"")
	var re3 := RegEx.new()
	re3.compile("[ \\t\\r\\f]+")
	s = re3.sub(s, " ", true)
	var re4 := RegEx.new()
	re4.compile("\\n\\s*\\n\\s*")
	s = re4.sub(s.replace(". ", ".\n"), "\n", true)
	s = s.strip_edges()
	if s.length() > 4000:
		s = s.substr(0, 4000) + "\n\n[...truncated...]"
	return s


func _fail(msg: String) -> void:
	_busy = false
	_out.text = "[color=#ff8866]error: %s[/color]" % msg
	_status.text = msg
