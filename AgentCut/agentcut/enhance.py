from __future__ import annotations

import json
import math
import os
import platform
import shutil
import tempfile
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

from .errors import AgentCutError
from .probe import probe_media
from .util import ensure_binary, run

BACKEND_REGISTRY = {
    "realesrgan": {
        "version": "20220424",
        "license": "MIT",
        "homepage": "https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan",
        "urls": {
            "windows": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip",
            "linux": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip",
            "darwin": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-macos.zip",
        },
        "binary": {"windows": "realesrgan-ncnn-vulkan.exe", "linux": "realesrgan-ncnn-vulkan", "darwin": "realesrgan-ncnn-vulkan"},
    },
    "rife": {
        "version": "20221029",
        "license": "MIT",
        "homepage": "https://github.com/nihui/rife-ncnn-vulkan",
        "urls": {
            "windows": "https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/rife-ncnn-vulkan-20221029-windows.zip",
            "linux": "https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/rife-ncnn-vulkan-20221029-ubuntu.zip",
            "darwin": "https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/rife-ncnn-vulkan-20221029-macos.zip",
        },
        "binary": {"windows": "rife-ncnn-vulkan.exe", "linux": "rife-ncnn-vulkan", "darwin": "rife-ncnn-vulkan"},
    },
}


def _platform_key() -> str:
    name = platform.system().lower()
    return "windows" if name.startswith("win") else "darwin" if name == "darwin" else "linux"


def backend_root() -> Path:
    root = os.environ.get("AGENTCUT_BACKEND_ROOT")
    return Path(root).expanduser() if root else Path.home() / ".agentcut" / "backends"



def _realesrgan_models_dir(exe: str) -> Path | None:
    try:
        resolved = Path(exe).resolve()
    except OSError:
        resolved = Path(exe)
    parent = resolved.parent
    for candidate in (parent / "models", parent.parent / "models"):
        if candidate.exists():
            return candidate
    return None


def _available_realesrgan_models(exe: str) -> set[str]:
    models = _realesrgan_models_dir(exe)
    if not models:
        return set()
    names = set()
    for param in models.glob("*.param"):
        if (models / (param.stem + ".bin")).exists():
            names.add(param.stem)
    return names


def _safe_extract(zf: zipfile.ZipFile, target: Path) -> None:
    root = target.resolve()
    for member in zf.infolist():
        dest = (target / member.filename).resolve()
        try:
            dest.relative_to(root)
        except ValueError as exc:
            raise AgentCutError("UNSAFE_ARCHIVE", "Third-party backend archive contains a path outside its destination", member=member.filename) from exc
    zf.extractall(target)


def install_backend(name: str, *, accept_third_party: bool = False) -> dict:
    key = str(name).lower()
    if key not in BACKEND_REGISTRY:
        raise AgentCutError("UNKNOWN_AI_BACKEND", "Unknown enhancement backend", backend=key, allowed=sorted(BACKEND_REGISTRY))
    if not accept_third_party:
        raise AgentCutError("THIRD_PARTY_ACCEPTANCE_REQUIRED", "Installing an AI backend downloads third-party binaries/models. Re-run with explicit acceptance.", backend=key, homepage=BACKEND_REGISTRY[key]["homepage"])
    spec = BACKEND_REGISTRY[key]
    plat = _platform_key()
    url = spec["urls"][plat]
    dest = backend_root() / key / str(spec["version"])
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / "backend.zip"
    try:
        try:
            urllib.request.urlretrieve(url, archive)
        except (urllib.error.URLError, OSError) as exc:
            raise AgentCutError("BACKEND_DOWNLOAD_FAILED", "Could not download the third-party AI backend", backend=key, url=url, reason=str(exc)) from exc
        with zipfile.ZipFile(archive) as zf:
            _safe_extract(zf, dest)
    finally:
        archive.unlink(missing_ok=True)
    binary_name = spec["binary"][plat]
    matches = list(dest.rglob(binary_name))
    if not matches:
        raise AgentCutError("BACKEND_INSTALL_FAILED", "Downloaded backend did not contain the expected executable", backend=key, expected=binary_name, destination=str(dest))
    binary = matches[0]
    if plat != "windows":
        binary.chmod(binary.stat().st_mode | 0o111)
    return {"backend": key, "version": spec["version"], "path": str(binary), "license": spec["license"], "homepage": spec["homepage"]}


