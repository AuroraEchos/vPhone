"""Data contracts shared by device backends and their callers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DeviceState(StrEnum):
    READY = "device"
    OFFLINE = "offline"
    UNAUTHORIZED = "unauthorized"
    UNKNOWN = "unknown"


class ConnectionType(StrEnum):
    USB = "usb"
    EMULATOR = "emulator"
    NETWORK = "network"
    UNKNOWN = "unknown"


class KeyCode(StrEnum):
    BACK = "4"  # 返回键，回到上一页
    HOME = "3"  # 主页键，回到系统桌面
    ENTER = "66"  # 回车键，确认输入
    POWER = "26"  # 电源键，锁屏/唤醒
    APP_SWITCH = "187"  # 多任务 / 最近应用键


@dataclass(frozen=True, slots=True)
class DeviceDescriptor:
    device_id: str
    state: DeviceState
    connection_type: ConnectionType
    product: str | None = None
    model: str | None = None
    device: str | None = None
    transport_id: str | None = None


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    screenshot: bool = True
    ui_tree: bool = True
    coordinate_input: bool = True
    key_events: bool = True
    ascii_text: bool = True
    unicode_text: bool = True
    native_node_action: bool = False


@dataclass(frozen=True, slots=True)
class DeviceHealth:
    ready: bool
    state: DeviceState
    checked_at: float
    message: str = ""


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int

    def __post_init__(self) -> None:
        if isinstance(self.x, bool) or isinstance(self.y, bool):
            raise TypeError("coordinates must be integers")
        if not isinstance(self.x, int) or not isinstance(self.y, int):
            raise TypeError("coordinates must be integers")
        if self.x < 0 or self.y < 0:
            raise ValueError("coordinates cannot be negative")


@dataclass(frozen=True, slots=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    def __post_init__(self) -> None:
        values = (self.left, self.top, self.right, self.bottom)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise TypeError("rectangle coordinates must be integers")
        if self.right < self.left or self.bottom < self.top:
            raise ValueError("rectangle bounds are inverted")

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


@dataclass(frozen=True, slots=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: bytes
    stderr: bytes
    duration_seconds: float


@dataclass(frozen=True, slots=True)
class ScreenFrame:
    data: bytes
    width: int
    height: int
    mime_type: str
    sha256: str
    captured_at: float
    duration_seconds: float

    def __post_init__(self) -> None:
        if not self.data:
            raise ValueError("screen data cannot be empty")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("screen dimensions must be positive")
        if self.duration_seconds < 0:
            raise ValueError("capture duration cannot be negative")


@dataclass(frozen=True, slots=True)
class RawUiNode:
    node_id: str
    parent_id: str | None
    package_name: str
    class_name: str
    resource_id: str
    text: str
    content_description: str
    bounds: Rect
    checkable: bool
    checked: bool
    clickable: bool
    enabled: bool
    focusable: bool
    focused: bool
    scrollable: bool
    long_clickable: bool
    selected: bool
    password: bool


@dataclass(frozen=True, slots=True)
class UiTreeSnapshot:
    nodes: tuple[RawUiNode, ...]
    rotation: int | None
    sha256: str
    captured_at: float
    duration_seconds: float
    source: str = "uiautomator"

    def __post_init__(self) -> None:
        if self.duration_seconds < 0:
            raise ValueError("capture duration cannot be negative")


@dataclass(frozen=True, slots=True)
class PrimitiveResult:
    operation: str
    duration_seconds: float

    def __post_init__(self) -> None:
        if self.duration_seconds < 0:
            raise ValueError("operation duration cannot be negative")
