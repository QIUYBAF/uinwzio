from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import hashlib
import platform
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

from .errors import AgentCutError
from .util import ensure_binary

SUBTITLE_STYLES = {
    "default", "band", "thought", "shout", "whisper", "aside",
    "karaoke", "neon", "manga", "boxed", "cinematic", "lower_third", "bilingual",
}



SPEAKER_PREFIX_RE = re.compile(r"^\s*([^：:\n]{1,24})\s*[：:]\s*(.+?)\s*$", re.S)

def split_speaker_prefix(text: str) -> tuple[str | None, str]:
    """Split a conservative `Speaker: text` / `Speaker：text` prefix.

    Resolution against the project Cast is deliberately left to Editor so arbitrary
    colons in normal subtitle prose are not silently reinterpreted as speakers.
    """
    value = str(text or "").strip()
    m = SPEAKER_PREFIX_RE.match(value)
    if not m:
        return None, value
    return m.group(1).strip(), m.group(2).strip()

def infer_subtitle_style(text: str, *, has_speaker: bool = False) -> str:
    """Low-cognition deterministic style hint; never guesses aesthetic identities."""
    value = str(text or "").strip()
    compact = re.sub(r"\s+", "", value)
    if re.fullmatch(r"(?:\d+\s*秒前|\d+\s*seconds?\s*(?:earlier|ago)|.+(?:之前|以后|later|earlier))", value, re.I):
        return "cinematic"
    if any(mark in compact for mark in ("？！", "!?", "!!", "！！")) or compact.endswith("——！"):
        return "shout"
    if compact.startswith(("……", "...")):
        return "aside" if has_speaker else "cinematic"
    return "band" if has_speaker else "default"



ASR_INSTALL_REGISTRY = {
    "whisper.cpp": {
        "version": "1.9.0",
        "license": "MIT",
        "homepage": "https://github.com/ggml-org/whisper.cpp",
        "windows_x64": {
            "url": "https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.0/whisper-bin-x64.zip",
            "sha256": "2b692a032b065762e7cd14c09b70cc8168edc756e07895f4bce6badefee93448",
            "expected": "whisper-cli.exe",
        },
        "models": {
            "tiny-q5_1": {
                "filename": "ggml-tiny-q5_1.bin",
                "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny-q5_1.bin?download=true",
                "sha256": "818710568da3ca15689e31a743197b520007872ff9576237bda97bd1b469c3d7",
                "approx_mib": 31,
            }
        },
    }
}

def _backend_root() -> Path:
    return Path(os.environ.get("AGENTCUT_BACKEND_ROOT", Path.home() / ".agentcut" / "backends")).expanduser()

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _safe_extract_zip(zf: zipfile.ZipFile, target: Path) -> None:
    target = target.resolve()
    for member in zf.infolist():
        dest = (target / member.filename).resolve()
        try:
            dest.relative_to(target)
        except ValueError as exc:
            raise AgentCutError("UNSAFE_ARCHIVE", "ASR archive contains an unsafe path", member=member.filename) from exc
    zf.extractall(target)

def _download_verified(url: str, target: Path, expected_sha256: str | None, *, code: str) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(url, target)
    except (urllib.error.URLError, OSError) as exc:
        raise AgentCutError(code, "Could not download ASR component", url=url, reason=str(exc), target=str(target)) from exc
    if expected_sha256:
        actual = _sha256_file(target)
        if actual.lower() != expected_sha256.lower():
            target.unlink(missing_ok=True)
            raise AgentCutError("ASR_CHECKSUM_MISMATCH", "Downloaded ASR component failed SHA-256 verification", url=url, expected=expected_sha256, actual=actual)
    return target

