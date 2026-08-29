from __future__ import annotations

import json

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .assets import CharacterAssets
from .audio import MicLevel
from .config import APP_NAME, APP_VERSION, ConfigStore
from .model import AvatarState, LayerTransform
from .window import AvatarWindow

OUTFIT_LABELS = {"casual": "常服", "cos": "COS"}
EXPRESSION_LABELS = {"neutral": "常态", "happy": "开心", "unamused": "无语", "surprised": "惊讶"}


class ControlPanel(QMainWindow):
    def __init__(
        self,
        config: ConfigStore,
        assets: CharacterAssets,
        state: AvatarState,
        avatar: AvatarWindow,
        mic: MicLevel,
    ) -> None:
        super().__init__()
        self.config = config
        self.assets = assets
        self.state = state
        self.avatar = avatar
        self.mic = mic
        self.hide_on_close = False
        self._calibration_loading = False
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}｜控制与校准")
        self.resize(520, 680)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.addTab(self._build_live_tab(), "直播")
        self.tabs.addTab(self._build_calibration_tab(), "Calibration")
        self.tabs.addTab(self._build_diagnostics_tab(), "诊断")
        self.tabs.currentChanged.connect(self._tab_changed)
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(100)
        self.status_timer.timeout.connect(self._refresh_status)
        self.status_timer.start()
        self._refresh_devices()
        self._load_calibration_controls()

    def _build_live_tab(self) -> QWidget:
        tab = QWidget()
        root = QVBoxLayout(tab)

        character = QGroupBox("周婉晴")
        grid = QGridLayout(character)
        self.outfit_combo = QComboBox()
        for key, label in OUTFIT_LABELS.items():
            self.outfit_combo.addItem(label, key)
        self.outfit_combo.setCurrentIndex(max(0, self.outfit_combo.findData(self.state.outfit)))
        self.outfit_combo.currentIndexChanged.connect(lambda: self.set_outfit(str(self.outfit_combo.currentData())))
        grid.addWidget(QLabel("服装"), 0, 0)
        grid.addWidget(self.outfit_combo, 0, 1, 1, 3)
        self.expression_buttons: dict[str, QPushButton] = {}
        for col, expression in enumerate(("neutral", "happy", "unamused", "surprised")):
            button = QPushButton(f"{col + 1} {EXPRESSION_LABELS[expression]}")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=expression: self.set_expression(value))
            grid.addWidget(button, 1, col)
            self.expression_buttons[expression] = button
        grid.addWidget(QLabel("全局快捷键：Ctrl+Alt+1–4 表情；Ctrl+Alt+7/8 换装"), 2, 0, 1, 4)
        root.addWidget(character)

        audio = QGroupBox("麦克风嘴型")
        form = QFormLayout(audio)
        self.mic_enabled = QCheckBox("启用麦克风")
        self.mic_enabled.setChecked(bool(self.config.data.get("mic_enabled", True)))
        self.mic_enabled.toggled.connect(self._mic_enabled_changed)
        form.addRow(self.mic_enabled)
        device_row = QHBoxLayout()
        self.mic_combo = QComboBox()
        self.mic_combo.currentIndexChanged.connect(self._mic_device_changed)
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self._refresh_devices)
        device_row.addWidget(self.mic_combo, 1)
        device_row.addWidget(refresh)
        form.addRow("输入设备", device_row)
        self.mic_meter = QProgressBar()
        self.mic_meter.setRange(0, 100)
        self.mic_status = QLabel("—")
        meter_row = QHBoxLayout()
        meter_row.addWidget(self.mic_meter, 1)
        meter_row.addWidget(self.mic_status)
        form.addRow("电平", meter_row)
        self.open_threshold = QDoubleSpinBox()
        self.open_threshold.setRange(-60, -18)
        self.open_threshold.setSuffix(" dB")
        self.open_threshold.setValue(float(self.config.data.get("mouth_open_threshold_db", -33)))
        self.close_threshold = QDoubleSpinBox()
        self.close_threshold.setRange(-65, -20)
        self.close_threshold.setSuffix(" dB")
        self.close_threshold.setValue(float(self.config.data.get("mouth_close_threshold_db", -38)))
        self.open_threshold.valueChanged.connect(self._threshold_changed)
        self.close_threshold.valueChanged.connect(self._threshold_changed)
        form.addRow("张嘴阈值", self.open_threshold)
        form.addRow("闭嘴阈值", self.close_threshold)
        root.addWidget(audio)

        behavior = QGroupBox("动态与窗口")
        form = QFormLayout(behavior)
        self.breathing = QCheckBox("轻微呼吸与摆动")
        self.breathing.setChecked(bool(self.config.data.get("breathing_enabled", True)))
        self.breathing.toggled.connect(lambda value: self._save_bool("breathing_enabled", value))
        self.eye_tracking = QCheckBox("眼球平滑追踪鼠标")
        self.eye_tracking.setChecked(bool(self.config.data.get("eye_tracking_enabled", True)))
        self.eye_tracking.toggled.connect(lambda value: self._save_bool("eye_tracking_enabled", value))
        self.click_through = QCheckBox("鼠标穿透（Ctrl+Alt+9 可预留给未来）")
        self.click_through.setChecked(bool(self.config.data.get("click_through", False)))
        self.click_through.toggled.connect(self.avatar.set_click_through)
        form.addRow(self.breathing)
        form.addRow(self.eye_tracking)
        form.addRow(self.click_through)
        self.render_mode = QComboBox()
        self.render_mode.addItem("透明背景", "transparent")
        self.render_mode.addItem("绿幕背景", "green")
        self.render_mode.setCurrentIndex(max(0, self.render_mode.findData(self.config.data.get("render_mode", "transparent"))))
        self.render_mode.currentIndexChanged.connect(self._render_mode_changed)
        form.addRow("输出背景", self.render_mode)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(200, 960)
        self.width_spin.setSuffix(" px")
        self.width_spin.setValue(int(self.config.data.get("window", {}).get("width", 360)))
        self.width_spin.valueChanged.connect(self.avatar.set_width)
        form.addRow("人物宽度", self.width_spin)
        self.input_display = QComboBox()
        self.input_display.addItem("手柄", "gamepad")
        self.input_display.addItem("键鼠", "keyboard")
        self.input_display.addItem("关闭", "off")
        self.input_display.setCurrentIndex(max(0, self.input_display.findData(self.config.data.get("input_display", "gamepad"))))
        self.input_display.currentIndexChanged.connect(lambda: self.avatar.set_input_display(str(self.input_display.currentData())))
        form.addRow("输入显示", self.input_display)
        self.input_fade = QCheckBox("空闲自动淡出")
        self.input_fade.setChecked(bool(self.config.data.get("input_auto_fade", True)))
        self.input_fade.toggled.connect(self.avatar.set_input_auto_fade)
        form.addRow(self.input_fade)
        root.addWidget(behavior)

        actions = QHBoxLayout()
        show_avatar = QPushButton("显示人物")
        show_avatar.clicked.connect(self.avatar.show)
        quit_button = QPushButton("退出 RNGtuber")
        quit_button.clicked.connect(lambda: self.close_and_quit())
        actions.addWidget(show_avatar)
        actions.addStretch(1)
        actions.addWidget(quit_button)
        root.addLayout(actions)
        root.addStretch(1)
        self._sync_expression_buttons()
        return tab

    def _build_calibration_tab(self) -> QWidget:
        tab = QWidget()
        root = QVBoxLayout(tab)
        intro = QLabel("可先整体校准左眼、右眼或嘴组，也可继续微调单个部件。支持移动、X/Y 独立缩放、旋转、透明度与层级；每套服装独立保存。")
        intro.setWordWrap(True)
        root.addWidget(intro)
        self.preview_enabled = QCheckBox("半透明 Base 校准预览")
        self.preview_enabled.setChecked(bool(self.config.data.get("calibration_preview", {}).get("enabled", False)))
        self.preview_enabled.toggled.connect(self._preview_changed)
        root.addWidget(self.preview_enabled)
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("Base 透明度"))
        self.base_opacity = QSlider(Qt.Horizontal)
        self.base_opacity.setRange(5, 100)
        self.base_opacity.setValue(round(float(self.config.data.get("calibration_preview", {}).get("base_opacity", 0.55)) * 100))
        self.base_opacity.valueChanged.connect(self._preview_opacity_changed)
        opacity_row.addWidget(self.base_opacity, 1)
        root.addLayout(opacity_row)
        selectors = QFormLayout()
        self.cal_outfit = QComboBox()
        for key, label in OUTFIT_LABELS.items():
            self.cal_outfit.addItem(label, key)
        self.cal_outfit.setCurrentIndex(max(0, self.cal_outfit.findData(self.state.outfit)))
        self.cal_outfit.currentIndexChanged.connect(self._load_calibration_controls)
        selectors.addRow("Transform profile", self.cal_outfit)
        self.cal_layer = QComboBox()
        for group in self.assets.groups:
            self.cal_layer.addItem(f"分组｜{group.label}  ({group.group_id})", f"group:{group.group_id}")
        if self.assets.groups:
            self.cal_layer.insertSeparator(self.cal_layer.count())
        for layer in self.assets.layers:
            self.cal_layer.addItem(f"部件｜{layer.layer_id}  ({layer.role})", f"layer:{layer.layer_id}")
        self.cal_layer.currentIndexChanged.connect(self._load_calibration_controls)
        selectors.addRow("目标", self.cal_layer)
        root.addLayout(selectors)
        values = QFormLayout()
        self.cal_controls: dict[str, QDoubleSpinBox] = {}
        definitions = (
            ("x", "X", -2048.0, 2048.0, 1.0, 1),
            ("y", "Y", -2048.0, 2048.0, 1.0, 1),
            ("scale_x", "Scale X", 0.02, 8.0, 0.01, 3),
            ("scale_y", "Scale Y", 0.02, 8.0, 0.01, 3),
            ("rotation", "Rotation", -180.0, 180.0, 0.1, 2),
            ("opacity", "Opacity", 0.0, 1.0, 0.01, 3),
            ("z", "Z-order", -1000.0, 1000.0, 1.0, 1),
        )
        for key, label, low, high, step, decimals in definitions:
            control = QDoubleSpinBox()
            control.setRange(low, high)
            control.setSingleStep(step)
            control.setDecimals(decimals)
            control.valueChanged.connect(self._calibration_value_changed)
            values.addRow(label, control)
            self.cal_controls[key] = control
        root.addLayout(values)
        buttons = QHBoxLayout()
        reset = QPushButton("恢复当前目标默认值")
        reset.clicked.connect(self._reset_calibration)
        save = QPushButton("立即保存")
        save.clicked.connect(self.config.save)
        buttons.addWidget(reset)
        buttons.addWidget(save)
        root.addLayout(buttons)
        root.addStretch(1)
        return tab

    def _build_diagnostics_tab(self) -> QWidget:
        tab = QWidget()
        root = QVBoxLayout(tab)
        self.diagnostics = QTextEdit()
        self.diagnostics.setReadOnly(True)
        refresh = QPushButton("刷新诊断")
        refresh.clicked.connect(self._refresh_diagnostics)
        root.addWidget(self.diagnostics, 1)
        root.addWidget(refresh)
        return tab

    def _tab_changed(self, index: int) -> None:
        calibration_tab = self.tabs.tabText(index) == "Calibration"
        if calibration_tab:
            self.preview_enabled.setChecked(True)
            self._select_calibration_target()
            self.avatar.show()
        elif not self.preview_enabled.isChecked():
            self.avatar.canvas.set_selected_layer(None)
            self.avatar.canvas.set_selected_group(None)
        if self.tabs.tabText(index) == "诊断":
            self._refresh_diagnostics()

    def set_expression(self, expression: str) -> None:
        if expression not in EXPRESSION_LABELS:
            return
        self.state.expression = expression
        self.config.data["expression"] = expression
        self.config.save()
        self.avatar.canvas.set_state(self.state)
        self._sync_expression_buttons()

    def set_outfit(self, outfit: str) -> None:
        if outfit not in OUTFIT_LABELS:
            return
        self.state.outfit = outfit
        self.config.data["outfit"] = outfit
        self.config.save()
        self.avatar.canvas.set_state(self.state)
        index = self.outfit_combo.findData(outfit)
        if index >= 0 and self.outfit_combo.currentIndex() != index:
            self.outfit_combo.blockSignals(True)
            self.outfit_combo.setCurrentIndex(index)
            self.outfit_combo.blockSignals(False)

    def _sync_expression_buttons(self) -> None:
        for expression, button in self.expression_buttons.items():
            button.setChecked(expression == self.state.expression)

    def _save_bool(self, key: str, value: bool) -> None:
        self.config.data[key] = bool(value)
        self.config.save()
        self.avatar.canvas.update()

    def _render_mode_changed(self) -> None:
        self.config.data["render_mode"] = str(self.render_mode.currentData())
        self.config.save()
        self.avatar.update()
        self.avatar.canvas.update()

    def _mic_enabled_changed(self, enabled: bool) -> None:
        self.config.data["mic_enabled"] = bool(enabled)
        self.config.save()
        self.mic.set_enabled(enabled)

    def _refresh_devices(self) -> None:
        current = str(self.config.data.get("mic_name", ""))
        self.mic_combo.blockSignals(True)
        self.mic_combo.clear()
        self.mic_combo.addItem("系统默认", "")
        for device in MicLevel.devices():
            self.mic_combo.addItem(device, device)
        index = self.mic_combo.findData(current)
        self.mic_combo.setCurrentIndex(max(0, index))
        self.mic_combo.blockSignals(False)

    def _mic_device_changed(self) -> None:
        name = str(self.mic_combo.currentData() or "")
        self.config.data["mic_name"] = name
        self.config.save()
        if self.mic.enabled:
            self.mic.start(name)

    def _threshold_changed(self) -> None:
        open_db = float(self.open_threshold.value())
        close_db = min(float(self.close_threshold.value()), open_db - 1.0)
        if close_db != self.close_threshold.value():
            self.close_threshold.blockSignals(True)
            self.close_threshold.setValue(close_db)
            self.close_threshold.blockSignals(False)
        self.config.data["mouth_open_threshold_db"] = open_db
        self.config.data["mouth_close_threshold_db"] = close_db
        self.config.save()

    def _preview_changed(self, enabled: bool) -> None:
        self.avatar.canvas.set_calibration_preview(enabled, self.base_opacity.value() / 100.0)
        self.config.save()
        if enabled:
            self._select_calibration_target()
        else:
            self.avatar.canvas.set_selected_layer(None)
            self.avatar.canvas.set_selected_group(None)

    def _preview_opacity_changed(self, value: int) -> None:
        self.avatar.canvas.set_calibration_preview(self.preview_enabled.isChecked(), value / 100.0)
        self.config.save()

    def _load_calibration_controls(self) -> None:
        if not hasattr(self, "cal_controls") or not self.cal_controls:
            return
        outfit = str(self.cal_outfit.currentData() or "casual")
        kind, target_id = self._calibration_target()
        if not target_id:
            return
        if kind == "group":
            transform = self.avatar.canvas.effective_group_transform(outfit, target_id)
        else:
            transform = self.avatar.canvas.effective_transform(outfit, target_id, "neutral")
        self._calibration_loading = True
        try:
            for key, value in transform.to_dict().items():
                self.cal_controls[key].setValue(value)
        finally:
            self._calibration_loading = False
        self._select_calibration_target()

    def _calibration_value_changed(self) -> None:
        if self._calibration_loading:
            return
        outfit = str(self.cal_outfit.currentData() or "casual")
        kind, target_id = self._calibration_target()
        if not target_id:
            return
        transform = LayerTransform.from_mapping({key: control.value() for key, control in self.cal_controls.items()})
        if kind == "group":
            self.avatar.canvas.save_group_transform(outfit, target_id, transform)
        else:
            self.avatar.canvas.save_transform(outfit, target_id, transform)

    def _reset_calibration(self) -> None:
        outfit = str(self.cal_outfit.currentData() or "casual")
        kind, target_id = self._calibration_target()
        if target_id:
            if kind == "group":
                self.avatar.canvas.reset_group_transform(outfit, target_id)
            else:
                self.avatar.canvas.reset_transform(outfit, target_id)
            self._load_calibration_controls()

    def _calibration_target(self) -> tuple[str, str]:
        value = str(self.cal_layer.currentData() or "")
        if ":" not in value:
            return "layer", value
        kind, target_id = value.split(":", 1)
        return kind, target_id

    def _select_calibration_target(self) -> None:
        kind, target_id = self._calibration_target()
        if kind == "group":
            self.avatar.canvas.set_selected_group(target_id or None)
        else:
            self.avatar.canvas.set_selected_layer(target_id or None)

    def _refresh_status(self) -> None:
        self.mic_meter.setValue(round(self.mic.level_01 * 100))
        self.mic_status.setText(f"{self.mic.smoothed_db:.1f} dB｜{self.mic.status}")

    def _refresh_diagnostics(self) -> None:
        payload = {
            "app": f"{APP_NAME} {APP_VERSION}",
            "assets": self.assets.diagnostics(),
            "microphone": {"status": self.mic.status, "error": self.mic.error, "device": self.mic.device_name},
            "controller": {
                "connected": self.avatar.overlay.inputs.snapshot.connected,
                "device": self.avatar.overlay.inputs.snapshot.device_name,
            },
            "config_path": str(self.config.path),
        }
        self.diagnostics.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))

    def close_and_quit(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.quit()

    def shutdown(self) -> None:
        self.status_timer.stop()
        self.mic.stop()
        self.config.save()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.hide_on_close:
            event.ignore()
            self.hide()
        else:
            super().closeEvent(event)

