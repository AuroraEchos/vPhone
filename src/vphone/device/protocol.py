"""Backend-independent interfaces for Android devices."""

from __future__ import annotations

from typing import Protocol

from vphone.device.models import (
    DeviceCapabilities,
    DeviceDescriptor,
    DeviceHealth,
    KeyCode,
    Point,
    PrimitiveResult,
    ScreenFrame,
    UiTreeSnapshot,
)


class DeviceSession(Protocol):
    descriptor: DeviceDescriptor
    capabilities: DeviceCapabilities

    def health_check(self, *, timeout: float = 5.0) -> DeviceHealth: ...

    def capture_screen(self, *, timeout: float = 10.0) -> ScreenFrame: ...

    def capture_ui_tree(self, *, timeout: float = 10.0) -> UiTreeSnapshot: ...

    def tap(self, point: Point, *, timeout: float = 5.0) -> PrimitiveResult: ...

    def swipe(
        self,
        start: Point,
        end: Point,
        *,
        duration_ms: int = 300,
        timeout: float = 5.0,
    ) -> PrimitiveResult: ...

    def key_event(self, key: KeyCode | int, *, timeout: float = 5.0) -> PrimitiveResult: ...

    def input_text(self, text: str, *, timeout: float = 10.0) -> PrimitiveResult: ...

    def close(self) -> None: ...


class DeviceBackend(Protocol):
    def list_devices(self, *, timeout: float = 5.0) -> list[DeviceDescriptor]: ...

    def open(self, device_id: str, *, timeout: float = 5.0) -> DeviceSession: ...
