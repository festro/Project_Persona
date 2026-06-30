extends RefCounted
## Media discovery + transcode helpers for the holotable player (scripts/media_player.gd).
## Scans local + network roots for audio/video, classifies by extension into
## native-playable vs needs-transcode, and shells out to the bundled ffmpeg
## (tools/ffmpeg/) to convert the rest to WAV / Ogg-Theora on demand. Static helpers;
## the player preloads this script (no class_name, to stay run-scene safe).

const AUDIO_NATIVE := ["wav", "ogg", "mp3"]
const AUDIO_TRANSCODE := ["flac", "m4a", "aac", "opus", "wma"]
const VIDEO_NATIVE := ["ogv"]
const VIDEO_TRANSCODE := ["mp4", "mkv", "avi", "mov", "webm", "wmv", "m4v"]


## Where to look: the OS Music + Movies folders, plus any roots in PERSONA_MEDIA_ROOTS
## (';'-separated -- e.g. mapped drives or UNC network shares like //nas/media).
static func default_roots() -> Array:
	var roots: Array = []
	var music: String = OS.get_system_dir(OS.SYSTEM_DIR_MUSIC)
	var movies: String = OS.get_system_dir(OS.SYSTEM_DIR_MOVIES)
	if music != "":
		roots.append(music)
	if movies != "":
		roots.append(movies)
	var extra: String = OS.get_environment("PERSONA_MEDIA_ROOTS")
	if extra != "":
		for r in extra.split(";", false):
			roots.append(r.strip_edges())
	return roots


static func ffmpeg_exe() -> String:
	var base: String = ProjectSettings.globalize_path("res://")
	var exe: String = base.path_join("../../tools/ffmpeg/ffmpeg.exe").simplify_path()
	return exe if FileAccess.file_exists(exe) else ""


static func kind_for(ext: String) -> String:
	ext = ext.to_lower()
	if ext in AUDIO_NATIVE or ext in AUDIO_TRANSCODE:
		return "audio"
	if ext in VIDEO_NATIVE or ext in VIDEO_TRANSCODE:
		return "video"
	return ""


static func needs_transcode(ext: String) -> bool:
	ext = ext.to_lower()
	return ext in AUDIO_TRANSCODE or ext in VIDEO_TRANSCODE


## Recursively scan `roots`; returns [{path, name, ext, kind}], deduped by filename,
## sorted naturally. Capped so a huge / slow share can't run away (called off-thread).
static func scan(roots: Array, max_files: int = 1500) -> Array:
	var out: Array = []
	var seen: Dictionary = {}
	for root in roots:
		_scan_dir(root, out, seen, max_files, 0)
		if out.size() >= max_files:
			break
	out.sort_custom(func(a, b): return a["name"].naturalnocasecmp_to(b["name"]) < 0)
	return out


static func _scan_dir(path: String, out: Array, seen: Dictionary, max_files: int, depth: int) -> void:
	if depth > 5 or out.size() >= max_files:
		return
	var d := DirAccess.open(path)
	if d == null:
		return
	d.list_dir_begin()
	var name := d.get_next()
	while name != "":
		if not name.begins_with("."):
			var full := path.path_join(name)
			if d.current_is_dir():
				_scan_dir(full, out, seen, max_files, depth + 1)
			else:
				var ext := name.get_extension().to_lower()
				var kind := kind_for(ext)
				if kind != "":
					var key := name.to_lower()         # basic dedup across roots (refine later)
					if not seen.has(key):
						seen[key] = true
						out.append({"path": full, "name": name.get_basename(), "ext": ext, "kind": kind})
		if out.size() >= max_files:
			break
		name = d.get_next()
	d.list_dir_end()


## Transcode an unsupported audio file to a cached PCM WAV; returns the path or "".
static func transcode_audio(src: String) -> String:
	return _transcode(src, "wav", ["-y", "-i", src, "-ac", "2", "-ar", "48000", "%OUT%"])


## Transcode an unsupported video to a cached Ogg-Theora .ogv (slow; run off-thread).
static func transcode_video(src: String) -> String:
	return _transcode(src, "ogv", ["-y", "-i", src, "-c:v", "libtheora", "-q:v", "6",
		"-c:a", "libvorbis", "-q:a", "5", "%OUT%"])


static func _transcode(src: String, out_ext: String, args_template: Array) -> String:
	var exe := ffmpeg_exe()
	if exe == "":
		return ""
	var tmp := _cache_path(src, out_ext)
	if FileAccess.file_exists(tmp):
		return tmp                                   # already converted this source
	var args: Array = []
	for a in args_template:
		args.append(tmp if a == "%OUT%" else a)
	var output: Array = []
	var code := OS.execute(exe, args, output, true)
	return tmp if (code == 0 and FileAccess.file_exists(tmp)) else ""


static func _cache_path(src: String, ext: String) -> String:
	var base := OS.get_cache_dir().path_join("persona_media")
	DirAccess.make_dir_recursive_absolute(base)
	return base.path_join(str(src.hash()) + "." + ext)
