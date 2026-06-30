extends Node3D
class_name Panel3D
## A diegetic 3D "screen": a SubViewport rendered onto an unshaded quad, with an
## Area3D collider so the player's crosshair ray (scripts/screen_interactor.gd) can
## target it and forward mouse/keyboard input. Drop any Control into set_content()
## and it becomes an interactive in-world display. Used by the command-seat panels
## in playspace.gd (research / network / weather).

@export var screen_size: Vector2i = Vector2i(1024, 660)
@export var world_size: Vector2 = Vector2(1.7, 1.1)   # metres (w, h)

var viewport: SubViewport
var content: Control
var _mat: StandardMaterial3D


func _ready() -> void:
	viewport = SubViewport.new()
	viewport.size = screen_size
	viewport.transparent_bg = false
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport.handle_input_locally = true
	add_child(viewport)

	var quad := MeshInstance3D.new()
	quad.name = "Quad"
	var qm := QuadMesh.new()
	qm.size = world_size
	quad.mesh = qm
	_mat = StandardMaterial3D.new()
	_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_mat.albedo_texture = viewport.get_texture()
	_mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR
	quad.material_override = _mat
	add_child(quad)

	# a slim dark bezel so the screen reads as mounted hardware, not a floating decal
	var bezel := MeshInstance3D.new()
	bezel.name = "Bezel"
	var bm := BoxMesh.new()
	bm.size = Vector3(world_size.x + 0.08, world_size.y + 0.08, 0.05)
	bezel.mesh = bm
	var bmat := StandardMaterial3D.new()
	bmat.albedo_color = Color(0.04, 0.045, 0.06)
	bmat.metallic = 0.6
	bmat.roughness = 0.4
	bezel.material_override = bmat
	bezel.position = Vector3(0, 0, -0.03)
	add_child(bezel)

	var area := Area3D.new()
	area.name = "Touch"
	area.input_ray_pickable = true
	var col := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(world_size.x, world_size.y, 0.06)
	col.shape = box
	area.add_child(col)
	add_child(area)


## Mount a Control as the screen's contents (stretched to fill the SubViewport).
func set_content(c: Control) -> void:
	content = c
	viewport.add_child(c)
	c.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)


## Convert a world-space ray hit on the quad to SubViewport pixel coordinates.
func world_to_screen(world_pos: Vector3) -> Vector2:
	var local: Vector3 = to_local(world_pos)
	var u: float = clampf(local.x / world_size.x + 0.5, 0.0, 1.0)
	var v: float = clampf(0.5 - local.y / world_size.y, 0.0, 1.0)
	return Vector2(u * float(screen_size.x), v * float(screen_size.y))