def _find_backend(name: str) -> str | None:
    env_name = "AGENTCUT_REALESRGAN" if name == "realesrgan" else "AGENTCUT_RIFE"
    if os.environ.get(env_name):
        p = Path(os.environ[env_name]).expanduser()
        if p.exists():
            return str(p)
    candidates = ["realesrgan-ncnn-vulkan", "realesrgan-ncnn-vulkan.exe"] if name == "realesrgan" else ["rife-ncnn-vulkan", "rife-ncnn-vulkan.exe"]
    for c in candidates:
        found = shutil.which(c)
        if found:
            return found
    spec = BACKEND_REGISTRY[name]
    root = backend_root() / name / str(spec["version"])
    expected = spec["binary"][_platform_key()]
    matches = list(root.rglob(expected)) if root.exists() else []
    return str(matches[0]) if matches else None


def enhancement_status() -> dict:
    real_path = _find_backend("realesrgan")
    rife_path = _find_backend("rife")
    return {
        "realesrgan": {
            "available": bool(real_path), "path": real_path, **BACKEND_REGISTRY["realesrgan"],
            "bundled": False,
            "bundled_models": [],
            "models_path": str(_realesrgan_models_dir(real_path)) if real_path and _realesrgan_models_dir(real_path) else None,
            "runtime_probe": "deferred_until_inference",
        },
        "rife": {"available": bool(rife_path), "path": rife_path, "runtime_probe": "deferred_until_inference", **BACKEND_REGISTRY["rife"]},
        "fallbacks": {"upscale": "ffmpeg_lanczos", "interpolation": "ffmpeg_minterpolate"},
    }


def _video_stream(path: Path) -> dict:
    info = probe_media(path)
    stream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if not stream:
        raise AgentCutError("NO_VIDEO_STREAM", "Enhancement input has no video stream", path=str(path))
    return stream


def _remux_audio(video_only: Path, original: Path, output: Path) -> Path:
    ffmpeg = ensure_binary("ffmpeg")
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_only), "-i", str(original), "-map", "0:v:0", "-map", "1:a?", "-c:v", "copy", "-c:a", "copy", "-shortest", str(output)]
    run(cmd)
    return output


def upscale_video(source: Path, output: Path, *, width: int, height: int, backend: str = "auto", model: str = "auto") -> dict:
    source = Path(source); output = Path(output)
    exe = _find_backend("realesrgan")
    selected = "realesrgan" if backend in {"auto", "ai", "realesrgan"} and exe else "lanczos"
    if backend in {"ai", "realesrgan"} and not exe:
        raise AgentCutError("AI_BACKEND_UNAVAILABLE", "Real-ESRGAN was explicitly requested but is not installed", backend="realesrgan")
    if selected == "lanczos":
        ffmpeg = ensure_binary("ffmpeg")
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-vf", f"scale={int(width)}:{int(height)}:flags=lanczos", "-c:v", "libx264", "-crf", "12", "-preset", "fast", "-c:a", "copy", str(output)])
        return {"backend": "ffmpeg_lanczos", "ai": False, "output": str(output), "width": width, "height": height}

    stream = _video_stream(source)
    fps = float(stream.get("fps") or 30)
    src_w = int(stream.get("width") or width)
    src_h = int(stream.get("height") or height)
    models_dir = _realesrgan_models_dir(exe)
    available = _available_realesrgan_models(exe)
    requested_anime = model in {"auto", "anime"}
    ratio = max(float(width) / max(src_w, 1), float(height) / max(src_h, 1))
    chosen_model = None
    scale = 4
    if requested_anime:
        if ratio <= 2.25 and "realesr-animevideov3-x2" in available:
            chosen_model, scale = "realesr-animevideov3-x2", 2
        elif "realesr-animevideov3-x4" in available:
            chosen_model, scale = "realesr-animevideov3-x4", 4
        elif "realesrgan-x4plus-anime" in available or not available:
            chosen_model, scale = "realesrgan-x4plus-anime", 4
    else:
        if "realesrgan-x4plus" in available or not available:
            chosen_model, scale = "realesrgan-x4plus", 4
    if chosen_model is None:
        details = {"requested_model": model, "available_models": sorted(available), "models_path": str(models_dir) if models_dir else None}
        if backend == "auto":
            fallback = upscale_video(source, output, width=width, height=height, backend="lanczos", model=model)
            fallback["fallback_from"] = "realesrgan-ncnn-vulkan"
            fallback["fallback_reason"] = {"code": "AI_MODEL_UNAVAILABLE", **details}
            return fallback
        raise AgentCutError("AI_MODEL_UNAVAILABLE", "Real-ESRGAN backend does not contain a suitable model", **details)

    with tempfile.TemporaryDirectory(prefix="agentcut_esrgan_") as td:
        td = Path(td); frames = td / "in"; enhanced = td / "out"
        frames.mkdir(); enhanced.mkdir()
        ffmpeg = ensure_binary("ffmpeg")
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-fps_mode", "passthrough", str(frames / "%08d.png")])
        cmd = [exe, "-i", str(frames), "-o", str(enhanced)]
        if models_dir:
            cmd += ["-m", str(models_dir)]
        cmd += ["-n", chosen_model, "-s", str(scale), "-f", "png"]
        try:
            run(cmd)
        except AgentCutError as exc:
            if backend == "auto":
                fallback = upscale_video(source, output, width=width, height=height, backend="lanczos", model=model)
                fallback["fallback_from"] = "realesrgan-ncnn-vulkan"
                fallback["fallback_reason"] = exc.as_dict()
                return fallback
            raise
        video_only = td / "upscaled_video.mp4"
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-framerate", f"{fps:g}", "-i", str(enhanced / "%08d.png"), "-vf", f"scale={int(width)}:{int(height)}:flags=lanczos", "-c:v", "libx264", "-crf", "10", "-preset", "fast", "-pix_fmt", "yuv420p", str(video_only)])
        _remux_audio(video_only, source, output)
    return {"backend": "realesrgan-ncnn-vulkan", "ai": True, "bundled": False, "model": chosen_model, "model_scale": scale, "output": str(output), "width": width, "height": height}

