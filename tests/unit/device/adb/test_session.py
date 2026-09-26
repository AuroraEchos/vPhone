"""Unit tests for ADB device session lifecycle and serialization."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from vphone.device.adb.session import AdbDeviceSession
from vphone.device.errors import DeviceClosedError
from vphone.device.models import (
    CommandResult,
    ConnectionType,
    DeviceDescriptor,
    DeviceState,
)


class FakeRunner:
    def run(self, args, **kwargs):
        """Return a ready-device state for any simulated ADB command."""
        return CommandResult(tuple(args), 0, b"device\n", b"", 0.1)


def descriptor() -> DeviceDescriptor:
    """Build the ready USB descriptor shared by session tests."""
    return DeviceDescriptor("serial", DeviceState.READY, ConnectionType.USB)


def test_health_check_reports_ready_device() -> None:
    """Verify health check reports ready device."""
    session = AdbDeviceSession(FakeRunner(), descriptor())

    health = session.health_check()

    assert health.ready is True
    assert health.state is DeviceState.READY


def test_closed_session_rejects_operations() -> None:
    """Verify closed session rejects operations."""
    session = AdbDeviceSession(FakeRunner(), descriptor())
    session.close()

    with pytest.raises(DeviceClosedError):
        session.health_check()


def test_sessions_for_same_device_serialize_commands() -> None:
    """Verify sessions for same device serialize commands."""

    class ConcurrentRunner:
        def __init__(self):
            """Initialize counters for simultaneous command execution."""
            self.guard = threading.Lock()
            self.active = 0
            self.max_active = 0

        def run(self, args, **kwargs):
            """Measure overlapping calls while simulating a slow command."""
            with self.guard:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            time.sleep(0.02)
            with self.guard:
                self.active -= 1
            return CommandResult(tuple(args), 0, b"device\n", b"", 0.02)

    runner = ConcurrentRunner()
    first = AdbDeviceSession(runner, descriptor())
    second = AdbDeviceSession(runner, descriptor())

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(session.health_check) for session in (first, second)]
        assert all(future.result().ready for future in futures)

    assert runner.max_active == 1
