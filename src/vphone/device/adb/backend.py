"""Public ADB backend implementation."""

from __future__ import annotations

from vphone.device.adb.discovery import list_devices
from vphone.device.adb.runner import AdbRunner
from vphone.device.adb.session import AdbDeviceSession
from vphone.device.errors import (
    DeviceNotFoundError,
    DeviceOfflineError,
    DeviceUnauthorizedError,
)
from vphone.device.models import DeviceDescriptor, DeviceState


class AdbDeviceBackend:
    def __init__(self, adb_path: str | None = None, *, runner: AdbRunner | None = None):
        if adb_path is not None and runner is not None:
            raise ValueError("pass adb_path or runner, not both")
        self._runner = runner or AdbRunner(adb_path)

    def list_devices(self, *, timeout: float = 5.0) -> list[DeviceDescriptor]:
        return list_devices(self._runner, timeout=timeout)

    def open(self, device_id: str, *, timeout: float = 5.0) -> AdbDeviceSession:
        if not isinstance(device_id, str):
            raise TypeError("device_id must be a string")
        device_id = device_id.strip()
        if not device_id:
            raise ValueError("device_id must be a non-empty string")
        descriptor = next(
            (item for item in self.list_devices(timeout=timeout) if item.device_id == device_id),
            None,
        )
        if descriptor is None:
            raise DeviceNotFoundError(f"ADB device was not found: {device_id}")
        if descriptor.state is DeviceState.UNAUTHORIZED:
            raise DeviceUnauthorizedError(f"ADB device is unauthorized: {device_id}")
        if descriptor.state is DeviceState.OFFLINE:
            raise DeviceOfflineError(f"ADB device is offline: {device_id}")
        if descriptor.state is not DeviceState.READY:
            raise DeviceOfflineError(
                f"ADB device is not ready: {device_id} ({descriptor.state.value})"
            )
        return AdbDeviceSession(self._runner, descriptor)
