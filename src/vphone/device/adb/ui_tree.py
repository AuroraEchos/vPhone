"""Capture an active-window UI hierarchy with UI Automator."""

from __future__ import annotations

import time

from vphone.device.adb.runner import AdbRunner
from vphone.device.adb.xml_parser import parse_ui_tree
from vphone.device.errors import DeviceCommandTimeoutError, DeviceError, UiTreeError
from vphone.device.models import UiTreeSnapshot

_REMOTE_PATH = "/data/local/tmp/vphone-window.xml"


def capture_ui_tree(
    runner: AdbRunner,
    serial: str,
    *,
    timeout: float = 10.0,
) -> UiTreeSnapshot:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    started = time.monotonic()
    deadline = started + timeout
    try:
        runner.run(
            ("shell", "uiautomator", "dump", "--compressed", _REMOTE_PATH),
            serial=serial,
            timeout=_remaining_timeout(deadline),
        )
        result = runner.run(
            ("exec-out", "cat", _REMOTE_PATH),
            serial=serial,
            timeout=_remaining_timeout(deadline),
        )
        return parse_ui_tree(
            result.stdout,
            captured_at=time.time(),
            duration_seconds=time.monotonic() - started,
        )
    except UiTreeError:
        raise
    except DeviceError as exc:
        raise UiTreeError(f"failed to capture UI hierarchy: {exc}") from exc
    finally:
        try:
            remaining = deadline - time.monotonic()
            if remaining > 0:
                runner.run(
                    ("shell", "rm", "-f", _REMOTE_PATH),
                    serial=serial,
                    timeout=min(remaining, 2.0),
                    check=False,
                )
        except DeviceError:
            pass


def _remaining_timeout(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise DeviceCommandTimeoutError("UI hierarchy capture exhausted its timeout budget")
    return remaining
