"""Concrete actions and their execution results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from vphone.device.errors import DeviceError
from vphone.device.models import KeyCode, Point, PrimitiveResult


class ActionKind(StrEnum):
    TAP = "tap"
    SWIPE = "swipe"
    KEY = "key"
    TEXT = "text"


@dataclass(frozen=True, slots=True)
class TapAction:
    point: Point

    def __post_init__(self) -> None:
        """Require a validated screen point for a tap."""
        if not isinstance(self.point, Point):
            raise TypeError("tap point must be a Point")


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
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")
        if not self.text:
            raise ValueError("text cannot be empty")
        if not self.text.isprintable():
            raise ValueError("text must contain printable characters only")


Action = TapAction | SwipeAction | KeyAction | TextAction


@dataclass(frozen=True, slots=True)
class ActionResult:
    kind: ActionKind
    duration_seconds: float
    primitive: PrimitiveResult | None = None
    error: DeviceError | None = None

    @property
    def completed(self) -> bool:
        """Whether L1 returned normally; this does not verify the resulting UI."""
        return self.error is None
