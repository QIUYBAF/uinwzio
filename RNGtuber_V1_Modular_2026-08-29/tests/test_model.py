from __future__ import annotations

import random

import pytest

from rngtuber.model import (
    AvatarState,
    BlinkController,
    LayerTransform,
    MouthController,
    Spring2D,
    apply_group_transform,
    scale_transform_about_center,
)


def test_transform_aliases_merge_and_clamp() -> None:
    base = LayerTransform.from_mapping({"x": 10, "scaleX": 2, "scaleY": 3, "opacity": 7})
    merged = base.merged({"y": 20, "rotation": -12})
    assert merged.x == 10
    assert merged.y == 20
    assert merged.scale_x == 2
    assert merged.scale_y == 3
    assert merged.opacity == 1
    assert merged.rotation == -12


def test_mouth_hysteresis_and_hold_times() -> None:
    state = AvatarState()
    mouth = MouthController(state, attack_hold=0.05, release_hold=0.28)
    mouth.update(-20, now=1.00)
    assert not state.talking
    mouth.update(-20, now=1.06)
    assert state.talking
    mouth.update(-60, now=1.10)
    assert state.talking
    mouth.update(-60, now=1.39)
    assert not state.talking


def test_blink_reopens_and_reschedules() -> None:
    state = AvatarState()
    blink = BlinkController(state, interval_min=1, interval_max=1, closed_seconds=0.1, clock=lambda: 0, rng=random.Random(3))
    assert blink.update(0.99) is False
    assert blink.update(1.0) is True and state.blinking
    assert blink.update(1.11) is True and not state.blinking
    assert blink.next_blink_at == pytest.approx(2.11)


def test_spring_remains_finite_during_large_step_sequence() -> None:
    spring = Spring2D()
    for _ in range(240):
        x, y = spring.update(1.0, -1.0, 1 / 60)
        assert abs(x) < 2 and abs(y) < 2
    assert abs(x - 1) < 0.001
    assert abs(y + 1) < 0.001


def test_group_transform_moves_components_around_shared_pivot() -> None:
    part = LayerTransform(x=40, y=30, scale_x=1.0, scale_y=1.0)
    group = LayerTransform(x=10, y=-5, scale_x=2.0, scale_y=0.5)
    result = apply_group_transform(part, group, (50, 40), (20, 20))
    assert result.x == 40.0
    assert result.y == 30.0
    assert result.scale_x == 2.0
    assert result.scale_y == 0.5


def test_center_preserving_motion_scale_does_not_jump() -> None:
    original = LayerTransform(x=100, y=200, scale_x=1.0, scale_y=1.0)
    changed = scale_transform_about_center(original, (20, 40), 0.9, 0.5)
    assert changed.x + 20 * changed.scale_x * 0.5 == 110.0
    assert changed.y + 40 * changed.scale_y * 0.5 == 220.0
