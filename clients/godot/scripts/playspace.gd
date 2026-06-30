extends Node3D
## Project_Persona -- the "playspace": a starship bridge in geostationary orbit with
## Earth filling the forward viewport. This is the shared world the persona inhabits
## (the "looking-glass" the north-star calls for): 2D app panels will later float on
## the bridge consoles and the avatar will stand on the command deck. STATE-driven
## avatar work is deliberately NOT here yet -- this file owns the environment only.
##
## Everything is built procedurally in code (no imported assets), mirroring how
## main.gd/avatar.gd build their UI/face in code. Flatscreen + XR-ready: the player
## is a PlayerRig (scripts/player_rig.gd) that an XR origin swaps into later.
##
## Screenshot demo (proof without a screen-grab tool), then quits:
##   $env:PERSONA_PLAYSPACE_SHOT="$PWD\playspace.png"; clients\godot\run_playspace.ps1

const PlayerRigScript := preload("res://scripts/player_rig.gd")
const Panel3DScript := preload("res://scripts/panel3d.gd")
const ScreenInteractorScript := preload("res://scripts/screen_interactor.gd")
const ShipAIScript := preload("res://scripts/ship_ai.gd")
const MediaPlayerScript := preload("res://scripts/media_player.gd")
const PanelResearchScript := preload("res://scripts/panels/panel_research.gd")
const PanelNetworkScript := preload("res://scripts/panels/panel_network.gd")
const PanelWeatherScript := preload("res://scripts/panels/panel_weather.gd")
const EarthShader := preload("res://shaders/earth.gdshader")
const SkyShader := preload("res://shaders/space_sky.gdshader")
const SpacePanoramaShader := preload("res://shaders/space_panorama.gdshader")

# Bridge envelope (metres). Faces -Z: the forward viewport (and Earth) are at -Z,
# the player spawns near the +Z back wall looking forward.
const ROOM_W: float = 26.0     # x in [-13, 13]
const ROOM_H: float = 6.5      # y in [0, 6.5]
const FRONT_Z: float = -16.0   # forward viewport frame plane
const BACK_Z: float = 11.0     # zones (forward->aft): helm/viewport, command deck, lounge, door

var _earth: MeshInstance3D
var _earth_mat: ShaderMaterial
var _sun: DirectionalLight3D
var _rig: Node3D
var _panels: Array = []
var _sky_mat: ShaderMaterial
var _sky_yaw: float = 0.0


func _ready() -> void:
	_build_environment()
	_build_sun()
	_build_earth()
	_build_bridge()
	_build_command_seat()
	_build_lounge()
	_build_player()
	_build_hud()
	_build_ship_ai()

	if OS.get_environment("PERSONA_PLAYSPACE_SHOT") != "":
		_run_shot()


func _process(delta: float) -> void:
	if _earth != null:
		_earth.rotate_y(delta * 0.012)  # lazy planet spin
	# keep the Earth shader's sun direction in sync with the scene's sun.
	# DirectionalLight3D shines down its local -Z, so the vector *toward* the sun
	# (what the shader wants for N.L) is +basis.z.
	if _earth_mat != null and _sun != null:
		_earth_mat.set_shader_parameter("sun_dir", _sun.global_transform.basis.z)
	# drift the star field in sync with Earth's spin (the skybox "follows" Earth)
	if _sky_mat != null and _sky_mat.shader == SpacePanoramaShader:
		_sky_yaw += delta * 0.012
		_sky_mat.set_shader_parameter("yaw", _sky_yaw)


# --- world environment: deep-space sky + bloom + cool ambient ---------------
func _build_environment() -> void:
	var sky_mat := ShaderMaterial.new()
	# prefer real space imagery (NASA Deep Star Map EXR, else ESO Milky Way jpg);
	# fall back to the procedural starfield if neither was fetched.
	var pano: ImageTexture = _load_image_texture("res://assets/space/starmap.exr")
	if pano == null:
		pano = _load_image_texture("res://assets/space/milkyway.jpg")
	if pano != null:
		sky_mat.shader = SpacePanoramaShader
		sky_mat.set_shader_parameter("panorama", pano)
		sky_mat.set_shader_parameter("exposure", 0.45)
		print("[playspace] space panorama skybox loaded")
	else:
		sky_mat.shader = SkyShader
		print("[playspace] space panorama missing -> procedural starfield (run fetch_earth.ps1)")
	_sky_mat = sky_mat
	var sky := Sky.new()
	sky.sky_material = sky_mat
	sky.process_mode = Sky.PROCESS_MODE_REALTIME

	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.32, 0.33, 0.38)
	env.ambient_light_energy = 1.8
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.tonemap_white = 6.0
	env.glow_enabled = true
	env.glow_intensity = 0.35
	env.glow_strength = 1.0
	env.glow_bloom = 0.1
	env.glow_hdr_threshold = 1.1

	var we := WorldEnvironment.new()
	we.name = "WorldEnvironment"
	we.environment = env
	add_child(we)


