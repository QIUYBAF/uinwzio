from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .assets import CharacterAssets
from .config import ConfigStore
from .model import AvatarState, LayerTransform
from .window import AvatarWindow


class EyeQuickCalibrator(QWidget):
    """Low-click binocular calibration built around the user's current config."""

    def __init__(self, config: ConfigStore, assets: CharacterAssets, state: AvatarState, avatar: AvatarWindow, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.assets = assets
        self.state = state
        self.avatar = avatar
        self.setFocusPolicy(Qt.StrongFocus)

        root = QVBoxLayout(self)
        intro = QLabel(
            "这里优先调整‘整只眼睛’，不会拆散眼白/上下眼睑/眉毛。"
            "你之前手调并保存在本机 config.json 的位置会继续作为基准，不会被补丁清空。"
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        row = QHBoxLayout()
        row.addWidget(QLabel("调整服装"))
        self.outfit = QComboBox()
        self.outfit.addItem("当前服装", "current")
        self.outfit.addItem("常服", "casual")
        self.outfit.addItem("COS", "cos")
        row.addWidget(self.outfit, 1)
        root.addLayout(row)

        rig = QGroupBox("双眼整体｜少点鼠标版")
        grid = QGridLayout(rig)
        self.up = self._repeat_button("↑", lambda: self._nudge_pair(0, -1))
        self.down = self._repeat_button("↓", lambda: self._nudge_pair(0, 1))
        self.left = self._repeat_button("←", lambda: self._nudge_pair(-1, 0))
        self.right = self._repeat_button("→", lambda: self._nudge_pair(1, 0))
        grid.addWidget(self.up, 0, 1)
        grid.addWidget(self.left, 1, 0)
        grid.addWidget(self.right, 1, 2)
        grid.addWidget(self.down, 2, 1)
        align = QPushButton("双眼同高")
        align.clicked.connect(self._align_height)
        grid.addWidget(align, 0, 3)
        closer = self._repeat_button("眼距 −", lambda: self._spacing(-0.5))
        wider = self._repeat_button("眼距 ＋", lambda: self._spacing(0.5))
        grid.addWidget(closer, 1, 3)
        grid.addWidget(wider, 2, 3)
        root.addWidget(rig)

        help_label = QLabel("键盘：方向键移动双眼 1px；Shift+方向键 5px；A/D 调眼距；无需反复点数值框。")
        help_label.setWordWrap(True)
        root.addWidget(help_label)

        anti = QGroupBox("防斗鸡眼 / 恐怖谷")
        anti_layout = QVBoxLayout(anti)
        self.auto_level = QCheckBox("未手调时自动统一左右眼高度")
        self.auto_level.setChecked(bool(config.data.get("eye_auto_level_defaults", True)))
        self.auto_level.toggled.connect(self._save_auto_level)
        anti_layout.addWidget(self.auto_level)

        self.socket_label = QLabel()
        self.socket = QSlider(Qt.Horizontal)
        self.socket.setRange(0, 100)
        self.socket.setValue(round(float(config.data.get("iris_socket_lock", 0.86)) * 100))
        self.socket.valueChanged.connect(self._socket_changed)
        anti_layout.addWidget(self.socket_label)
        anti_layout.addWidget(self.socket)

        self.outward_label = QLabel()
        self.outward = QSlider(Qt.Horizontal)
        self.outward.setRange(0, 40)
        self.outward.setValue(round(float(config.data.get("iris_outward_px", 1.2)) * 10))
        self.outward.valueChanged.connect(self._outward_changed)
        anti_layout.addWidget(self.outward_label)
        anti_layout.addWidget(self.outward)

        self.gaze_label = QLabel()
        self.gaze = QSlider(Qt.Horizontal)
        self.gaze.setRange(0, 100)
        self.gaze.setValue(round(float(config.data.get("eye_tracking_strength", 0.62)) * 100))
        self.gaze.valueChanged.connect(self._gaze_changed)
        anti_layout.addWidget(self.gaze_label)
        anti_layout.addWidget(self.gaze)
        root.addWidget(anti)

        actions = QHBoxLayout()
        show = QPushButton("显示人物")
        show.clicked.connect(self.avatar.show)
        preview = QPushButton("开启校准背景")
        preview.clicked.connect(lambda: self.avatar.canvas.set_calibration_preview(True, 0.55))
        actions.addWidget(show)
        actions.addWidget(preview)
        root.addLayout(actions)
        root.addStretch(1)
        self._refresh_labels()

    def _repeat_button(self, text: str, callback) -> QPushButton:
        button = QPushButton(text)
        button.setMinimumHeight(42)
        button.setAutoRepeat(True)
        button.setAutoRepeatDelay(260)
        button.setAutoRepeatInterval(45)
        button.clicked.connect(callback)
        return button

    def _active_outfit(self) -> str:
        value = str(self.outfit.currentData() or "current")
        return self.state.outfit if value == "current" else value

    def _pair(self) -> tuple[LayerTransform, LayerTransform]:
        outfit = self._active_outfit()
        return (
            self.avatar.canvas.effective_group_transform(outfit, "eye_left"),
            self.avatar.canvas.effective_group_transform(outfit, "eye_right"),
        )

    def _save_pair(self, left: LayerTransform, right: LayerTransform) -> None:
        outfit = self._active_outfit()
        self.avatar.canvas.save_group_transform(outfit, "eye_left", left)
        self.avatar.canvas.save_group_transform(outfit, "eye_right", right)
        self.avatar.canvas.set_selected_group(None)
        self.avatar.canvas.update()
        self.setFocus(Qt.OtherFocusReason)

    def _nudge_pair(self, dx: float, dy: float) -> None:
        left, right = self._pair()
        self._save_pair(replace(left, x=left.x + dx, y=left.y + dy), replace(right, x=right.x + dx, y=right.y + dy))

    def _spacing(self, amount: float) -> None:
        left, right = self._pair()
        self._save_pair(replace(left, x=left.x - amount), replace(right, x=right.x + amount))

    def _align_height(self) -> None:
        left, right = self._pair()
        y = (left.y + right.y) * 0.5
        self._save_pair(replace(left, y=y), replace(right, y=y))

    def _save_auto_level(self, value: bool) -> None:
        self.config.data["eye_auto_level_defaults"] = bool(value)
        self.config.save()
        self.avatar.canvas.update()

    def _socket_changed(self, value: int) -> None:
        self.config.data["iris_socket_lock"] = value / 100.0
        self.config.save()
        self.avatar.canvas.update()
        self._refresh_labels()

    def _outward_changed(self, value: int) -> None:
        self.config.data["iris_outward_px"] = value / 10.0
        self.config.save()
        self.avatar.canvas.update()
        self._refresh_labels()

    def _gaze_changed(self, value: int) -> None:
        self.config.data["eye_tracking_strength"] = value / 100.0
        self.config.save()
        self.avatar.canvas.update()
        self._refresh_labels()

    def _refresh_labels(self) -> None:
        self.socket_label.setText(f"虹膜锁定眼白中心：{self.socket.value()}%（越高越不容易斗鸡眼）")
        self.outward_label.setText(f"瞳距外扩修正：{self.outward.value() / 10.0:.1f}px")
        self.gaze_label.setText(f"眼球追踪幅度：{self.gaze.value()}%")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        step = 5 if event.modifiers() & Qt.ShiftModifier else 1
        if event.key() == Qt.Key_Left:
            self._nudge_pair(-step, 0)
        elif event.key() == Qt.Key_Right:
            self._nudge_pair(step, 0)
        elif event.key() == Qt.Key_Up:
            self._nudge_pair(0, -step)
        elif event.key() == Qt.Key_Down:
            self._nudge_pair(0, step)
        elif event.key() == Qt.Key_A:
            self._spacing(-0.5 * step)
        elif event.key() == Qt.Key_D:
            self._spacing(0.5 * step)
        else:
            super().keyPressEvent(event)
