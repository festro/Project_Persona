extends Control
## WEATHER / NEWS panel (Stage B), mounted on a Panel3D in the command seat.
## Autodetects your region (ip-api.com) on load, then shows current weather + a 3-day
## forecast (open-meteo, no API key), a map tile of the area (OpenStreetMap), and a
## world-news headline feed (BBC RSS). A search box geocodes any place name so you can
## explore other regions. All keyless/public endpoints.

var _lat: float = 0.0
var _lon: float = 0.0

var _geo_http: HTTPRequest    # ip-api autodetect + place-name geocoding
var _wx_http: HTTPRequest     # open-meteo forecast
var _map_http: HTTPRequest    # OSM tile
var _news_http: HTTPRequest   # RSS

var _search: LineEdit
var _place: Label
var _now: RichTextLabel
var _forecast: RichTextLabel
var _map: TextureRect
var _news: RichTextLabel
var _status: Label


func _ready() -> void:
	_build()
	_geo_http = _mk_http(_on_geo)
	_wx_http = _mk_http(_on_weather)
	_map_http = _mk_http(_on_map)
	_news_http = _mk_http(_on_news)
	_status.text = "detecting your region..."
	_geo_http.request("http://ip-api.com/json/?fields=status,lat,lon,city,regionName,country")
	_news_http.request("https://feeds.bbci.co.uk/news/world/rss.xml",
		PackedStringArray(["User-Agent: Project_Persona/1.0"]))


func _mk_http(cb: Callable) -> HTTPRequest:
	var h := HTTPRequest.new()
	add_child(h)
	h.request_completed.connect(cb)
	return h


func _build() -> void:
	var bg := ColorRect.new()
	bg.color = Color(0.04, 0.05, 0.09)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	var col := VBoxContainer.new()
	col.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	col.offset_left = 22; col.offset_top = 18; col.offset_right = -22; col.offset_bottom = -18
	col.add_theme_constant_override("separation", 8)
	add_child(col)

	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 10)
	col.add_child(head)
	var t := Label.new()
	t.text = "WEATHER"
	t.add_theme_font_size_override("font_size", 40)
	t.add_theme_color_override("font_color", Color(0.95, 0.75, 0.35))
	head.add_child(t)
	_search = LineEdit.new()
	_search.placeholder_text = "explore a region (city name)..."
	_search.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_search.add_theme_font_size_override("font_size", 22)
	_search.text_submitted.connect(func(_x): _do_search())
	head.add_child(_search)
	var go := Button.new()
	go.text = "Go"
	go.add_theme_font_size_override("font_size", 22)
	go.pressed.connect(_do_search)
	head.add_child(go)

	_place = Label.new()
	_place.add_theme_font_size_override("font_size", 26)
	_place.add_theme_color_override("font_color", Color(0.85, 0.92, 1.0))
	col.add_child(_place)

	var mid := HBoxContainer.new()
	mid.add_theme_constant_override("separation", 14)
	mid.size_flags_vertical = Control.SIZE_EXPAND_FILL
	col.add_child(mid)

	var info := VBoxContainer.new()
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	info.add_theme_constant_override("separation", 8)
	mid.add_child(info)
	_now = _rt(28, Color(0.95, 0.97, 1.0))
	info.add_child(_now)
	_forecast = _rt(22, Color(0.8, 0.88, 1.0))
	_forecast.size_flags_vertical = Control.SIZE_EXPAND_FILL
	info.add_child(_forecast)

	_map = TextureRect.new()
	_map.custom_minimum_size = Vector2(256, 256)
	_map.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	mid.add_child(_map)

	var nh := Label.new()
	nh.text = "World news"
	nh.add_theme_font_size_override("font_size", 22)
	nh.add_theme_color_override("font_color", Color(0.95, 0.75, 0.35))
	col.add_child(nh)
	_news = _rt(20, Color(0.82, 0.9, 1.0))
	_news.custom_minimum_size = Vector2(0, 150)
	col.add_child(_news)

	_status = Label.new()
	_status.add_theme_font_size_override("font_size", 18)
	_status.add_theme_color_override("font_color", Color(0.6, 0.7, 0.85))
	col.add_child(_status)


func _rt(font_size: int, c: Color) -> RichTextLabel:
	var r := RichTextLabel.new()
	r.bbcode_enabled = true
	r.scroll_active = true
	r.add_theme_font_size_override("normal_font_size", font_size)
	r.add_theme_color_override("default_color", c)
	return r


func _do_search() -> void:
	var q: String = _search.text.strip_edges()
	if q == "":
		return
	_status.text = "geocoding '%s'..." % q
	_geo_http.cancel_request()
	_geo_http.request("https://geocoding-api.open-meteo.com/v1/search?count=1&name=" + q.uri_encode())


