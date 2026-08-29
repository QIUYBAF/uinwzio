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
        self._screen_signal_connected = False
        self._last_auto_screen_name = ""
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
        self.set_width(int(config.data.get("window", {}).get("width", 360)), persist=False, preserve_bottom=False)
        self._restore_position()
        if bool(self.config.data.get("auto_size_enabled", True)):
            self.auto_fit_to_screen(persist=True)

    @staticmethod
    def _character_height(width: int) -> int:
        return round(width * 1.5)

    @staticmethod
    def _overlay_height(width: int) -> int:
        return round(width * 0.39)

    def set_width(self, width: int, *, persist: bool = True, preserve_bottom: bool = True) -> None:
        width = max(200, min(960, int(width)))
        anchor: QPoint | None = None
        if preserve_bottom and self.isVisible():
            rect = self.frameGeometry()
            anchor = QPoint(rect.center().x(), rect.bottom())

        self.canvas.setFixedSize(width, self._character_height(width))
        self.overlay.setFixedSize(width, self._overlay_height(width))
        overlay_height = 0 if self.overlay.display_mode == "off" else self._overlay_height(width)
        self.resize(width, self._character_height(width) + overlay_height)

        if anchor is not None:
            self._programmatic_move = True
            self.move(anchor.x() - self.width() // 2, anchor.y() - self.height() + 1)
            self._programmatic_move = False

        self.config.data.setdefault("window", {})["width"] = width
        if persist:
            self.config.save()
        if self.isVisible():
            self._clamp_to_screen()

    def _screen_for_current_position(self):
        return QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()

    def _auto_width_for_screen(self, screen) -> int:
        if screen is None:
            return int(self.config.data.get("window", {}).get("width", 360))
        area = screen.availableGeometry()
        try:
            fraction = float(self.config.data.get("auto_size_fraction", 0.92))
        except (TypeError, ValueError):
            fraction = 0.92
        fraction = max(0.60, min(1.0, fraction))
        total_height_ratio = 1.5 + (0.0 if self.overlay.display_mode == "off" else 0.39)
        width_by_height = int(area.height() * fraction / total_height_ratio)
        width_by_screen = int(area.width() * 0.48)
        return max(260, min(960, width_by_height, width_by_screen))

    def auto_fit_to_screen(self, *, persist: bool = True) -> None:
        if not bool(self.config.data.get("auto_size_enabled", True)):
            return
        screen = self._screen_for_current_position()
        if screen is None:
            return
        self._last_auto_screen_name = screen.name()
        self.set_width(self._auto_width_for_screen(screen), persist=persist, preserve_bottom=True)

    def set_auto_size(self, enabled: bool, *, fraction: float | None = None) -> None:
        self.config.data["auto_size_enabled"] = bool(enabled)
        if fraction is not None:
            self.config.data["auto_size_fraction"] = max(0.60, min(1.0, float(fraction)))
        self.config.save()
        if enabled:
            self.auto_fit_to_screen(persist=True)

    def set_input_display(self, mode: str) -> None:
        if mode not in {"gamepad", "keyboard", "off"}:
            return
        self.overlay.set_mode(mode)
        self.config.data["input_display"] = mode
        if bool(self.config.data.get("auto_size_enabled", True)):
            self.auto_fit_to_screen(persist=False)
        else:
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
        screen = self._screen_for_current_position()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = max(area.left(), min(self.x(), area.right() - self.width() + 1))
        y = max(area.top(), min(self.y(), area.bottom() - self.height() + 1))
        self._programmatic_move = True
        self.move(x, y)
        self._programmatic_move = False

    def _screen_changed(self, screen) -> None:
        if not bool(self.config.data.get("auto_size_enabled", True)):
            return
        if screen is None:
            return
        if screen.name() == self._last_auto_screen_name:
            return
        self._last_auto_screen_name = screen.name()
        self.auto_fit_to_screen(persist=True)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        handle = self.windowHandle()
        if handle is not None and not self._screen_signal_connected:
            handle.screenChanged.connect(self._screen_changed)
            self._screen_signal_connected = True
        if bool(self.config.data.get("auto_size_enabled", True)):
            self.auto_fit_to_screen(persist=False)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self._drag_offset = None
        if bool(self.config.data.get("auto_size_enabled", True)):
            screen = self._screen_for_current_position()
            screen_name = screen.name() if screen is not None else ""
            if screen_name and screen_name != self._last_auto_screen_name:
                self.auto_fit_to_screen(persist=False)
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
