from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from vphone.device.adb.screenshot import capture_screen
from vphone.device.errors import ScreenshotError
from vphone.device.models import CommandResult


class FakeRunner:
    def __init__(self, data: bytes):
        self.data = data

    def run(self, args, **kwargs):
        return CommandResult(tuple(args), 0, self.data, b"", 0.25)


def png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (4, 3), color="blue").save(output, format="PNG")
    return output.getvalue()


def test_capture_screen_returns_verified_frame() -> None:
    frame = capture_screen(FakeRunner(png_bytes()), "serial")

    assert (frame.width, frame.height) == (4, 3)
    assert frame.mime_type == "image/png"
    assert len(frame.sha256) == 64
    assert frame.duration_seconds == 0.25


def test_capture_screen_rejects_invalid_data() -> None:
    with pytest.raises(ScreenshotError, match="invalid screenshot"):
        capture_screen(FakeRunner(b"not an image"), "serial")
