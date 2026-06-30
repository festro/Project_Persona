// Project_Persona -- textured Earth for the bridge viewport, from NASA imagery.
// spatial + unshaded: we light the globe ourselves from a `sun_dir` uniform so we
// fully control the day/night terminator and the night-side city lights. Equirect
// (lat/long) textures map straight onto SphereMesh UVs. Day = Blue Marble, night =
// Black Marble city lights, plus an animated cloud layer and an atmospheric rim.
// If a texture is missing the host did not fetch (clients/godot/fetch_earth.ps1),
// playspace.gd sets `use_textures = false` and a flat fallback tint is used.
shader_type spatial;
render_mode unshaded, cull_back;

uniform sampler2D day_tex : source_color, filter_linear_mipmap;
uniform sampler2D night_tex : source_color, filter_linear_mipmap;
uniform sampler2D clouds_tex : hint_default_black, filter_linear_mipmap;
uniform bool use_textures = true;

uniform vec3 sun_dir = vec3(0.6, 0.3, 0.7);
uniform vec3 fallback_color : source_color = vec3(0.05, 0.20, 0.40);
uniform vec3 atmo_color : source_color = vec3(0.32, 0.55, 1.0);
uniform vec3 sunset_color : source_color = vec3(1.0, 0.45, 0.18);
uniform float cloud_amount : hint_range(0.0, 1.0) = 0.9;
uniform float cloud_speed = 0.003;
uniform float night_strength : hint_range(0.0, 4.0) = 2.2;
uniform float ambient = 0.03;

varying vec3 v_wnormal;   // world-space normal
varying vec3 v_wpos;      // world-space position
varying vec2 v_uv;

void vertex() {
	v_wnormal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	v_wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_uv = UV;
}

void fragment() {
	vec3 n = normalize(v_wnormal);
	vec3 view = normalize(CAMERA_POSITION_WORLD - v_wpos);
	vec3 L = normalize(sun_dir);

	vec3 day = use_textures ? texture(day_tex, v_uv).rgb : fallback_color;
	vec3 night = use_textures ? texture(night_tex, v_uv).rgb : vec3(0.0);

	// scrolling clouds (two offset samples so they drift + evolve a little)
	float cloud = 0.0;
	if (use_textures) {
		float c = texture(clouds_tex, v_uv + vec2(TIME * cloud_speed, 0.0)).r;
		cloud = clamp(c * cloud_amount, 0.0, 1.0);
	}

	// --- day / night lighting (manual, unshaded) ---
	float ndl = dot(n, L);
	float dayf = smoothstep(-0.06, 0.18, ndl);
	float termf = smoothstep(0.0, 0.18, ndl) * smoothstep(0.38, 0.10, ndl); // peaks at terminator

	vec3 day_lit = day * (ambient + dayf);
	day_lit += day * sunset_color * termf * 0.30;          // warm rake along the terminator
	day_lit = mix(day_lit, vec3(1.0) * (ambient + dayf), cloud); // clouds are white + lit

	// night side: city lights where it is dark, fading out under cloud
	vec3 night_lit = night * night_strength * (1.0 - cloud);

	vec3 col = mix(night_lit, day_lit, dayf);

	// ocean sun glint (water reads dark/blue in the day texture)
	float water = (1.0 - smoothstep(0.18, 0.34, day.b - day.r)) ; // bluish -> water-ish
	float spec = pow(max(dot(reflect(-L, n), view), 0.0), 80.0) * water * dayf * (1.0 - cloud);
	col += spec * vec3(1.0, 0.96, 0.88) * 0.5;

	// --- emission: atmosphere rim (bloom pickup) ---
	float fres = pow(1.0 - max(dot(n, view), 0.0), 3.0);
	vec3 emis = atmo_color * fres * (0.25 + dayf * 0.9);
	emis += sunset_color * fres * termf * 1.1;
	emis += night_lit * 0.6; // let cities glow into the bloom too

	ALBEDO = col;
	EMISSION = emis;
}
