from __future__ import annotations

import argparse
import json
import logging
import platform
import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .assets import CharacterAssets
from .audio import MicLevel
from .config import APP_NAME, APP_VERSION, ConfigStore, app_data_dir
from .control_panel import ControlPanel
from .input import GlobalInput
from .model import AvatarState, BlinkController, MouthController
from .window import AvatarWindow

EXPRESSION_HOTKEYS = {"1": "neutral", "2": "happy", "3": "unamused", "4": "surprised"}
OUTFIT_HOTKEYS = {"7": "casual", "8": "cos"}


def _tray_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setBrush(QColor(44, 40, 78))
    painter.setPen(QColor(112, 231, 255))
    painter.drawEllipse(4, 4, 56, 56)
    painter.setPen(QColor(248, 248, 255))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "RNG")
    painter.end()
    return QIcon(pixmap)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--demo", action="store_true", help="使用模拟麦克风和手柄输入")
    parser.add_argument("--smoke-seconds", type=float, default=0.0, metavar="SECONDS")
    parser.add_argument("--diagnostics", action="store_true", help="输出资产诊断后退出")
    args = parser.parse_args(argv)
    if args.smoke_seconds < 0:
        parser.error("--smoke-seconds must be non-negative")

    log_path = app_data_dir() / "rngtuber-v1.log"
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        encoding="utf-8",
        format="%(asctime)s %(levelname)s %(message)s",
    )

    # CharacterAssets uses QPixmap, so QGuiApplication must exist even for
    # packaged diagnostics. Diagnostics intentionally never probe PortAudio:
    # some headless Windows hosts block inside query_devices() while holding
    # the GIL, which prevents any Python-side timeout from firing.
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setQuitOnLastWindowClosed(False)

    config = ConfigStore()
    assets = CharacterAssets()
    if args.diagnostics:
        report = {
            "app": APP_NAME,
            "version": APP_VERSION,
            "platform": platform.platform(),
            "python": sys.version,
            "assets": assets.diagnostics(),
            "microphone_probe": "deferred_to_interactive_runtime",
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        app.quit()
        return 0 if report["assets"]["ok"] else 2

    if not assets.diagnostics()["ok"]:
        QMessageBox.critical(None, APP_NAME, "角色资产缺失或损坏。请重新解压完整 ZIP。")
        return 2

    state = AvatarState(
        outfit=str(config.data.get("outfit", "casual")),
        expression=str(config.data.get("expression", "neutral")),
    ).normalized()
    inputs = GlobalInput(demo=args.demo)
    mic = MicLevel(
        demo=args.demo,
        enabled=bool(config.data.get("mic_enabled", True)),
        device_name=str(config.data.get("mic_name", "")),
    )
    blink = BlinkController(state)
    mouth = MouthController(
        state,
        open_threshold_db=float(config.data.get("mouth_open_threshold_db", -33.0)),
        close_threshold_db=float(config.data.get("mouth_close_threshold_db", -38.0)),
    )
    avatar = AvatarWindow(config, assets, state, inputs)
    panel = ControlPanel(config, assets, state, avatar, mic)

    tray: QSystemTrayIcon | None = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(_tray_icon(), app)
        menu = QMenu()
        show_panel = QAction("控制与校准", menu)
        show_panel.triggered.connect(panel.show)
        show_avatar = QAction("显示人物", menu)
        show_avatar.triggered.connect(avatar.show)
        toggle_click = QAction("切换鼠标穿透", menu)
        toggle_click.triggered.connect(lambda: panel.click_through.setChecked(not panel.click_through.isChecked()))
        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(app.quit)
        menu.addAction(show_panel)
        menu.addAction(show_avatar)
        menu.addAction(toggle_click)
        menu.addSeparator()
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(lambda reason: panel.show() if reason == QSystemTrayIcon.Trigger else None)
        tray.show()
        panel.hide_on_close = True

    timer = QTimer()
    timer.setTimerType(Qt.PreciseTimer)
    timer.setInterval(16)

    def tick() -> None:
        inputs.poll()
        mic.update()
        blink.update()
        mouth.set_thresholds(panel.open_threshold.value(), panel.close_threshold.value())
        mouth.update(mic.raw_db)
        if inputs.keys.get("CTRL") and inputs.keys.get("ALT"):
            for key, expression in EXPRESSION_HOTKEYS.items():
                if inputs.just_pressed(key):
                    panel.set_expression(expression)
            for key, outfit in OUTFIT_HOTKEYS.items():
                if inputs.just_pressed(key):
                    panel.set_outfit(outfit)
        avatar.canvas.set_state(state)

    def cleanup_runtime() -> None:
        timer.stop()
        if tray is not None:
            tray.hide()
        inputs.close()

    timer.timeout.connect(tick)
    timer.start()
    app.aboutToQuit.connect(panel.shutdown)
    app.aboutToQuit.connect(cleanup_runtime)
    avatar.show()
    panel.show()
    if args.smoke_seconds > 0:
        QTimer.singleShot(max(250, round(args.smoke_seconds * 1000)), app.quit)
    exit_code = app.exec()
    cleanup_runtime()
    return exit_code
