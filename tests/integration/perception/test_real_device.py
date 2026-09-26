"""Opt-in screenshot-only observation on a real Android device."""

from __future__ import annotations

import os

import pytest

from vphone.device import AdbDeviceBackend
from vphone.device.adb.runner import AdbRunner
from vphone.perception import PerceptionEngine

DEVICE_ID = os.getenv("VPHONE_DEVICE_ID")


class RecordingRunner:
    def __init__(self) -> None:
        """Wrap the real runner while recording every ADB argument tuple."""
        self.inner = AdbRunner()
        self.calls: list[tuple[str, ...]] = []

    def run(self, args: tuple[str, ...], **kwargs: object):
        """Record and forward one ADB command to the real runner."""
        self.calls.append(tuple(args))
        return self.inner.run(args, **kwargs)


@pytest.mark.android
@pytest.mark.skipif(not DEVICE_ID, reason="VPHONE_DEVICE_ID is not configured")
def test_real_page_observation_contains_current_screenshot() -> None:
    """Verify real page observation contains current screenshot."""
    runner = RecordingRunner()
    with AdbDeviceBackend(runner=runner).open(DEVICE_ID) as device:
        observation = PerceptionEngine().observe(device)

    assert observation.screen.width > 0
    assert observation.screen.height > 0
    assert len(observation.screen.sha256) == 64
    assert observation.observation_id
    assert runner.calls == [("devices", "-l"), ("exec-out", "screencap", "-p")]
    assert not hasattr(observation, "text_candidates")
    assert not hasattr(observation, "tree_status")
