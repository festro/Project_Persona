extends Control
## Holotable media player (Stage C), mounted on a Panel3D screen above the lounge
## holo-table. Auto-discovers audio + video from local + network roots
## (scripts/media_library.gd), plays WAV/OGG/MP3 natively and FLAC / non-Theora video
## via the bundled ffmpeg (transcoded off-thread). Transport + volume + a filterable
## library list; video renders on the screen, audio shows a now-playing card and pulses
## the holo-table disc. Interact via the crosshair (scripts/screen_interactor.gd).

const MediaLibrary := preload("res://scripts/media_library.gd")

var _glow: Node3D                 # the holo-table disc (pulsed while playing)
var _glow_base: float = 1.8

var _player: AudioStreamPlayer
var _video: VideoStreamPlayer
var _list: ItemList
var _now: Label
var _status: Label
var _art: Panel
var _play_btn: Button

var _entries: Array = []          # full library
var _shown: Array = []            # filtered subset shown in the list
var _filter: String = "all"
var _index: int = -1
var _vol_db: float = -6.0
var _t: float = 0.0
var _scan_thread: Thread
var _xcode_thread: Thread


func setup(glow_target: Node3D) -> void:
	_glow = glow_target


func _ready() -> void:
	_build()
	_player = AudioStreamPlayer.new()
	add_child(_player)
	_player.finished.connect(_play_next)
	_video.finished.connect(_play_next)
	_scan()
	set_process(true)


func _build() -> void:
	var bg := ColorRect.new()
	bg.color = Color(0.03, 0.05, 0.08)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	var col := VBoxContainer.new()
	col.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	col.offset_left = 22; col.offset_top = 16; col.offset_right = -22; col.offset_bottom = -16
	col.add_theme_constant_override("separation", 8)
	add_child(col)

	var head := HBoxContainer.new()
	col.add_child(head)
	var t := Label.new()
	t.text = "MEDIA"
	t.add_theme_font_size_override("font_size", 40)
	t.add_theme_color_override("font_color", Color(0.5, 0.85, 1.0))
	t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(t)
	for f in ["all", "audio", "video"]:
		var b := Button.new()
		b.text = f.capitalize()
		b.add_theme_font_size_override("font_size", 20)
		b.pressed.connect(_set_filter.bind(f))
		head.add_child(b)
	var rescan := Button.new()
	rescan.text = "Rescan"
	rescan.add_theme_font_size_override("font_size", 20)
	rescan.pressed.connect(_scan)
	head.add_child(rescan)

	# stage: video output OR now-playing card
	var stage := Control.new()
	stage.custom_minimum_size = Vector2(0, 320)
	col.add_child(stage)
	_video = VideoStreamPlayer.new()
	_video.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_video.expand = true
	_video.visible = false
	stage.add_child(_video)
	_art = Panel.new()
	_art.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.06, 0.10, 0.16)
	sb.set_corner_radius_all(8)
	_art.add_theme_stylebox_override("panel", sb)
	stage.add_child(_art)
	_now = Label.new()
	_now.text = "(nothing playing)"
	_now.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_now.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_now.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_now.add_theme_font_size_override("font_size", 30)
	_now.add_theme_color_override("font_color", Color(0.7, 0.88, 1.0))
	_art.add_child(_now)

	# transport
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	col.add_child(row)
	_add_transport(row, "|<", _play_prev)
	_play_btn = _add_transport(row, "Play", _toggle_play)
	_add_transport(row, "Stop", _stop_playback)
	_add_transport(row, ">|", _play_next)
	var vol := HSlider.new()
	vol.min_value = -40.0; vol.max_value = 6.0; vol.value = _vol_db
	vol.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vol.value_changed.connect(_on_volume)
	row.add_child(vol)

	_list = ItemList.new()
	_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_list.add_theme_font_size_override("font_size", 20)
	_list.item_clicked.connect(func(idx, _pos, _btn): _play_index(idx))
	col.add_child(_list)

	_status = Label.new()
	_status.add_theme_font_size_override("font_size", 16)
	_status.add_theme_color_override("font_color", Color(0.55, 0.72, 0.9))
	col.add_child(_status)


