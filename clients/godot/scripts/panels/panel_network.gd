extends Control
## NETWORK panel (Stage B), mounted on a Panel3D in the command seat. Two tabs:
##   MESH -- GET <PERSONA_API>/health and show the persona node's status (model,
##           avatar-state, etc.) plus the known anchor/mesh endpoints.
##   LAN  -- reachability probe of hosts on the local /24 (StreamPeerTCP): a curated
##           set on load, plus an opt-in subnet sweep for SMB(445)/web(80) "devices".
## Real but intentionally light; a full discovery/dedup pass is future work.

var _api: String = "http://192.168.8.114:8000"
var _http: HTTPRequest
var _mesh_box: RichTextLabel
var _lan_box: RichTextLabel
var _status: Label
var _tabs: TabContainer


func _ready() -> void:
	var env: String = OS.get_environment("PERSONA_API")
	if env != "":
		_api = env.rstrip("/")
	_build()
	_http = HTTPRequest.new()
	add_child(_http)
	_http.request_completed.connect(_on_health)
	_refresh_mesh()
	_probe_curated()


func _build() -> void:
	var bg := ColorRect.new()
	bg.color = Color(0.03, 0.07, 0.06)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	var col := VBoxContainer.new()
	col.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	col.offset_left = 22; col.offset_top = 18; col.offset_right = -22; col.offset_bottom = -18
	col.add_theme_constant_override("separation", 10)
	add_child(col)

	var head := HBoxContainer.new()
	col.add_child(head)
	var t := Label.new()
	t.text = "NETWORK"
	t.add_theme_font_size_override("font_size", 40)
	t.add_theme_color_override("font_color", Color(0.4, 1.0, 0.7))
	t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(t)
	var refresh := Button.new()
	refresh.text = "Refresh"
	refresh.add_theme_font_size_override("font_size", 20)
	refresh.pressed.connect(func(): _refresh_mesh(); _probe_curated())
	head.add_child(refresh)

	_tabs = TabContainer.new()
	_tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	col.add_child(_tabs)

	_mesh_box = _mono_box()
	_mesh_box.name = "Mesh"
	_tabs.add_child(_mesh_box)

	var lan_wrap := VBoxContainer.new()
	lan_wrap.name = "LAN"
	_tabs.add_child(lan_wrap)
	_lan_box = _mono_box()
	_lan_box.size_flags_vertical = Control.SIZE_EXPAND_FILL
	lan_wrap.add_child(_lan_box)
	var scan := Button.new()
	scan.text = "Scan /24 for SMB(445)/web(80) devices"
	scan.add_theme_font_size_override("font_size", 20)
	scan.pressed.connect(_scan_subnet)
	lan_wrap.add_child(scan)

	_status = Label.new()
	_status.add_theme_font_size_override("font_size", 18)
	_status.add_theme_color_override("font_color", Color(0.5, 0.8, 0.7))
	col.add_child(_status)


func _mono_box() -> RichTextLabel:
	var r := RichTextLabel.new()
	r.bbcode_enabled = true
	r.scroll_active = true
	r.add_theme_font_size_override("normal_font_size", 22)
	r.add_theme_color_override("default_color", Color(0.8, 0.95, 0.88))
	return r


# --- MESH: persona /health -------------------------------------------------
func _refresh_mesh() -> void:
	_status.text = "GET %s/health ..." % _api
	_mesh_box.text = "[i]querying persona node...[/i]"
	var err := _http.request(_api + "/health")
	if err != OK:
		_mesh_box.text = "[color=#ff8866]request error %d[/color]" % err