func _build_sun() -> void:
	_sun = DirectionalLight3D.new()
	_sun.name = "Sun"
	# Side-and-front so the terminator rakes across the visible Earth disc rather
	# than lighting it flat-on (more dramatic; verified via the screenshot demo).
	_sun.rotation_degrees = Vector3(-22.0, -58.0, 0.0)
	_sun.light_energy = 1.3
	_sun.light_color = Color(1.0, 0.97, 0.92)
	_sun.shadow_enabled = true
	add_child(_sun)


func _build_earth() -> void:
	var mesh := SphereMesh.new()
	mesh.radius = 54.0
	mesh.height = 108.0
	mesh.radial_segments = 128
	mesh.rings = 80

	_earth_mat = ShaderMaterial.new()
	_earth_mat.shader = EarthShader
	_earth_mat.set_shader_parameter("cloud_amount", 0.6)
	_earth_mat.set_shader_parameter("night_strength", 2.4)
	_load_earth_textures()

	_earth = MeshInstance3D.new()
	_earth.name = "Earth"
	_earth.mesh = mesh
	_earth.material_override = _earth_mat
	# Hangs in the forward viewport, geostationary-distant, axis tilted.
	_earth.position = Vector3(-6.0, -2.0, -132.0)
	_earth.rotation_degrees = Vector3(0.0, 0.0, 23.5)
	add_child(_earth)


## Load the NASA Blue/Black Marble textures at runtime (no editor import needed) and
## bind them to the Earth shader; if any are missing, fall back to the procedural look.
func _load_earth_textures() -> void:
	var base := "res://assets/earth/"
	var day := _load_image_texture(base + "earth_day.jpg")
	var night := _load_image_texture(base + "earth_night.jpg")
	var clouds := _load_image_texture(base + "earth_clouds.jpg")
	if day != null and night != null:
		_earth_mat.set_shader_parameter("day_tex", day)
		_earth_mat.set_shader_parameter("night_tex", night)
		if clouds != null:
			_earth_mat.set_shader_parameter("clouds_tex", clouds)
		_earth_mat.set_shader_parameter("use_textures", true)
		print("[playspace] Earth textures loaded (NASA Blue/Black Marble)")
	else:
		_earth_mat.set_shader_parameter("use_textures", false)
		print("[playspace] Earth textures missing -> procedural fallback (run fetch_earth.ps1)")


func _load_image_texture(path: String) -> ImageTexture:
	if not FileAccess.file_exists(path):
		return null
	var img := Image.new()
	if img.load(path) != OK:
		return null
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


