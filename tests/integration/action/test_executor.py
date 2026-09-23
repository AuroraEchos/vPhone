from __future__ import annotations

import os

import pytest

from vphone.action import ActionExecutor, ActionKind, KeyAction
from vphone.device import AdbDeviceBackend, KeyCode

DEVICE_ID = os.getenv("VPHONE_DEVICE_ID")


@pytest.mark.android
@pytest.mark.skipif(not DEVICE_ID, reason="VPHONE_DEVICE_ID is not configured")
def test_executor_sends_home_key_to_real_device() -> None:
    with AdbDeviceBackend().open(DEVICE_ID) as device:
        result = ActionExecutor(device).execute(KeyAction(KeyCode.HOME), timeout=5)
        screen = device.capture_screen(timeout=10)

    assert result.kind is ActionKind.KEY
    assert result.completed is True
    assert result.primitive is not None
    assert result.primitive.operation == "key_event"
    assert screen.width > 0 and screen.height > 0
