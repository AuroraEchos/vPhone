"""Low-level, non-retrying Android input primitives."""

from __future__ import annotations

import shlex

from vphone.device.adb.runner import AdbRunner
from vphone.device.errors import InputError
from vphone.device.models import KeyCode, Point, PrimitiveResult


def tap(
    runner: AdbRunner,
    serial: str,
    point: Point,
    *,
    timeout: float = 5.0,
) -> PrimitiveResult:
    result = runner.run(
        ("shell", "input", "tap", str(point.x), str(point.y)),
        serial=serial,
        timeout=timeout,
    )
    return PrimitiveResult("tap", result.duration_seconds)


def swipe(
    runner: AdbRunner,
    serial: str,
    start: Point,
    end: Point,
    *,
    duration_ms: int = 300,
    timeout: float = 5.0,
) -> PrimitiveResult:
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, int):
        raise InputError("duration_ms must be an integer")
    if not 1 <= duration_ms <= 10_000:
        raise InputError("duration_ms must be between 1 and 10000")
    result = runner.run(
        (
            "shell",
            "input",
            "swipe",
            str(start.x),
            str(start.y),
            str(end.x),
            str(end.y),
            str(duration_ms),
        ),
        serial=serial,
        timeout=timeout,
    )
    return PrimitiveResult("swipe", result.duration_seconds)


def key_event(
    runner: AdbRunner,
    serial: str,
    key: KeyCode | int,
    *,
    timeout: float = 5.0,
) -> PrimitiveResult:
    if isinstance(key, KeyCode):
        value = key.value
    elif isinstance(key, int) and not isinstance(key, bool) and key >= 0:
        value = str(key)
    else:
        raise InputError("key must be a KeyCode or non-negative integer")
    result = runner.run(("shell", "input", "keyevent", value), serial=serial, timeout=timeout)
    return PrimitiveResult("key_event", result.duration_seconds)


def input_text(
    runner: AdbRunner,
    serial: str,
    text: str,
    *,
    timeout: float = 10.0,
) -> PrimitiveResult:
    if not isinstance(text, str) or not text:
        raise InputError("text must be a non-empty string")
    if not text.isascii() or any(
        ord(character) < 32 or ord(character) == 127 for character in text
    ):
        raise InputError("the ADB text backend supports printable ASCII only")
    encoded = shlex.quote(text.replace(" ", "%s"))
    result = runner.run(("shell", "input", "text", encoded), serial=serial, timeout=timeout)
    return PrimitiveResult("input_text", result.duration_seconds)
