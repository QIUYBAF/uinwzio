from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

from .errors import AgentCutError
from .probe import probe_media
from .util import ensure_binary, run

CONTAINERS = {"mp4", "mov", "mkv", "webm"}
VIDEO_CODECS = {
    "h264": {"cpu": "libx264", "gpu": "h264_nvenc", "containers": {"mp4", "mov", "mkv"}},
    "hevc": {"cpu": "libx265", "gpu": "hevc_nvenc", "containers": {"mp4", "mov", "mkv"}},
    "av1": {"cpu": "libaom-av1", "gpu": "av1_nvenc", "containers": {"mp4", "mkv", "webm"}},
    "vp9": {"cpu": "libvpx-vp9", "gpu": None, "containers": {"mkv", "webm"}},
    "prores": {"cpu": "prores_ks", "gpu": None, "containers": {"mov", "mkv"}},
}
AUDIO_CODEC_DEFAULTS = {"mp4": "aac", "mov": "aac", "mkv": "aac", "webm": "libopus"}


def _ffmpeg_encoders() -> str:
    ffmpeg = ensure_binary("ffmpeg")
    cp = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], text=True, capture_output=True, check=False)
    return (cp.stdout or "") + (cp.stderr or "")


def encoder_available(name: str) -> bool:
    return name in _ffmpeg_encoders()


def nvenc_runtime_available(codec: str = "h264") -> bool:
    spec = VIDEO_CODECS.get(codec)
    enc = spec.get("gpu") if spec else None
    if not enc or not encoder_available(enc):
        return False
    ffmpeg = ensure_binary("ffmpeg")
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=128x72:r=1",
        "-frames:v", "1", "-c:v", enc, "-f", "null", "-",
    ]
    return subprocess.run(cmd, text=True, capture_output=True, check=False).returncode == 0


def _normalize_even(value: int) -> int:
    value = int(value)
    return value if value % 2 == 0 else value - 1


@dataclass(frozen=True)
class ExportSpec:
    width: int
    height: int
    fps: float
    container: str = "mp4"
    codec: str = "h264"
    encoder: str = "auto"  # auto/cpu/gpu
    quality: int = 18
    audio_codec: str | None = None
    audio_bitrate: str = "320k"
    pixel_format: str = "yuv420p"

    @classmethod
    def normalized(cls, **kwargs) -> "ExportSpec":
        width = _normalize_even(int(kwargs.get("width", 1920)))
        height = _normalize_even(int(kwargs.get("height", 1080)))
        fps = float(kwargs.get("fps", 30))
        container = str(kwargs.get("container", "mp4")).lower().lstrip(".")
        codec = str(kwargs.get("codec", "h264")).lower()
        encoder = str(kwargs.get("encoder", "auto")).lower()
        quality = int(kwargs.get("quality", 18))
        audio_codec = kwargs.get("audio_codec")
        audio_bitrate = str(kwargs.get("audio_bitrate", "320k"))
        pixel_format = str(kwargs.get("pixel_format", "yuv420p"))
        if not (64 <= width <= 7680 and 64 <= height <= 4320):
            raise AgentCutError("INVALID_EXPORT_RESOLUTION", "Export resolution must be between 64x64 and 7680x4320", width=width, height=height)
        if not (1 <= fps <= 120):
            raise AgentCutError("INVALID_EXPORT_FPS", "Export fps must be between 1 and 120", fps=fps)
        if container not in CONTAINERS:
            raise AgentCutError("INVALID_EXPORT_CONTAINER", "Unsupported export container", container=container, allowed=sorted(CONTAINERS))
        if codec not in VIDEO_CODECS:
            raise AgentCutError("INVALID_EXPORT_CODEC", "Unsupported video codec", codec=codec, allowed=sorted(VIDEO_CODECS))
        if container not in VIDEO_CODECS[codec]["containers"]:
            raise AgentCutError("INCOMPATIBLE_EXPORT", "Codec/container combination is not supported", codec=codec, container=container, allowed_containers=sorted(VIDEO_CODECS[codec]["containers"]))
        if encoder not in {"auto", "cpu", "gpu"}:
            raise AgentCutError("INVALID_EXPORT_ENCODER", "encoder must be auto, cpu or gpu", encoder=encoder)
        if audio_codec is None:
            audio_codec = AUDIO_CODEC_DEFAULTS[container]
        return cls(width, height, fps, container, codec, encoder, quality, str(audio_codec), audio_bitrate, pixel_format)

    def as_dict(self) -> dict:
        return asdict(self)


