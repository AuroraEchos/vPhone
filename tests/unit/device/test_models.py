"""Unit tests for device-layer data model invariants."""

from __future__ import annotations

import pytest

from vphone.device import Point, Rect


def test_point_rejects_negative_coordinates() -> None:
    """Verify point rejects negative coordinates."""
    with pytest.raises(ValueError, match="negative"):
        Point(-1, 2)


def test_point_rejects_boolean_coordinates() -> None:
    """Verify point rejects boolean coordinates."""
    with pytest.raises(TypeError, match="integers"):
        Point(True, 2)


def test_rect_exposes_dimensions() -> None:
    """Verify rect exposes dimensions."""
    bounds = Rect(10, 20, 35, 70)

    assert bounds.width == 25
    assert bounds.height == 50


def test_rect_rejects_inverted_bounds() -> None:
    """Verify rect rejects inverted bounds."""
    with pytest.raises(ValueError, match="inverted"):
        Rect(10, 0, 9, 20)
