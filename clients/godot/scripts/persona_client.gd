extends Node
class_name PersonaClient
## Talks to the persona API (/chat) on the EVO-X2 anchor node and surfaces the
## reply text + the Phase 4 STATE directives. One in-flight request at a time
## (an HTTPRequest constraint) -- the UI disables Send while busy.

signal reply(text: String, state: Dictionary, cid: String)
signal failed(message: String)

var api_base: String = "http://192.168.8.114:8000"
var profile: String = "default"
var conversation_id: String = ""
var busy: bool = false
var _http: HTTPRequest


func _ready() -> void:
	_ensure_ready()


## Lazy one-time setup. Done here (not only in _ready) because a node added to the
## tree from SceneTree._initialize() has its _ready() deferred a frame -- the
## headless smoke test calls ask() immediately, so _http must be created on demand.
func _ensure_ready() -> void:
	if _http != null:
		return
	var env_api: String = OS.get_environment("PERSONA_API")
	if env_api != "":
		api_base = env_api.rstrip("/")
	var env_profile: String = OS.get_environment("PERSONA_PROFILE")
	if env_profile != "":
		profile = env_profile
	_http = HTTPRequest.new()
	add_child(_http)
	_http.request_completed.connect(_on_completed)


func ask(text: String) -> void:
	_ensure_ready()
	if busy:
		failed.emit("busy")
		return
	var body: Dictionary = {"text": text, "profile": profile}
	if conversation_id != "":
		body["conversation_id"] = conversation_id
	var err: int = _http.request(
		api_base + "/chat",
		PackedStringArray(["Content-Type: application/json"]),
		HTTPClient.METHOD_POST,
		JSON.stringify(body))
	if err != OK:
		failed.emit("request error %d" % err)
		return
	busy = true


func _on_completed(result: int, code: int, _headers: PackedStringArray, raw: PackedByteArray) -> void:
	busy = false
	if result != HTTPRequest.RESULT_SUCCESS:
		failed.emit("transport result %d (is the EVO-X2 API reachable?)" % result)
		return
	if code != 200:
		failed.emit("HTTP %d" % code)
		return
	var data: Variant = JSON.parse_string(raw.get_string_from_utf8())
	if typeof(data) != TYPE_DICTIONARY:
		failed.emit("unexpected response (not JSON)")
		return
	conversation_id = String(data.get("conversation_id", conversation_id))
	var state: Dictionary = data.get("state", {})
	reply.emit(String(data.get("text", "")), state, conversation_id)