func _on_health(result: int, code: int, _h: PackedStringArray, raw: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS:
		_mesh_box.text = "[color=#ff8866]persona node unreachable (result %d)[/color]\nis the EVO-X2 API up at %s ?" % [result, _api]
		_status.text = "mesh: offline"
		return
	var data: Variant = JSON.parse_string(raw.get_string_from_utf8())
	var s := "[b]Anchor node[/b]  %s\n" % _api
	s += "  HTTP %d\n" % code
	if typeof(data) == TYPE_DICTIONARY:
		for k in data.keys():
			s += "  [color=#7fd]%s[/color] = %s\n" % [k, _short(data[k])]
	else:
		s += "  " + raw.get_string_from_utf8().substr(0, 400)
	s += "\n[b]Known endpoints[/b]\n"
	s += "  persona API   %s\n" % _api
	s += "  OpenWebUI     %s\n" % _api.replace(":8000", ":3000")
	_mesh_box.text = s
	_status.text = "mesh: online"


func _short(v: Variant) -> String:
	var s := str(v)
	if s.length() > 90:
		s = s.substr(0, 90) + "..."
	return s


# --- LAN: TCP reachability probe -------------------------------------------
func _subnet_prefix() -> String:
	# derive "a.b.c." from the persona api host (default 192.168.8.114)
	var host: String = _api.replace("http://", "").replace("https://", "").split(":")[0]
	var parts := host.split(".")
	if parts.size() == 4:
		return "%s.%s.%s." % [parts[0], parts[1], parts[2]]
	return "192.168.8."


func _probe_curated() -> void:
	var pre := _subnet_prefix()
	var targets := [
		{"host": pre + "1", "ports": [80, 443, 53]},
		{"host": pre + "114", "ports": [8000, 3000, 22]},
		{"host": "127.0.0.1", "ports": [8000, 3000]},
	]
	_lan_box.text = "[i]probing known hosts...[/i]"
	var s := "[b]Reachability (%s0/24)[/b]\n" % pre
	for t in targets:
		var up := []
		for p in t["ports"]:
			if await _probe(t["host"], int(p), 0.6):
				up.append(str(p))
		var mark: String = ("[color=#6f6]open: " + ", ".join(up) + "[/color]") if up.size() > 0 else "[color=#955]--[/color]"
		s += "  %s   %s\n" % [t["host"], mark]
	_lan_box.text = s


func _scan_subnet() -> void:
	var pre := _subnet_prefix()
	_status.text = "scanning %s0/24 (445,80)..." % pre
	var found := []
	# launch all connects concurrently, then poll within a short window
	var peers := []
	for i in range(1, 255):
		for port in [445, 80]:
			var peer := StreamPeerTCP.new()
			if peer.connect_to_host(pre + str(i), port) == OK:
				peers.append({"peer": peer, "host": pre + str(i), "port": port})
	var t := 0.0
	while t < 1.8:
		for e in peers:
			e["peer"].poll()
			if e["peer"].get_status() == StreamPeerTCP.STATUS_CONNECTED and not e.get("done", false):
				e["done"] = true
				found.append("%s:%d" % [e["host"], e["port"]])
				e["peer"].disconnect_from_host()
		await get_tree().create_timer(0.1).timeout
		t += 0.1
	for e in peers:
		e["peer"].disconnect_from_host()
	found.sort()
	var s := "[b]Subnet sweep %s0/24[/b]\n" % pre
	if found.is_empty():
		s += "  (no SMB/web hosts answered)\n"
	else:
		for f in found:
			s += "  [color=#6f6]%s[/color]\n" % f
	_lan_box.text = s
	_status.text = "scan done: %d service(s)" % found.size()


## Async TCP connect with a timeout window; true if it reaches CONNECTED.
func _probe(host: String, port: int, timeout: float) -> bool:
	var peer := StreamPeerTCP.new()
	if peer.connect_to_host(host, port) != OK:
		return false
	var t := 0.0
	while t < timeout:
		peer.poll()
		var st := peer.get_status()
		if st == StreamPeerTCP.STATUS_CONNECTED:
			peer.disconnect_from_host()
			return true
		if st == StreamPeerTCP.STATUS_ERROR:
			return false
		await get_tree().create_timer(0.06).timeout
		t += 0.06
	peer.disconnect_from_host()
	return false
