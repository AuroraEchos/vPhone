"""Unit tests for the bounded ADB subprocess runner."""

from __future__ import annotations

import subprocess

import pytest

from vphone.device.adb.runner import AdbRunner
from vphone.device.errors import (
    DeviceCommandTimeoutError,
    DeviceOfflineError,
    DeviceUnauthorizedError,
)


def test_runner_builds_serial_scoped_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify runner builds serial scoped command."""
    observed: dict[str, object] = {}

    def fake_run(command, **kwargs):
        """Capture the subprocess arguments and return a ready device."""
        observed["command"] = command
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout=b"device\n", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = AdbRunner("/opt/adb").run(("get-state",), serial="serial-1", timeout=3)

    assert observed["command"] == ["/opt/adb", "-s", "serial-1", "get-state"]
    assert observed["kwargs"]["timeout"] == 3
    assert observed["kwargs"]["check"] is False
    assert result.stdout == b"device\n"


def test_runner_converts_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify runner converts timeout."""

    def fake_run(command, **kwargs):
        """Raise a subprocess timeout for the requested duration."""
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(DeviceCommandTimeoutError):
        AdbRunner("/opt/adb").run(("get-state",), timeout=0.1)


@pytest.mark.parametrize(
    ("stderr", "error_type"),
    [
        (b"error: device unauthorized", DeviceUnauthorizedError),
        (b"error: device offline", DeviceOfflineError),
    ],
)
def test_runner_classifies_device_errors(
    monkeypatch: pytest.MonkeyPatch, stderr: bytes, error_type: type[Exception]
) -> None:
    """Verify runner classifies device errors."""

    def fake_run(command, **kwargs):
        """Return an ADB failure with the parameterized error text."""
        return subprocess.CompletedProcess(command, 1, stdout=b"", stderr=stderr)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(error_type):
        AdbRunner("/opt/adb").run(("get-state",))


def test_runner_rejects_empty_arguments() -> None:
    """Verify runner rejects empty arguments."""
    with pytest.raises(ValueError, match="cannot be empty"):
        AdbRunner("/opt/adb").run(())