# --- bridge interior --------------------------------------------------------
func _build_bridge() -> void:
	var hull := _mat_metal(Color(0.15, 0.17, 0.21), 0.25, 0.65)
	var frame := _mat_metal(Color(0.24, 0.26, 0.32), 0.5, 0.45)
	var deck := _mat_metal(Color(0.10, 0.11, 0.14), 0.3, 0.6)

	var mid_z: float = (BACK_Z + FRONT_Z) * 0.5
	var depth: float = BACK_Z - FRONT_Z + 0.8
	var depth_fc: float = BACK_Z - FRONT_Z   # floor/ceiling end flush at the bay mouth (no overlap)

	# shell (floors + walls collide so the player stays inside the vessel)
	_add_box(Vector3(ROOM_W, 0.3, depth_fc), Vector3(0, -0.15, mid_z), deck, "Floor", true)
	_add_box(Vector3(ROOM_W, 0.3, depth_fc), Vector3(0, ROOM_H + 0.15, mid_z), hull, "Ceiling")
	# back wall with a central doorway opening through to the lounge
	_add_box(Vector3(11.7, ROOM_H, 0.3), Vector3(-7.15, ROOM_H * 0.5, BACK_Z), hull, "BackWallL", true)
	_add_box(Vector3(11.7, ROOM_H, 0.3), Vector3(7.15, ROOM_H * 0.5, BACK_Z), hull, "BackWallR", true)
	_add_box(Vector3(2.6, ROOM_H - 3.0, 0.3), Vector3(0, 3.0 + (ROOM_H - 3.0) * 0.5, BACK_Z), hull, "BackWallLintel")
	_add_box(Vector3(0.3, ROOM_H, depth), Vector3(-ROOM_W * 0.5, ROOM_H * 0.5, mid_z), hull, "WallL", true)
	_add_box(Vector3(0.3, ROOM_H, depth), Vector3(ROOM_W * 0.5, ROOM_H * 0.5, mid_z), hull, "WallR", true)

	# forward bay: the front wall opens (x in [-bay_r, bay_r]) into a semicircular glass
	# outcrop; solid hull flanks the bay mouth on each side.
	var bay_r: float = 10.0
	var flank_w: float = ROOM_W * 0.5 - bay_r
	_add_box(Vector3(flank_w, ROOM_H, 0.3), Vector3(-(bay_r + flank_w * 0.5), ROOM_H * 0.5, FRONT_Z), hull, "FrontFlankL", true)
	_add_box(Vector3(flank_w, ROOM_H, 0.3), Vector3(bay_r + flank_w * 0.5, ROOM_H * 0.5, FRONT_Z), hull, "FrontFlankR", true)
	_build_bay(bay_r, 18, 0.4, ROOM_H - 0.3)

	# command deck: a raised dais mid-room (captain's spot / future avatar stand)
	var dais := MeshInstance3D.new()
	dais.name = "CommandDais"
	var cyl := CylinderMesh.new()
	cyl.top_radius = 2.6
	cyl.bottom_radius = 2.9
	cyl.height = 0.25
	cyl.radial_segments = 48
	dais.mesh = cyl
	dais.material_override = _mat_metal(Color(0.09, 0.10, 0.13), 0.7, 0.35)
	dais.position = Vector3(0, 0.12, -3.0)
	add_child(dais)
	# glowing rim around the dais (subtle deck inlay, not a headline light)
	_add_ring_strip(Vector3(0, 0.2, -3.0), 2.75, Color(0.2, 0.8, 1.0), 0.55)

	# (the forward sill is kept clear -- no glowing helm panels in front of the viewport)

	# side console banks with slanted glowing readouts
	_build_console_bank(-ROOM_W * 0.5 + 0.9, 1.0)   # left, faces +x
	_build_console_bank(ROOM_W * 0.5 - 0.9, -1.0)   # right, faces -x

	# ambience: cool light strips along the floor base and ceiling perimeter
	for sx in [-1.0, 1.0]:
		_add_box(Vector3(0.08, 0.08, depth), Vector3(sx * (ROOM_W * 0.5 - 0.2), 0.06, mid_z),
				_mat_emissive(Color(0.15, 0.6, 1.0), 1.2), "FloorStrip")
		_add_box(Vector3(0.08, 0.08, depth), Vector3(sx * (ROOM_W * 0.5 - 0.2), ROOM_H - 0.1, mid_z),
				_mat_emissive(Color(0.25, 0.7, 1.0), 0.9), "CeilStrip")

	_build_doorway()
	_build_furniture()
	_build_interior_lights()


## The semicircular glass bay outcrop -- a panoramic observation alcove bulging forward
## from the bridge front. Mostly glass with only slim posts + sill/header trim (more
## glass, less frame). `radius` is the bay depth/half-width; `segs` the smoothness.
func _build_bay(radius: float, segs: int, sill_y: float, head_y: float) -> void:
	var z0: float = FRONT_Z
	var frame := _mat_metal(Color(0.24, 0.26, 0.32), 0.6, 0.4)
	var glass := _mat_glass()
	var gh: float = head_y - sill_y
	var yc: float = (sill_y + head_y) * 0.5
	var center := Vector3(0.0, yc, z0)

	# glass panels (one flat pane per angular segment, approximating the curve)
	var chord: float = 2.0 * radius * sin(PI / float(segs) / 2.0) * 1.04
	for i in range(segs):
		var t: float = (float(i) + 0.5) / float(segs) * PI
		var p := Vector3(radius * cos(t), yc, z0 - radius * sin(t))
		var qm := QuadMesh.new()
		qm.size = Vector2(chord, gh)
		var mi := MeshInstance3D.new()
		mi.name = "BayGlass"
		mi.mesh = qm
		mi.material_override = glass
		add_child(mi)
		mi.look_at_from_position(p, center, Vector3.UP)   # -Z faces the arc centre
		_attach_box_collision(mi, Vector3(chord, gh, 0.06))  # can't walk out through the glass

	# a few slim structural posts only (kept sparse -> more glass, less frame)
	for i in range(0, segs + 1, 3):
		var t: float = float(i) / float(segs) * PI
		var p := Vector3(radius * cos(t), yc, z0 - radius * sin(t))
		var post := MeshInstance3D.new()
		post.name = "BayPost"
		var bm := BoxMesh.new()
		bm.size = Vector3(0.08, gh + 0.1, 0.16)
		post.mesh = bm
		post.material_override = frame
		add_child(post)
		post.look_at_from_position(p, center, Vector3.UP)

	# thin sill + header arcs (segmented to follow the curve)
	for yy in [sill_y, head_y]:
		for i in range(segs):
			var a := Vector3(radius * cos(float(i) / float(segs) * PI), yy, z0 - radius * sin(float(i) / float(segs) * PI))
			var b := Vector3(radius * cos(float(i + 1) / float(segs) * PI), yy, z0 - radius * sin(float(i + 1) / float(segs) * PI))
			var bar := MeshInstance3D.new()
			bar.name = "BayTrim"
			var bbm := BoxMesh.new()
			bbm.size = Vector3(a.distance_to(b) * 1.05, 0.14, 0.2)
			bar.mesh = bbm
			bar.material_override = frame
			add_child(bar)
			bar.look_at_from_position((a + b) * 0.5, Vector3(0.0, yy, z0), Vector3.UP)

	# framed glass floor + ceiling: the observation outcrop sees space below AND above.
	# the floor is collidable (you stand on the glass over open space).
	_build_glass_cap(0.0, radius, segs, frame, true)
	_build_glass_cap(ROOM_H, radius, segs, frame, false)