def choose_video_encoder(spec: ExportSpec) -> dict:
    row = VIDEO_CODECS[spec.codec]
    cpu = row["cpu"]
    gpu = row["gpu"]
    warnings = []
    if spec.encoder == "gpu":
        if not gpu or not nvenc_runtime_available(spec.codec):
            raise AgentCutError("GPU_ENCODER_UNAVAILABLE", "Requested GPU encoder is unavailable at runtime", codec=spec.codec, encoder=gpu)
        return {"backend": "gpu", "encoder": gpu, "warnings": warnings}
    if spec.encoder == "auto" and gpu and nvenc_runtime_available(spec.codec):
        return {"backend": "gpu", "encoder": gpu, "warnings": warnings}
    if not encoder_available(cpu):
        raise AgentCutError("ENCODER_UNAVAILABLE", "CPU encoder is unavailable in FFmpeg", codec=spec.codec, encoder=cpu)
    if spec.encoder == "auto" and gpu:
        warnings.append({"code": "GPU_ENCODER_FALLBACK", "message": f"{gpu} is listed by FFmpeg but no usable GPU runtime was detected; using {cpu}."})
    return {"backend": "cpu", "encoder": cpu, "warnings": warnings}


def transcode_video(source: Path, output: Path, spec: ExportSpec, *, copy_audio: bool = False) -> Path:
    ffmpeg = ensure_binary("ffmpeg")
    choice = choose_video_encoder(spec)
    encoder = choice["encoder"]
    output.parent.mkdir(parents=True, exist_ok=True)
    vf = f"scale={spec.width}:{spec.height}:flags=lanczos,fps={spec.fps:g}"
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-vf", vf, "-c:v", encoder]
    if encoder in {"libx264", "libx265"}:
        cmd += ["-crf", str(spec.quality), "-preset", "medium"]
    elif encoder.endswith("_nvenc"):
        cmd += ["-cq", str(spec.quality), "-preset", "p5"]
    elif encoder == "libvpx-vp9":
        cmd += ["-crf", str(spec.quality), "-b:v", "0"]
    elif encoder == "libaom-av1":
        cmd += ["-crf", str(spec.quality), "-b:v", "0", "-cpu-used", "6"]
    elif encoder == "prores_ks":
        cmd += ["-profile:v", "3"]
    if spec.codec != "prores":
        cmd += ["-pix_fmt", spec.pixel_format]
    if copy_audio:
        cmd += ["-c:a", "copy"]
    else:
        cmd += ["-c:a", spec.audio_codec, "-b:a", spec.audio_bitrate]
    if spec.container in {"mp4", "mov"}:
        cmd += ["-movflags", "+faststart"]
    cmd += [str(output)]
    run(cmd)
    return output


def plan_export(spec: ExportSpec, *, project_video: dict, enhancement_plan: dict | None = None) -> dict:
    choice = choose_video_encoder(spec)
    official = spec.width <= 3840 and spec.height <= 2160 and spec.fps <= 60
    warnings = list(choice.get("warnings", []))
    if not official:
        warnings.append({"code": "EXPERIMENTAL_OUTPUT_CEILING", "message": "Values above 4K60 are accepted but are not part of AgentCut 3.0's validated output ceiling."})
    if spec.width > int(project_video.get("width", spec.width)) or spec.height > int(project_video.get("height", spec.height)):
        if not (enhancement_plan or {}).get("upscale", {}).get("enabled"):
            warnings.append({"code": "NON_AI_UPSCALE", "message": "Target resolution exceeds the project canvas and AI super-resolution is disabled; Lanczos scaling will not create new source detail."})
    return {
        "spec": spec.as_dict(),
        "encoder": choice,
        "officially_validated_ceiling": official,
        "enhancement": enhancement_plan or {},
        "warnings": warnings,
    }


def probe_export(path: Path) -> dict:
    info = probe_media(path)
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    return {
        "path": str(path),
        "width": video.get("width"),
        "height": video.get("height"),
        "fps": video.get("fps"),
        "codec": video.get("codec_name"),
        "duration": info.get("duration"),
    }
