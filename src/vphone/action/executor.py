"""Execute concrete actions through a backend-independent device session."""

from __future__ import annotations

import math
import time

from vphone.action.models import (
    Action,
    ActionKind,
    ActionResult,
    KeyAction,
    SwipeAction,
    TapAction,
    TextAction,
)
from vphone.device.errors import DeviceError
from vphone.device.protocol import DeviceSession


class ActionExecutor:
    def __init__(self, device: DeviceSession):
        self._device = device

    def execute(self, action: Action, *, timeout: float | None = None) -> ActionResult:
        """Run one action without retrying or judging the resulting screen."""
        kind = _kind_of(action)
        if timeout is not None:
            if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
                raise TypeError("timeout must be a number")
            if not math.isfinite(timeout) or timeout <= 0:
                raise ValueError("timeout must be finite and positive")
        options = {} if timeout is None else {"timeout": timeout}

        started = time.monotonic()
        try:
            if isinstance(action, TapAction):
                primitive = self._device.tap(action.point, **options)
            elif isinstance(action, SwipeAction):
                primitive = self._device.swipe(
                    action.start, action.end, duration_ms=action.duration_ms, **options
                )
            elif isinstance(action, KeyAction):
                primitive = self._device.key_event(action.key, **options)
            else:
                primitive = self._device.input_text(action.text, **options)
        except DeviceError as exc:
            return ActionResult(
                kind=kind,
                duration_seconds=time.monotonic() - started,
                error=exc,
            )

        return ActionResult(
            kind=kind,
            duration_seconds=time.monotonic() - started,
            primitive=primitive,
        )


def _kind_of(action: Action) -> ActionKind:
    if isinstance(action, TapAction):
        return ActionKind.TAP
    if isinstance(action, SwipeAction):
        return ActionKind.SWIPE
    if isinstance(action, KeyAction):
        return ActionKind.KEY
    if isinstance(action, TextAction):
        return ActionKind.TEXT
    raise TypeError("action must be a supported L2 action")
