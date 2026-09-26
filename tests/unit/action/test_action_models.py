"""Tests for concrete L2 action models."""

from __future__ import annotations

import pytest

from vphone.action import KeyAction, SwipeAction, TapAction, TextAction
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
