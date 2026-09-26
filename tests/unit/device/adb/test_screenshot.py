"""Unit tests for PNG screenshot capture and validation."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from vphone.device.adb.screenshot import capture_screen
from vphone.device.errors import ScreenshotError
from vphone.device.models import CommandResult


class FakeRunner:
    def __init__(self, data: bytes):
        """Store bytes to return as a simulated screenshot."""
        self.data = data

    def run(self, args, **kwargs):
        """Return the configured screenshot bytes as command output."""
        return CommandResult(tuple(args), 0, self.data, b"", 0.25)


def png_bytes() -> bytes:
    """Build a small valid PNG for screenshot tests."""
    output = BytesIO()
    Image.new("RGB", (4, 3), color="blue").save(output, format="PNG")
    return output.getvalue()


def test_capture_screen_returns_verified_frame() -> None:
    """Verify capture screen returns verified frame."""
    frame = capture_screen(FakeRunner(png_bytes()), "serial")

    assert (frame.width, frame.height) == (4, 3)
    assert frame.mime_type == "image/png"
    assert len(frame.sha256) == 64
    assert frame.duration_seconds == 0.25


def test_capture_screen_rejects_invalid_data() -> None:
    """Verify capture screen rejects invalid data."""
    with pytest.raises(ScreenshotError, match="invalid screenshot"):
        capture_screen(FakeRunner(b"not an image"), "serial")


def test_capture_screen_wraps_image_verification_syntax_error(monkeypatch) -> None:
    """Verify capture screen wraps image verification syntax error."""

    class MalformedImage:
        format = "PNG"
        size = (4, 3)

        def __enter__(self):
            """Return this malformed image as a context manager."""
            return self

        def __exit__(self, *args):
            """Leave the context without suppressing exceptions."""
            return False

        def verify(self) -> None:
            """Simulate a Pillow syntax error during verification."""
            raise SyntaxError("malformed PNG")

    monkeypatch.setattr("vphone.device.adb.screenshot.Image.open", lambda _data: MalformedImage())

    with pytest.raises(ScreenshotError, match="invalid screenshot"):
        capture_screen(FakeRunner(b"malformed PNG"), "serial")
