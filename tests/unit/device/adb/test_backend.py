"""Unit tests for ADB backend discovery and session opening."""

from __future__ import annotations

import pytest

from vphone.device.adb.backend import AdbDeviceBackend
from vphone.device.errors import DeviceNotFoundError, DeviceUnauthorizedError
from vphone.device.models import CommandResult


class FakeRunner:
    def __init__(self, output: bytes):
        """Set the ADB device-listing bytes returned by this fake."""
        self.output = output

    def run(self, args, **kwargs):
        """Return the configured device listing for any command."""
        return CommandResult(tuple(args), 0, self.output, b"", 0.1)


def test_backend_opens_ready_device() -> None:
    """Verify backend opens ready device."""
    backend = AdbDeviceBackend(
        runner=FakeRunner(b"List of devices attached\nserial-1\tdevice model:Pixel\n")
    )

    with backend.open("serial-1") as session:
        assert session.descriptor.device_id == "serial-1"


def test_backend_normalizes_device_id_before_lookup() -> None:
    """Verify backend normalizes device id before lookup."""
    backend = AdbDeviceBackend(
        runner=FakeRunner(b"List of devices attached\nserial-1\tdevice model:Pixel\n")
    )

    with backend.open("  serial-1\t") as session:
        assert session.descriptor.device_id == "serial-1"


def test_backend_rejects_non_string_device_id() -> None:
    """Verify backend rejects non string device id."""
    backend = AdbDeviceBackend(runner=FakeRunner(b"List of devices attached\n"))

    with pytest.raises(TypeError, match="must be a string"):
        backend.open(123)  # type: ignore[arg-type]


def test_backend_rejects_unauthorized_device() -> None:
    """Verify backend rejects unauthorized device."""
    backend = AdbDeviceBackend(
        runner=FakeRunner(b"List of devices attached\nserial-1\tunauthorized\n")
    )

    with pytest.raises(DeviceUnauthorizedError):
        backend.open("serial-1")


def test_backend_rejects_missing_device() -> None:
    """Verify backend rejects missing device."""
    backend = AdbDeviceBackend(runner=FakeRunner(b"List of devices attached\n"))

    with pytest.raises(DeviceNotFoundError):
        backend.open("missing")
