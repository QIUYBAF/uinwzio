from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CHARACTER = ROOT / "assets" / "characters" / "zhou_wanqing"


def test_character_schema_and_runtime_assets() -> None:
    spec = json.loads((CHARACTER / "character.json").read_text(encoding="utf-8"))
    assert spec["canvas"] == [1024, 1536]
    assert set(spec["outfits"]) == {"casual", "cos"}
    assert set(spec["expressions"]) == {"neutral", "happy", "unamused", "surprised"}
    layer_ids = {item["id"] for item in spec["layers"]}
    assert {"iris_left", "iris_right", "mouth_open", "mouth_closed"} <= layer_ids
    for outfit in spec["outfits"].values():
        path = CHARACTER / outfit["base"]
        image = Image.open(path)
        assert image.mode == "RGBA" and image.size == (1024, 1536)
        assert image.getchannel("A").getbbox()
    for relative in spec["sprites"].values():
        image = Image.open(CHARACTER / relative)
        assert image.mode == "RGBA"
        assert image.width > 0 and image.height > 0
        assert image.getchannel("A").getbbox()


def test_every_outfit_has_every_layer_transform() -> None:
    spec = json.loads((CHARACTER / "character.json").read_text(encoding="utf-8"))
    ids = {item["id"] for item in spec["layers"]}
    for outfit in spec["outfits"].values():
        assert set(outfit["transforms"]) == ids
        for transform in outfit["transforms"].values():
            assert 0.02 <= transform.get("scale_x", 1.0) <= 8.0
            assert 0.02 <= transform.get("scale_y", 1.0) <= 8.0


def test_asset_qa_report_is_clean() -> None:
    report = json.loads((CHARACTER / "ASSET_QA.json").read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["issues"] == []


def test_expression_sprite_variants_are_complete() -> None:
    spec = json.loads((CHARACTER / "character.json").read_text(encoding="utf-8"))
    variants = spec.get("sprite_variants", {})
    expected_layers = {
        "eye_white_left", "eye_white_right", "iris_left", "iris_right",
        "eyeliner_open_left", "eyeliner_open_right",
        "eyeliner_lower_left", "eyeliner_lower_right",
        "eyelid_closed_left", "eyelid_closed_right",
        "eyebrow_left", "eyebrow_right", "mouth_closed", "mouth_open",
    }
    for outfit in ("casual", "cos"):
        for expression in ("neutral", "happy", "unamused", "surprised"):
            mapping = variants[outfit][expression]
            assert set(mapping) == expected_layers
            for sprite_id in mapping.values():
                assert sprite_id in spec["sprites"]

