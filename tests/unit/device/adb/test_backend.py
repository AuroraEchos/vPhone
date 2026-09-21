from __future__ import annotations

import pytest

from vphone.device.adb.backend import AdbDeviceBackend
from vphone.device.errors import DeviceNotFoundError, DeviceUnauthorizedError
from vphone.device.models import CommandResult


class FakeRunner:
    def __init__(self, output: bytes):
        self.output = output

    def run(self, args, **kwargs):
        return CommandResult(tuple(args), 0, self.output, b"", 0.1)


def test_backend_opens_ready_device() -> None:
    backend = AdbDeviceBackend(
        runner=FakeRunner(b"List of devices attached\nserial-1\tdevice model:Pixel\n")
    )

    with backend.open("serial-1") as session:
        assert session.descriptor.device_id == "serial-1"


def test_backend_rejects_unauthorized_device() -> None:
    backend = AdbDeviceBackend(
        runner=FakeRunner(b"List of devices attached\nserial-1\tunauthorized\n")
    )

    with pytest.raises(DeviceUnauthorizedError):
        backend.open("serial-1")


def test_backend_rejects_missing_device() -> None:
    backend = AdbDeviceBackend(runner=FakeRunner(b"List of devices attached\n"))

    with pytest.raises(DeviceNotFoundError):
        backend.open("missing")