## A framed glass disc cap for the bay (floor or ceiling): a thin glass disc with a
## radial + concentric frame grid, optionally collidable so you can stand on it.
func _build_glass_cap(y: float, radius: float, segs: int, frame_mat: Material, collide: bool) -> void:
	var z0: float = FRONT_Z
	# a HALF-disc (front semicircle only) so it doesn't overlap / z-fight the bridge
	# floor + ceiling behind the bay mouth.
	var glass := MeshInstance3D.new()
	glass.name = "BayGlassCap"
	glass.mesh = _half_disc_mesh(radius, segs * 2)
	glass.material_override = _mat_glass()
	glass.position = Vector3(0.0, y, z0)
	add_child(glass)
	if collide:
		var body := StaticBody3D.new()
		var cs := CollisionShape3D.new()
		var shp := CylinderShape3D.new()
		shp.radius = radius
		shp.height = 0.2
		cs.shape = shp
		cs.position = Vector3(0.0, -0.1, 0.0)   # collision top sits flush with y
		body.add_child(cs)
		glass.add_child(body)

	# frame grid: a perimeter + mid-radius arc, the straight diameter edge, radial ribs
	var fy: float = y - 0.005
	for rr in [radius, radius * 0.5]:
		for i in range(segs):
			var a := Vector3(rr * cos(float(i) / float(segs) * PI), fy, z0 - rr * sin(float(i) / float(segs) * PI))
			var b := Vector3(rr * cos(float(i + 1) / float(segs) * PI), fy, z0 - rr * sin(float(i + 1) / float(segs) * PI))
			var bar := MeshInstance3D.new()
			bar.name = "CapArc"
			var bm := BoxMesh.new()
			bm.size = Vector3(a.distance_to(b) * 1.05, 0.06, 0.1)
			bar.mesh = bm
			bar.material_override = frame_mat
			add_child(bar)
			bar.look_at_from_position((a + b) * 0.5, Vector3(0.0, fy, z0), Vector3.UP)
	_add_box(Vector3(radius * 2.0, 0.06, 0.12), Vector3(0.0, fy, z0), frame_mat, "CapEdge")
	for t in [0.0, PI * 0.25, PI * 0.5, PI * 0.75, PI]:
		var rim := Vector3(radius * cos(t), fy, z0 - radius * sin(t))
		var rib := MeshInstance3D.new()
		rib.name = "CapRib"
		var rbm := BoxMesh.new()
		rbm.size = Vector3(0.06, 0.06, radius)
		rib.mesh = rbm
		rib.material_override = frame_mat
		add_child(rib)
		rib.look_at_from_position((Vector3(0.0, fy, z0) + rim) * 0.5, rim, Vector3.UP)


## Clear, faintly-tinted glass for the bay -- mostly transparent so Earth + the star
## field read crisply, with a slight specular sheen.
func _mat_glass() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.5, 0.7, 0.95, 0.08)
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.metallic = 0.0
	m.roughness = 0.04
	m.metallic_specular = 0.6
	return m


## The command seat: a captain's chair on the dais facing the viewport, with three
## interactive console screens (Panel3D) on a shallow arc just forward of it, angled
## back to face the captain and kept at chest height so Earth stays visible above.
## The screens are the research terminal, the network panel, and the weather panel.
func _build_command_seat() -> void:
	_add_chair(Vector3(0.0, 0.24, -2.2), 1.4, Color(0.2, 0.8, 1.0))
	var specs := [
		{"script": PanelResearchScript, "pos": Vector3(-1.9, 1.5, -4.35), "yaw": 30.0},
		{"script": PanelNetworkScript,  "pos": Vector3(0.0, 1.55, -4.85),  "yaw": 0.0},
		{"script": PanelWeatherScript,  "pos": Vector3(1.9, 1.5, -4.35),  "yaw": -30.0},
	]
	for s in specs:
		var panel: Node3D = Panel3DScript.new()
		add_child(panel)                                  # _ready() builds the SubViewport
		panel.position = s["pos"]
		panel.rotation_degrees = Vector3(6.0, s["yaw"], 0.0)
		panel.set_content(s["script"].new())
		_panels.append(panel)


