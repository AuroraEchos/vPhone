"""The single subprocess boundary for the ADB backend."""

from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Sequence

from vphone.device.errors import (
    AdbNotFoundError,
    DeviceCommandError,
    DeviceCommandTimeoutError,
    DeviceError,
    DeviceNotFoundError,
    DeviceOfflineError,
    DeviceProtocolError,
    DeviceSelectionError,
    DeviceUnauthorizedError,
)
from vphone.device.models import CommandResult


class AdbRunner:
    """Run bounded ADB commands without invoking a local shell."""

    def __init__(self, adb_path: str | None = None, *, max_output_bytes: int = 32 * 1024 * 1024):
        """Resolve ADB and set a per-stream output safety limit.

        Args:
            adb_path: Explicit executable path, or ``None`` to search ``PATH``.
            max_output_bytes: Maximum bytes accepted from each output stream.

        Raises:
            AdbNotFoundError: If no ADB executable can be located.
            ValueError: If the output limit is not positive.
        """
        resolved = adb_path or shutil.which("adb")
        if not resolved:
            raise AdbNotFoundError("adb was not found in PATH")
        if max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")
        self.adb_path = resolved
        self.max_output_bytes = max_output_bytes

    def run(
        self,
        args: Sequence[str],
        *,
        serial: str | None = None,
        timeout: float = 10.0,
        check: bool = True,
    ) -> CommandResult:
        """Run one bounded ADB command without a local shell.

        Args:
            args: ADB arguments after the optional device selector.
            serial: Optional target device serial.
            timeout: Maximum subprocess duration in seconds.
            check: Whether a nonzero exit status raises a device error.

        Returns:
            Command output, exit status, arguments, and elapsed time.

        Raises:
            DeviceError: If ADB fails, times out, or exceeds the output limit.
            ValueError: If the timeout, serial, or arguments are invalid.
        """
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        normalized = self._validate_args(args)
        command = [self.adb_path]
        if serial is not None:
            if not serial or "\x00" in serial:
                raise ValueError("serial must be a non-empty device id")
            command.extend(("-s", serial))
        command.extend(normalized)

        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise AdbNotFoundError(f"adb executable does not exist: {self.adb_path}") from exc
        except subprocess.TimeoutExpired as exc:
            raise DeviceCommandTimeoutError(
                f"adb operation timed out after {timeout:g} seconds"
            ) from exc

        result = CommandResult(
            argv=tuple(command),
            returncode=completed.returncode,
            stdout=completed.stdout or b"",
            stderr=completed.stderr or b"",
            duration_seconds=time.monotonic() - started,
        )
        if len(result.stdout) > self.max_output_bytes or len(result.stderr) > self.max_output_bytes:
            raise DeviceProtocolError(
                f"adb output exceeded the {self.max_output_bytes}-byte safety limit"
            )
        if check and result.returncode != 0:
            raise self.error_for(result)
        return result

    @staticmethod
    def error_for(result: CommandResult) -> DeviceError:
        """Classify a failed ADB result into a structured device error."""
        output = (result.stdout + b"\n" + result.stderr).decode("utf-8", errors="replace").strip()
        folded = output.casefold()
        message = output[:1000] or f"adb exited with status {result.returncode}"
        if "unauthorized" in folded:
            return DeviceUnauthorizedError(message)
        if "offline" in folded:
            return DeviceOfflineError(message)
        if "more than one device" in folded:
            return DeviceSelectionError(message)
        if "no devices/emulators found" in folded or (
            "device '" in folded and "not found" in folded
        ):
            return DeviceNotFoundError(message)
        return DeviceCommandError(message, returncode=result.returncode)

    @staticmethod
    def _validate_args(args: Sequence[str]) -> list[str]:
        """Reject empty, non-string, or NUL-containing ADB arguments."""
        if not args:
            raise ValueError("adb arguments cannot be empty")
        normalized: list[str] = []
        for value in args:
            if not isinstance(value, str):
                raise TypeError("adb arguments must be strings")
            if not value or "\x00" in value:
                raise ValueError("adb arguments cannot be empty or contain NUL")
            normalized.append(value)
        return normalized
