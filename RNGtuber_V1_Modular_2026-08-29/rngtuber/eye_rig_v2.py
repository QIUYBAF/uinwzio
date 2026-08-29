from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path
from types import MethodType

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from .model import LayerTransform


class EyeRigUX(QObject):
    """Paired-eye correction plus low-click calibration controls.

    The user's existing calibration stays authoritative.  On first launch this
    module backs it up, then performs one conservative migration: align the two
    open upper eyelids to a common visual baseline.  Iris placement is derived
    from each eye white at draw time, preventing the two pupils from drifting
    into a cross-eyed neutral pose while preserving shared gaze motion.
    """

    def __init__(self, panel, avatar, config, assets) -> None:
        super().__init__(panel)
        self.panel = panel
        self.avatar = avatar
        self.canvas = avatar.canvas
        self.config = config
        self.assets = assets
        self.pair_mode = False
        self._drag_last = None
        self._click_through_before_calibration = None
        self.shortcuts: list[QShortcut] = []

        self._backup_manual_baseline_once()
        self._migrate_eye_baseline_once()
        self._patch_iris_registration()
        self._localize_calibration_ui()
        self._install_quick_controls()
        self._install_shortcuts()
        self._install_mouse_calibration()
        self.panel.tabs.currentChanged.connect(self._tab_changed)
        self._tab_changed(self.panel.tabs.currentIndex())

    # ------------------------------------------------------------------
    # Preserve the user's work before changing anything.
    def _backup_manual_baseline_once(self) -> None:
        if bool(self.config.data.get("eye_rig_v2_baseline_saved", False)):
            return
        try:
            if self.config.path.exists():
                backup = self.config.path.with_name("config.manual_baseline_before_eye_rig_v2.json")
                shutil.copy2(self.config.path, backup)
                self.config.data["eye_rig_v2_baseline_path"] = str(backup)
        finally:
            self.config.data["eye_rig_v2_baseline_saved"] = True
            self.config.save()

    def _layer_center_y(self, outfit: str, layer_id: str) -> float | None:
        layer = self.assets.layer_for(layer_id)
        if layer is None:
            return None
        sprite = self.assets.sprite_for(outfit, "neutral", layer)
        if sprite is None:
            return None
        transform = self.canvas._transform_for_draw(outfit, layer, "neutral")
        return transform.y + sprite.height * transform.scale_y * 0.5

    def _migrate_eye_baseline_once(self) -> None:
        self.config.data.setdefault("eye_rig_auto_center", True)
        self.config.data.setdefault("eye_rig_iris_outward", 0.0)
        self.config.data.setdefault("eye_rig_iris_vertical", 0.0)
        if bool(self.config.data.get("eye_rig_v2_migrated", False)):
            return

        # Use the user's current effective positions as the starting point.
        # Only remove the vertical mismatch between the two upper eyelids.
        for outfit in ("casual", "cos"):
            left_y = self._layer_center_y(outfit, "eyeliner_open_left")
            right_y = self._layer_center_y(outfit, "eyeliner_open_right")
            if left_y is None or right_y is None:
                continue
            target = (left_y + right_y) * 0.5
            left_group = self.canvas.effective_group_transform(outfit, "eye_left")
            right_group = self.canvas.effective_group_transform(outfit, "eye_right")
            left_group = replace(left_group, y=left_group.y + (target - left_y))
            right_group = replace(right_group, y=right_group.y + (target - right_y))
            group_map = self.config.data.setdefault("group_calibration", {}).setdefault(outfit, {})
            group_map["eye_left"] = left_group.to_dict()
            group_map["eye_right"] = right_group.to_dict()

        self.config.data["eye_rig_v2_migrated"] = True
        self.config.save()
        self.canvas.update()

    # ------------------------------------------------------------------
    # Neutral gaze: keep each iris inside the centre of its own sclera.
    def _patch_iris_registration(self) -> None:
        original = self.canvas._transform_for_draw
        assets = self.assets
        config = self.config

        def rigged_transform(canvas, outfit: str, layer, expression: str):
            transform = original(outfit, layer, expression)
            if layer.role != "iris" or not bool(config.data.get("eye_rig_auto_center", True)):
                return transform

            side = "left" if layer.layer_id.endswith("_left") else "right" if layer.layer_id.endswith("_right") else ""
            if not side:
                return transform
            white_layer = assets.layer_for(f"eye_white_{side}")
            if white_layer is None:
                return transform
            white_sprite = assets.sprite_for(outfit, expression, white_layer)
            iris_sprite = assets.sprite_for(outfit, expression, layer)
            if white_sprite is None or iris_sprite is None:
                return transform
            white = original(outfit, white_layer, expression)

            white_cx = white.x + white_sprite.width * white.scale_x * 0.5
            white_cy = white.y + white_sprite.height * white.scale_y * 0.5
            outward = float(config.data.get("eye_rig_iris_outward", 0.0))
            vertical = float(config.data.get("eye_rig_iris_vertical", 0.0))
            signed_outward = -outward if side == "left" else outward
            return replace(
                transform,
                x=white_cx - iris_sprite.width * transform.scale_x * 0.5 + signed_outward,
                y=white_cy - iris_sprite.height * transform.scale_y * 0.5 + vertical,
            )

        self.canvas._transform_for_draw = MethodType(rigged_transform, self.canvas)

    # ------------------------------------------------------------------
    # Chinese labels + quick calibration block.
    def _localize_calibration_ui(self) -> None:
        if self.panel.tabs.count() > 1:
            self.panel.tabs.setTabText(1, "校准")
        replacements = {
            "Transform profile": "服装配置",
            "Scale X": "横向缩放",
            "Scale Y": "纵向缩放",
            "Rotation": "旋转",
            "Opacity": "透明度",
            "Z-order": "图层顺序",
            "X": "水平位置 X",
            "Y": "垂直位置 Y",
        }
        for label in self.panel.findChildren(QLabel):
            text = label.text().strip()
            if text in replacements:
                label.setText(replacements[text])

    def _install_quick_controls(self) -> None:
        tab = self.panel.tabs.widget(1)
        layout = tab.layout()
        if layout is None:
            return

        box = QGroupBox("快捷校准｜少点鼠标版")
        root = QVBoxLayout(box)
        row = QHBoxLayout()

        pair = QPushButton("双眼整体")
        left = QPushButton("左眼")
        right = QPushButton("右眼")
        mouth = QPushButton("嘴巴")
        align = QPushButton("自动拉齐双眼")
        pair.clicked.connect(self._select_pair)
        left.clicked.connect(lambda: self._select_combo_target("group:eye_left"))
        right.clicked.connect(lambda: self._select_combo_target("group:eye_right"))
        mouth.clicked.connect(lambda: self._select_combo_target("group:mouth"))
        align.clicked.connect(self.align_eyes_now)
        for button in (pair, left, right, mouth, align):
            row.addWidget(button)
        root.addLayout(row)

        row2 = QHBoxLayout()
        spacing_minus = QPushButton("眼距 −")
        spacing_plus = QPushButton("眼距 +")
        iris_in = QPushButton("虹膜向内")
        iris_out = QPushButton("虹膜向外")
        iris_center = QPushButton("虹膜居中")
        spacing_minus.clicked.connect(lambda: self._change_eye_spacing(-1.0))
        spacing_plus.clicked.connect(lambda: self._change_eye_spacing(1.0))
        iris_in.clicked.connect(lambda: self._change_iris_outward(-0.5))
        iris_out.clicked.connect(lambda: self._change_iris_outward(0.5))
        iris_center.clicked.connect(self._reset_iris_bias)
        for button in (spacing_minus, spacing_plus, iris_in, iris_out):
            button.setAutoRepeat(True)
            button.setAutoRepeatInterval(70)
        for button in (spacing_minus, spacing_plus, iris_in, iris_out, iris_center):
            row2.addWidget(button)
        root.addLayout(row2)

        self.quick_status = QLabel(
            "直接在人物上左键拖动＝移动当前目标；滚轮＝等比缩放。方向键＝1 px，Shift+方向键＝5 px；[ / ]＝缩放。"
        )
        self.quick_status.setWordWrap(True)
        root.addWidget(self.quick_status)
        layout.insertWidget(1, box)

    def _select_combo_target(self, data: str) -> None:
        self.pair_mode = False
        index = self.panel.cal_layer.findData(data)
        if index >= 0:
            self.panel.cal_layer.setCurrentIndex(index)
        self.quick_status.setText("当前目标：" + ("左眼整体" if data.endswith("eye_left") else "右眼整体" if data.endswith("eye_right") else "嘴巴整体"))

    def _select_pair(self) -> None:
        self.pair_mode = True
        self.canvas.set_selected_group(None)
        self.canvas.set_selected_layer(None)
        self.quick_status.setText("当前目标：双眼整体｜拖动/方向键会同时移动两只眼，眼距按钮只改变左右间距。")

    # ------------------------------------------------------------------
    # Pair operations.
    def _current_outfit(self) -> str:
        return str(self.panel.cal_outfit.currentData() or self.panel.state.outfit or "casual")

    def _set_group_transform(self, outfit: str, group_id: str, transform: LayerTransform, *, save: bool = False) -> None:
        group_map = self.config.data.setdefault("group_calibration", {}).setdefault(outfit, {})
        group_map[group_id] = transform.to_dict()
        if save:
            self.config.save()

    def _move_pair(self, dx: float, dy: float) -> None:
        outfit = self._current_outfit()
        left = self.canvas.effective_group_transform(outfit, "eye_left")
        right = self.canvas.effective_group_transform(outfit, "eye_right")
        self._set_group_transform(outfit, "eye_left", replace(left, x=left.x + dx, y=left.y + dy))
        self._set_group_transform(outfit, "eye_right", replace(right, x=right.x + dx, y=right.y + dy))
        self.config.save()
        self.canvas.update()

    def _scale_pair(self, factor: float) -> None:
        outfit = self._current_outfit()
        for group_id in ("eye_left", "eye_right"):
            current = self.canvas.effective_group_transform(outfit, group_id)
            updated = replace(
                current,
                scale_x=max(0.2, min(3.0, current.scale_x * factor)),
                scale_y=max(0.2, min(3.0, current.scale_y * factor)),
            )
            self._set_group_transform(outfit, group_id, updated)
        self.config.save()
        self.canvas.update()

    def _change_eye_spacing(self, delta: float) -> None:
        outfit = self._current_outfit()
        left = self.canvas.effective_group_transform(outfit, "eye_left")
        right = self.canvas.effective_group_transform(outfit, "eye_right")
        # Positive delta increases distance symmetrically around the current face centre.
        self._set_group_transform(outfit, "eye_left", replace(left, x=left.x - delta * 0.5))
        self._set_group_transform(outfit, "eye_right", replace(right, x=right.x + delta * 0.5))
        self.config.save()
        self.canvas.update()

    def _change_iris_outward(self, delta: float) -> None:
        value = float(self.config.data.get("eye_rig_iris_outward", 0.0))
        self.config.data["eye_rig_iris_outward"] = max(-6.0, min(6.0, value + delta))
        self.config.save()
        self.canvas.update()
        self.quick_status.setText(f"虹膜对称外移：{self.config.data['eye_rig_iris_outward']:.1f} px")

    def _reset_iris_bias(self) -> None:
        self.config.data["eye_rig_iris_outward"] = 0.0
        self.config.data["eye_rig_iris_vertical"] = 0.0
        self.config.save()
        self.canvas.update()
        self.quick_status.setText("虹膜已重新以各自眼白中心为基准。")

    def align_eyes_now(self) -> None:
        outfit = self._current_outfit()
        left_y = self._layer_center_y(outfit, "eyeliner_open_left")
        right_y = self._layer_center_y(outfit, "eyeliner_open_right")
        if left_y is None or right_y is None:
            return
        target = (left_y + right_y) * 0.5
        left = self.canvas.effective_group_transform(outfit, "eye_left")
        right = self.canvas.effective_group_transform(outfit, "eye_right")
        self._set_group_transform(outfit, "eye_left", replace(left, y=left.y + target - left_y))
        self._set_group_transform(outfit, "eye_right", replace(right, y=right.y + target - right_y))
        self.config.save()
        self.canvas.update()
        self.panel._load_calibration_controls()
        self.quick_status.setText("已按睁眼上眼睑中心重新拉齐左右眼高度。")

    # ------------------------------------------------------------------
    # Keyboard + mouse direct manipulation.
    def _calibration_active(self) -> bool:
        return self.panel.tabs.currentIndex() == 1

    def _nudge(self, dx: float, dy: float) -> None:
        if not self._calibration_active():
            return
        if self.pair_mode:
            self._move_pair(dx, dy)
            return
        if "x" in self.panel.cal_controls and "y" in self.panel.cal_controls:
            self.panel.cal_controls["x"].setValue(self.panel.cal_controls["x"].value() + dx)
            self.panel.cal_controls["y"].setValue(self.panel.cal_controls["y"].value() + dy)

    def _scale_selected(self, factor: float) -> None:
        if not self._calibration_active():
            return
        if self.pair_mode:
            self._scale_pair(factor)
            return
        sx = self.panel.cal_controls.get("scale_x")
        sy = self.panel.cal_controls.get("scale_y")
        if sx is not None and sy is not None:
            sx.setValue(max(sx.minimum(), min(sx.maximum(), sx.value() * factor)))
            sy.setValue(max(sy.minimum(), min(sy.maximum(), sy.value() * factor)))

    def _shortcut(self, key: str, callback) -> None:
        shortcut = QShortcut(QKeySequence(key), self.panel)
        shortcut.setContext(Qt.ApplicationShortcut)
        shortcut.activated.connect(callback)
        self.shortcuts.append(shortcut)

    def _install_shortcuts(self) -> None:
        self._shortcut("Up", lambda: self._nudge(0, -1))
        self._shortcut("Down", lambda: self._nudge(0, 1))
        self._shortcut("Left", lambda: self._nudge(-1, 0))
        self._shortcut("Right", lambda: self._nudge(1, 0))
        self._shortcut("Shift+Up", lambda: self._nudge(0, -5))
        self._shortcut("Shift+Down", lambda: self._nudge(0, 5))
        self._shortcut("Shift+Left", lambda: self._nudge(-5, 0))
        self._shortcut("Shift+Right", lambda: self._nudge(5, 0))
        self._shortcut("[", lambda: self._scale_selected(0.98))
        self._shortcut("]", lambda: self._scale_selected(1.02))

    def _install_mouse_calibration(self) -> None:
        self.canvas.installEventFilter(self)

    def _tab_changed(self, index: int) -> None:
        active = index == 1
        self.canvas.setAttribute(Qt.WA_TransparentForMouseEvents, not active)
        if active:
            if self.panel.click_through.isChecked():
                self._click_through_before_calibration = True
                self.panel.click_through.setChecked(False)
            self.avatar.show()
            self.avatar.raise_()
        elif self._click_through_before_calibration:
            self._click_through_before_calibration = None
            self.panel.click_through.setChecked(True)

    def eventFilter(self, obj, event):
        if obj is not self.canvas or not self._calibration_active():
            return super().eventFilter(obj, event)

        etype = event.type()
        if etype == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
            self._drag_last = event.globalPosition()
            return True
        if etype == QEvent.Type.MouseMove and self._drag_last is not None and event.buttons() & Qt.LeftButton:
            current = event.globalPosition()
            dx_px = current.x() - self._drag_last.x()
            dy_px = current.y() - self._drag_last.y()
            self._drag_last = current
            scale = min(
                self.canvas.width() / max(1, self.assets.canvas_width),
                self.canvas.height() / max(1, self.assets.canvas_height),
            )
            if scale > 0:
                self._nudge(dx_px / scale, dy_px / scale)
            return True
        if etype == QEvent.Type.MouseButtonRelease:
            self._drag_last = None
            return True
        if etype == QEvent.Type.Wheel:
            steps = event.angleDelta().y() / 120.0
            if steps:
                self._scale_selected(1.0 + steps * 0.02)
            return True
        return super().eventFilter(obj, event)


def install_eye_rig_v2(panel, avatar, config, assets) -> EyeRigUX:
    controller = EyeRigUX(panel, avatar, config, assets)
    # Keep a strong reference on the panel so Qt/Python GC cannot remove it.
    panel.eye_rig_v2 = controller
    return controller
