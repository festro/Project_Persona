extends SceneTree
## Headless smoke test for the avatar client -- no display needed. Instances the
## avatar + client scripts (catches GDScript parse/API errors), applies a STATE
## sample, then does one real /chat round-trip to the EVO-X2 API and prints the
## parsed reply + STATE. Exit 0 on success, 1 on failure.
##
## Run (from repo root):
##   tools/godot/Godot_v4.7-stable_win64_console.exe --headless \
##     --path clients/godot -s res://tools/headless_check.gd

var _client: Node
var _avatar: Node
var _elapsed: float = 0.0
var _done: bool = false
var _sent: bool = false


func _initialize() -> void:
	print("[headless] start")
	_avatar = preload("res://scripts/avatar.gd").new()
	root.add_child(_avatar)
	_avatar.apply_state({"emotion": "excited", "intensity": 0.8, "gesture": "nod", "speaking": false})
	_avatar.speak_for(1.0)
	print("[headless] avatar instanced + STATE applied OK (emotion=%s gesture=%s)" % [_avatar.emotion, _avatar.gesture])

	_client = preload("res://scripts/persona_client.gd").new()
	root.add_child(_client)
	_client.reply.connect(_on_reply)
	_client.failed.connect(_on_failed)
	# NB: nodes added to root from _initialize() are not "inside the tree" until the
	# main loop starts iterating, so the POST is fired from the first _process frame.


func _on_reply(text: String, state: Dictionary, cid: String) -> void:
	print("[reply] %s" % text.strip_edges())
	print("[state] %s" % str(state))
	print("[cid]   %s" % cid)
	print("[headless] PASS")
	_done = true
	quit(0)


func _on_failed(message: String) -> void:
	push_error("chat failed: " + message)
	print("[FAIL] %s" % message)
	_done = true
	quit(1)


func _process(delta: float) -> bool:
	_elapsed += delta
	if not _sent and _elapsed > 0.1:
		_sent = true
		print("[headless] client api_base=%s -> POST /chat" % _client.api_base)
		_client.ask("Say hello in one short sentence and sound happy about it.")
	if _elapsed > 45.0 and not _done:
		print("[FAIL] timeout after 45s")
		quit(1)
		return true
	return false
