"""Real-device integration coverage for the L2 action executor."""

from __future__ import annotations

import os

import pytest

from vphone.action import ActionExecutor, ActionKind, KeyAction, LongPressAction
from vphone.device import AdbDeviceBackend, KeyCode, Point

DEVICE_ID = os.getenv("VPHONE_DEVICE_ID")


@pytest.mark.android
@pytest.mark.skipif(not DEVICE_ID, reason="VPHONE_DEVICE_ID is not configured")
def test_executor_sends_home_key_to_real_device() -> None:
    """Verify executor sends home key to real device."""
    with AdbDeviceBackend().open(DEVICE_ID) as device:
        result = ActionExecutor(device).execute(KeyAction(KeyCode.HOME), timeout=5)
        screen = device.capture_screen(timeout=10)

    assert result.kind is ActionKind.KEY
    assert result.completed is True
    assert result.primitive is not None
    assert result.primitive.operation == "key_event"
    assert screen.width > 0 and screen.height > 0


@pytest.mark.android
@pytest.mark.skipif(not DEVICE_ID, reason="VPHONE_DEVICE_ID is not configured")
def test_executor_long_presses_real_device() -> None:
    """Verify a coordinate long press completes against a real Android device."""
    with AdbDeviceBackend().open(DEVICE_ID) as device:
        device.key_event(KeyCode.HOME, timeout=5)
        screen = device.capture_screen(timeout=10)
        point = Point(screen.width // 2, screen.height // 3)
        result = ActionExecutor(device).execute(LongPressAction(point), timeout=5)
        after = device.capture_screen(timeout=10)

    assert result.kind is ActionKind.LONG_PRESS
    assert result.completed is True
    assert result.primitive is not None
    assert result.primitive.operation == "long_press"
    assert after.width == screen.width and after.height == screen.height
    assert after.sha256 != screen.sha256
