"""Stable error types for the device layer."""

from __future__ import annotations


class DeviceError(RuntimeError):
    """Base class for device-layer failures."""


class AdbNotFoundError(DeviceError):
    pass


class DeviceNotFoundError(DeviceError):
    pass


class DeviceUnauthorizedError(DeviceError):
    pass


class DeviceOfflineError(DeviceError):
    pass


class DeviceSelectionError(DeviceError):
    pass


class DeviceClosedError(DeviceError):
    pass


class DeviceCommandError(DeviceError):
    def __init__(self, message: str, *, returncode: int | None = None):
        super().__init__(message)
        self.returncode = returncode


class DeviceCommandTimeoutError(DeviceCommandError):
    pass


class DeviceProtocolError(DeviceError):
    pass


class ScreenshotError(DeviceError):
    pass


class UiTreeError(DeviceError):
    pass


class InputError(DeviceError):
    pass


class UnsupportedCapabilityError(DeviceError):
    pass
