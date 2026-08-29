from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, replace
from typing import Callable, Mapping

OUTFITS = ("casual", "cos")
EXPRESSIONS = ("neutral", "happy", "unamused", "surprised")


@dataclass
class AvatarState:
    outfit: str = "casual"
    expression: str = "neutral"
    talking: bool = False
    blinking: bool = False

    def normalized(self) -> "AvatarState":
        return AvatarState(
            outfit=self.outfit if self.outfit in OUTFITS else "casual",
            expression=self.expression if self.expression in EXPRESSIONS else "neutral",
            talking=bool(self.talking),
            blinking=bool(self.blinking),
        )


@dataclass(frozen=True)
class LayerTransform:
    x: float = 0.0
    y: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    rotation: float = 0.0
    opacity: float = 1.0
    z: float = 0.0

    @classmethod
    def from_mapping(cls, value: Mapping[str, object] | None, fallback: "LayerTransform | None" = None) -> "LayerTransform":
        base = fallback or cls()
        value = value or {}
        return cls(
            x=float(value.get("x", base.x)),
            y=float(value.get("y", base.y)),
            scale_x=float(value.get("scale_x", value.get("scaleX", base.scale_x))),
            scale_y=float(value.get("scale_y", value.get("scaleY", base.scale_y))),
            rotation=float(value.get("rotation", base.rotation)),
            opacity=float(value.get("opacity", base.opacity)),
            z=float(value.get("z", value.get("z_order", base.z))),
        ).clamped()

    def clamped(self) -> "LayerTransform":
        return replace(
            self,
            x=max(-2048.0, min(2048.0, self.x)),
            y=max(-2048.0, min(2048.0, self.y)),
            scale_x=max(0.02, min(8.0, self.scale_x)),
            scale_y=max(0.02, min(8.0, self.scale_y)),
            rotation=max(-180.0, min(180.0, self.rotation)),
            opacity=max(0.0, min(1.0, self.opacity)),
            z=max(-1000.0, min(1000.0, self.z)),
        )

    def merged(self, override: Mapping[str, object] | None) -> "LayerTransform":
        return LayerTransform.from_mapping(override, self)

    def to_dict(self) -> dict[str, float]:
        return {
            "x": self.x,
            "y": self.y,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
            "rotation": self.rotation,
            "opacity": self.opacity,
            "z": self.z,
        }

    @staticmethod
    def lerp(a: "LayerTransform", b: "LayerTransform", amount: float) -> "LayerTransform":
        t = smootherstep(amount)
        mix = lambda x, y: x + (y - x) * t
        return LayerTransform(
            x=mix(a.x, b.x),
            y=mix(a.y, b.y),
            scale_x=mix(a.scale_x, b.scale_x),
            scale_y=mix(a.scale_y, b.scale_y),
            rotation=mix(a.rotation, b.rotation),
            opacity=mix(a.opacity, b.opacity),
            z=b.z if t >= 0.5 else a.z,
        )


def smootherstep(value: float) -> float:
    value = max(0.0, min(1.0, float(value)))
    return value * value * value * (value * (value * 6.0 - 15.0) + 10.0)


class BlinkController:
    def __init__(
        self,
        state: AvatarState,
        *,
        interval_min: float = 2.8,
        interval_max: float = 6.5,
        closed_seconds: float = 0.12,
        clock: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        self.state = state
        self.interval_min = max(0.2, float(interval_min))
        self.interval_max = max(self.interval_min, float(interval_max))
        self.closed_seconds = max(0.05, float(closed_seconds))
        self.clock = clock
        self.rng = rng or random.Random()
        self._close_until: float | None = None
        self.next_blink_at = self.clock() + self.rng.uniform(self.interval_min, self.interval_max)

    def update(self, now: float | None = None) -> bool:
        now = self.clock() if now is None else float(now)
        if self.state.blinking:
            if self._close_until is not None and now >= self._close_until:
                self.state.blinking = False
                self._close_until = None
                self.next_blink_at = now + self.rng.uniform(self.interval_min, self.interval_max)
                return True
            return False
        if now >= self.next_blink_at:
            self.state.blinking = True
            self._close_until = now + self.closed_seconds
            return True
        return False


class MouthController:
    """Stable closed/open microphone gate with hysteresis and hold times."""

    def __init__(
        self,
        state: AvatarState,
        *,
        open_threshold_db: float = -33.0,
        close_threshold_db: float = -38.0,
        attack_hold: float = 0.05,
        release_hold: float = 0.28,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.state = state
        self.attack_hold = max(0.0, float(attack_hold))
        self.release_hold = max(0.0, float(release_hold))
        self.clock = clock
        self._above_since: float | None = None
        self._below_since: float | None = None
        self.set_thresholds(open_threshold_db, close_threshold_db)

    def set_thresholds(self, open_threshold_db: float, close_threshold_db: float) -> None:
        self.open_threshold_db = float(open_threshold_db)
        self.close_threshold_db = min(float(close_threshold_db), self.open_threshold_db - 1.0)

    def update(self, raw_db: float, now: float | None = None) -> bool:
        now = self.clock() if now is None else float(now)
        raw_db = float(raw_db)
        if not self.state.talking:
            self._below_since = None
            if raw_db >= self.open_threshold_db:
                self._above_since = now if self._above_since is None else self._above_since
                if now - self._above_since >= self.attack_hold:
                    self.state.talking = True
                    self._above_since = None
                    return True
            else:
                self._above_since = None
            return False
        self._above_since = None
        if raw_db <= self.close_threshold_db:
            self._below_since = now if self._below_since is None else self._below_since
            if now - self._below_since >= self.release_hold:
                self.state.talking = False
                self._below_since = None
                return True
        else:
            self._below_since = None
        return False


@dataclass
class Spring2D:
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0

    def update(self, target_x: float, target_y: float, dt: float, stiffness: float = 44.0, damping: float = 12.5) -> tuple[float, float]:
        dt = max(0.001, min(0.05, float(dt)))
        self.vx += (stiffness * (target_x - self.x) - damping * self.vx) * dt
        self.vy += (stiffness * (target_y - self.y) - damping * self.vy) * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        return self.x, self.y


def approach(current: float, target: float, speed_per_second: float, dt: float) -> float:
    delta = speed_per_second * max(0.0, dt)
    if abs(target - current) <= delta:
        return target
    return current + math.copysign(delta, target - current)

