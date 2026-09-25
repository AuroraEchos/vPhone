"""Public device-layer API."""

from vphone.device.adb.backend import AdbDeviceBackend
from vphone.device.adb.session import AdbDeviceSession
from vphone.device.errors import (
    AdbNotFoundError,
    DeviceClosedError,
    DeviceCommandError,
    DeviceCommandTimeoutError,
    DeviceError,
    DeviceNotFoundError,
    DeviceOfflineError,
    DeviceProtocolError,
    DeviceSelectionError,
    DeviceUnauthorizedError,
    InputError,
    ScreenshotError,
    UnsupportedCapabilityError,
)
from vphone.device.models import (
    ConnectionType,
    DeviceCapabilities,
    DeviceDescriptor,
    DeviceHealth,
    DeviceState,
    KeyCode,
    Point,
    PrimitiveResult,
    Rect,
    ScreenFrame,
)

__all__ = [
    "AdbDeviceBackend",
    "AdbDeviceSession",
    "AdbNotFoundError",
    "ConnectionType",
    "DeviceCapabilities",
    "DeviceClosedError",
    "DeviceCommandError",
    "DeviceCommandTimeoutError",
    "DeviceDescriptor",
    "DeviceError",
    "DeviceHealth",
    "DeviceNotFoundError",
    "DeviceOfflineError",
    "DeviceProtocolError",
    "DeviceSelectionError",
    "DeviceState",
    "DeviceUnauthorizedError",
    "InputError",
    "KeyCode",
    "Point",
    "PrimitiveResult",
    "Rect",
    "ScreenFrame",
    "ScreenshotError",
    "UnsupportedCapabilityError",
]
