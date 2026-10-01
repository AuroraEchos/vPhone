"""Unit tests for planner tool schemas and pixel validation."""

from __future__ import annotations

import json

import pytest

from vphone.action import (
    KeyAction,
    ReplaceTextAction,
    SwipeAction,
    TapAction,
    TextAction,
    WaitAction,
)
from vphone.device import KeyCode, Point, ScreenFrame
from vphone.planner.coordinates import to_screen_point
from vphone.planner.errors import InvalidDecisionError
from vphone.planner.models import (
    ActionDecision,
    DecisionTrace,
    FinishDecision,
    StopDecision,
)
from vphone.planner.tools import parse_tool_call, tools_for_screen

TRACE = DecisionTrace("Settings screen with a Battery entry", "Open Battery for the task")


def _args(**values: object) -> str:
    """Build tool arguments with the required task-aware trace fields."""
    return json.dumps(
        {
            "screen_summary": TRACE.screen_summary,
            "decision_reason": TRACE.decision_reason,
            **values,
        }
    )


@pytest.fixture
def screen() -> ScreenFrame:
    """Return the phone-sized synthetic frame used by tool tests."""
    return ScreenFrame(b"png", 1216, 2640, "image/png", "a" * 64, 1.0, 0.1)


def test_coordinate_edges_and_midpoint(screen: ScreenFrame) -> None:
    """Verify coordinate edges and midpoint."""
    assert to_screen_point(0, 0, screen) == Point(0, 0)
    assert to_screen_point(1215, 2639, screen) == Point(1215, 2639)
    assert to_screen_point(608, 1320, screen) == Point(608, 1320)


def test_every_tool_requires_task_aware_trace_fields(screen: ScreenFrame) -> None:
    """Require screen meaning and decision intent for every possible decision."""
    tools = tools_for_screen(screen)

    assert len(tools) == 8
    assert all(tool["function"]["name"] != "request_confirmation" for tool in tools)
    for tool in tools:
        parameters = tool["function"]["parameters"]
        assert "screen_summary" in parameters["properties"]
        assert "decision_reason" in parameters["properties"]
        assert "screen_summary" in parameters["required"]
        assert "decision_reason" in parameters["required"]


@pytest.mark.parametrize("x,y", [(-1, 2), (1216, 2), (1, 2640), (False, 3), (1.5, 3)])
def test_coordinate_rejects_bad_values(screen: ScreenFrame, x: object, y: object) -> None:
    """Verify coordinate rejects bad values."""
    with pytest.raises(InvalidDecisionError):
        to_screen_point(x, y, screen)


def test_parse_supported_tools(screen: ScreenFrame) -> None:
    """Verify parse supported tools."""
    tap = parse_tool_call("tap", _args(x=1215, y=0), screen)
    swipe = parse_tool_call(
        "swipe",
        _args(start_x=500, start_y=800, end_x=500, end_y=300, duration_ms=350),
        screen,
    )
    key = parse_tool_call("press_key", _args(key="BACK"), screen)
    typed = parse_tool_call("input_text", _args(text="hello"), screen)
    replaced = parse_tool_call("replace_text", _args(text="updated"), screen)
    wait = parse_tool_call("wait", _args(seconds=3), screen)
    assert tap == ActionDecision(TapAction(Point(1215, 0)), TRACE)
    assert isinstance(swipe, ActionDecision) and isinstance(swipe.action, SwipeAction)
    assert swipe.trace == TRACE
    assert key == ActionDecision(KeyAction(KeyCode.BACK), TRACE)
    assert typed == ActionDecision(TextAction("hello"), TRACE)
    assert replaced == ActionDecision(ReplaceTextAction("updated"), TRACE)
    assert wait == ActionDecision(WaitAction(3), TRACE)
    assert parse_tool_call("finish", _args(answer="42"), screen) == FinishDecision("42", TRACE)
    assert parse_tool_call("stop", _args(reason="unknown"), screen) == StopDecision(
        "unknown", TRACE
    )


def test_wait_tool_advertises_and_enforces_upper_cap(screen: ScreenFrame) -> None:
    """Guide normal model output and defensively cap an out-of-schema duration."""
    wait_tool = next(
        tool for tool in tools_for_screen(screen) if tool["function"]["name"] == "wait"
    )
    seconds = wait_tool["function"]["parameters"]["properties"]["seconds"]
    assert seconds["exclusiveMinimum"] == 0
    assert seconds["maximum"] == 30.0

    decision = parse_tool_call("wait", _args(seconds=300), screen)

    assert decision == ActionDecision(WaitAction(30), TRACE)


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("tap", "not json"),
        ("tap", "[]"),
        ("tap", _args(x=1, y=2, extra=3)),
        ("tap", _args(x=True, y=2)),
        ("tap", _args(x=1216, y=2)),
        (
            "swipe",
            _args(start_x=0, start_y=0, end_x=1, end_y=1, duration_ms=10001),
        ),
        ("press_key", _args(key="POWER")),
        ("input_text", _args(text="\n")),
        ("replace_text", _args(text="\n")),
        ("wait", _args(seconds=0)),
        ("wait", _args(seconds=True)),
        ("finish", _args(answer="")),
        ("tap", json.dumps({"screen_summary": "settings", "x": 1, "y": 2})),
        ("tap", _args(x=1, y=2, screen_summary="\n")),
        ("made_up", _args()),
    ],
)
def test_parse_rejects_invalid_tool_calls(screen: ScreenFrame, name: str, arguments: str) -> None:
    """Verify parse rejects invalid tool calls."""
    with pytest.raises(InvalidDecisionError):
        parse_tool_call(name, arguments, screen)