## A glowing frame around the back-wall doorway opening (the wall gap itself is built
## in _build_bridge); the opening leads through to the lounge.
func _build_doorway() -> void:
	var trim := _mat_emissive(Color(0.2, 0.7, 1.0), 1.2)
	_add_box(Vector3(0.14, 3.1, 0.45), Vector3(-1.3, 1.55, BACK_Z), trim, "DoorJamb")
	_add_box(Vector3(0.14, 3.1, 0.45), Vector3(1.3, 1.55, BACK_Z), trim, "DoorJamb")
	_add_box(Vector3(2.74, 0.14, 0.45), Vector3(0, 3.05, BACK_Z), trim, "DoorLintel")
	_add_box(Vector3(2.6, 0.05, 0.5), Vector3(0, 0.03, BACK_Z), trim, "DoorThreshold")


## Bridge dressing: two officers' chairs at the forward helm, seen from behind so they
## frame the viewport. (The holo-table now lives in the lounge -- see _build_lounge.)
func _build_furniture() -> void:
	_add_chair(Vector3(-3.5, 0.0, -13.5), 0.95, Color(0.3, 1.0, 0.6)) # helm left
	_add_chair(Vector3(3.5, 0.0, -13.5), 0.95, Color(1.0, 0.6, 0.2))  # helm right


## A second room -- a cozy lounge -- behind the bridge through the back doorway. Warmer
## materials + warm, soft light so the holo-table (entertainment) and sofas feel at home
## here rather than out of place on the command bridge.
func _build_lounge() -> void:
	var lf: float = BACK_Z     # shared wall with the bridge (the doorway is here)
	var lb: float = 26.0       # lounge back wall
	var lw: float = 18.0       # width (x in [-9, 9])
	var lh: float = 4.6        # lower ceiling than the bridge -> cozier
	var lmid: float = (lf + lb) * 0.5
	var ldepth: float = lb - lf

	var wall := _mat_metal(Color(0.21, 0.18, 0.17), 0.05, 0.85)
	var floor := _mat_metal(Color(0.17, 0.12, 0.09), 0.0, 0.9)
	var ceil := _mat_metal(Color(0.15, 0.14, 0.14), 0.1, 0.8)

	# shell (its front is the bridge's back wall, which already has the door gap)
	_add_box(Vector3(lw, 0.3, ldepth), Vector3(0, -0.15, lmid), floor, "LoungeFloor", true)
	_add_box(Vector3(lw, 0.3, ldepth), Vector3(0, lh + 0.15, lmid), ceil, "LoungeCeil")
	_add_box(Vector3(0.3, lh, ldepth), Vector3(-lw * 0.5, lh * 0.5, lmid), wall, "LoungeWallL", true)
	_add_box(Vector3(0.3, lh, ldepth), Vector3(lw * 0.5, lh * 0.5, lmid), wall, "LoungeWallR", true)
	_add_box(Vector3(lw, lh, 0.3), Vector3(0, lh * 0.5, lb), wall, "LoungeBack", true)
	# soft glowing cove strips where wall meets ceiling
	for sx in [-1.0, 1.0]:
		_add_box(Vector3(0.06, 0.06, ldepth), Vector3(sx * (lw * 0.5 - 0.15), lh - 0.15, lmid),
				_mat_emissive(Color(1.0, 0.7, 0.4), 0.7), "LoungeCove")

	# rug to anchor the seating group
	_add_box(Vector3(6.5, 0.04, 6.5), Vector3(0, 0.02, 18.0),
			_mat_metal(Color(0.26, 0.11, 0.12), 0.0, 0.95), "Rug")

	# the holo-table (entertainment system) at the lounge centre, with a holographic
	# media screen above it (scripts/media_player.gd) facing the main sofa.
	var disc := _add_holotable(Vector3(0.0, 0.0, 18.0))
	var screen = Panel3DScript.new()
	screen.screen_size = Vector2i(1300, 820)
	screen.world_size = Vector2(2.7, 1.7)
	add_child(screen)
	screen.position = Vector3(0.0, 1.95, 17.7)   # faces +Z (toward the main sofa)
	var mp = MediaPlayerScript.new()
	screen.set_content(mp)
	mp.setup(disc)
	_panels.append(screen)

	# an L of sofas facing the holo-table
	_add_sofa(Vector3(0.0, 0.0, 21.4), 5.0, 0.0, Color(0.17, 0.25, 0.30))    # faces -Z (toward table + door)
	_add_sofa(Vector3(-3.9, 0.0, 18.0), 4.2, -90.0, Color(0.17, 0.25, 0.30)) # faces +X (toward table)

	# warm, soft lounge lighting
	for p in [Vector3(-4.5, lh - 0.6, 14.0), Vector3(4.5, lh - 0.6, 14.0),
			Vector3(-4.5, lh - 0.6, 22.0), Vector3(4.5, lh - 0.6, 22.0)]:
		var o := OmniLight3D.new()
		o.name = "LoungeLight"
		o.position = p
		o.light_color = Color(1.0, 0.80, 0.55)
		o.light_energy = 1.5
		o.omni_range = 12.0
		o.omni_attenuation = 0.6
		add_child(o)


