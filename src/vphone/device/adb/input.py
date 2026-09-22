"""Low-level, non-retrying Android input primitives."""

from __future__ import annotations

import base64
import importlib.resources
import shlex
import time
import uuid

from vphone.device.adb.runner import AdbRunner
from vphone.device.errors import DeviceCommandTimeoutError, DeviceError, InputError
from vphone.device.models import KeyCode, Point, PrimitiveResult

_UNICODE_HELPER = "resources/vphone-unicode-input.jar"
_UNICODE_TEST_CLASS = "dev.vphone.UnicodeInputTest"


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
    if not text.isprintable():
        raise InputError("text must contain printable characters only")
    if not text.isascii():
        return _input_unicode(runner, serial, text, timeout=timeout)

    if timeout <= 0:
        raise ValueError("timeout must be positive")
    started = time.monotonic()
    deadline = started + timeout
    for chunk in _ascii_input_chunks(text):
        encoded = chunk.replace(" ", "%s")
        # ADB joins shell arguments, so quote the user-controlled value for the remote shell.
        remote_command = f"input text {shlex.quote(encoded)}"
        runner.run(("shell", remote_command), serial=serial, timeout=_remaining_timeout(deadline))
    return PrimitiveResult("input_text", time.monotonic() - started)


def _ascii_input_chunks(text: str) -> list[str]:
    """Keep literal %s across commands; Android input text decodes it as a space."""
    chunks: list[str] = []
    start = 0
    while (index := text.find("%s", start)) != -1:
        chunks.append(text[start : index + 1])
        start = index + 1
    chunks.append(text[start:])
    return chunks


def _input_unicode(
    runner: AdbRunner,
    serial: str,
    text: str,
    *,
    timeout: float,
) -> PrimitiveResult:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    started = time.monotonic()
    deadline = started + timeout
    remote_path = f"/data/local/tmp/vphone-unicode-input-{uuid.uuid4().hex}.jar"
    helper = importlib.resources.files("vphone.device.adb").joinpath(_UNICODE_HELPER)

    try:
        with importlib.resources.as_file(helper) as helper_path:
            if not helper_path.is_file():
                raise InputError("the packaged Unicode input helper is missing")
            runner.run(
                ("push", str(helper_path), remote_path),
                serial=serial,
                timeout=_remaining_timeout(deadline),
            )

        encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
        result = runner.run(
            (
                "shell",
                "uiautomator",
                "runtest",
                remote_path,
                "-c",
                _UNICODE_TEST_CLASS,
                "-e",
                "text_base64",
                encoded,
                "-e",
                "outputFormat",
                "simple",
            ),
            serial=serial,
            timeout=_remaining_timeout(deadline),
        )
        output = result.stdout + result.stderr
        if b"OK (" not in output or b"FAILURES!!!" in output:
            raise InputError("the focused UI node rejected Unicode text")
        return PrimitiveResult("input_text", time.monotonic() - started)
    finally:
        try:
            remaining = deadline - time.monotonic()
            if remaining > 0:
                runner.run(
                    ("shell", "rm", "-f", remote_path),
                    serial=serial,
                    timeout=min(remaining, 2.0),
                    check=False,
                )
        except DeviceError:
            pass


def _remaining_timeout(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise DeviceCommandTimeoutError("text input exhausted its timeout budget")
    return remaining
