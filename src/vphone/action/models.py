"""Concrete actions and their execution results."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum

from vphone.device.errors import DeviceError
from vphone.device.models import KeyCode, Point, PrimitiveResult

MAX_WAIT_SECONDS = 30.0


class ActionKind(StrEnum):
    TAP = "tap"
    LONG_PRESS = "long_press"
    SWIPE = "swipe"
    KEY = "key"
    TEXT = "text"
    REPLACE_TEXT = "replace_text"
    WAIT = "wait"


@dataclass(frozen=True, slots=True)
class TapAction:
    point: Point

    def __post_init__(self) -> None:
        """Require a validated screen point for a tap."""
        if not isinstance(self.point, Point):
            raise TypeError("tap point must be a Point")


@dataclass(frozen=True, slots=True)
class LongPressAction:
    point: Point

    def __post_init__(self) -> None:
        """Require a validated screen point for a long press."""
        if not isinstance(self.point, Point):
            raise TypeError("long-press point must be a Point")


@dataclass(frozen=True, slots=True)
class SwipeAction:
    start: Point
    end: Point
    duration_ms: int = 300

    def __post_init__(self) -> None:
        """Validate swipe endpoints and the millisecond duration."""
        if not isinstance(self.start, Point) or not isinstance(self.end, Point):
            raise TypeError("swipe endpoints must be Points")
        if isinstance(self.duration_ms, bool) or not isinstance(self.duration_ms, int):
            raise TypeError("swipe duration_ms must be an integer")
        if not 1 <= self.duration_ms <= 10_000:
            raise ValueError("swipe duration_ms must be between 1 and 10000")


@dataclass(frozen=True, slots=True)
class KeyAction:
    key: KeyCode | int

    def __post_init__(self) -> None:
        """Accept a named key or a non-negative numeric keycode."""
        if isinstance(self.key, KeyCode):
            return
        if isinstance(self.key, bool) or not isinstance(self.key, int):
            raise TypeError("key must be a KeyCode or integer")
        if self.key < 0:
            raise ValueError("key code cannot be negative")


@dataclass(frozen=True, slots=True)
class TextAction:
    text: str = field(repr=False)

    def __post_init__(self) -> None:
        """Require nonempty, printable text without exposing it in ``repr``."""
        _validate_text(self.text)


@dataclass(frozen=True, slots=True)
class ReplaceTextAction:
    """Replace all text in the currently focused editor."""

    text: str = field(repr=False)

    def __post_init__(self) -> None:
        """Require nonempty, printable replacement text."""
        _validate_text(self.text)


def _validate_text(text: str) -> None:
    """Validate text shared by insertion and replacement actions."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text:
        raise ValueError("text cannot be empty")
    if not text.isprintable():
        raise ValueError("text must contain printable characters only")


@dataclass(frozen=True, slots=True)
class WaitAction:
    seconds: float

    def __post_init__(self) -> None:
        """Require a positive duration and cap it to the safe wait limit."""
        if isinstance(self.seconds, bool) or not isinstance(self.seconds, (int, float)):
            raise TypeError("wait seconds must be a number")
        if not math.isfinite(self.seconds) or self.seconds <= 0:
            raise ValueError("wait seconds must be finite and positive")
        object.__setattr__(self, "seconds", min(float(self.seconds), MAX_WAIT_SECONDS))


Action = (
    TapAction
    | LongPressAction
    | SwipeAction
    | KeyAction
    | TextAction
    | ReplaceTextAction
    | WaitAction
)


@dataclass(frozen=True, slots=True)
class ActionResult:
    kind: ActionKind
    duration_seconds: float
    primitive: PrimitiveResult | None = None
    error: DeviceError | None = None

    @property
    def completed(self) -> bool:
        """Whether the action returned normally; this does not verify the resulting UI."""
        return self.error is None