## A sofa assembled from primitives under a rotating pivot. `facing_deg` rotates about
## Y (0 = seat faces -Z); `length` is the number-of-seats span in metres.
func _add_sofa(center: Vector3, length: float, facing_deg: float, color: Color) -> void:
	var pivot := Node3D.new()
	pivot.name = "Sofa"
	add_child(pivot)
	pivot.position = center
	pivot.rotation_degrees = Vector3(0, facing_deg, 0)
	var fab := _mat_metal(color, 0.0, 0.92)
	var d: float = 0.95
	_box_in(pivot, Vector3(length, 0.4, d), Vector3(0, 0.2, 0), fab, "Base", true)
	_box_in(pivot, Vector3(length - 0.3, 0.22, d - 0.28), Vector3(0, 0.5, -0.06), fab, "Seat")
	_box_in(pivot, Vector3(length, 0.72, 0.22), Vector3(0, 0.76, d * 0.5 - 0.11), fab, "Back", true)
	for ax in [-1.0, 1.0]:
		_box_in(pivot, Vector3(0.22, 0.55, d), Vector3(ax * (length * 0.5 - 0.11), 0.45, 0), fab, "Arm")


## A waist-high pedestal topped by a glowing projection disc. Returns the disc so the
## media player can pulse it while playing.
func _add_holotable(base_pos: Vector3) -> MeshInstance3D:
	var pedestal := MeshInstance3D.new()
	pedestal.name = "HoloPedestal"
	var pc := CylinderMesh.new()
	pc.top_radius = 0.45
	pc.bottom_radius = 0.6
	pc.height = 0.7
	pc.radial_segments = 32
	pedestal.mesh = pc
	pedestal.material_override = _mat_metal(Color(0.12, 0.13, 0.16), 0.6, 0.4)
	pedestal.position = base_pos + Vector3(0, 0.35, 0)
	add_child(pedestal)

	var disc := MeshInstance3D.new()
	disc.name = "HoloDisc"
	var dc := CylinderMesh.new()
	dc.top_radius = 0.85
	dc.bottom_radius = 0.85
	dc.height = 0.06
	dc.radial_segments = 48
	disc.mesh = dc
	disc.material_override = _mat_emissive(Color(0.25, 0.85, 1.0), 1.8)
	disc.position = base_pos + Vector3(0, 0.73, 0)
	add_child(disc)

	_add_collider(base_pos + Vector3(0, 0.5, 0), Vector3(1.15, 1.0, 1.15))  # solid pedestal
	return disc


## A simple seat assembled from primitives, facing forward (-Z, toward the viewport).
## `s` scales the whole chair; `accent` tints an emissive trim strip on the headrest.
func _add_chair(base_pos: Vector3, s: float, accent: Color) -> void:
	var frame := _mat_metal(Color(0.10, 0.11, 0.14), 0.5, 0.5)
	var seat_y: float = 0.46 * s
	_add_box(Vector3(0.30 * s, seat_y, 0.30 * s), base_pos + Vector3(0, seat_y * 0.5, 0), frame, "ChairBase")
	_add_box(Vector3(0.72 * s, 0.12 * s, 0.70 * s), base_pos + Vector3(0, seat_y, 0), frame, "ChairSeat")
	_add_box(Vector3(0.72 * s, 0.85 * s, 0.13 * s),
			base_pos + Vector3(0, seat_y + 0.45 * s, 0.30 * s), frame, "ChairBack")
	for ax in [-1.0, 1.0]:
		_add_box(Vector3(0.12 * s, 0.10 * s, 0.55 * s),
				base_pos + Vector3(ax * 0.40 * s, seat_y + 0.18 * s, -0.02 * s), frame, "ChairArm")
	# emissive trim across the top of the headrest
	_add_box(Vector3(0.72 * s, 0.06 * s, 0.06 * s),
			base_pos + Vector3(0, seat_y + 0.86 * s, 0.30 * s), _mat_emissive(accent, 1.2), "ChairTrim")
	_add_collider(base_pos + Vector3(0, 0.6 * s, 0.1 * s), Vector3(0.85 * s, 1.25 * s, 0.95 * s))


