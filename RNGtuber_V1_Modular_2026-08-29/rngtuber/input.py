from __future__ import annotations

import ctypes
import math
import sys
import time
from dataclasses import dataclass, field
from typing import Any


BUTTON_NAMES = ("A", "B", "X", "Y", "LB", "RB", "BACK", "START", "LS", "RS", "UP", "DOWN", "LEFT", "RIGHT")
KEY_NAMES = ("W", "A", "S", "D", "SPACE", "CTRL", "ALT", "1", "2", "3", "4", "7", "8", "MOUSE1", "MOUSE2")


@dataclass
class InputSnapshot:
    buttons: dict[str, bool] = field(default_factory=lambda: {key: False for key in BUTTON_NAMES})
    keys: dict[str, bool] = field(default_factory=lambda: {key: False for key in KEY_NAMES})
    left_stick: tuple[float, float] = (0.0, 0.0)
    right_stick: tuple[float, float] = (0.0, 0.0)
    left_trigger: float = 0.0
    right_trigger: float = 0.0
    connected: bool = False
    device_name: str = "No controller"


def _deadzone(value: float, threshold: float = 0.12) -> float:
    if abs(value) <= threshold:
        return 0.0
    return math.copysign((abs(value) - threshold) / (1.0 - threshold), value)


class _XInputGamepad(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class _XInputState(ctypes.Structure):
    _fields_ = [("dwPacketNumber", ctypes.c_ulong), ("Gamepad", _XInputGamepad)]


class _XInputBackend:

    MASKS = {
        "UP": 0x0001,
        "DOWN": 0x0002,
        "LEFT": 0x0004,
        "RIGHT": 0x0008,
        "START": 0x0010,
        "BACK": 0x0020,
        "LS": 0x0040,
        "RS": 0x0080,
        "LB": 0x0100,
        "RB": 0x0200,
        "A": 0x1000,
        "B": 0x2000,
        "X": 0x4000,
        "Y": 0x8000,
    }

    def __init__(self) -> None:
        self.get_state = None
        if sys.platform != "win32":
            return
        for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
            try:
                dll = ctypes.WinDLL(name)
                self.get_state = dll.XInputGetState
                self.get_state.argtypes = [ctypes.c_ulong, ctypes.POINTER(_XInputState)]
                self.get_state.restype = ctypes.c_ulong
                break
            except Exception:
                continue

    def poll(self) -> InputSnapshot | None:
        if self.get_state is None:
            return None
        for index in range(4):
            state = _XInputState()
            if self.get_state(index, ctypes.byref(state)) != 0:
                continue
            pad = state.Gamepad
            snap = InputSnapshot(connected=True, device_name=f"XInput Controller {index + 1}")
            snap.buttons.update({key: bool(pad.wButtons & mask) for key, mask in self.MASKS.items()})
            norm = lambda value: _deadzone(max(-1.0, min(1.0, value / 32767.0)))
            snap.left_stick = (norm(pad.sThumbLX), -norm(pad.sThumbLY))
            snap.right_stick = (norm(pad.sThumbRX), -norm(pad.sThumbRY))
            snap.left_trigger = pad.bLeftTrigger / 255.0
            snap.right_trigger = pad.bRightTrigger / 255.0
            return snap
        return None


class _PygameBackend:
    def __init__(self) -> None:
        self.pg: Any = None
        self.joystick: Any = None
        try:
            import os

            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            import pygame

            pygame.init()
            pygame.joystick.init()
            self.pg = pygame
        except Exception:
            self.pg = None

    def poll(self) -> InputSnapshot | None:
        if self.pg is None:
            return None
        try:
            self.pg.event.pump()
            if self.joystick is None or not self.joystick.get_init():
                if self.pg.joystick.get_count() <= 0:
                    return None
                self.joystick = self.pg.joystick.Joystick(0)
                self.joystick.init()
            joy = self.joystick
            snap = InputSnapshot(connected=True, device_name=joy.get_name() or "SDL Controller")
            button_map = {"A": 0, "B": 1, "X": 2, "Y": 3, "LB": 4, "RB": 5, "BACK": 6, "START": 7, "LS": 8, "RS": 9}
            for name, index in button_map.items():
                if index < joy.get_numbuttons():
                    snap.buttons[name] = bool(joy.get_button(index))
            if joy.get_numhats() > 0:
                hx, hy = joy.get_hat(0)
                snap.buttons.update(LEFT=hx < 0, RIGHT=hx > 0, UP=hy > 0, DOWN=hy < 0)
            axis = lambda index: float(joy.get_axis(index)) if index < joy.get_numaxes() else 0.0
            snap.left_stick = (_deadzone(axis(0)), _deadzone(axis(1)))
            snap.right_stick = (_deadzone(axis(2)), _deadzone(axis(3)))
            snap.left_trigger = max(0.0, min(1.0, (axis(4) + 1.0) * 0.5))
            snap.right_trigger = max(0.0, min(1.0, (axis(5) + 1.0) * 0.5))
            return snap
        except Exception:
            self.joystick = None
            return None


class GlobalInput:
    """Polls global keyboard/mouse and gamepads without ever making startup fatal."""

    VK = {
        "W": 0x57, "A": 0x41, "S": 0x53, "D": 0x44, "SPACE": 0x20,
        "CTRL": 0x11, "ALT": 0x12, "1": 0x31, "2": 0x32, "3": 0x33,
        "4": 0x34, "7": 0x37, "8": 0x38, "MOUSE1": 0x01, "MOUSE2": 0x02,
    }

    def __init__(self, *, demo: bool = False) -> None:
        self.demo = bool(demo)
        self.snapshot = InputSnapshot()
        self.previous = InputSnapshot()
        self.last_activity = time.monotonic()
        self._started_at = self.last_activity
        self._xinput = _XInputBackend()
        self._pygame = _PygameBackend()
        self._user32 = ctypes.windll.user32 if sys.platform == "win32" else None

    @property
    def keys(self) -> dict[str, bool]:
        return self.snapshot.keys

    @property
    def buttons(self) -> dict[str, bool]:
        return self.snapshot.buttons

    def just_pressed(self, name: str) -> bool:
        if name in self.snapshot.keys:
            return self.snapshot.keys[name] and not self.previous.keys.get(name, False)
        return self.snapshot.buttons.get(name, False) and not self.previous.buttons.get(name, False)

    def _poll_keys(self) -> dict[str, bool]:
        if self._user32 is None:
            return {name: False for name in KEY_NAMES}
        return {name: bool(self._user32.GetAsyncKeyState(code) & 0x8000) for name, code in self.VK.items()}

    def _demo_snapshot(self) -> InputSnapshot:
        t = time.monotonic() - self._started_at
        snap = InputSnapshot(connected=True, device_name="Demo Controller")
        snap.left_stick = (math.sin(t * 1.8) * 0.75, math.cos(t * 1.4) * 0.55)
        snap.right_stick = (math.sin(t * 0.9) * 0.55, math.sin(t * 1.2) * 0.45)
        snap.left_trigger = (math.sin(t * 1.1) + 1.0) * 0.35
        snap.right_trigger = (math.cos(t * 1.3) + 1.0) * 0.35
        snap.buttons["A"] = int(t * 2.0) % 5 == 0
        snap.buttons["RB"] = int(t * 1.2) % 7 == 0
        snap.keys["W"] = int(t) % 4 < 2
        return snap

    def poll(self) -> None:
        self.previous = self.snapshot
        if self.demo:
            snap = self._demo_snapshot()
        else:
            snap = self._xinput.poll() or self._pygame.poll() or InputSnapshot()
            snap.keys = self._poll_keys()
        self.snapshot = snap
        active = (
            any(snap.buttons.values())
            or any(snap.keys.values())
            or max(map(abs, (*snap.left_stick, *snap.right_stick))) > 0.15
            or snap.left_trigger > 0.08
            or snap.right_trigger > 0.08
        )
        if active:
            self.last_activity = time.monotonic()