func _add_transport(row: HBoxContainer, text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.add_theme_font_size_override("font_size", 22)
	b.pressed.connect(cb)
	row.add_child(b)
	return b


# --- library scan ----------------------------------------------------------
func _scan() -> void:
	if _scan_thread != null and _scan_thread.is_alive():
		return
	_status.text = "scanning media..."
	_scan_thread = Thread.new()
	_scan_thread.start(_scan_worker)


func _scan_worker() -> void:
	var entries := MediaLibrary.scan(MediaLibrary.default_roots())
	call_deferred("_on_scanned", entries)


func _on_scanned(entries: Array) -> void:
	if _scan_thread != null:
		_scan_thread.wait_to_finish()
		_scan_thread = null
	_entries = entries
	_refresh_list()
	var ff: String = "ffmpeg ok" if MediaLibrary.ffmpeg_exe() != "" else "no ffmpeg (flac/video disabled)"
	_status.text = "%d item(s)   -   %s" % [_entries.size(), ff]


func _set_filter(f: String) -> void:
	_filter = f
	_refresh_list()


func _refresh_list() -> void:
	_shown.clear()
	_list.clear()
	for e in _entries:
		if _filter == "all" or e["kind"] == _filter:
			_shown.append(e)
			var tag: String = "[V]" if e["kind"] == "video" else "[A]"
			_list.add_item("%s  %s" % [tag, e["name"]])


# --- playback --------------------------------------------------------------
func _play_index(i: int) -> void:
	if i < 0 or i >= _shown.size():
		return
	_index = i
	_list.select(i)
	var e: Dictionary = _shown[i]
	_now.text = e["name"]
	_stop_playback()
	_play_btn.text = "Pause"
	if e["kind"] == "audio":
		_show_video(false)
		if MediaLibrary.needs_transcode(e["ext"]):
			_status.text = "transcoding %s ..." % e["ext"]
			_start_transcode("audio", e["path"])
		else:
			var s := _load_audio(e["path"])
			if s == null:
				# native decode failed (odd mp3/ogg headers) -> fall back to ffmpeg
				_status.text = "decoding %s via ffmpeg..." % e["ext"]
				_start_transcode("audio", e["path"])
			else:
				_player.stream = s
				_player.volume_db = _vol_db
				_player.play()
				_status.text = "playing"
	else:
		_show_video(true)
		if MediaLibrary.needs_transcode(e["ext"]):
			_status.text = "transcoding video (%s) -- this can take a while..." % e["ext"]
			_start_transcode("video", e["path"])
		else:
			_play_video(e["path"])


func _load_audio(path: String) -> AudioStream:
	match path.get_extension().to_lower():
		"mp3": return AudioStreamMP3.load_from_file(path)
		"ogg": return AudioStreamOggVorbis.load_from_file(path)
		"wav": return AudioStreamWAV.load_from_file(path)
	return null


func _play_video(path: String) -> void:
	var vs := VideoStreamTheora.new()
	vs.file = path
	_video.stream = vs
	_video.volume_db = _vol_db
	_video.play()
	_status.text = "playing video"


func _start_transcode(kind: String, src: String) -> void:
	if _xcode_thread != null and _xcode_thread.is_alive():
		return
	_xcode_thread = Thread.new()
	_xcode_thread.start(func(): _xcode_worker(kind, src))


func _xcode_worker(kind: String, src: String) -> void:
	var out: String = MediaLibrary.transcode_audio(src) if kind == "audio" else MediaLibrary.transcode_video(src)
	call_deferred("_on_transcoded", kind, out)


func _on_transcoded(kind: String, path: String) -> void:
	if _xcode_thread != null:
		_xcode_thread.wait_to_finish()
		_xcode_thread = null
	if path == "":
		_status.text = "transcode failed (is ffmpeg present?)"
		return
	if kind == "audio":
		_player.stream = AudioStreamWAV.load_from_file(path)
		_player.volume_db = _vol_db
		_player.play()
		_status.text = "playing"
	else:
		_play_video(path)


func _toggle_play() -> void:
	if _video.visible:
		_video.paused = not _video.paused
		_play_btn.text = "Play" if _video.paused else "Pause"
	elif _player.playing:
		_player.stream_paused = not _player.stream_paused
		_play_btn.text = "Play" if _player.stream_paused else "Pause"
	elif _index >= 0:
		_play_index(_index)
	elif _shown.size() > 0:
		_play_index(0)


func _stop_playback() -> void:
	if _player.playing:
		_player.stop()
	if _video.is_playing():
		_video.stop()
	_play_btn.text = "Play"


func _play_next() -> void:
	if _shown.size() > 0:
		_play_index((_index + 1) % _shown.size())


func _play_prev() -> void:
	if _shown.size() > 0:
		_play_index((_index - 1 + _shown.size()) % _shown.size())


func _on_volume(v: float) -> void:
	_vol_db = v
	_player.volume_db = v
	_video.volume_db = v


func _show_video(show_v: bool) -> void:
	_video.visible = show_v
	_art.visible = not show_v


func _process(delta: float) -> void:
	_t += delta
	if _glow == null or _glow.material_override == null:
		return
	var mat := _glow.material_override as StandardMaterial3D
	if mat == null:
		return
	var playing: bool = _player.playing or _video.is_playing()
	if playing:
		mat.emission_energy_multiplier = _glow_base * (1.0 + 0.4 * sin(_t * 6.0))
	else:
		mat.emission_energy_multiplier = _glow_base


func _exit_tree() -> void:
	if _scan_thread != null and _scan_thread.is_alive():
		_scan_thread.wait_to_finish()
	if _xcode_thread != null and _xcode_thread.is_alive():
		_xcode_thread.wait_to_finish()