## Soft overhead fill so the bridge reads as an interior -- the sun is outside
## lighting Earth, so without these the cabin is nearly black.
func _build_interior_lights() -> void:
	# an even grid of soft ceiling fills (rather than a single bright center row) so the
	# whole bridge reads uniformly lit, not as bright pools over dark gaps.
	for x in [-6.5, 0.0, 6.5]:
		for z in [-12.0, -5.0, 2.0, 8.0]:
			var omni := OmniLight3D.new()
			omni.name = "CabinLight"
			omni.position = Vector3(x, ROOM_H - 0.9, z)
			omni.light_color = Color(0.80, 0.86, 1.0)
			omni.light_energy = 0.85          # soft, wide, overlapping -> diffuse wash
			omni.omni_range = 16.0
			omni.omni_attenuation = 0.5
			add_child(omni)


## One bank of four slanted, glowing consoles along a side wall.
## `wall_x` is the inner face; `facing` is +1 (left wall, screens face +x) or -1.
func _build_console_bank(wall_x: float, facing: float) -> void:
	var body_mat := _mat_metal(Color(0.10, 0.11, 0.14), 0.7, 0.4)
	var cols := [Color(0.2, 0.8, 1.0), Color(1.0, 0.55, 0.2), Color(0.4, 1.0, 0.5)]
	for i in range(4):
		var z: float = -12.0 + float(i) * 4.0
		var bx: float = wall_x - facing * 0.7
		_add_box(Vector3(1.3, 1.0, 2.6), Vector3(bx, 0.5, z), body_mat, "ConsoleBody", true)
		var screen := _add_box(Vector3(0.08, 0.8, 2.2),
				Vector3(bx - facing * 0.55, 1.15, z),
				_mat_emissive(cols[i % cols.size()], 1.9), "ConsoleScreen")
		screen.rotation_degrees = Vector3(0.0, 0.0, facing * 30.0)  # slant the readout inward


func _build_player() -> void:
	_rig = PlayerRigScript.new()
	_rig.name = "PlayerRig"
	_rig.position = Vector3(0.0, 0.2, BACK_Z - 1.5)  # near the back wall; settles onto the deck

	var cam := Camera3D.new()
	cam.name = "Camera3D"
	cam.position = Vector3(0.0, 1.7, 0.0)             # eye height
	cam.fov = 72.0
	cam.near = 0.05
	cam.far = 6000.0
	cam.current = true
	_rig.add_child(cam)
	add_child(_rig)

	# crosshair-driven interaction with the diegetic 3D panels
	var interactor: Node = ScreenInteractorScript.new()
	interactor.name = "ScreenInteractor"
	_rig.add_child(interactor)
	interactor.setup(cam, _rig)


func _build_hud() -> void:
	var layer := CanvasLayer.new()
	layer.name = "HUD"
	add_child(layer)
	var label := Label.new()
	label.text = "WASD move   Mouse look   Shift sprint   Space jump   F fly/noclip   |   aim at a screen + click to use, type, Esc free cursor   |   T talk to ship"
	label.add_theme_color_override("font_color", Color(0.6, 0.78, 0.95, 0.85))
	label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
	label.add_theme_constant_override("outline_size", 4)
	label.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	label.offset_left = 16
	label.offset_top = -34
	label.offset_bottom = -10
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE   # never intercept mouse-look motion
	layer.add_child(label)

	# centre crosshair (the panel-targeting reticle). MUST ignore the mouse: a captured
	# cursor sits dead-centre on it, and a STOP filter would eat every look motion event.
	var cross := ColorRect.new()
	cross.color = Color(0.75, 0.92, 1.0, 0.7)
	cross.set_anchors_preset(Control.PRESET_CENTER)
	cross.offset_left = -3; cross.offset_top = -3
	cross.offset_right = 3; cross.offset_bottom = 3
	cross.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(cross)


## The omnipresent ship AI (the persona as a disembodied ship's computer) -- voice +
## HUD presence, until the embodied avatar exists. See scripts/ship_ai.gd.
func _build_ship_ai() -> void:
	var ai := ShipAIScript.new()
	ai.name = "ShipAI"
	add_child(ai)
	ai.setup(_rig)


