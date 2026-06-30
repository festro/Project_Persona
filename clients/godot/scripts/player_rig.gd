extends CharacterBody3D
class_name PlayerRig
## First-person character for the playspace: grounded with gravity + collision (so you
## stay on the deck and can't no-clip out through the hull), mouse-look, WASD walk,
## Shift sprint, Space jump. F toggles a free-fly inspect mode (gravity off, Space/Ctrl
## or E/Q for up/down) -- still collides. Esc frees the cursor; click to recapture.
##
## XR swap path: a CharacterBody3D works as the locomotion body under an XROrigin3D;
## the camera becomes an XRCamera3D and locomotion comes from controller input instead
## of _gather_move(). The world (scripts/playspace.gd) only references get_camera() and
## this body's transform, both of which survive that swap.

@export var walk_speed: float = 6.0
@export var sprint_mult: float = 1.8
@export var jump_speed: float = 5.0
@export var gravity: float = 18.0
@export var mouse_sensitivity: float = 0.0022
@export var pitch_limit_deg: float = 89.0

var _cam: Camera3D
var _col: CollisionShape3D
var _yaw: float = 0.0       # body rotation about Y
var _pitch: float = 0.0     # camera rotation about X
var _active: bool = true    # false in screenshot/headless mode (no capture/move)
var _move_enabled: bool = true  # paused while a 3D panel is focused (typing)
var _fly: bool = false      # F: free-fly + noclip (collision shape disabled)


func _ready() -> void:
	_ensure_collision()
	_cam = _find_camera()
	if _cam == null:
		_cam = Camera3D.new()
		_cam.position = Vector3(0.0, 1.6, 0.0)
		add_child(_cam)
	_yaw = rotation.y
	_pitch = _cam.rotation.x
	if _active:
		_capture(true)


func get_camera() -> Camera3D:
	return _cam


func set_active(active: bool) -> void:
	_active = active
	set_physics_process(active)
	if not active:
		_capture(false)


func set_movement_enabled(enabled: bool) -> void:
	_move_enabled = enabled


func is_movement_enabled() -> bool:
	return _move_enabled


## Create the capsule body if the scene didn't supply one (feet at the body origin).
func _ensure_collision() -> void:
	for c in get_children():
		if c is CollisionShape3D:
			_col = c
			return
	var col := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.3
	cap.height = 1.8
	col.shape = cap
	col.position = Vector3(0.0, 0.9, 0.0)
	add_child(col)
	_col = col


func _find_camera() -> Camera3D:
	for child in get_children():
		if child is Camera3D:
			return child
	return null


func _capture(on: bool) -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if on else Input.MOUSE_MODE_VISIBLE


func _can_input() -> bool:
	return _move_enabled and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED


func _unhandled_input(event: InputEvent) -> void:
	if not _active:
		return
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		_yaw -= event.relative.x * mouse_sensitivity
		_pitch -= event.relative.y * mouse_sensitivity
		_pitch = clampf(_pitch, -deg_to_rad(pitch_limit_deg), deg_to_rad(pitch_limit_deg))
		rotation.y = _yaw
		_cam.rotation.x = _pitch
	elif event is InputEventMouseButton and event.pressed:
		if Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
			_capture(true)
	elif event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_ESCAPE:
			_capture(false)
		elif event.keycode == KEY_F and _move_enabled:
			_fly = not _fly  # toggle free-fly inspect mode
			if _col != null:
				_col.disabled = _fly  # fly = noclip: pass through the hull/geometry


func _physics_process(delta: float) -> void:
	if not _active:
		return
	var sprint: bool = _can_input() and Input.is_key_pressed(KEY_SHIFT)
	var speed: float = walk_speed * (sprint_mult if sprint else 1.0)

	# vertical: fly (manual up/down) or gravity + jump
	if _fly:
		var up: float = 0.0
		if _can_input():
			if Input.is_key_pressed(KEY_SPACE) or Input.is_key_pressed(KEY_E):
				up += 1.0
			if Input.is_key_pressed(KEY_CTRL) or Input.is_key_pressed(KEY_Q):
				up -= 1.0
		velocity.y = up * speed
	else:
		if not is_on_floor():
			velocity.y -= gravity * delta
		elif _can_input() and Input.is_key_pressed(KEY_SPACE):
			velocity.y = jump_speed
		elif velocity.y < 0.0:
			velocity.y = 0.0

	# horizontal: WASD relative to look yaw
	var h: Vector3 = Vector3.ZERO
	if _can_input():
		var m: Vector3 = _gather_move()
		h = Basis(Vector3.UP, _yaw) * Vector3(m.x, 0.0, m.z)
		if h.length() > 0.0:
			h = h.normalized()
	velocity.x = h.x * speed
	velocity.z = h.z * speed

	move_and_slide()


func _gather_move() -> Vector3:
	var v: Vector3 = Vector3.ZERO
	if Input.is_key_pressed(KEY_W): v.z -= 1.0
	if Input.is_key_pressed(KEY_S): v.z += 1.0
	if Input.is_key_pressed(KEY_A): v.x -= 1.0
	if Input.is_key_pressed(KEY_D): v.x += 1.0
	return v
