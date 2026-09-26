"""Function-tool schemas and validated conversion to L2 actions."""

from __future__ import annotations

import json
from typing import Any

from vphone.action.models import KeyAction, SwipeAction, TapAction, TextAction
from vphone.device.models import KeyCode, ScreenFrame
from vphone.planner.coordinates import to_screen_point
from vphone.planner.errors import InvalidDecisionError
from vphone.planner.models import (
    ActionDecision,
    ConfirmationDecision,
    Decision,
    FinishDecision,
    StopDecision,
)


def _tool(name: str, description: str, properties: dict[str, Any]) -> dict[str, Any]:
    """Build one function tool definition from required JSON properties."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        },
    }


def tools_for_screen(screen: ScreenFrame) -> list[dict[str, Any]]:
    """Create function tools bounded to one screenshot's pixel dimensions.

    Args:
        screen: Current screenshot defining valid pixel bounds.

    Returns:
        Chat Completions-compatible function tool definitions.
    """
    x_coord = {"type": "integer", "minimum": 0, "maximum": screen.width - 1}
    y_coord = {"type": "integer", "minimum": 0, "maximum": screen.height - 1}
    return [
        _tool(
            "tap",
            "Tap one visible target using exact x/y pixels in the full current screenshot.",
            {"x": x_coord, "y": y_coord},
        ),
        _tool(
            "swipe",
            "Swipe using exact pixel coordinates in the full current screenshot.",
            {
                "start_x": x_coord,
                "start_y": y_coord,
                "end_x": x_coord,
                "end_y": y_coord,
                "duration_ms": {"type": "integer", "minimum": 100, "maximum": 2000},
            },
        ),
        _tool(
            "press_key",
            "Press an Android navigation key; POWER is not available.",
            {"key": {"type": "string", "enum": ["BACK", "HOME", "ENTER", "APP_SWITCH"]}},
        ),
        _tool(
            "input_text",
            "Type printable text into the currently focused input field.",
            {"text": {"type": "string"}},
        ),
        _tool(
            "finish",
            "Finish only when the current screenshot supports the answer.",
            {"answer": {"type": "string"}},
        ),
        _tool(
            "stop",
            "Stop when the screen or next step is uncertain.",
            {"reason": {"type": "string"}},
        ),
        _tool(
            "request_confirmation",
            "Pause before a consequential or irreversible step.",
            {"question": {"type": "string"}},
        ),
    ]


def parse_tool_call(name: str, arguments: str, screen: ScreenFrame) -> Decision:
    """Convert one model tool call into a validated planner decision.

    Args:
        name: Function name returned by the model.
        arguments: JSON argument object returned by the model.
        screen: Current screenshot used for pixel-bound validation.

    Returns:
        An L2 action proposal or a terminal planner decision.

    Raises:
        InvalidDecisionError: If the tool, fields, or values are invalid.
    """
    try:
        values = json.loads(arguments)
    except (TypeError, ValueError) as exc:
        raise InvalidDecisionError("tool arguments are not JSON") from exc
    if not isinstance(values, dict):
        raise InvalidDecisionError("tool arguments must be an object")

    expected = {
        "tap": {"x", "y"},
        "swipe": {"start_x", "start_y", "end_x", "end_y", "duration_ms"},
        "press_key": {"key"},
        "input_text": {"text"},
        "finish": {"answer"},
        "stop": {"reason"},
        "request_confirmation": {"question"},
    }
    if name not in expected or values.keys() != expected[name]:
        raise InvalidDecisionError(
            f"unknown tool or invalid argument fields: tool={name[:40]}, "
            f"fields={sorted(str(key)[:40] for key in values)}"
        )

    if name == "tap":
        return ActionDecision(TapAction(to_screen_point(values["x"], values["y"], screen)))
    if name == "swipe":
        duration = values["duration_ms"]
        if type(duration) is not int or not 100 <= duration <= 2000:
            raise InvalidDecisionError("swipe duration must be an integer in 100..2000")
        return ActionDecision(
            SwipeAction(
                start=to_screen_point(values["start_x"], values["start_y"], screen),
                end=to_screen_point(values["end_x"], values["end_y"], screen),
                duration_ms=duration,
            )
        )
    if name == "press_key":
        key = values["key"]
        if not isinstance(key, str) or key not in {"BACK", "HOME", "ENTER", "APP_SWITCH"}:
            raise InvalidDecisionError("unsupported key")
        return ActionDecision(KeyAction(KeyCode[key]))

    field = {
        "input_text": "text",
        "finish": "answer",
        "stop": "reason",
        "request_confirmation": "question",
    }[name]
    value = values[field]
    if not isinstance(value, str) or not value.strip() or len(value) > 1000:
        raise InvalidDecisionError(f"{field} must be non-empty text up to 1000 characters")
    if name == "input_text":
        if not value.isprintable():
            raise InvalidDecisionError("input text must be printable")
        return ActionDecision(TextAction(value))
    if name == "finish":
        return FinishDecision(value)
    if name == "stop":
        return StopDecision(value)
    return ConfirmationDecision(value)
