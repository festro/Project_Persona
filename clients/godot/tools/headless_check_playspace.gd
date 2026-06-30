extends SceneTree
## Headless smoke test for the playspace scene -- no display needed. Instances
## playspace.gd (catches GDScript parse/API errors + shader load), lets it build the
## world for a few frames, then asserts the key nodes exist (player rig + camera,
## Earth, sun, world environment). Exit 0 on success, 1 on failure.
##
## Run (from repo root):
##   tools\godot\Godot_v4.7-stable_win64_console.exe --headless \
##     --path clients\godot -s res://tools/headless_check_playspace.gd

var _space: Node
var _elapsed: float = 0.0
var _checked: bool = false


func _initialize() -> void:
	print("[headless] playspace start")
	_space = preload("res://scripts/playspace.gd").new()
	root.add_child(_space)
	# _ready() runs deferred for tree-added nodes; the assertions wait for _process.


func _process(delta: float) -> bool:
	_elapsed += delta
	if _checked or _elapsed < 0.2:
		return false
	_checked = true

	var ok: bool = true
	ok = _require(_space.get_node_or_null("PlayerRig") != null, "PlayerRig present") and ok
	var rig: Node = _space.get_node_or_null("PlayerRig")
	ok = _require(rig != null and rig.get_node_or_null("Camera3D") != null, "Camera3D under rig") and ok
	ok = _require(_space.get_node_or_null("Earth") != null, "Earth present") and ok
	ok = _require(_space.get_node_or_null("Sun") != null, "Sun present") and ok
	ok = _require(_space.get_node_or_null("WorldEnvironment") != null, "WorldEnvironment present") and ok
	ok = _require(_space.get_node_or_null("CommandDais") != null, "CommandDais present") and ok

	if ok:
		print("[headless] PASS -- playspace built (%d children)" % _space.get_child_count())
		quit(0)
	else:
		print("[FAIL] playspace missing expected nodes")
		quit(1)
	return true


func _require(cond: bool, label: String) -> bool:
	print("  [%s] %s" % ["ok" if cond else "XX", label])
	return cond
