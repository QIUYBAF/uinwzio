from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .input import GlobalInput


class InputOverlayWidget(QWidget):
    """Live vector controller/keyboard overlay with sticks, triggers and glow."""

    def __init__(self, inputs: GlobalInput, display_mode: str = "gamepad", auto_fade: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.inputs = inputs
        self.display_mode = display_mode
        self.auto_fade = bool(auto_fade)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.update)
        self.timer.start()
        self.setVisible(self.display_mode != "off")

    def set_mode(self, mode: str) -> None:
        self.display_mode = mode if mode in {"gamepad", "keyboard", "off"} else "off"
        self.setVisible(self.display_mode != "off")
        self.update()

    def set_auto_fade(self, enabled: bool) -> None:
        self.auto_fade = bool(enabled)

    def _opacity(self) -> float:
        if not self.auto_fade:
            return 1.0
        idle = time.monotonic() - self.inputs.last_activity
        if idle <= 2.2:
            return 1.0
        return max(0.20, 1.0 - (idle - 2.2) / 1.2)

    def paintEvent(self, event) -> None:
        del event
        if self.display_mode == "off":
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setOpacity(self._opacity())
        if self.display_mode == "keyboard":
            self._draw_keyboard(painter)
        else:
            self._draw_gamepad(painter)
        painter.end()

    def _draw_panel(self, painter: QPainter) -> QRectF:
        margin = max(4.0, self.width() * 0.02)
        rect = QRectF(margin, margin, self.width() - margin * 2, self.height() - margin * 2)
        painter.setPen(QPen(QColor(133, 113, 255, 150), max(1.0, self.width() / 320.0)))
        painter.setBrush(QColor(10, 12, 25, 198))
        painter.drawRoundedRect(rect, rect.height() * 0.16, rect.height() * 0.16)
        return rect

    def _draw_gamepad(self, painter: QPainter) -> None:
        rect = self._draw_panel(painter)
        snap = self.inputs.snapshot
        w, h = rect.width(), rect.height()
        ox, oy = rect.left(), rect.top()
        body = QPainterPath()
        body.moveTo(ox + w * 0.25, oy + h * 0.24)
        body.cubicTo(ox + w * 0.08, oy + h * 0.19, ox + w * 0.06, oy + h * 0.82, ox + w * 0.19, oy + h * 0.86)
        body.cubicTo(ox + w * 0.28, oy + h * 0.90, ox + w * 0.29, oy + h * 0.67, ox + w * 0.39, oy + h * 0.66)
        body.lineTo(ox + w * 0.61, oy + h * 0.66)
        body.cubicTo(ox + w * 0.71, oy + h * 0.67, ox + w * 0.72, oy + h * 0.90, ox + w * 0.81, oy + h * 0.86)
        body.cubicTo(ox + w * 0.94, oy + h * 0.82, ox + w * 0.92, oy + h * 0.19, ox + w * 0.75, oy + h * 0.24)
        body.cubicTo(ox + w * 0.63, oy + h * 0.16, ox + w * 0.37, oy + h * 0.16, ox + w * 0.25, oy + h * 0.24)
        painter.setPen(QPen(QColor(151, 128, 255, 200), max(1.0, w * 0.006)))
        painter.setBrush(QColor(25, 28, 50, 245))
        painter.drawPath(body)

        def glow(active: bool) -> QColor:
            return QColor(97, 231, 255, 245) if active else QColor(91, 82, 145, 210)

        def circle(cx: float, cy: float, radius: float, active: bool = False) -> None:
            painter.setPen(QPen(glow(active), max(1.0, radius * 0.12)))
            painter.setBrush(QColor(35, 38, 65, 245))
            painter.drawEllipse(QPointF(ox + w * cx, oy + h * cy), radius, radius)

        r = h * 0.105
        lx, ly = snap.left_stick
        rx, ry = snap.right_stick
        circle(0.29, 0.42, r, abs(lx) + abs(ly) > 0.18)
        circle(0.57, 0.60, r, abs(rx) + abs(ry) > 0.18)
        for cx, cy, dx, dy in ((0.29, 0.42, lx, ly), (0.57, 0.60, rx, ry)):
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(111, 235, 255, 230))
            painter.drawEllipse(QPointF(ox + w * cx + dx * r * 0.48, oy + h * cy + dy * r * 0.48), r * 0.38, r * 0.38)

        # D-pad
        dcx, dcy = ox + w * 0.40, oy + h * 0.60
        size = h * 0.09
        for name, dx, dy in (("UP", 0, -1), ("DOWN", 0, 1), ("LEFT", -1, 0), ("RIGHT", 1, 0)):
            painter.setPen(QPen(glow(snap.buttons[name]), 1.0))
            painter.setBrush(QColor(71, 64, 112, 230) if snap.buttons[name] else QColor(35, 38, 65, 235))
            painter.drawRoundedRect(QRectF(dcx + dx * size - size * 0.45, dcy + dy * size - size * 0.45, size * 0.9, size * 0.9), 3, 3)

        # ABXY diamond
        font = QFont("Segoe UI", max(7, round(h * 0.075)), QFont.Bold)
        painter.setFont(font)
        for name, cx, cy in (("Y", 0.76, 0.32), ("B", 0.84, 0.45), ("A", 0.76, 0.58), ("X", 0.68, 0.45)):
            circle(cx, cy, h * 0.067, snap.buttons[name])
            painter.setPen(QColor(245, 246, 255))
            painter.drawText(QRectF(ox + w * cx - h * 0.06, oy + h * cy - h * 0.055, h * 0.12, h * 0.11), Qt.AlignCenter, name)

        # Shoulders/triggers
        for name, x, value in (("LB", 0.19, snap.left_trigger), ("RB", 0.67, snap.right_trigger)):
            active = snap.buttons[name] or value > 0.08
            bar = QRectF(ox + w * x, oy + h * 0.12, w * 0.14, h * 0.075)
            painter.setPen(QPen(glow(active), 1.2))
            painter.setBrush(QColor(45, 47, 77, 240))
            painter.drawRoundedRect(bar, 5, 5)
            fill = QRectF(bar.left(), bar.top(), bar.width() * max(value, 0.12 if snap.buttons[name] else 0.0), bar.height())
            painter.fillRect(fill, QColor(91, 219, 255, 175))

        painter.setPen(QColor(220, 222, 245, 210))
        painter.setFont(QFont("Segoe UI", max(7, round(h * 0.06))))
        status = snap.device_name if snap.connected else "等待手柄（键鼠仍可用）"
        painter.drawText(QRectF(ox + w * 0.31, oy + h * 0.77, w * 0.38, h * 0.12), Qt.AlignCenter, status)

    def _draw_keyboard(self, painter: QPainter) -> None:
        rect = self._draw_panel(painter)
        keys = self.inputs.snapshot.keys
        w, h = rect.width(), rect.height()
        unit = min(w / 10.5, h / 3.4)
        start_x = rect.left() + unit * 0.8
        start_y = rect.top() + unit * 0.42

        def key(name: str, col: float, row: float, width: float = 1.0, label: str | None = None) -> None:
            active = keys.get(name, False)
            box = QRectF(start_x + col * unit, start_y + row * unit, unit * width * 0.88, unit * 0.82)
            painter.setPen(QPen(QColor(92, 229, 255, 240) if active else QColor(124, 110, 210, 190), 1.2))
            painter.setBrush(QColor(55, 94, 125, 235) if active else QColor(29, 32, 55, 235))
            painter.drawRoundedRect(box, unit * 0.12, unit * 0.12)
            painter.setPen(QColor(245, 246, 255))
            painter.setFont(QFont("Segoe UI", max(7, round(unit * 0.32)), QFont.Bold))
            painter.drawText(box, Qt.AlignCenter, label or name)

        key("W", 1, 0)
        key("A", 0, 1)
        key("S", 1, 1)
        key("D", 2, 1)
        key("SPACE", 0, 2, 3.0, "SPACE")
        key("MOUSE1", 5.2, 0.3, 1.4, "LMB")
        key("MOUSE2", 6.7, 0.3, 1.4, "RMB")
        painter.setPen(QColor(210, 212, 235, 200))
        painter.setFont(QFont("Segoe UI", max(7, round(unit * 0.27))))
        painter.drawText(QRectF(start_x + unit * 4.7, start_y + unit * 1.55, unit * 3.8, unit), Qt.AlignCenter, "Ctrl+Alt+1–4 表情｜7–8 换装")
