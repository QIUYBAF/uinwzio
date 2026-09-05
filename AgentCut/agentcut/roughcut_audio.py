"""Optional FFmpeg audio-activity detector, using only Python's standard library."""
from __future__ import annotations

import array
import math
import sys
import wave
from pathlib import Path

from .roughcut import media_run, number
from .util import ensure_binary, hash_obj


class AudioActivityDetector:
    def __init__(self, *, threshold_db=-28, audio_stream=0):
        self.threshold = number(threshold_db, "threshold_db", -100, 0)
        self.audio_stream = int(number(audio_stream, "audio_stream", 0))
        self.ffmpeg = ensure_binary("ffmpeg")
        stat = Path(self.ffmpeg).stat()
        self.cache_key = hash_obj({"detector": "audio-rms-v1", "threshold": self.threshold,
                                   "stream": self.audio_stream, "ffmpeg": self.ffmpeg,
                                   "binary_size": stat.st_size, "binary_mtime": stat.st_mtime_ns})

    def analyze(self, source, start, end, scratch):
        wav = scratch / "audio.wav"
        media_run([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-threads", "2",
                   "-ss", str(start), "-i", str(source), "-t", str(end - start), "-map", f"0:a:{self.audio_stream}",
                   "-vn", "-af", "aresample=async=1:first_pts=0", "-ac", "1", "-ar", "8000",
                   "-c:a", "pcm_s16le", str(wav)], timeout=max(120, (end - start) * 4))
        events, offset = [], start
        with wave.open(str(wav), "rb") as audio:
            while raw := audio.readframes(4000):
                samples = array.array("h", raw)
                if sys.byteorder != "little":
                    samples.byteswap()
                stop = min(end, offset + len(samples) / 8000)
                rms = math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768
                db = 20 * math.log10(max(rms, 1e-6))
                if db >= self.threshold and stop > offset:
                    score = min(1, 0.5 + (db - self.threshold) / 40)
                    if events and abs(events[-1]["end"] - offset) < 1e-6:
                        events[-1]["end"] = stop
                        events[-1]["score"] = max(events[-1]["score"], score)
                    else:
                        events.append({"start": offset, "end": stop, "score": score, "label": "audio_activity"})
                offset = stop
        return events
