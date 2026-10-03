"""Execute concrete actions through a backend-independent device session."""

from __future__ import annotations

import math
import time

from vphone.action.models import (
    Action,
    ActionKind,
    ActionResult,
    KeyAction,
    LongPressAction,
    ReplaceTextAction,
    SwipeAction,
    TapAction,
    TextAction,
    WaitAction,
)
from vphone.device.errors import DeviceError
from vphone.device.protocol import DeviceSession


class ActionExecutor:
    def __init__(self, device: DeviceSession):
        """Bind an executor to one backend-independent device session.

        Args:
            device: Session that will receive actions backed by device primitives.
        """
        self._device = device

    def execute(self, action: Action, *, timeout: float | None = None) -> ActionResult:
        """Run one action without retrying or judging the resulting screen.

        Args:
            action: Concrete L2 action to dispatch.
            timeout: Optional override for the L1 primitive timeout.

        Returns:
            Action outcome; completion does not prove a UI effect.

        Raises:
            TypeError: If the action or timeout has an invalid type.
            ValueError: If the timeout is not finite and positive.
        """
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
            elif isinstance(action, LongPressAction):
                primitive = self._device.long_press(action.point, **options)
            elif isinstance(action, SwipeAction):
                primitive = self._device.swipe(
                    action.start, action.end, duration_ms=action.duration_ms, **options
                )
            elif isinstance(action, KeyAction):
                primitive = self._device.key_event(action.key, **options)
            elif isinstance(action, TextAction):
                primitive = self._device.input_text(action.text, **options)
            elif isinstance(action, ReplaceTextAction):
                primitive = self._device.replace_text(action.text, **options)
            else:
                time.sleep(action.seconds)
                primitive = None
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
    """Map an L2 action instance to its result kind."""
    if isinstance(action, TapAction):
        return ActionKind.TAP
    if isinstance(action, LongPressAction):
        return ActionKind.LONG_PRESS
    if isinstance(action, SwipeAction):
        return ActionKind.SWIPE
    if isinstance(action, KeyAction):
        return ActionKind.KEY
    if isinstance(action, TextAction):
        return ActionKind.TEXT
    if isinstance(action, ReplaceTextAction):
        return ActionKind.REPLACE_TEXT
    if isinstance(action, WaitAction):
        return ActionKind.WAIT
    raise TypeError("action must be a supported L2 action")


if __name__ == "__main__":
    from vphone.device import AdbDeviceBackend
    from vphone.device.models import Point

    backend = AdbDeviceBackend()
    devices = backend.list_devices()

    with backend.open(devices[0].device_id) as device:
        executor = ActionExecutor(device)

        executor.execute(LongPressAction(Point(100, 200)))