# --- material + geometry helpers -------------------------------------------
func _mat_metal(color: Color, metallic: float, roughness: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.metallic = metallic
	m.roughness = roughness
	return m


func _mat_emissive(color: Color, energy: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color.darkened(0.6)
	m.emission_enabled = true
	m.emission = color
	m.emission_energy_multiplier = energy
	return m


func _add_box(size: Vector3, pos: Vector3, mat: Material, node_name: String, collide: bool = false) -> MeshInstance3D:
	return _box_in(self, size, pos, mat, node_name, collide)


## Like _add_box but parented to an arbitrary node (e.g. a rotating sofa pivot). When
## `collide` is true a matching StaticBody3D is attached so the player can't pass through.
func _box_in(parent: Node, size: Vector3, pos: Vector3, mat: Material, node_name: String, collide: bool = false) -> MeshInstance3D:
	var box := BoxMesh.new()
	box.size = size
	var mi := MeshInstance3D.new()
	mi.name = node_name
	mi.mesh = box
	mi.material_override = mat
	mi.position = pos
	parent.add_child(mi)
	if collide:
		_attach_box_collision(mi, size)
	return mi


## Attach a StaticBody3D + BoxShape3D (inheriting the node's transform) for collision.
func _attach_box_collision(node: Node3D, size: Vector3) -> void:
	var body := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var shp := BoxShape3D.new()
	shp.size = size
	cs.shape = shp
	body.add_child(cs)
	node.add_child(body)


## A standalone solid box (no mesh) -- used to give furniture a collision footprint
## without coupling it to any one visual piece.
func _add_collider(pos: Vector3, size: Vector3) -> void:
	var body := StaticBody3D.new()
	body.position = pos
	var cs := CollisionShape3D.new()
	var shp := BoxShape3D.new()
	shp.size = size
	cs.shape = shp
	body.add_child(cs)
	add_child(body)


## A flat half-disc (front semicircle, in the local XZ plane) for the bay glass caps,
## so they cover only the outcrop and never overlap the bridge floor/ceiling.
func _half_disc_mesh(radius: float, segs: int) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in range(segs):
		var t0: float = float(i) / float(segs) * PI
		var t1: float = float(i + 1) / float(segs) * PI
		var a := Vector3(radius * cos(t0), 0.0, -radius * sin(t0))
		var b := Vector3(radius * cos(t1), 0.0, -radius * sin(t1))
		for vtx in [Vector3.ZERO, a, b]:
			st.set_normal(Vector3.UP)
			st.set_uv(Vector2(vtx.x / (2.0 * radius) + 0.5, vtx.z / (2.0 * radius) + 0.5))
			st.add_vertex(vtx)
	return st.commit()


## A thin glowing torus, used as the command-deck rim light.
func _add_ring_strip(pos: Vector3, radius: float, color: Color, energy: float) -> void:
	var torus := TorusMesh.new()
	torus.inner_radius = radius - 0.06
	torus.outer_radius = radius + 0.06
	torus.rings = 64
	torus.ring_segments = 12
	var mi := MeshInstance3D.new()
	mi.name = "DaisRim"
	mi.mesh = torus
	mi.material_override = _mat_emissive(color, energy)
	mi.position = pos
	add_child(mi)


# --- screenshot demo (proof path, no external grab tool) --------------------
func _run_shot() -> void:
	if _rig != null and _rig.has_method("set_active"):
		_rig.set_active(false)  # no mouse capture / movement during the grab
	# PERSONA_PLAYSPACE_VIEW=command frames the command seat + panels (and waits longer
	# so the panels' live HTTP fetches can populate); default is the wide bridge view.
	var view: String = OS.get_environment("PERSONA_PLAYSPACE_VIEW")
	var wait: float = 1.2
	var c: Camera3D = _rig.get_node("Camera3D")
	if view == "command":
		c.global_position = Vector3(0.0, 1.55, -2.1)   # captain's eye, at the arc centre
		c.look_at(Vector3(0.0, 1.45, -5.0), Vector3.UP)
		c.fov = 95.0                                    # wide enough to take in all three panels
		wait = 5.0
	elif view == "lounge":
		c.global_position = Vector3(4.8, 2.5, 24.6)     # aft corner of the lounge
		c.look_at(Vector3(-0.5, 1.0, 17.5), Vector3.UP)
		c.fov = 80.0
		wait = 2.0
	await get_tree().create_timer(wait).timeout  # let shaders compile + a few frames settle
	await RenderingServer.frame_post_draw
	var img: Image = get_viewport().get_texture().get_image()
	var path: String = OS.get_environment("PERSONA_PLAYSPACE_SHOT")
	var err: int = img.save_png(path)
	print("[playspace] screenshot %s -> %s" % ["OK" if err == OK else "ERR %d" % err, path])
	await get_tree().create_timer(0.3).timeout
	get_tree().quit()