def install_whisper_backend(*, profile: str = "tiny-q5_1", accept_third_party: bool = False, model_only: bool = False) -> dict:
    """Install a persistent whisper.cpp ASR runtime once, outside project source.

    Windows x64 gets an official portable CPU binary plus a small quantized model.
    On Linux/macOS we only install the model unless whisper-cli is already available;
    this avoids pretending AgentCut ships an upstream portable binary that does not exist.
    """
    if not accept_third_party:
        raise AgentCutError("THIRD_PARTY_ACCEPTANCE_REQUIRED", "ASR setup downloads whisper.cpp and a third-party model. Re-run with explicit acceptance.", backend="whisper.cpp")
    spec = ASR_INSTALL_REGISTRY["whisper.cpp"]
    model_spec = spec["models"].get(profile)
    if not model_spec:
        raise AgentCutError("ASR_PROFILE_UNKNOWN", "Unknown ASR install profile", profile=profile, allowed=sorted(spec["models"]))
    base = _backend_root() / "whisper"
    models = base / "models"
    models.mkdir(parents=True, exist_ok=True)
    model_path = models / model_spec["filename"]
    model_reused = model_path.exists() and _sha256_file(model_path) == model_spec["sha256"]
    if not model_reused:
        tmp = model_path.with_suffix(model_path.suffix + ".download")
        _download_verified(model_spec["url"], tmp, model_spec["sha256"], code="ASR_MODEL_DOWNLOAD_FAILED")
        tmp.replace(model_path)

    installed_binary = discover_whisper_cli()
    binary_reused = bool(installed_binary)
    sysname = platform.system().lower()
    if not model_only and not installed_binary and sysname.startswith("win"):
        bspec = spec["windows_x64"]
        dest = base / f"v{spec['version']}"
        dest.mkdir(parents=True, exist_ok=True)
        archive = dest / "whisper-bin-x64.zip"
        _download_verified(bspec["url"], archive, bspec["sha256"], code="ASR_BACKEND_DOWNLOAD_FAILED")
        try:
            with zipfile.ZipFile(archive) as zf:
                _safe_extract_zip(zf, dest)
        finally:
            archive.unlink(missing_ok=True)
        matches = list(dest.rglob(bspec["expected"]))
        if not matches:
            raise AgentCutError("ASR_BACKEND_INSTALL_FAILED", "Official whisper.cpp archive did not contain whisper-cli.exe", destination=str(dest))
        installed_binary = str(matches[0].resolve())
    elif not model_only and not installed_binary and not sysname.startswith("win"):
        raise AgentCutError(
            "ASR_BINARY_INSTALL_UNSUPPORTED",
            "The verified one-command binary installer currently targets Windows x64; the model is already installed persistently.",
            platform=sysname, model=str(model_path),
            recovery="Install whisper-cli with your platform package/build method, or set AGENTCUT_WHISPER. The model will not need to be downloaded again.",
        )

    return {
        "backend": "whisper.cpp", "version": spec["version"], "profile": profile,
        "executable": installed_binary, "model": str(model_path.resolve()),
        "binary_reused": binary_reused, "model_reused": model_reused,
        "persistent_root": str(base), "ready": bool(installed_binary and model_path.exists()),
        "license": spec["license"], "homepage": spec["homepage"],
    }

