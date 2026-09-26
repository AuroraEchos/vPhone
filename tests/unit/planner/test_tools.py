"""Unit tests for planner tool schemas and pixel validation."""

from __future__ import annotations

import pytest

from vphone.action import KeyAction, SwipeAction, TapAction, TextAction
from vphone.device import KeyCode, Point, ScreenFrame
from vphone.planner.coordinates import to_screen_point
from vphone.planner.errors import InvalidDecisionError
from vphone.planner.models import (
    ActionDecision,
    ConfirmationDecision,
    FinishDecision,
    StopDecision,
)
from vphone.planner.tools import parse_tool_call


@pytest.fixture
def screen() -> ScreenFrame:
    """Return the phone-sized synthetic frame used by tool tests."""
    return ScreenFrame(b"png", 1216, 2640, "image/png", "a" * 64, 1.0, 0.1)


def test_coordinate_edges_and_midpoint(screen: ScreenFrame) -> None:
    """Verify coordinate edges and midpoint."""
    assert to_screen_point(0, 0, screen) == Point(0, 0)
    assert to_screen_point(1215, 2639, screen) == Point(1215, 2639)
    assert to_screen_point(608, 1320, screen) == Point(608, 1320)


@pytest.mark.parametrize("x,y", [(-1, 2), (1216, 2), (1, 2640), (False, 3), (1.5, 3)])
def test_coordinate_rejects_bad_values(screen: ScreenFrame, x: object, y: object) -> None:
    """Verify coordinate rejects bad values."""
    with pytest.raises(InvalidDecisionError):
        to_screen_point(x, y, screen)


def test_parse_supported_tools(screen: ScreenFrame) -> None:
    """Verify parse supported tools."""
    tap = parse_tool_call("tap", '{"x":1215,"y":0}', screen)
    swipe = parse_tool_call(
        "swipe",
        '{"start_x":500,"start_y":800,"end_x":500,"end_y":300,"duration_ms":350}',
        screen,
    )
    key = parse_tool_call("press_key", '{"key":"BACK"}', screen)
    typed = parse_tool_call("input_text", '{"text":"hello"}', screen)
    assert tap == ActionDecision(TapAction(Point(1215, 0)))
    assert isinstance(swipe, ActionDecision) and isinstance(swipe.action, SwipeAction)
    assert key == ActionDecision(KeyAction(KeyCode.BACK))
    assert typed == ActionDecision(TextAction("hello"))
    assert parse_tool_call("finish", '{"answer":"42"}', screen) == FinishDecision("42")
    assert parse_tool_call("stop", '{"reason":"unknown"}', screen) == StopDecision("unknown")
    assert parse_tool_call(
        "request_confirmation", '{"question":"Proceed?"}', screen
    ) == ConfirmationDecision("Proceed?")


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("tap", "not json"),
        ("tap", "[]"),
        ("tap", '{"x":1,"y":2,"extra":3}'),
        ("tap", '{"x":true,"y":2}'),
        ("tap", '{"x":1216,"y":2}'),
        ("swipe", '{"start_x":0,"start_y":0,"end_x":1,"end_y":1,"duration_ms":10001}'),
        ("press_key", '{"key":"POWER"}'),
        ("input_text", '{"text":"\\n"}'),
        ("finish", '{"answer":""}'),
        ("made_up", "{}"),
    ],
)
def test_parse_rejects_invalid_tool_calls(screen: ScreenFrame, name: str, arguments: str) -> None:
    """Verify parse rejects invalid tool calls."""
    with pytest.raises(InvalidDecisionError):
        parse_tool_call(name, arguments, screen)
