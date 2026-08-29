from __future__ import annotations

import json
import logging
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

APP_NAME = "RNGtuber"
APP_VERSION = "1.0.0"
WINDOW_TITLE = "RNGtuber V1 Modular｜周婉晴"


def resource_path(relative: str | Path) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return root / relative


def app_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / "RNGtuberV1"
    path.mkdir(parents=True, exist_ok=True)
    return path


DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "character": "zhou_wanqing",
    "outfit": "casual",
    "expression": "neutral",
    "render_mode": "transparent",
    "click_through": False,
    "breathing_enabled": True,
    "eye_tracking_enabled": True,
    "mic_enabled": True,
    "mic_name": "",
    "mouth_open_threshold_db": -33.0,
    "mouth_close_threshold_db": -38.0,
    "input_display": "gamepad",
    "input_auto_fade": True,
    "window": {"x": -1, "y": -1, "width": 360},
    "calibration": {},
    "calibration_preview": {"enabled": False, "base_opacity": 0.55},
}


def _merge(base: dict[str, Any], incoming: dict[str, Any]) -> None:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value


class ConfigStore:
    """Atomic, self-healing user configuration.

    Calibration overrides live under ``calibration[outfit][layer_id]``.  The
    character JSON remains immutable, so a damaged user config can always be
    discarded without damaging the shipped profile.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else app_data_dir() / "config.json"
        self.data = deepcopy(DEFAULT_CONFIG)
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    _merge(self.data, loaded)
            except Exception:
                logging.exception("Config read failed; defaults retained")
        self.normalize()

    def normalize(self) -> None:
        self.data["schema_version"] = 1
        if self.data.get("outfit") not in {"casual", "cos"}:
            self.data["outfit"] = "casual"
        if self.data.get("expression") not in {"neutral", "happy", "unamused", "surprised"}:
            self.data["expression"] = "neutral"
        if self.data.get("render_mode") not in {"transparent", "green"}:
            self.data["render_mode"] = "transparent"
        if self.data.get("input_display") not in {"gamepad", "keyboard", "off"}:
            self.data["input_display"] = "gamepad"
        for key in ("click_through", "breathing_enabled", "eye_tracking_enabled", "mic_enabled", "input_auto_fade"):
            self.data[key] = bool(self.data.get(key, DEFAULT_CONFIG[key]))
        open_db = max(-60.0, min(-18.0, float(self.data.get("mouth_open_threshold_db", -33.0))))
        close_db = max(-65.0, min(-20.0, float(self.data.get("mouth_close_threshold_db", -38.0))))
        if close_db >= open_db:
            close_db = open_db - 5.0
        self.data["mouth_open_threshold_db"] = open_db
        self.data["mouth_close_threshold_db"] = close_db
        window = self.data.setdefault("window", {})
        window["width"] = max(200, min(960, int(window.get("width", 360))))
        for key in ("x", "y"):
            try:
                window[key] = int(window.get(key, -1))
            except (TypeError, ValueError):
                window[key] = -1
        preview = self.data.setdefault("calibration_preview", {})
        preview["enabled"] = bool(preview.get("enabled", False))
        preview["base_opacity"] = max(0.05, min(1.0, float(preview.get("base_opacity", 0.55))))
        if not isinstance(self.data.get("calibration"), dict):
            self.data["calibration"] = {}

    def save(self) -> None:
        self.normalize()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def calibration_for(self, outfit: str, layer_id: str) -> dict[str, float]:
        value = self.data.get("calibration", {}).get(outfit, {}).get(layer_id, {})
        return dict(value) if isinstance(value, dict) else {}

    def set_calibration(self, outfit: str, layer_id: str, values: dict[str, float]) -> None:
        outfit_map = self.data.setdefault("calibration", {}).setdefault(outfit, {})
        outfit_map[layer_id] = {str(key): float(value) for key, value in values.items()}
        self.save()

    def reset_calibration(self, outfit: str, layer_id: str) -> None:
        outfit_map = self.data.setdefault("calibration", {}).setdefault(outfit, {})
        outfit_map.pop(layer_id, None)
        self.save()

