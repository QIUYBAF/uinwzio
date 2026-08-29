from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from .assets import CharacterAssets
from .config import ConfigStore, WINDOW_TITLE
from .input import GlobalInput
from .model import AvatarState
from .overlay import InputOverlayWidget
from .renderer import AvatarCanvas


class AvatarWindow(QWidget):
    moved = Signal(int, int)

    def __init__(self, config: ConfigStore, assets: CharacterAssets, state: AvatarState, inputs: GlobalInput) -> None:
        super().__init__()
        self.config = config
        self._drag_offset: QPoint | None = None
        self._programmatic_move = False
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.canvas = AvatarCanvas(assets, config, state, self)
        self.overlay = InputOverlayWidget(
            inputs,
            display_mode=str(config.data.get("input_display", "gamepad")),
            auto_fade=bool(config.data.get("input_auto_fade", True)),
            parent=self,
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(self.overlay, 0)
        self.set_click_through(bool(config.data.get("click_through", False)))
        self.set_width(int(config.data.get("window", {}).get("width", 360)), persist=False)
        self._restore_position()

    @staticmethod
    def _character_height(width: int) -> int:
        return round(width * 1.5)

    @staticmethod
    def _overlay_height(width: int) -> int:
        return round(width * 0.39)

    def set_width(self, width: int, *, persist: bool = True) -> None:
        width = max(200, min(960, int(width)))
        self.canvas.setFixedSize(width, self._character_height(width))
        self.overlay.setFixedSize(width, self._overlay_height(width))
        overlay_height = 0 if self.overlay.display_mode == "off" else self._overlay_height(width)
        self.resize(width, self._character_height(width) + overlay_height)
        self.config.data.setdefault("window", {})["width"] = width
        if persist:
            self.config.save()
        if self.isVisible():
            self._clamp_to_screen()

    def set_input_display(self, mode: str) -> None:
        if mode not in {"gamepad", "keyboard", "off"}:
            return
        self.overlay.set_mode(mode)
        self.config.data["input_display"] = mode
        self.set_width(self.width(), persist=False)
        self.config.save()

    def set_input_auto_fade(self, enabled: bool) -> None:
        self.overlay.set_auto_fade(enabled)
        self.config.data["input_auto_fade"] = bool(enabled)
        self.config.save()

    def set_click_through(self, enabled: bool) -> None:
        enabled = bool(enabled)
        was_visible = self.isVisible()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)
        # WindowTransparentForInput maps to the native Windows input-transparent
        # style, so clicks reach OBS/games behind the avatar rather than merely
        # being ignored by child widgets.
        self.setWindowFlag(Qt.WindowTransparentForInput, enabled)
        if was_visible:
            self.show()
        self.config.data["click_through"] = enabled
        self.config.save()

    def _restore_position(self) -> None:
        window = self.config.data.setdefault("window", {})
        x, y = int(window.get("x", -1)), int(window.get("y", -1))
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        if x < 0 and y < 0:
            x = area.right() - self.width() - 28
            y = area.bottom() - self.height() - 20
        self._programmatic_move = True
        self.move(x, y)
        self._programmatic_move = False
        self._clamp_to_screen()

    def _clamp_to_screen(self) -> None:
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = max(area.left(), min(self.x(), area.right() - self.width() + 1))
        y = max(area.top(), min(self.y(), area.bottom() - self.height() + 1))
        self._programmatic_move = True
        self.move(x, y)
        self._programmatic_move = False

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self._drag_offset = None
        self._save_position()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if self.isVisible() and not self._programmatic_move:
            self._save_position(save_disk=False)

    def _save_position(self, *, save_disk: bool = True) -> None:
        self.config.data.setdefault("window", {}).update(x=self.x(), y=self.y())
        self.moved.emit(self.x(), self.y())
        if save_disk:
            self.config.save()
