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
)


class DeviceSession(Protocol):
    descriptor: DeviceDescriptor
    capabilities: DeviceCapabilities

    def health_check(self, *, timeout: float = 5.0) -> DeviceHealth:
        """Return current readiness within the requested timeout."""
        ...

    def capture_screen(self, *, timeout: float = 10.0) -> ScreenFrame:
        """Capture one verified current screen frame."""
        ...

    def tap(self, point: Point, *, timeout: float = 5.0) -> PrimitiveResult:
        """Tap a concrete screen pixel and report command completion."""
        ...

    def swipe(
        self,
        start: Point,
        end: Point,
        *,
        duration_ms: int = 300,
        timeout: float = 5.0,
    ) -> PrimitiveResult:
        """Swipe between concrete pixels for the requested duration."""
        ...

    def key_event(self, key: KeyCode | int, *, timeout: float = 5.0) -> PrimitiveResult:
        """Send one Android key event."""
        ...

    def input_text(self, text: str, *, timeout: float = 10.0) -> PrimitiveResult:
        """Type printable text into the currently focused field."""
        ...

    def close(self) -> None:
        """Close this session and prevent further use."""
        ...


class DeviceBackend(Protocol):
    def list_devices(self, *, timeout: float = 5.0) -> list[DeviceDescriptor]:
        """List ADB-visible devices and their states."""
        ...

    def open(self, device_id: str, *, timeout: float = 5.0) -> DeviceSession:
        """Open a session for a ready device with the given serial."""
        ...
