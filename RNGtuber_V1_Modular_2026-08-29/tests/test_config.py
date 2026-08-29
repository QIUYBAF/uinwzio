from __future__ import annotations

import json

from rngtuber.config import ConfigStore


def test_corrupt_config_recovers_to_defaults(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{broken", encoding="utf-8")
    store = ConfigStore(path)
    assert store.data["outfit"] == "casual"
    assert store.data["expression"] == "neutral"


def test_calibration_persists_per_outfit_and_layer(tmp_path) -> None:
    path = tmp_path / "config.json"
    store = ConfigStore(path)
    store.set_calibration("casual", "iris_left", {"x": 444.5, "scale_x": 0.5})
    store.set_calibration("cos", "iris_left", {"x": 449.0, "scale_x": 0.6})
    restored = ConfigStore(path)
    assert restored.calibration_for("casual", "iris_left")["x"] == 444.5
    assert restored.calibration_for("cos", "iris_left")["x"] == 449.0
    assert json.loads(path.read_text(encoding="utf-8"))["calibration"]["cos"]["iris_left"]["scale_x"] == 0.6