func _on_geo(_r: int, _c: int, _h: PackedStringArray, raw: PackedByteArray) -> void:
	var data: Variant = JSON.parse_string(raw.get_string_from_utf8())
	if typeof(data) != TYPE_DICTIONARY:
		_status.text = "location lookup failed"
		return
	if data.has("results") and data["results"] is Array and data["results"].size() > 0:
		var r0: Dictionary = data["results"][0]
		_set_location(float(r0["latitude"]), float(r0["longitude"]),
			"%s, %s" % [r0.get("name", "?"), r0.get("country", "")])
	elif data.has("lat"):
		_set_location(float(data["lat"]), float(data["lon"]),
			"%s, %s" % [data.get("city", "?"), data.get("country", "")])
	else:
		_status.text = "no match"


func _set_location(lat: float, lon: float, name: String) -> void:
	_lat = lat
	_lon = lon
	_place.text = "%s   (%.2f, %.2f)" % [name, lat, lon]
	_status.text = "loading weather + map..."
	_wx_http.cancel_request()
	_wx_http.request("https://api.open-meteo.com/v1/forecast?latitude=%f&longitude=%f&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m&daily=temperature_2m_max,temperature_2m_min,weather_code&timezone=auto&forecast_days=3" % [lat, lon])
	_fetch_map(lat, lon, 5)


func _on_weather(_r: int, _c: int, _h: PackedStringArray, raw: PackedByteArray) -> void:
	var d: Variant = JSON.parse_string(raw.get_string_from_utf8())
	if typeof(d) != TYPE_DICTIONARY or not d.has("current"):
		_status.text = "weather unavailable"
		return
	var cur: Dictionary = d["current"]
	_now.text = "[b]%.1f C[/b]   %s\nwind %.0f km/h   humidity %s%%" % [
		float(cur.get("temperature_2m", 0.0)), _wmo(int(cur.get("weather_code", 0))),
		float(cur.get("wind_speed_10m", 0.0)), str(cur.get("relative_humidity_2m", "?"))]
	if d.has("daily"):
		var day: Dictionary = d["daily"]
		var times: Array = day.get("time", [])
		var hi: Array = day.get("temperature_2m_max", [])
		var lo: Array = day.get("temperature_2m_min", [])
		var wc: Array = day.get("weather_code", [])
		var s := "\n[b]Forecast[/b]\n"
		for i in range(min(times.size(), 3)):
			s += "  %s   %.0f / %.0f C   %s\n" % [times[i], float(hi[i]), float(lo[i]), _wmo(int(wc[i]))]
		_forecast.text = s
	_status.text = "updated"


func _fetch_map(lat: float, lon: float, z: int) -> void:
	var n: float = pow(2.0, z)
	var x: int = int((lon + 180.0) / 360.0 * n)
	var lat_r: float = deg_to_rad(lat)
	var y: int = int((1.0 - log(tan(lat_r) + 1.0 / cos(lat_r)) / PI) / 2.0 * n)
	var url := "https://tile.openstreetmap.org/%d/%d/%d.png" % [z, x, y]
	_map_http.cancel_request()
	_map_http.request(url, PackedStringArray(["User-Agent: Project_Persona/1.0 (playspace)"]))


func _on_map(result: int, _c: int, _h: PackedStringArray, raw: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS:
		return
	var img := Image.new()
	if img.load_png_from_buffer(raw) == OK:
		_map.texture = ImageTexture.create_from_image(img)


func _on_news(result: int, _c: int, _h: PackedStringArray, raw: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS:
		_news.text = "[i]news feed unavailable[/i]"
		return
	# RSS <title>s are CDATA-wrapped (XMLParser reports those as CDATA, not TEXT, which
	# is why the old parser found nothing). Pull item titles with a CDATA-aware regex.
	var text: String = raw.get_string_from_utf8()
	var item_re := RegEx.new()
	item_re.compile("(?s)<item[^>]*>(.*?)</item>")
	var title_re := RegEx.new()
	title_re.compile("(?s)<title[^>]*>(.*?)</title>")
	var titles: Array = []
	for m in item_re.search_all(text):
		var tm := title_re.search(m.get_string(1))
		if tm == null:
			continue
		var t: String = tm.get_string(1).replace("<![CDATA[", "").replace("]]>", "").strip_edges()
		t = _decode_entities(t)
		if t != "":
			titles.append(t)
	var s := ""
	for i in range(min(titles.size(), 6)):
		s += "[color=#7bf]*[/color] %s\n" % titles[i]
	_news.text = s if s != "" else "[i]no headlines parsed[/i]"


func _decode_entities(s: String) -> String:
	return s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">") \
		.replace("&quot;", "\"").replace("&#39;", "'").replace("&apos;", "'")


func _wmo(code: int) -> String:
	match code:
		0: return "Clear sky"
		1, 2, 3: return "Partly cloudy"
		45, 48: return "Fog"
		51, 53, 55: return "Drizzle"
		61, 63, 65: return "Rain"
		66, 67: return "Freezing rain"
		71, 73, 75, 77: return "Snow"
		80, 81, 82: return "Showers"
		85, 86: return "Snow showers"
		95: return "Thunderstorm"
		96, 99: return "Thunderstorm + hail"
		_: return "code %d" % code
