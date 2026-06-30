// Project_Persona -- procedural deep-space sky for the bridge viewport.
// shader_type sky: drives the WorldEnvironment background, so it is what you see
// through the forward viewport (and supplies ambient/reflection). Renders a deep
// blue-black gradient, a faint nebula band, and a hashed multi-layer starfield.
// Star edges are smoothstep-softened to fight the sky pass's reduced-res twinkle.
shader_type sky;

uniform vec3 space_zenith : source_color = vec3(0.012, 0.014, 0.030);
uniform vec3 space_horizon : source_color = vec3(0.020, 0.028, 0.055);
uniform vec3 nebula_color : source_color = vec3(0.18, 0.10, 0.34);
uniform float nebula_strength : hint_range(0.0, 1.0) = 0.25;
uniform vec3 band_normal = vec3(0.30, 0.90, 0.20);
uniform float star_brightness : hint_range(0.0, 4.0) = 1.4;
uniform float twinkle : hint_range(0.0, 1.0) = 0.35;

float hash13(vec3 p) {
	p = fract(p * 0.1031);
	p += dot(p, p.zyx + 31.32);
	return fract((p.x + p.y) * p.z);
}

float vnoise(vec3 x) {
	vec3 i = floor(x);
	vec3 f = fract(x);
	f = f * f * (3.0 - 2.0 * f);
	return mix(
		mix(mix(hash13(i + vec3(0,0,0)), hash13(i + vec3(1,0,0)), f.x),
			mix(hash13(i + vec3(0,1,0)), hash13(i + vec3(1,1,0)), f.x), f.y),
		mix(mix(hash13(i + vec3(0,0,1)), hash13(i + vec3(1,0,1)), f.x),
			mix(hash13(i + vec3(0,1,1)), hash13(i + vec3(1,1,1)), f.x), f.y), f.z);
}

float fbm(vec3 p) {
	float v = 0.0;
	float a = 0.5;
	for (int i = 0; i < 5; i++) {
		v += a * vnoise(p);
		p *= 2.03;
		a *= 0.5;
	}
	return v;
}

// One scale of stars: cells along the view ray, each cell maybe holds one star.
float star_layer(vec3 dir, float density, float size, float thresh, float t) {
	vec3 g = dir * density;
	vec3 id = floor(g);
	vec3 f = fract(g) - 0.5;
	float present = step(thresh, hash13(id));
	vec3 jitter = vec3(hash13(id + 1.7), hash13(id + 3.3), hash13(id + 5.9)) - 0.5;
	float d = length(f - jitter * 0.6);
	float core = smoothstep(size, 0.0, d);
	// per-star twinkle + brightness variation
	float bvar = 0.45 + 0.55 * hash13(id + 8.1);
	float tw = 1.0 - twinkle * 0.5 * (0.5 + 0.5 * sin(t * 3.0 + hash13(id + 2.2) * 30.0));
	return present * core * bvar * tw;
}

void sky() {
	vec3 dir = normalize(EYEDIR);

	// deep-space gradient (brighter toward the galactic-ish horizon)
	float up = clamp(dir.y * 0.5 + 0.5, 0.0, 1.0);
	vec3 col = mix(space_horizon, space_zenith, up);

	// faint nebula clouds + a soft galactic band
	float band = exp(-pow(dot(dir, normalize(band_normal)) * 3.2, 2.0));
	float neb = fbm(dir * 3.0 + 11.0);
	col += nebula_color * (smoothstep(0.5, 0.95, neb) * 0.6 + band * 0.5) * nebula_strength;

	// layered starfield (near = sparse/big, far = dense/small)
	float s = 0.0;
	s += star_layer(dir, 90.0,  0.55, 0.965, TIME) * 1.0;
	s += star_layer(dir, 170.0, 0.45, 0.972, TIME) * 0.7;
	s += star_layer(dir, 320.0, 0.40, 0.978, TIME) * 0.45;
	// subtle color: most white, a few warm/cool
	vec3 tint = mix(vec3(0.75, 0.85, 1.0), vec3(1.0, 0.92, 0.78), hash13(floor(dir * 90.0)));
	col += s * tint * star_brightness;

	COLOR = col;
}
