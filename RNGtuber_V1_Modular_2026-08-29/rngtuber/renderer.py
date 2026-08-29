from __future__ import annotations

import math
import time
from dataclasses import replace

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .assets import CharacterAssets, LayerSpec, SpriteAsset
from .config import ConfigStore
from .model import (
    AvatarState,
    LayerTransform,
    Spring2D,
    apply_group_transform,
    approach,
    scale_transform_about_center,
    smootherstep,
)


class AvatarCanvas(QWidget):
    """Renderer for fixed outfit bases plus independent transformable sprites."""

    def __init__(self, assets: CharacterAssets, config: ConfigStore, state: AvatarState, parent=None) -> None:
        super().__init__(parent)
        self.assets = assets
        self.config = config
        self.state = state.normalized()
        self._last_time = time.monotonic()
        self._blink_amount = 0.0
        self._mouth_amount = 0.0
        self._gaze = Spring2D()
        self._gaze_x = self._gaze_y = 0.0
        self._previous_expression = self.state.expression
        self._expression_progress = 1.0
        self._previous_outfit = self.state.outfit
        self._outfit_progress = 1.0
        self.selected_layer: str | None = None
        self.selected_group: str | None = None
        self._layers_by_id = {layer.layer_id: layer for layer in self.assets.layers}
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def set_state(self, state: AvatarState) -> None:
        normalized = state.normalized()
        if normalized.outfit != self.state.outfit:
            self._previous_outfit = self.state.outfit
            self._outfit_progress = 0.0
        if normalized.expression != self.state.expression:
            self._previous_expression = self.state.expression
            self._expression_progress = 0.0
        self.state = normalized
        self.update()

    def set_selected_layer(self, layer_id: str | None) -> None:
        self.selected_layer = layer_id
        if layer_id is not None:
            self.selected_group = None
        self.update()

    def set_selected_group(self, group_id: str | None) -> None:
        self.selected_group = group_id
        if group_id is not None:
            self.selected_layer = None
        self.update()

    def set_calibration_preview(self, enabled: bool, base_opacity: float | None = None) -> None:
        preview = self.config.data.setdefault("calibration_preview", {})
        preview["enabled"] = bool(enabled)
        if base_opacity is not None:
            preview["base_opacity"] = max(0.05, min(1.0, float(base_opacity)))
        self.update()

    def effective_transform(self, outfit: str, layer_id: str, expression: str | None = None) -> LayerTransform:
        expression = expression or self.state.expression
        default = self.assets.default_transform(outfit, layer_id, expression)
        override = self.config.calibration_for(outfit, layer_id)
        return default.merged(override)

    def effective_group_transform(self, outfit: str, group_id: str) -> LayerTransform:
        default = self.assets.default_group_transform(outfit, group_id)
        override = self.config.group_calibration_for(outfit, group_id)
        if override:
            return default.merged(override)

        if group_id in {"eye_left", "eye_right"} and bool(self.config.data.get("eye_auto_level_defaults", True)):
            pair_overrides = self.config.data.get("group_calibration", {}).get(outfit, {})
            if not pair_overrides.get("eye_left") and not pair_overrides.get("eye_right"):
                left = self.assets.default_group_transform(outfit, "eye_left")
                right = self.assets.default_group_transform(outfit, "eye_right")
                return replace(default, y=(left.y + right.y) * 0.5)
        return default

    def save_group_transform(self, outfit: str, group_id: str, transform: LayerTransform) -> None:
        self.config.set_group_calibration(outfit, group_id, transform.to_dict())
        self.update()

    def reset_group_transform(self, outfit: str, group_id: str) -> None:
        self.config.reset_group_calibration(outfit, group_id)
        self.update()

    def save_transform(self, outfit: str, layer_id: str, transform: LayerTransform) -> None:
        self.config.set_calibration(outfit, layer_id, transform.to_dict())
        self.update()

    def reset_transform(self, outfit: str, layer_id: str) -> None:
        self.config.reset_calibration(outfit, layer_id)
        self.update()

    def _tick(self) -> None:
        now = time.monotonic()
        dt = max(0.001, min(0.05, now - self._last_time))
        self._last_time = now
        blink_target = 1.0 if self.state.blinking else 0.0
        mouth_target = 1.0 if self.state.talking else 0.0
        self._blink_amount = approach(self._blink_amount, blink_target, 12.0 if blink_target else 8.5, dt)
        self._mouth_amount = approach(self._mouth_amount, mouth_target, 8.5 if mouth_target else 5.5, dt)
        self._expression_progress = approach(self._expression_progress, 1.0, 4.8, dt)
        self._outfit_progress = approach(self._outfit_progress, 1.0, 3.6, dt)
        self._update_gaze(dt)
        self.update()

    def _update_gaze(self, dt: float) -> None:
        if not bool(self.config.data.get("eye_tracking_enabled", True)):
            target_x = target_y = 0.0
        else:
            cursor = QCursor.pos()
            face_global = self.mapToGlobal(QPointF(self.width() * 0.5, self.height() * 0.105).toPoint())
            dx = (cursor.x() - face_global.x()) / max(180.0, self.width() * 1.2)
            dy = (cursor.y() - face_global.y()) / max(180.0, self.height() * 0.55)
            length = math.hypot(dx, dy)
            dead_zone = 0.075
            if length <= dead_zone:
                dx = dy = 0.0
            else:
                normalized = min(1.0, (length - dead_zone) / (1.0 - dead_zone))
                dx, dy = dx / length * normalized, dy / length * normalized
            target_x, target_y = dx, dy
        gaze_x, gaze_y = self._gaze.update(target_x, target_y, dt, stiffness=38.0, damping=13.5)
        length = math.hypot(gaze_x, gaze_y)
        if length > 1.0:
            gaze_x, gaze_y = gaze_x / length, gaze_y / length
        self._gaze_x, self._gaze_y = gaze_x, gaze_y

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform, True)
        if self.config.data.get("render_mode") == "green":
            painter.fillRect(self.rect(), QColor(0, 255, 0))
        elif bool(self.config.data.get("calibration_preview", {}).get("enabled", False)):
            painter.fillRect(self.rect(), QColor(24, 25, 31, 210))
            self._draw_grid(painter)

        cw, ch = self.assets.canvas_width, self.assets.canvas_height
        scale = min(self.width() / max(1, cw), self.height() / max(1, ch))
        left = (self.width() - cw * scale) * 0.5
        top = (self.height() - ch * scale) * 0.5
        painter.save()
        painter.translate(left, top)
        painter.scale(scale, scale)

        t = time.monotonic()
        breathing = bool(self.config.data.get("breathing_enabled", True))
        wave = math.sin(t * 1.65) if breathing else 0.0
        sway = math.sin(t * 0.72 + 0.8) if breathing else 0.0
        painter.translate(cw * 0.5, ch * 0.62)
        painter.rotate(sway * 0.22)
        painter.scale(1.0 + wave * 0.0018, 1.0 + wave * 0.0042)
        painter.translate(-cw * 0.5, -ch * 0.62 - wave * 1.4)

        if self._outfit_progress < 1.0 and self._previous_outfit in self.assets.bases:
            self._draw_scene(painter, self._previous_outfit, self._previous_expression, 1.0)
            self._draw_scene(painter, self.state.outfit, self.state.expression, smootherstep(self._outfit_progress))
        else:
            self._draw_scene(painter, self.state.outfit, self.state.expression, 1.0)
        painter.restore()
        painter.end()

    def _draw_grid(self, painter: QPainter) -> None:
        painter.save()
        painter.setPen(QPen(QColor(255, 255, 255, 22), 1.0))
        step = max(16, self.width() // 16)
        for x in range(0, self.width(), step):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), step):
            painter.drawLine(0, y, self.width(), y)
        painter.restore()

    def _transform_for_draw(self, outfit: str, layer: LayerSpec, expression: str) -> LayerTransform:
        current = self.effective_transform(outfit, layer.layer_id, expression)
        if outfit == self.state.outfit and self._expression_progress < 1.0:
            previous = self.effective_transform(outfit, layer.layer_id, self._previous_expression)
            current = LayerTransform.lerp(previous, current, self._expression_progress)
        registration = layer.registration
        current = replace(
            current,
            x=current.x + registration.x,
            y=current.y + registration.y,
            scale_x=current.scale_x * registration.scale_x,
            scale_y=current.scale_y * registration.scale_y,
            rotation=current.rotation + registration.rotation,
            opacity=current.opacity * registration.opacity,
            z=current.z + registration.z,
        )
        sprite = self.assets.sprite_for(outfit, expression, layer)
        if sprite is not None and layer.group_id:
            current = apply_group_transform(
                current,
                self.effective_group_transform(outfit, layer.group_id),
                self.assets.group_pivot(outfit, layer.group_id),
                (sprite.width, sprite.height),
            )
        return replace(current, z=current.z + layer.z)

    @staticmethod
    def _ramp(value: float, start: float, end: float) -> float:
        return smootherstep((value - start) / max(0.001, end - start))

    def _role_opacity(self, role: str, expression: str) -> float:
        blink = max(0.0, min(1.0, self._blink_amount))
        mouth_bias = float(self.assets.spec.get("expressions", {}).get(expression, {}).get("mouth_bias", 0.0))
        mouth = max(max(0.0, min(1.0, self._mouth_amount)), mouth_bias)
        if role in {"eye_white", "iris", "eyelid_upper", "eyelid_lower", "eye_aux"}:
            return 1.0 - self._ramp(blink, 0.34, 0.82)
        if role == "eyelid_closed":
            return self._ramp(blink, 0.16, 0.72)
        if role == "mouth_closed":
            return 1.0 - self._ramp(mouth, 0.26, 0.62)
        if role == "mouth_open":
            return self._ramp(mouth, 0.38, 0.74)
        return 1.0

    def _draw_scene(self, painter: QPainter, outfit: str, expression: str, scene_opacity: float) -> None:
        base = self.assets.bases.get(outfit)
        if base is None:
            return
        calibration = bool(self.config.data.get("calibration_preview", {}).get("enabled", False))
        base_opacity = float(self.config.data.get("calibration_preview", {}).get("base_opacity", 0.55)) if calibration else 1.0
        painter.save()
        painter.setOpacity(scene_opacity * base_opacity)
        painter.drawPixmap(QRectF(0, 0, self.assets.canvas_width, self.assets.canvas_height), base, QRectF(base.rect()))
        painter.restore()

        prepared: list[tuple[float, LayerSpec, LayerTransform]] = []
        for layer in self.assets.layers:
            transform = self._transform_for_draw(outfit, layer, expression)
            prepared.append((transform.z, layer, transform))
        for _, layer, transform in sorted(prepared, key=lambda item: item[0]):
            self._draw_layer(painter, outfit, layer, transform, expression, scene_opacity, calibration)

    def _motion_transform(self, transform: LayerTransform, layer: LayerSpec, sprite: SpriteAsset) -> LayerTransform:
        blink = smootherstep(self._blink_amount)
        mouth = smootherstep(self._mouth_amount)
        size = (sprite.width, sprite.height)
        if layer.role in {"eye_white", "iris"}:
            return scale_transform_about_center(transform, size, 1.0, 1.0 - blink * 0.78)
        if layer.role in {"eyelid_upper", "eyelid_lower"}:
            return scale_transform_about_center(transform, size, 1.0, 1.0 - blink * 0.52)
        if layer.role == "eyelid_closed":
            return scale_transform_about_center(transform, size, 1.0, 0.72 + blink * 0.28)
        if layer.role == "mouth_open":
            return scale_transform_about_center(transform, size, 0.94 + mouth * 0.06, 0.72 + mouth * 0.28)
        if layer.role == "mouth_closed":
            return scale_transform_about_center(transform, size, 1.0, 1.0 - mouth * 0.08)
        return transform

    def _iris_socket_target(self, outfit: str, expression: str, layer: LayerSpec) -> tuple[float, float] | None:
        side = "left" if layer.layer_id.endswith("_left") else "right" if layer.layer_id.endswith("_right") else ""
        if not side:
            return None
        white_layer = self._layers_by_id.get(f"eye_white_{side}")
        if white_layer is None:
            return None
        white_sprite = self.assets.sprite_for(outfit, expression, white_layer)
        if white_sprite is None:
            return None
        white_transform = self._transform_for_draw(outfit, white_layer, expression)
        white_transform = self._motion_transform(white_transform, white_layer, white_sprite)
        cx = white_transform.x + white_sprite.width * white_transform.scale_x * 0.5
        cy = white_transform.y + white_sprite.height * white_transform.scale_y * 0.5
        outward = float(self.config.data.get("iris_outward_px", 1.2))
        cx += -outward if side == "left" else outward
        return cx, cy

    def _draw_layer(
        self,
        painter: QPainter,
        outfit: str,
        layer: LayerSpec,
        transform: LayerTransform,
        expression: str,
        scene_opacity: float,
        calibration: bool,
    ) -> None:
        sprite = self.assets.sprite_for(outfit, expression, layer)
        if sprite is None:
            return
        transform = self._motion_transform(transform, layer, sprite)
        role_opacity = self._role_opacity(layer.role, expression)
        opacity = transform.opacity * role_opacity * scene_opacity
        if opacity <= 0.001:
            return

        width, height = sprite.width, sprite.height
        x, y = transform.x, transform.y
        if layer.role == "iris":
            target = self._iris_socket_target(outfit, expression, layer)
            lock = max(0.0, min(1.0, float(self.config.data.get("iris_socket_lock", 0.86))))
            if target is not None and lock > 0.0:
                current_cx = x + width * transform.scale_x * 0.5
                current_cy = y + height * transform.scale_y * 0.5
                x += (target[0] - current_cx) * lock
                y += (target[1] - current_cy) * lock
            gaze_visibility = 1.0 - smootherstep(self._blink_amount)
            strength = max(0.0, min(1.0, float(self.config.data.get("eye_tracking_strength", 0.62))))
            x += self._gaze_x * layer.eye_limit_x * gaze_visibility * strength
            y += self._gaze_y * layer.eye_limit_y * gaze_visibility * strength

        painter.save()
        painter.setOpacity(opacity)
        painter.translate(x + width * transform.scale_x * 0.5, y + height * transform.scale_y * 0.5)
        painter.rotate(transform.rotation)
        painter.scale(transform.scale_x, transform.scale_y)
        painter.drawPixmap(QPointF(-width * 0.5, -height * 0.5), sprite.pixmap)
        selected = layer.layer_id == self.selected_layer or (
            self.selected_group is not None and layer.group_id == self.selected_group
        )
        if calibration and selected:
            painter.setOpacity(1.0)
            painter.setPen(QPen(QColor(71, 232, 255, 245), max(1.2, 2.0 / max(transform.scale_x, transform.scale_y))))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRectF(-width * 0.5, -height * 0.5, width, height))
            painter.drawLine(QPointF(-8, 0), QPointF(8, 0))
            painter.drawLine(QPointF(0, -8), QPointF(0, 8))
        painter.restore()
