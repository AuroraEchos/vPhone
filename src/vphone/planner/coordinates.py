"""Validate model coordinates in the current screenshot's pixel space."""

from __future__ import annotations

from vphone.device.models import Point, ScreenFrame
from vphone.planner.errors import InvalidDecisionError


def to_screen_point(x: object, y: object, screen: ScreenFrame) -> Point:
    """Validate pixel coordinates against the current screenshot.

    Args:
        x: Proposed horizontal pixel coordinate.
        y: Proposed vertical pixel coordinate.
        screen: Screenshot that defines the valid pixel bounds.

    Returns:
        Validated device point.

    Raises:
        InvalidDecisionError: If either coordinate is not an in-bounds integer.
    """
    if (
        type(x) is not int
        or type(y) is not int
        or not 0 <= x < screen.width
        or not 0 <= y < screen.height
    ):
        raise InvalidDecisionError(
            f"coordinates must be screenshot pixels (0..{screen.width - 1}, "
            f"0..{screen.height - 1}; got x={str(x)[:30]}, y={str(y)[:30]})"
        )
    return Point(x=x, y=y)
