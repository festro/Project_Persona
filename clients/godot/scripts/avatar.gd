extends Node2D
class_name AvatarFace
## A minimal procedural face that animates against the STATE contract
## (docs/avatar_protocol.md): emotion -> color + mouth curve + eye shape,
## intensity -> strength, gesture -> a one-shot body cue, speaking/viseme ->
## mouth motion. Deliberately drawn in code (no rigged-mesh asset yet); a
## blend-shape 3D head is the natural next step and consumes the same STATE.

const EMO_COLOR: Dictionary = {
	"neutral":   Color(0.62, 0.66, 0.72),
	"happy":     Color(0.96, 0.80, 0.30),
	"excited":   Color(0.98, 0.58, 0.25),
	"thinking":  Color(0.55, 0.70, 0.95),
	"concerned": Color(0.86, 0.52, 0.42),
	"confused":  Color(0.72, 0.60, 0.86),
	"amused":    Color(0.55, 0.84, 0.52),
}

var emotion: String = "neutral"
var intensity: float = 0.4
var gesture: String = "idle"
var speaking: bool = false

var _t: float = 0.0
var _speak_until: float = 0.0
var _gesture_kind: String = ""
var _gesture_t: float = 0.0          # seconds remaining in the one-shot
const GESTURE_DUR: float = 0.85
var _mouth: float = 0.0              # 0 closed .. 1 open
var _base_pos: Vector2 = Vector2.ZERO


func _ready() -> void:
	_base_pos = position
	set_process(true)


## Set the rest position the gesture offsets play around. Must be used (not a raw
## `position =`) because _process() rewrites position = _base_pos + offset each frame.
func set_anchor(pos: Vector2) -> void:
	_base_pos = pos
	position = pos


func apply_state(state: Dictionary) -> void:
	emotion = String(state.get("emotion", "neutral"))
	intensity = clampf(float(state.get("intensity", 0.4)), 0.0, 1.0)
	gesture = String(state.get("gesture", "idle"))
	if gesture != "idle":
		_gesture_kind = gesture
		_gesture_t = GESTURE_DUR
	# If the reply will be spoken, the caller drives speak_for(); honor an
	# already-speaking STATE too (Phase 5 will set state.speaking=true live).
	if bool(state.get("speaking", false)):
		speak_for(1.2)


func speak_for(seconds: float) -> void:
	speaking = true
	_speak_until = _t + maxf(0.3, seconds)


func _process(delta: float) -> void:
	_t += delta
	if speaking and _t >= _speak_until:
		speaking = false

	var target: float = 0.0
	if speaking:
		target = 0.45 + 0.55 * absf(sin(_t * 17.0))
	_mouth = lerpf(_mouth, target, clampf(delta * 14.0, 0.0, 1.0))

	var off: Vector2 = Vector2.ZERO
	var rot: float = 0.0
	var sc: float = 1.0
	if _gesture_t > 0.0:
		_gesture_t -= delta
		var p: float = 1.0 - clampf(_gesture_t / GESTURE_DUR, 0.0, 1.0)  # 0..1
		var wave: float = sin(p * PI)                                    # 0..1..0
		match _gesture_kind:
			"nod":
				off.y = wave * 20.0
			"shrug":
				off.y = -wave * 16.0
			"lean_in":
				sc = 1.0 + wave * 0.13
			"tilt_head":
				rot = deg_to_rad(wave * 13.0)
			"wave", "point":
				off.x = sin(p * TAU) * 12.0
			_:
				pass
	position = _base_pos + off
	rotation = rot
	scale = Vector2(sc, sc)
	queue_redraw()


func _draw() -> void:
	var col: Color = EMO_COLOR.get(emotion, EMO_COLOR["neutral"])
	var r: float = 135.0
	# head
	draw_circle(Vector2.ZERO, r, col)
	draw_arc(Vector2.ZERO, r, 0.0, TAU, 72, Color(0, 0, 0, 0.22), 5.0, true)

	# eyes (narrower when thinking/confused)
	var eye_dx: float = 50.0
	var eye_y: float = -32.0
	var eye_r: float = 17.0
	if emotion == "thinking" or emotion == "confused":
		eye_r = 12.0
	for sx in [-1.0, 1.0]:
		var c: Vector2 = Vector2(sx * eye_dx, eye_y)
		draw_circle(c, eye_r, Color.WHITE)
		draw_circle(c, eye_r * 0.45, Color(0.08, 0.08, 0.1))

	# brows hint surprise/concern via a short slanted line
	var brow_y: float = eye_y - 26.0
	var slant: float = 0.0
	if emotion == "concerned":
		slant = 8.0
	elif emotion == "excited":
		slant = -7.0
	for sx in [-1.0, 1.0]:
		var bx: float = sx * eye_dx
		draw_line(Vector2(bx - 16.0, brow_y + sx * slant),
				  Vector2(bx + 16.0, brow_y - sx * slant),
				  Color(0.1, 0.08, 0.08), 4.0)

	# mouth: a smile/frown parabola + an open-amount cavity
	var curve: float = 0.0  # + smile, - frown
	match emotion:
		"happy", "amused":
			curve = 0.55
		"excited":
			curve = 0.75
		"concerned":
			curve = -0.5
		"confused", "thinking":
			curve = -0.15
		_:
			curve = 0.0
	curve *= (0.55 + intensity)
	_draw_mouth(Vector2(0.0, 52.0), 78.0, curve, _mouth)


func _draw_mouth(center: Vector2, width: float, curve: float, open_amt: float) -> void:
	var pts: PackedVector2Array = PackedVector2Array()
	var n: int = 26
	for i in range(n + 1):
		var x: float = -0.5 + float(i) / float(n)       # -0.5 .. 0.5
		var py: float = -curve * 42.0 * (1.0 - 4.0 * x * x)
		pts.append(center + Vector2(x * width, py))
	draw_polyline(pts, Color(0.12, 0.05, 0.05), 6.0)
	if open_amt > 0.05:
		var oh: float = open_amt * 27.0
		draw_circle(center + Vector2(0.0, oh * 0.35), oh, Color(0.30, 0.07, 0.10))