def interpolate_video(source: Path, output: Path, *, target_fps: float, backend: str = "auto", hard_cut_times: list[float] | None = None, uhd: bool = False) -> dict:
    source = Path(source); output = Path(output)
    stream = _video_stream(source)
    source_fps = float(stream.get("fps") or 30)
    if target_fps <= source_fps + 1e-6:
        shutil.copy2(source, output)
        return {"backend": "copy", "ai": False, "source_fps": source_fps, "target_fps": target_fps, "output": str(output)}
    exe = _find_backend("rife")
    selected = "rife" if backend in {"auto", "ai", "rife"} and exe else "minterpolate"
    if backend in {"ai", "rife"} and not exe:
        raise AgentCutError("AI_BACKEND_UNAVAILABLE", "RIFE was explicitly requested but is not installed", backend="rife")
    ffmpeg = ensure_binary("ffmpeg")
    info = probe_media(source)
    duration = float(info.get("duration") or 0.0)
    if selected == "minterpolate":
        # minterpolate has temporal look-ahead and can otherwise drop the tail of short clips.
        # Pad enough context, interpolate, trim back to the source duration, then rebuild
        # timestamps from the target frame index. This makes frame interpolation duration-neutral.
        pad = max(0.5, 4.0 / max(source_fps, 1.0))
        filt = (
            f"tpad=stop_mode=clone:stop_duration={pad:.6f},"
            f"minterpolate=fps={target_fps:g}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1:scd=fdiff:scd_threshold=10,"
            f"trim=duration={duration:.9f},setpts=N/({target_fps:g}*TB)"
        )
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-vf", filt, "-r", f"{target_fps:g}", "-t", f"{duration:.9f}", "-c:v", "libx264", "-crf", "12", "-preset", "fast", "-c:a", "copy", str(output)])
        return {"backend": "ffmpeg_minterpolate", "ai": False, "scene_change_guard": True, "duration_preserved": True, "source_fps": source_fps, "target_fps": target_fps, "output": str(output)}

    cuts = sorted({float(x) for x in (hard_cut_times or []) if 0.001 < float(x) < duration - 0.001})
    boundaries = [0.0] + cuts + [duration]
    with tempfile.TemporaryDirectory(prefix="agentcut_rife_") as td:
        td = Path(td); global_frames = td / "global"; global_frames.mkdir()
        global_index = 1
        target_total_frames = max(1, int(round(duration * target_fps)))
        segments_meta = []
        for si, (start, end) in enumerate(zip(boundaries[:-1], boundaries[1:])):
            seg_dur = max(0.0, end - start)
            if seg_dur <= 1.0 / max(source_fps, 1):
                continue
            seg_in = td / f"seg_{si:03d}_in"; seg_out = td / f"seg_{si:03d}_out"
            seg_in.mkdir(); seg_out.mkdir()
            run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.6f}", "-t", f"{seg_dur:.6f}", "-i", str(source), "-an", "-fps_mode", "passthrough", str(seg_in / "%08d.png")])
            input_frames = sorted(seg_in.glob("*.png"))
            if len(input_frames) < 2:
                for p in input_frames:
                    shutil.copy2(p, global_frames / f"{global_index:08d}.png"); global_index += 1
                continue
            target_start = int(round(start * target_fps))
            target_end = int(round(end * target_fps))
            target_count = max(2, target_end - target_start)
            cmd = [exe, "-i", str(seg_in), "-o", str(seg_out), "-n", str(target_count), "-f", "%08d.png"]
            if uhd:
                cmd.append("-u")
            try:
                run(cmd)
            except AgentCutError as exc:
                if backend == "auto":
                    fallback = interpolate_video(source, output, target_fps=target_fps, backend="minterpolate", hard_cut_times=hard_cut_times, uhd=uhd)
                    fallback["fallback_from"] = "rife-ncnn-vulkan"
                    fallback["fallback_reason"] = exc.as_dict()
                    return fallback
                raise
            out_frames = sorted(seg_out.glob("*.png"))
            for p in out_frames:
                shutil.copy2(p, global_frames / f"{global_index:08d}.png"); global_index += 1
            segments_meta.append({"start": start, "end": end, "input_frames": len(input_frames), "output_frames": len(out_frames)})
        produced = sorted(global_frames.glob("*.png"))
        if produced:
            while len(produced) < target_total_frames:
                shutil.copy2(produced[-1], global_frames / f"{len(produced)+1:08d}.png")
                produced = sorted(global_frames.glob("*.png"))
            for extra in produced[target_total_frames:]:
                extra.unlink()
        video_only = td / "rife_video.mp4"
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-framerate", f"{target_fps:g}", "-i", str(global_frames / "%08d.png"), "-frames:v", str(target_total_frames), "-c:v", "libx264", "-crf", "10", "-preset", "fast", "-pix_fmt", "yuv420p", str(video_only)])
        _remux_audio(video_only, source, output)
    return {"backend": "rife-ncnn-vulkan", "ai": True, "scene_change_guard": True, "duration_preserved": True, "target_frames": target_total_frames, "hard_cut_segments": segments_meta, "source_fps": source_fps, "target_fps": target_fps, "output": str(output)}


