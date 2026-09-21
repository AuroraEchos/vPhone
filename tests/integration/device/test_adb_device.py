from __future__ import annotations

import os

import pytest

from vphone.device import AdbDeviceBackend

DEVICE_ID = os.getenv("VPHONE_DEVICE_ID")


@pytest.mark.android
@pytest.mark.skipif(not DEVICE_ID, reason="VPHONE_DEVICE_ID is not configured")
def test_authorized_device_supports_read_only_observation() -> None:
    backend = AdbDeviceBackend()

    with backend.open(DEVICE_ID) as device:
        health = device.health_check(timeout=5)
        screen = device.capture_screen(timeout=10)
        tree = device.capture_ui_tree(timeout=15)

    assert health.ready is True
    assert screen.width > 0
    assert screen.height > 0
    assert len(screen.sha256) == 64
    assert tree.source == "uiautomator"
    assert len(tree.sha256) == 64
