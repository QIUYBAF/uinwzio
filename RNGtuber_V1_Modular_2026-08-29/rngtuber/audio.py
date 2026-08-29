from __future__ import annotations

import logging
import math
import threading
import time
from typing import Any

import numpy as np


class MicLevel:
    """Non-blocking microphone meter that degrades to silence on any failure."""

    def __init__(self, *, demo: bool = False, enabled: bool = True, device_name: str = "") -> None:
        self.demo = bool(demo)
        self.enabled = bool(enabled)
        self.device_name = str(device_name)
        self.raw_db = -80.0
        self.smoothed_db = -80.0
        self.status = "demo" if demo else "stopped"
        self.error = ""
        self._stream: Any = None
        self._lock = threading.Lock()
        self._callback_db = -80.0
        self._started_at = time.monotonic()
        if self.enabled and not self.demo:
            self.start(self.device_name)

    @staticmethod
    def devices() -> list[str]:
        try:
            import sounddevice as sd

            result: list[str] = []
            for item in sd.query_devices():
                if int(item.get("max_input_channels", 0)) > 0:
                    result.append(str(item.get("name", "Unknown input")))
            return result
        except Exception:
            return []

    def _resolve_device(self, requested: str) -> int | None:
        if not requested:
            return None
        try:
            import sounddevice as sd

            for index, item in enumerate(sd.query_devices()):
                if int(item.get("max_input_channels", 0)) > 0 and str(item.get("name", "")) == requested:
                    return index
        except Exception:
            pass
        return None

    def start(self, device_name: str = "") -> bool:
        self.stop()
        self.device_name = str(device_name)
        if self.demo:
            self.status = "demo"
            return True
        if not self.enabled:
            self.status = "disabled"
            return False
        try:
            import sounddevice as sd

            device = self._resolve_device(self.device_name)

            def callback(indata, frames, callback_time, status) -> None:
                del frames, callback_time
                if status:
                    logging.debug("PortAudio callback status: %s", status)
                samples = np.asarray(indata, dtype=np.float32)
                rms = float(np.sqrt(np.mean(samples * samples))) if samples.size else 0.0
                db = 20.0 * math.log10(max(rms, 1e-6))
                with self._lock:
                    self._callback_db = max(-80.0, min(0.0, db))

            self._stream = sd.InputStream(
                device=device,
                channels=1,
                dtype="float32",
                blocksize=512,
                callback=callback,
            )
            self._stream.start()
            self.status = "running"
            self.error = ""
            return True
        except Exception as exc:
            self._stream = None
            self.status = "unavailable"
            self.error = str(exc)
            logging.warning("Microphone unavailable; continuing silently: %s", exc)
            return False

    def stop(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                logging.exception("Microphone shutdown failed")
        if not self.demo:
            self.status = "disabled" if not self.enabled else "stopped"

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        if self.enabled:
            self.start(self.device_name)
        else:
            self.stop()
            self.raw_db = self.smoothed_db = -80.0

    def update(self) -> None:
        if self.demo:
            t = time.monotonic() - self._started_at
            active = int(t * 1.4) % 3 != 0
            self.raw_db = -27.0 + 5.0 * math.sin(t * 8.0) if active else -58.0
        elif self._stream is not None:
            with self._lock:
                self.raw_db = self._callback_db
        else:
            self.raw_db = -80.0
        # Fast attack, slower release keeps the meter readable without adding
        # extra mouth-state toggles (those are handled by MouthController).
        coefficient = 0.42 if self.raw_db > self.smoothed_db else 0.12
        self.smoothed_db += (self.raw_db - self.smoothed_db) * coefficient

    @property
    def level_01(self) -> float:
        return max(0.0, min(1.0, (self.smoothed_db + 60.0) / 50.0))

