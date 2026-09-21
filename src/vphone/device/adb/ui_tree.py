"""Capture an active-window UI hierarchy with UI Automator."""

from __future__ import annotations

import time

from vphone.device.adb.runner import AdbRunner
from vphone.device.adb.xml_parser import parse_ui_tree
from vphone.device.errors import DeviceError, UiTreeError
from vphone.device.models import UiTreeSnapshot

_REMOTE_PATH = "/data/local/tmp/vphone-window.xml"


def capture_ui_tree(
    runner: AdbRunner,
    serial: str,
    *,
    timeout: float = 10.0,
) -> UiTreeSnapshot:
    started = time.monotonic()
    try:
        runner.run(
            ("shell", "uiautomator", "dump", "--compressed", _REMOTE_PATH),
            serial=serial,
            timeout=timeout,
        )
        result = runner.run(("exec-out", "cat", _REMOTE_PATH), serial=serial, timeout=timeout)
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
            runner.run(
                ("shell", "rm", "-f", _REMOTE_PATH),
                serial=serial,
                timeout=min(timeout, 2.0),
                check=False,
            )
        except DeviceError:
            pass
