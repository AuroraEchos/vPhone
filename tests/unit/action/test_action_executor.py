"""Tests for the L2 action executor."""

from __future__ import annotations

import pytest

from vphone.action import (
    ActionExecutor,
    ActionKind,
    KeyAction,
    LongPressAction,
    ReplaceTextAction,
    SwipeAction,
    TapAction,
    TextAction,
    WaitAction,
)
from vphone.device import DeviceCommandTimeoutError, KeyCode, Point, PrimitiveResult


class FakeDevice:
    def __init__(self, error: DeviceCommandTimeoutError | None = None) -> None:
        """Create a device fake with an optional injected command failure."""
        self.calls: list[tuple[str, tuple, dict]] = []
        self.error = error

    def _record(self, operation: str, args: tuple, kwargs: dict) -> PrimitiveResult:
        """Record one requested primitive and optionally raise its failure."""
        self.calls.append((operation, args, kwargs))
        if self.error is not None:
            raise self.error
        return PrimitiveResult(operation, 0.01)

    def tap(self, point: Point, **kwargs) -> PrimitiveResult:
        """Record a tap request."""
        return self._record("tap", (point,), kwargs)

    def long_press(self, point: Point, **kwargs) -> PrimitiveResult:
        """Record a long-press request."""
        return self._record("long_press", (point,), kwargs)

    def swipe(self, start: Point, end: Point, **kwargs) -> PrimitiveResult:
        """Record a swipe request."""
        return self._record("swipe", (start, end), kwargs)

    def key_event(self, key: KeyCode | int, **kwargs) -> PrimitiveResult:
        """Record a key-event request."""
        return self._record("key_event", (key,), kwargs)

    def input_text(self, text: str, **kwargs) -> PrimitiveResult:
        """Record a text-input request."""
        return self._record("input_text", (text,), kwargs)

    def replace_text(self, text: str, **kwargs) -> PrimitiveResult:
        """Record a text-replacement request."""
        return self._record("replace_text", (text,), kwargs)


@pytest.mark.parametrize(
    ("action", "kind", "operation", "args", "kwargs"),
    [
        (TapAction(Point(10, 20)), ActionKind.TAP, "tap", (Point(10, 20),), {}),
        (
            LongPressAction(Point(10, 20)),
            ActionKind.LONG_PRESS,
            "long_press",
            (Point(10, 20),),
            {},
        ),
        (
            SwipeAction(Point(1, 2), Point(3, 4), duration_ms=250),
            ActionKind.SWIPE,
            "swipe",
            (Point(1, 2), Point(3, 4)),
            {"duration_ms": 250},
        ),
        (KeyAction(KeyCode.BACK), ActionKind.KEY, "key_event", (KeyCode.BACK,), {}),
        (TextAction("你好"), ActionKind.TEXT, "input_text", ("你好",), {}),
        (
            ReplaceTextAction("新内容"),
            ActionKind.REPLACE_TEXT,
            "replace_text",
            ("新内容",),
            {},
        ),
    ],
)
def test_executor_dispatches_supported_actions(action, kind, operation, args, kwargs) -> None:
    """Verify executor dispatches supported actions."""
    device = FakeDevice()

    result = ActionExecutor(device).execute(action)

    assert result.kind is kind
    assert result.completed is True
    assert result.error is None
    assert result.primitive is not None
    assert result.primitive.operation == operation
    assert result.duration_seconds >= 0
    assert device.calls == [(operation, args, kwargs)]


def test_executor_forwards_explicit_timeout() -> None:
    """Verify executor forwards explicit timeout."""
    device = FakeDevice()

    ActionExecutor(device).execute(TapAction(Point(10, 20)), timeout=2.5)

    assert device.calls == [("tap", (Point(10, 20),), {"timeout": 2.5})]


def test_executor_waits_without_calling_device(monkeypatch: pytest.MonkeyPatch) -> None:
    """A wait is a local action and does not dispatch a device primitive."""
    waits = []
    monkeypatch.setattr("vphone.action.executor.time.sleep", waits.append)
    device = FakeDevice()

    result = ActionExecutor(device).execute(WaitAction(2.5))

    assert waits == [2.5]
    assert result.kind is ActionKind.WAIT
    assert result.completed is True
    assert result.primitive is None
    assert device.calls == []


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_executor_rejects_invalid_timeout_before_device_call(timeout: float) -> None:
    """Verify executor rejects invalid timeout before device call."""
    device = FakeDevice()

    with pytest.raises(ValueError, match="finite and positive"):
        ActionExecutor(device).execute(KeyAction(KeyCode.HOME), timeout=timeout)

    assert device.calls == []


def test_executor_returns_device_failure_without_retry() -> None:
    """Verify executor returns device failure without retry."""
    failure = DeviceCommandTimeoutError("device command timed out")
    device = FakeDevice(error=failure)

    result = ActionExecutor(device).execute(TextAction("hello"))

    assert result.kind is ActionKind.TEXT
    assert result.completed is False
    assert result.error is failure
    assert result.primitive is None
    assert len(device.calls) == 1


def test_executor_rejects_unknown_action_before_device_call() -> None:
    """Verify executor rejects unknown action before device call."""
    device = FakeDevice()

    with pytest.raises(TypeError, match="supported L2 action"):
        ActionExecutor(device).execute("tap")  # type: ignore[arg-type]

    assert device.calls == []
