"""PNG screenshot capture through ADB."""

from __future__ import annotations

import hashlib
import time
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from vphone.device.adb.runner import AdbRunner
from vphone.device.errors import ScreenshotError
from vphone.device.models import ScreenFrame


def capture_screen(
    runner: AdbRunner,
    serial: str,
    *,
    timeout: float = 10.0,
) -> ScreenFrame:
    """Capture and verify a PNG screenshot from one device.

    Args:
        runner: ADB command runner.
        serial: Target device serial.
        timeout: Maximum screenshot command duration in seconds.

    Returns:
        Raw PNG bytes with dimensions, hash, and capture metadata.

    Raises:
        ScreenshotError: If ADB returns empty or invalid PNG data.
    """
    result = runner.run(("exec-out", "screencap", "-p"), serial=serial, timeout=timeout)
    data = result.stdout
    if not data:
        raise ScreenshotError("adb returned an empty screenshot")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format != "PNG":
                raise ScreenshotError(
                    f"expected a PNG screenshot, received {image.format or 'unknown'}"
                )
            width, height = image.size
            image.verify()
    except ScreenshotError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ScreenshotError(f"invalid screenshot data: {exc}") from exc
    return ScreenFrame(
        data=data,
        width=width,
        height=height,
        mime_type="image/png",
        sha256=hashlib.sha256(data).hexdigest(),
        captured_at=time.time(),
        duration_seconds=result.duration_seconds,
    )
