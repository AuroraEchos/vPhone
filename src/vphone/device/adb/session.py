"""Synchronous session for one ready ADB device."""

from __future__ import annotations

import threading
import time
from types import TracebackType
from typing import Self

from vphone.device.adb import input as adb_input
from vphone.device.adb.runner import AdbRunner
from vphone.device.adb.screenshot import capture_screen
from vphone.device.adb.ui_tree import capture_ui_tree
from vphone.device.errors import DeviceClosedError
from vphone.device.models import (
    DeviceCapabilities,
    DeviceDescriptor,
    DeviceHealth,
    DeviceState,
    KeyCode,
    Point,
    PrimitiveResult,
    ScreenFrame,
    UiTreeSnapshot,
)

_DEVICE_LOCKS_GUARD = threading.Lock()
_DEVICE_LOCKS: dict[str, threading.RLock] = {}


def _lock_for_device(device_id: str) -> threading.RLock:
    with _DEVICE_LOCKS_GUARD:
        lock = _DEVICE_LOCKS.get(device_id)
        if lock is None:
            lock = threading.RLock()
            _DEVICE_LOCKS[device_id] = lock
        return lock


class AdbDeviceSession:
    def __init__(self, runner: AdbRunner, descriptor: DeviceDescriptor):
        self._runner = runner
        self.descriptor = descriptor
        self.capabilities = DeviceCapabilities()
        self._lock = _lock_for_device(descriptor.device_id)
        self._closed = False

    def health_check(self, *, timeout: float = 5.0) -> DeviceHealth:
        with self._lock:
            self._ensure_open()
            result = self._runner.run(
                ("get-state",), serial=self.descriptor.device_id, timeout=timeout, check=False
            )
            state_text = result.stdout.decode("utf-8", errors="replace").strip()
            try:
                state = DeviceState(state_text)
            except ValueError:
                combined = (result.stdout + result.stderr).decode("utf-8", errors="replace")
                folded = combined.casefold()
                state = (
                    DeviceState.UNAUTHORIZED
                    if "unauthorized" in folded
                    else DeviceState.OFFLINE
                    if "offline" in folded
                    else DeviceState.UNKNOWN
                )
            return DeviceHealth(
                ready=result.returncode == 0 and state is DeviceState.READY,
                state=state,
                checked_at=time.time(),
                message=result.stderr.decode("utf-8", errors="replace").strip(),
            )

    def capture_screen(self, *, timeout: float = 10.0) -> ScreenFrame:
        with self._lock:
            self._ensure_open()
            return capture_screen(self._runner, self.descriptor.device_id, timeout=timeout)

    def capture_ui_tree(self, *, timeout: float = 10.0) -> UiTreeSnapshot:
        with self._lock:
            self._ensure_open()
            return capture_ui_tree(self._runner, self.descriptor.device_id, timeout=timeout)

    def tap(self, point: Point, *, timeout: float = 5.0) -> PrimitiveResult:
        with self._lock:
            self._ensure_open()
            return adb_input.tap(self._runner, self.descriptor.device_id, point, timeout=timeout)

    def swipe(
        self,
        start: Point,
        end: Point,
        *,
        duration_ms: int = 300,
        timeout: float = 5.0,
    ) -> PrimitiveResult:
        with self._lock:
            self._ensure_open()
            return adb_input.swipe(
                self._runner,
                self.descriptor.device_id,
                start,
                end,
                duration_ms=duration_ms,
                timeout=timeout,
            )

    def key_event(self, key: KeyCode | int, *, timeout: float = 5.0) -> PrimitiveResult:
        with self._lock:
            self._ensure_open()
            return adb_input.key_event(
                self._runner, self.descriptor.device_id, key, timeout=timeout
            )

    def input_text(self, text: str, *, timeout: float = 10.0) -> PrimitiveResult:
        with self._lock:
            self._ensure_open()
            return adb_input.input_text(
                self._runner, self.descriptor.device_id, text, timeout=timeout
            )

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def __enter__(self) -> Self:
        with self._lock:
            self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise DeviceClosedError(f"device session is closed: {self.descriptor.device_id}")
