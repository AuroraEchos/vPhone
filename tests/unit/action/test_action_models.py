"""Tests for concrete L2 action models."""

from __future__ import annotations

import pytest

from vphone.action import KeyAction, SwipeAction, TapAction, TextAction, WaitAction
from vphone.device import Point


def test_tap_requires_point() -> None:
    """Verify tap requires point."""
    with pytest.raises(TypeError, match="Point"):
        TapAction((1, 2))  # type: ignore[arg-type]


@pytest.mark.parametrize("duration", [0, 10_001])
def test_swipe_rejects_out_of_range_duration(duration: int) -> None:
    """Verify swipe rejects out of range duration."""
    with pytest.raises(ValueError, match="between"):
        SwipeAction(Point(1, 2), Point(3, 4), duration_ms=duration)


def test_key_rejects_boolean() -> None:
    """Verify key rejects boolean."""
    with pytest.raises(TypeError, match="KeyCode or integer"):
        KeyAction(True)


def test_text_rejects_control_characters() -> None:
    """Verify text rejects control characters."""
    with pytest.raises(ValueError, match="printable"):
        TextAction("first\nsecond")


def test_text_is_hidden_from_default_representation() -> None:
    """Verify text is hidden from default representation."""
    assert "secret" not in repr(TextAction("secret"))


def test_wait_caps_requested_duration() -> None:
    """Keep waits bounded even when constructed outside the model-tool parser."""
    assert WaitAction(2).seconds == 2.0
    assert WaitAction(300).seconds == 30.0


@pytest.mark.parametrize("seconds", [0, -1, float("inf"), float("nan")])
def test_wait_rejects_non_positive_or_non_finite_duration(seconds: float) -> None:
    """Reject wait durations that cannot represent a useful bounded pause."""
    with pytest.raises(ValueError, match="finite and positive"):
        WaitAction(seconds)


def test_wait_rejects_boolean_duration() -> None:
    """Do not silently treat booleans as numeric wait durations."""
    with pytest.raises(TypeError, match="number"):
        WaitAction(True)
