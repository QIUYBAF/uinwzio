from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np

from .errors import AgentCutError
from .util import ensure_binary


def _decode_mono(path: Path, *, sample_rate: int = 22050) -> np.ndarray:
    ffmpeg = ensure_binary("ffmpeg")
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "pipe:1",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise AgentCutError(
            "AUDIO_ANALYSIS_FAILED", "FFmpeg could not decode audio for rhythm analysis",
            path=str(path), stderr=proc.stderr.decode(errors="replace")[-2000:],
        )
    audio = np.frombuffer(proc.stdout, dtype=np.float32)
    if audio.size < max(256, sample_rate // 10):
        raise AgentCutError("AUDIO_ANALYSIS_FAILED", "Audio is too short for rhythm analysis", path=str(path))
    return audio


def _robust_onsets(audio: np.ndarray, sample_rate: int, *, hop: int = 512) -> tuple[np.ndarray, np.ndarray]:
    frame = 2048
    if audio.size < frame:
        return np.array([], dtype=float), np.array([], dtype=float)
    window = np.hanning(frame).astype(np.float32)
    prev = None
    flux = []
    for start in range(0, audio.size - frame + 1, hop):
        spec = np.abs(np.fft.rfft(audio[start:start + frame] * window))
        if prev is None:
            value = 0.0
        else:
            value = float(np.maximum(spec - prev, 0.0).sum())
        flux.append(value)
        prev = spec
    env = np.asarray(flux, dtype=np.float64)
    if env.size == 0:
        return np.array([], dtype=float), env
    # Normalize against a local-ish robust baseline without scipy.
    med = float(np.median(env))
    mad = float(np.median(np.abs(env - med))) + 1e-12
    norm = np.maximum((env - med) / (1.4826 * mad), 0.0)
    if norm.size >= 5:
        smooth = np.convolve(norm, np.array([0.15, 0.35, 0.35, 0.15]), mode="same")
    else:
        smooth = norm
    threshold = max(1.0, float(np.percentile(smooth, 70)))
    peaks = []
    min_gap = max(1, int(round((0.11 * sample_rate) / hop)))
    last = -min_gap
    for i in range(1, max(1, len(smooth) - 1)):
        if smooth[i] >= threshold and smooth[i] >= smooth[i - 1] and smooth[i] > smooth[i + 1]:
            if i - last >= min_gap:
                peaks.append(i)
                last = i
            elif peaks and smooth[i] > smooth[peaks[-1]]:
                peaks[-1] = i
                last = i
    times = np.asarray(peaks, dtype=float) * hop / sample_rate
    return times, smooth


def _tempo_from_envelope(env: np.ndarray, sample_rate: int, *, hop: int = 512, min_bpm: float = 55.0, max_bpm: float = 210.0) -> float | None:
    if env.size < 8 or not np.any(env > 0):
        return None
    x = env - float(np.mean(env))
    corr = np.correlate(x, x, mode="full")[len(x) - 1:]
    min_lag = max(1, int(math.floor((60.0 / max_bpm) * sample_rate / hop)))
    max_lag = min(len(corr) - 1, int(math.ceil((60.0 / min_bpm) * sample_rate / hop)))
    if max_lag <= min_lag:
        return None
    segment = corr[min_lag:max_lag + 1].copy()
    # Prefer musically useful central tempi over octave errors by a mild log-distance prior.
    bpms = 60.0 * sample_rate / (hop * np.arange(min_lag, max_lag + 1, dtype=float))
    prior = np.exp(-0.14 * np.abs(np.log2(bpms / 120.0)))
    idx = int(np.argmax(segment * prior))
    bpm = float(bpms[idx])
    return bpm if math.isfinite(bpm) else None


def analyze_audio(path: str | Path, *, sample_rate: int = 22050) -> dict:
    path = Path(path)
    audio = _decode_mono(path, sample_rate=sample_rate)
    onsets, env = _robust_onsets(audio, sample_rate)
    bpm = _tempo_from_envelope(env, sample_rate)
    # Refine the coarse autocorrelation estimate from detected onset spacing. The hop-based
    # intervals alternate around the true period, so a robust mean is less biased than a
    # single-lag peak and recovers synthetic 120 BPM references closely.
    if len(onsets) >= 4:
        diffs = np.diff(onsets)
        useful = diffs[(diffs >= 0.24) & (diffs <= 1.20)]
        if useful.size >= 3:
            med = float(np.median(useful))
            useful = useful[np.abs(useful - med) <= max(0.08, med * 0.28)]
            if useful.size:
                refined = 60.0 / float(np.mean(useful))
                while refined < 55.0:
                    refined *= 2.0
                while refined > 210.0:
                    refined /= 2.0
                bpm = refined
    duration = float(audio.size / sample_rate)
    beats: list[float] = []
    if bpm and bpm > 0:
        period = 60.0 / bpm
        if onsets.size:
            # Pick the onset whose phase explains the most other onsets.
            candidates = onsets[: min(24, len(onsets))]
            best_phase = float(candidates[0]) if len(candidates) else 0.0
            best_score = -1.0
            for c in candidates:
                phase = float(c % period)
                residual = np.abs(((onsets - phase + period / 2) % period) - period / 2)
                score = float(np.exp(-((residual / max(0.04, period * 0.12)) ** 2)).sum())
                if score > best_score:
                    best_score, best_phase = score, phase
            first = best_phase
            while first - period >= 0:
                first -= period
            t = first
            while t <= duration + 1e-9:
                if t >= 0:
                    beats.append(round(float(t), 6))
                t += period
    return {
        "version": 1,
        "sample_rate": sample_rate,
        "duration": round(duration, 6),
        "tempo_bpm": None if bpm is None else round(bpm, 3),
        "onsets": [round(float(x), 6) for x in onsets.tolist()],
        "beats": beats,
    }


def suggest_cut_points(analysis: dict, *, include_onsets: bool = True, min_gap: float = 0.16) -> list[float]:
    points = list(analysis.get("beats") or [])
    if include_onsets:
        points += list(analysis.get("onsets") or [])
    points = sorted({round(float(x), 6) for x in points if float(x) >= 0})
    out: list[float] = []
    for t in points:
        if not out or t - out[-1] >= min_gap:
            out.append(t)
        elif t in set(analysis.get("beats") or []):
            out[-1] = t
    return out
