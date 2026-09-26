"""Opt-in integration checks for authorized Android devices."""

from __future__ import annotations

import os

import pytest

from vphone.device import AdbDeviceBackend

DEVICE_ID = os.getenv("VPHONE_DEVICE_ID")
INPUT_TEST_TEXT = os.getenv("VPHONE_INPUT_TEST_TEXT")


@pytest.mark.android
@pytest.mark.skipif(not DEVICE_ID, reason="VPHONE_DEVICE_ID is not configured")
def test_authorized_device_supports_read_only_screenshot() -> None:
    """Verify authorized device supports read only screenshot."""
    with AdbDeviceBackend().open(DEVICE_ID) as device:
        health = device.health_check(timeout=5)
        screen = device.capture_screen(timeout=10)

    assert health.ready is True
    assert screen.width > 0
    assert screen.height > 0
    assert len(screen.sha256) == 64


@pytest.mark.android
@pytest.mark.skipif(
    not DEVICE_ID or not INPUT_TEST_TEXT,
    reason="VPHONE_DEVICE_ID and VPHONE_INPUT_TEST_TEXT are not configured",
)
def test_authorized_device_inputs_unicode_into_focused_field() -> None:
    """Verify authorized device inputs unicode into focused field."""
    with AdbDeviceBackend().open(DEVICE_ID) as device:
        result = device.input_text(INPUT_TEST_TEXT, timeout=15)
        screen = device.capture_screen(timeout=10)

    assert result.operation == "input_text"
    assert screen.width > 0 and screen.height > 0
