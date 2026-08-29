from __future__ import annotations

import math
import time
from dataclasses import replace

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from .assets import CharacterAssets, LayerSpec
from .config import ConfigStore
from .model import AvatarState, LayerTransform, Spring2D, approach, smootherstep


class AvatarCanvas(QWidget):
    """Renderer for fixed outfit bases plus independent transformable sprites.

    Character files describe layers and default transforms; the renderer knows
    only generic roles (mouth, eyelid, iris).  This keeps character content out
    of the input/audio controllers and makes a second character a data change.
    """

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
            face_global = self.mapToGlobal(QPointF(self.width() * 0.5, self.height() * 0.135).toPoint())
            dx = (cursor.x() - face_global.x()) / max(180.0, self.width() * 1.2)
            dy = (cursor.y() - face_global.y()) / max(180.0, self.height() * 0.55)
            length = math.hypot(dx, dy)
            if length > 1.0:
                dx, dy = dx / length, dy / length
            target_x, target_y = dx, dy
        gaze_x, gaze_y = self._gaze.update(target_x, target_y, dt)
        self._gaze_x = max(-1.0, min(1.0, gaze_x))
        self._gaze_y = max(-1.0, min(1.0, gaze_y))

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
        return replace(current, z=current.z + layer.z)

    def _role_opacity(self, role: str, expression: str) -> float:
        blink = smootherstep(self._blink_amount)
        mouth_bias = float(self.assets.spec.get("expressions", {}).get(expression, {}).get("mouth_bias", 0.0))
        mouth = max(smootherstep(self._mouth_amount), mouth_bias)
        if role in {"eye_white", "iris", "eyeliner_open", "eye_aux"}:
            return 1.0 - blink
        if role == "eyelid_closed":
            return blink
        if role == "mouth_closed":
            return 1.0 - mouth
        if role == "mouth_open":
            return mouth
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
        role_opacity = self._role_opacity(layer.role, expression)
        opacity = transform.opacity * role_opacity * scene_opacity
        if opacity <= 0.001:
            return
        x, y = transform.x, transform.y
        if layer.role == "iris":
            x += self._gaze_x * layer.eye_limit_x
            y += self._gaze_y * layer.eye_limit_y
        width, height = sprite.width, sprite.height
        painter.save()
        painter.setOpacity(opacity)
        painter.translate(x + width * transform.scale_x * 0.5, y + height * transform.scale_y * 0.5)
        painter.rotate(transform.rotation)
        painter.scale(transform.scale_x, transform.scale_y)
        painter.drawPixmap(QPointF(-width * 0.5, -height * 0.5), sprite.pixmap)
        if calibration and layer.layer_id == self.selected_layer:
            painter.setOpacity(1.0)
            painter.setPen(QPen(QColor(71, 232, 255, 245), max(1.2, 2.0 / max(transform.scale_x, transform.scale_y))))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRectF(-width * 0.5, -height * 0.5, width, height))
            painter.drawLine(QPointF(-8, 0), QPointF(8, 0))
            painter.drawLine(QPointF(0, -8), QPointF(0, 8))
        painter.restore()
