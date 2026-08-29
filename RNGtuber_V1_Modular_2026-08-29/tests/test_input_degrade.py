from __future__ import annotations

from rngtuber.input import GlobalInput, _deadzone


def test_no_device_poll_never_raises() -> None:
    inputs = GlobalInput()
    for _ in range(3):
        inputs.poll()
    assert isinstance(inputs.snapshot.connected, bool)


def test_demo_exercises_controller_path() -> None:
    inputs = GlobalInput(demo=True)
    inputs.poll()
    assert inputs.snapshot.connected
    assert inputs.snapshot.device_name == "Demo Controller"


def test_deadzone() -> None:
    assert _deadzone(0.05) == 0.0
    assert 0.0 < _deadzone(0.5) < 1.0