def plan_enhancement(*, source_width: int, source_height: int, source_fps: float, target_width: int, target_height: int, target_fps: float, upscale: str = "auto", interpolate: str = "auto", content: str = "anime") -> dict:
    status = enhancement_status()
    need_upscale = target_width > source_width or target_height > source_height
    need_interp = target_fps > source_fps + 1e-6
    if not need_upscale or upscale == "off":
        up_backend = "none"
    elif status["realesrgan"]["available"]:
        up_backend = "realesrgan"
    elif upscale in {"ai", "realesrgan"}:
        up_backend = "unavailable"
    else:
        up_backend = "ffmpeg_lanczos"
    if not need_interp or interpolate == "off":
        fi_backend = "none"
    elif status["rife"]["available"]:
        fi_backend = "rife"
    elif interpolate in {"ai", "rife"}:
        fi_backend = "unavailable"
    else:
        fi_backend = "ffmpeg_minterpolate"
    warnings = []
    if need_upscale and upscale in {"ai", "realesrgan"} and not status["realesrgan"]["available"]:
        warnings.append({"code": "REALSERGAN_UNAVAILABLE", "message": "AI super-resolution was requested but Real-ESRGAN is not installed."})
    if need_interp and interpolate in {"ai", "rife"} and not status["rife"]["available"]:
        warnings.append({"code": "RIFE_UNAVAILABLE", "message": "AI frame interpolation was requested but RIFE is not installed."})
    return {
        "upscale": {"enabled": need_upscale and upscale != "off", "requested": upscale, "backend": up_backend, "model": "realesrgan-x4plus-anime" if content == "anime" else "realesrgan-x4plus"},
        "interpolation": {"enabled": need_interp and interpolate != "off", "requested": interpolate, "backend": fi_backend, "scene_change_guard": True},
        "recommended_order": "interpolate_then_upscale" if need_interp and need_upscale else "single_stage",
        "warnings": warnings,
    }
