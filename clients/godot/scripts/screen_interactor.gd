extends Node3D
## Lets the diegetic 3D screens (scripts/panel3d.gd) be used without leaving
## mouse-look. Each frame it casts a ray from the camera centre (the crosshair); the
## Panel3D under the crosshair gets hover (mouse-motion) events, a left-click is
## forwarded as a press/release at that point, and -- once a panel is clicked
## ("focused") -- keyboard input is routed to it (so you can type into a panel's
## fields). While a panel is focused the rig's WALK is paused so WASD types instead of
## moving; look still works, and Esc drops focus. Lives on the PlayerRig.
##
## NB the Panel3D type is referenced via its preloaded SCRIPT (not the `Panel3D`
## class_name) so this parses under a fresh `-s`/run-scene launch, where the global
## class registry is not populated (same pattern as scripts/main.gd).

const Panel3DScript := preload("res://scripts/panel3d.gd")

@export var reach: float = 4.5

var _cam: Camera3D
var _rig: Node             # PlayerRig (for pausing movement while typing)
var _hovered: Node3D       # a Panel3D, or null
var _focused: Node3D       # a Panel3D, or null
var _hover_pos: Vector3


func setup(cam: Camera3D, rig: Node) -> void:
	_cam = cam
	_rig = rig


func _physics_process(_delta: float) -> void:
	if _cam == null:
		return
	var from: Vector3 = _cam.global_position
	var to: Vector3 = from - _cam.global_transform.basis.z * reach
	var q := PhysicsRayQueryParameters3D.create(from, to)
	q.collide_with_areas = true
	q.collide_with_bodies = false
	var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(q)

	var panel: Node3D = null
	if not hit.is_empty():
		panel = _panel_of(hit.collider)
		_hover_pos = hit.position
	_hovered = panel
	if panel != null:
		var mm := InputEventMouseMotion.new()
		mm.position = panel.world_to_screen(_hover_pos)
		panel.viewport.push_input(mm)


## Walk up the parent chain to the Panel3D (identified by its script), or null.
func _panel_of(node: Object) -> Node3D:
	var n: Node = node as Node
	while n != null:
		if n.get_script() == Panel3DScript:
			return n as Node3D
		n = n.get_parent()
	return null


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if _hovered != null:
			_set_focus(_hovered)
			_push_click(_hovered, event.pressed)
		elif not event.pressed:
			_set_focus(null)  # click into empty space -> drop focus
	elif event is InputEventKey and _focused != null:
		if event.pressed and event.keycode == KEY_ESCAPE:
			_set_focus(null)
		else:
			_focused.viewport.push_input(event)


func _push_click(panel: Node3D, pressed: bool) -> void:
	var mb := InputEventMouseButton.new()
	mb.button_index = MOUSE_BUTTON_LEFT
	mb.pressed = pressed
	mb.position = panel.world_to_screen(_hover_pos)
	panel.viewport.push_input(mb)


func _set_focus(panel: Node3D) -> void:
	if panel == _focused:
		return
	_focused = panel
	# pause walking (so typing doesn't drive the rig) while a panel is focused
	if _rig != null and _rig.has_method("set_movement_enabled"):
		_rig.set_movement_enabled(panel == null)