def subtitle_read_units(text: str) -> float:
    value = str(text or "").strip()
    cjk = len(re.findall(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", value))
    latin = len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?", value))
    punctuation = len(re.findall(r"[，。！？!?；;：:]", value))
    return float(cjk + latin * 1.15 + punctuation * 0.18)

def fit_subtitle_layout(primary: str, secondary: str | None, duration: float, *, font_size: int = 54, secondary_font_scale: float = 0.72) -> dict:
    """Deterministic readability-first layout advice; it never rewrites translation text."""
    primary = str(primary or "").strip(); secondary = str(secondary or "").strip()
    duration = max(0.25, float(duration))
    has_cjk = bool(re.search(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", primary))
    p_chars = len(primary.replace("\n", "")); s_chars = len(secondary.replace("\n", ""))
    units = subtitle_read_units(primary) + subtitle_read_units(secondary)
    density = units / duration
    primary_wrap = 18 if has_cjk else 32
    secondary_wrap = 34
    sec_scale = float(secondary_font_scale)
    size = int(font_size)
    level = "normal"
    if secondary:
        if p_chars + s_chars > 68 or density > 8.8:
            level = "dense"; primary_wrap = 16 if has_cjk else 28; secondary_wrap = 30; sec_scale = min(sec_scale, 0.64)
        if p_chars + s_chars > 92 or density > 12.5:
            level = "very_dense"; primary_wrap = 14 if has_cjk else 25; secondary_wrap = 26; sec_scale = min(sec_scale, 0.57); size = max(42, int(round(size * 0.94)))
        if p_chars + s_chars > 118 or density > 16.5:
            level = "split_recommended"; primary_wrap = 13 if has_cjk else 23; secondary_wrap = 23; sec_scale = min(sec_scale, 0.53); size = max(40, int(round(size * 0.90)))
    elif p_chars > 34 or density > 9.5:
        level = "dense"; primary_wrap = 16 if has_cjk else 28
    return {
        "font_size": size, "max_line_chars": primary_wrap, "secondary_max_line_chars": secondary_wrap if secondary else None,
        "secondary_font_scale": round(sec_scale, 3), "layout_density": round(density, 3), "layout_level": level,
        "auto_fit": True,
    }

ASR_EXECUTABLE_CANDIDATES = (
    "whisper-cli", "whisper-cli.exe", "whisper", "whisper.exe", "main", "main.exe",
)


def _resolve_executable(value: str | None) -> str | None:
    if not value:
        return None
    p = Path(value).expanduser()
    if p.exists() and p.is_file():
        return str(p.resolve())
    found = shutil.which(str(value))
    return found


def discover_whisper_cli() -> str | None:
    explicit = _resolve_executable(os.environ.get("AGENTCUT_WHISPER"))
    if explicit:
        return explicit
    for candidate in ASR_EXECUTABLE_CANDIDATES:
        found = shutil.which(candidate)
        if found:
            return found
    root = Path(os.environ.get("AGENTCUT_BACKEND_ROOT", Path.home() / ".agentcut" / "backends"))
    for rel in (
        "whisper/whisper-cli", "whisper/whisper-cli.exe",
        "whisper/build/bin/whisper-cli", "whisper/build/bin/Release/whisper-cli.exe",
    ):
        p = root / rel
        if p.exists() and p.is_file():
            return str(p.resolve())
    whisper_root = root / "whisper"
    if whisper_root.exists():
        for name in ("whisper-cli.exe", "whisper-cli", "whisper.exe", "whisper"):
            matches = list(whisper_root.rglob(name))
            if matches:
                return str(matches[0].resolve())
    return None


def discover_whisper_model(model: str | None = None) -> str | None:
    if model:
        p = Path(model).expanduser()
        if p.exists() and p.is_file():
            return str(p.resolve())
        raise AgentCutError("ASR_MODEL_NOT_FOUND", "Whisper model file does not exist", model=str(model))
    env = os.environ.get("AGENTCUT_WHISPER_MODEL")
    if env:
        p = Path(env).expanduser()
        if p.exists() and p.is_file():
            return str(p.resolve())
    root = Path(os.environ.get("AGENTCUT_BACKEND_ROOT", Path.home() / ".agentcut" / "backends")) / "whisper" / "models"
    for name in ("ggml-tiny-q5_1.bin", "ggml-base-q5_1.bin", "ggml-base.bin", "ggml-small.bin", "ggml-tiny.bin", "ggml-base.en.bin", "ggml-tiny.en.bin"):
        p = root / name
        if p.exists() and p.is_file():
            return str(p.resolve())
    return None


def asr_status() -> dict:
    exe = discover_whisper_cli()
    model = discover_whisper_model()
    return {
        "backend": "whisper.cpp",
        "installed": bool(exe),
        "ready": bool(exe and model),
        "executable": exe,
        "model": model,
        "language_detection": bool(exe and model),
        "translate_to_english": bool(exe and model),
        "note": "ASR is optional. `agentcut asr-install --accept-third-party` performs a persistent Windows x64 setup; external/newer whisper-cli paths still override it.",
        "installer": {"profile": "tiny-q5_1", "model_approx_mib": 31, "persistent": True, "windows_x64_one_command": True},
    }


def _extract_wav(source: Path, target: Path) -> None:
    ffmpeg = ensure_binary("ffmpeg")
    cp = subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target)],
        text=True, capture_output=True, check=False,
    )
    if cp.returncode != 0 or not target.exists() or target.stat().st_size <= 44:
        raise AgentCutError("ASR_AUDIO_EXTRACT_FAILED", "Could not convert source to 16 kHz mono WAV", source=str(source), detail=(cp.stderr or cp.stdout or "")[-1200:])


def _time_seconds(value) -> float:
    # whisper.cpp JSON currently uses millisecond integer timestamps in t0/t1 on some builds,
    # while other JSON shapes expose floating seconds. Accept both deterministically.
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if abs(v) > 1000:
        return v / 1000.0
    return v


def _parse_whisper_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AgentCutError("ASR_OUTPUT_INVALID", "Whisper JSON output could not be parsed", path=str(path), detail=str(exc)) from exc
    language = None
    if isinstance(data, dict):
        language = ((data.get("result") or {}).get("language") if isinstance(data.get("result"), dict) else None) or data.get("language")
        rows = data.get("transcription") or data.get("segments") or []
    elif isinstance(data, list):
        rows = data
    else:
        rows = []
    segments = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        text = str(row.get("text", row.get("content", ""))).strip()
        if not text:
            continue
        offsets = row.get("offsets") if isinstance(row.get("offsets"), dict) else {}
        if offsets and offsets.get("from") is not None:
            start = float(offsets.get("from", 0)) / 1000.0
            end = float(offsets.get("to", offsets.get("from", 0))) / 1000.0
        else:
            start = _time_seconds(row.get("start", row.get("t0", 0)))
            end = _time_seconds(row.get("end", row.get("t1", start)))
        if end <= start:
            end = start + 0.01
        segments.append({"index": idx, "start": round(start, 3), "end": round(end, 3), "text": text})
    if not segments:
        raise AgentCutError("ASR_EMPTY_RESULT", "Whisper produced no timestamped transcription segments", path=str(path))
    return {"language": language, "segments": segments}


def transcribe_media(
    source: str | Path, *, model: str | None = None, language: str = "auto", translate_to_english: bool = False,
    threads: int | None = None, executable: str | None = None,
) -> dict:
    src = Path(source).expanduser().resolve()
    if not src.exists() or not src.is_file():
        raise AgentCutError("FILE_NOT_FOUND", "ASR source does not exist", path=str(src))
    exe = _resolve_executable(executable) or discover_whisper_cli()
    if not exe:
        raise AgentCutError("ASR_BACKEND_MISSING", "whisper.cpp whisper-cli is not installed", recovery="Install whisper.cpp and set AGENTCUT_WHISPER, or place it under ~/.agentcut/backends/whisper.")
    model_path = discover_whisper_model(model)
    if not model_path:
        raise AgentCutError("ASR_MODEL_MISSING", "No whisper.cpp model is configured", recovery="Set AGENTCUT_WHISPER_MODEL to a ggml model file. tiny/base are suitable deployment defaults.")
    with tempfile.TemporaryDirectory(prefix="agentcut_asr_") as td:
        td = Path(td)
        wav = td / "input.wav"
        _extract_wav(src, wav)
        out_base = td / "transcript"
        cmd = [exe, "-m", model_path, "-f", str(wav), "-oj", "-of", str(out_base), "-np", "-l", str(language or "auto")]
        if translate_to_english:
            cmd.append("-tr")
        if threads is not None:
            cmd += ["-t", str(max(1, int(threads)))]
        cp = subprocess.run(cmd, text=True, capture_output=True, check=False)
        out_json = out_base.with_suffix(".json")
        # Some whisper.cpp builds historically return exit code 0 even when decoding failed.
        # Treat a missing/empty JSON product as failure regardless of process code.
        if not out_json.exists() or out_json.stat().st_size == 0:
            raise AgentCutError(
                "ASR_RUN_FAILED", "whisper.cpp did not produce JSON output", executable=exe, returncode=cp.returncode,
                detail=((cp.stderr or "") + "\n" + (cp.stdout or ""))[-1600:],
            )
        parsed = _parse_whisper_json(out_json)
        parsed.update({"backend": "whisper.cpp", "model": model_path, "translated_to_english": bool(translate_to_english), "source": str(src)})
        return parsed


def align_secondary(primary: list[dict], secondary: list[dict]) -> list[str | None]:
    """Align translated segments to primary timestamps by overlap, not fragile list index."""
    out: list[str | None] = []
    for p in primary:
        ps, pe = float(p["start"]), float(p["end"])
        best_text, best_score = None, 0.0
        for s in secondary:
            ss, se = float(s["start"]), float(s["end"])
            overlap = max(0.0, min(pe, se) - max(ps, ss))
            union = max(pe, se) - min(ps, ss)
            score = overlap / union if union > 1e-9 else 0.0
            if score > best_score:
                best_score, best_text = score, str(s.get("text", "")).strip() or None
        out.append(best_text if best_score >= 0.08 else None)
    return out


def parse_srt_time(value: str) -> float:
    m = re.match(r"\s*(\d+):(\d{2}):(\d{2})[,.](\d{3})\s*$", value)
    if not m:
        raise AgentCutError("SUBTITLE_PARSE_FAILED", "Invalid SRT timestamp", timestamp=value)
    h, mnt, sec, ms = map(int, m.groups())
    return h * 3600 + mnt * 60 + sec + ms / 1000.0


def parse_srt(path: str | Path) -> list[dict]:
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    blocks = re.split(r"\n\s*\n", text.strip())
    rows = []
    for block in blocks:
        lines = [x.rstrip() for x in block.split("\n") if x.strip()]
        if len(lines) < 2:
            continue
        time_idx = 1 if re.fullmatch(r"\d+", lines[0].strip()) else 0
        if time_idx >= len(lines) or "-->" not in lines[time_idx]:
            continue
        a, b = [x.strip() for x in lines[time_idx].split("-->", 1)]
        start, end = parse_srt_time(a), parse_srt_time(b.split()[0])
        body = "\n".join(lines[time_idx + 1:]).strip()
        if body and end > start:
            rows.append({"start": round(start, 3), "end": round(end, 3), "text": body})
    if not rows:
        raise AgentCutError("SUBTITLE_PARSE_FAILED", "No subtitle cues found in SRT", path=str(p))
    return rows
