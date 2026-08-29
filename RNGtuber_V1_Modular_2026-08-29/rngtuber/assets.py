from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtGui import QImage, QPixmap

from .config import resource_path
from .model import LayerTransform


@dataclass(frozen=True)
class SpriteAsset:
    sprite_id: str
    path: Path
    pixmap: QPixmap
    source_width: int
    source_height: int
    alpha_bbox: tuple[int, int, int, int]
    natural_x: float = 0.0
    natural_y: float = 0.0

    @property
    def width(self) -> int:
        return self.pixmap.width()

    @property
    def height(self) -> int:
        return self.pixmap.height()


@dataclass(frozen=True)
class LayerSpec:
    layer_id: str
    sprite_id: str
    role: str
    z: float
    group_id: str = ""
    eye_limit_x: float = 0.0
    eye_limit_y: float = 0.0
    registration: LayerTransform = field(default_factory=LayerTransform)


@dataclass(frozen=True)
class GroupSpec:
    group_id: str
    label: str
    pivots: dict[str, tuple[float, float]]

    def pivot_for(self, outfit: str) -> tuple[float, float]:
        return self.pivots.get(outfit, self.pivots.get("default", (0.0, 0.0)))


class CharacterAssets:
    """Loads a renderer-independent character specification and trimmed sprites."""

    def __init__(self, spec_path: Path | None = None) -> None:
        self.spec_path = Path(spec_path or resource_path("assets/characters/zhou_wanqing/character.json"))
        self.root = self.spec_path.parent
        self.spec: dict[str, Any] = json.loads(self.spec_path.read_text(encoding="utf-8"))
        canvas = self.spec.get("canvas", [1024, 1536])
        self.canvas_width, self.canvas_height = int(canvas[0]), int(canvas[1])
        self.bases: dict[str, QPixmap] = {}
        self.sprites: dict[str, SpriteAsset] = {}
        self.layers: list[LayerSpec] = []
        self.groups: list[GroupSpec] = []
        self._layers_by_id: dict[str, LayerSpec] = {}
        self._groups_by_id: dict[str, GroupSpec] = {}
        self.errors: list[str] = []
        self._load()

    def _load(self) -> None:
        for outfit, data in self.spec.get("outfits", {}).items():
            path = self.root / str(data.get("base", ""))
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                self.errors.append(f"base not readable: {path}")
            else:
                self.bases[str(outfit)] = pixmap
        for sprite_id, relative in self.spec.get("sprites", {}).items():
            path = self.root / str(relative)
            loaded = self._load_trimmed(str(sprite_id), path)
            if loaded is None:
                self.errors.append(f"sprite not readable or empty: {path}")
            else:
                self.sprites[str(sprite_id)] = loaded
        for group_id, item in self.spec.get("groups", {}).items():
            raw_pivots = item.get("pivots", {})
            pivots = {
                str(outfit): (float(value[0]), float(value[1]))
                for outfit, value in raw_pivots.items()
                if isinstance(value, (list, tuple)) and len(value) == 2
            }
            group = GroupSpec(
                group_id=str(group_id),
                label=str(item.get("label", group_id)),
                pivots=pivots,
            )
            self.groups.append(group)
            self._groups_by_id[group.group_id] = group
        for item in self.spec.get("layers", []):
            layer = LayerSpec(
                layer_id=str(item["id"]),
                sprite_id=str(item["sprite"]),
                role=str(item.get("role", "always")),
                z=float(item.get("z", 0.0)),
                group_id=str(item.get("group", "")),
                eye_limit_x=float(item.get("eye_limit_x", 0.0)),
                eye_limit_y=float(item.get("eye_limit_y", 0.0)),
                registration=LayerTransform.from_mapping(item.get("registration", {})),
            )
            if layer.sprite_id not in self.sprites:
                self.errors.append(f"layer {layer.layer_id} references missing sprite {layer.sprite_id}")
            if layer.group_id and layer.group_id not in self._groups_by_id:
                self.errors.append(f"layer {layer.layer_id} references missing group {layer.group_id}")
            self.layers.append(layer)
            self._layers_by_id[layer.layer_id] = layer
        if self.errors:
            for error in self.errors:
                logging.error("Character asset QA: %s", error)

    def _load_trimmed(self, sprite_id: str, path: Path) -> SpriteAsset | None:
        image = QImage(str(path)).convertToFormat(QImage.Format_RGBA8888)
        if image.isNull():
            return None
        raw = np.frombuffer(image.bits(), dtype=np.uint8, count=image.sizeInBytes())
        rows = raw.reshape(image.height(), image.bytesPerLine())
        rgba = rows[:, : image.width() * 4].reshape(image.height(), image.width(), 4)
        ys, xs = np.nonzero(rgba[..., 3] >= 8)
        if not len(xs):
            return None
        left, top = int(xs.min()), int(ys.min())
        right, bottom = int(xs.max()) + 1, int(ys.max()) + 1
        # Full-canvas AI sprites occasionally contain a few remote low-alpha
        # pixels. Ignore statistical outliers while leaving compact authored
        # sprites untouched.
        if image.width() >= self.canvas_width * 0.75 and image.height() >= self.canvas_height * 0.75 and len(xs) >= 1000:
            q_left, q_right = np.quantile(xs, (0.001, 0.999))
            q_top, q_bottom = np.quantile(ys, (0.001, 0.999))
            left = max(0, int(q_left) - 2)
            top = max(0, int(q_top) - 2)
            right = min(image.width(), int(q_right) + 3)
            bottom = min(image.height(), int(q_bottom) + 3)
        cropped = image.copy(left, top, right - left, bottom - top)
        canvas_sized = image.width() == self.canvas_width and image.height() == self.canvas_height
        return SpriteAsset(
            sprite_id=sprite_id,
            path=path,
            pixmap=QPixmap.fromImage(cropped),
            source_width=image.width(),
            source_height=image.height(),
            alpha_bbox=(left, top, right, bottom),
            natural_x=float(left if canvas_sized else 0),
            natural_y=float(top if canvas_sized else 0),
        )

    def sprite_for(self, outfit: str, expression: str, layer: LayerSpec) -> SpriteAsset | None:
        """Resolve an outfit/expression-specific sprite, falling back to the layer default."""
        sprite_id = (
            self.spec.get("sprite_variants", {})
            .get(outfit, {})
            .get(expression, {})
            .get(layer.layer_id, layer.sprite_id)
        )
        return self.sprites.get(str(sprite_id))

    def default_transform(self, outfit: str, layer_id: str, expression: str = "neutral") -> LayerTransform:
        outfit_data = self.spec.get("outfits", {}).get(outfit, {})
        base_mapping = outfit_data.get("transforms", {}).get(layer_id, {})
        layer = self._layers_by_id.get(layer_id)
        natural = LayerTransform()
        if layer is not None:
            sprite = self.sprite_for(outfit, expression, layer)
            if sprite is not None:
                natural = LayerTransform(x=sprite.natural_x, y=sprite.natural_y)
        base = LayerTransform.from_mapping(base_mapping, natural)
        variant = (
            self.spec.get("variant_transforms", {})
            .get(outfit, {})
            .get(expression, {})
            .get(layer_id, {})
        )
        current = base.merged(variant)
        expression_data = self.spec.get("expressions", {}).get(expression, {})
        override = expression_data.get("layers", {}).get(layer_id, {})
        return current.merged(override)

    def default_group_transform(self, outfit: str, group_id: str) -> LayerTransform:
        mapping = (
            self.spec.get("outfits", {})
            .get(outfit, {})
            .get("group_transforms", {})
            .get(group_id, {})
        )
        return LayerTransform.from_mapping(mapping)

    def group_pivot(self, outfit: str, group_id: str) -> tuple[float, float]:
        group = self._groups_by_id.get(group_id)
        return group.pivot_for(outfit) if group is not None else (0.0, 0.0)

    def layer_for(self, layer_id: str) -> LayerSpec | None:
        return self._layers_by_id.get(layer_id)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "character_id": self.spec.get("id", "unknown"),
            "canvas": [self.canvas_width, self.canvas_height],
            "outfits": sorted(self.bases),
            "sprites_loaded": sorted(self.sprites),
            "layers": [layer.layer_id for layer in self.layers],
            "groups": [group.group_id for group in self.groups],
            "errors": list(self.errors),
            "ok": not self.errors and set(self.bases) >= {"casual", "cos"},
        }

