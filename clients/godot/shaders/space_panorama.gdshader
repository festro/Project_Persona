// Project_Persona -- real-imagery space skybox for the bridge bay.
// Samples an equirectangular all-sky panorama (NASA Deep Star Map 2020, public
// domain; or the ESO Milky Way panorama) as the WorldEnvironment background, so the
// view out the bay is genuine deep-space imagery rather than procedural stars. A
// `yaw` uniform lets the field slowly drift in sync with Earth's spin ("follow
// Earth"); playspace.gd advances it. If the texture is missing, playspace.gd keeps
// the procedural space_sky.gdshader instead.
shader_type sky;

uniform sampler2D panorama : source_color, filter_linear_mipmap;
uniform float yaw = 0.0;
uniform float exposure : hint_range(0.1, 4.0) = 1.0;

void sky() {
	vec3 d = normalize(EYEDIR);
	float c = cos(yaw);
	float s = sin(yaw);
	vec3 r = vec3(c * d.x - s * d.z, d.y, s * d.x + c * d.z);   // rotate about Y
	float u = atan(r.z, r.x) / (2.0 * PI) + 0.5;
	float v = acos(clamp(r.y, -1.0, 1.0)) / PI;
	COLOR = texture(panorama, vec2(u, v)).rgb * exposure;
}
