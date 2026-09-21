from __future__ import annotations

import base64

import pytest

from vphone.device.adb import input as adb_input
from vphone.device.errors import InputError
from vphone.device.models import CommandResult, KeyCode, Point


class FakeRunner:
    def __init__(self):
        self.calls: list[tuple[tuple[str, ...], dict]] = []

    def run(self, args, **kwargs):
        self.calls.append((tuple(args), kwargs))
        stdout = b"OK (1 test)\n" if "uiautomator" in args else b""
        return CommandResult(tuple(args), 0, stdout, b"", 0.1)


def test_tap_builds_input_command() -> None:
    runner = FakeRunner()

    result = adb_input.tap(runner, "serial", Point(12, 34))

    assert runner.calls[0][0] == ("shell", "input", "tap", "12", "34")
    assert result.operation == "tap"


def test_swipe_validates_duration() -> None:
    with pytest.raises(InputError, match="between"):
        adb_input.swipe(FakeRunner(), "serial", Point(0, 0), Point(1, 1), duration_ms=0)


def test_key_event_accepts_named_key() -> None:
    runner = FakeRunner()

    adb_input.key_event(runner, "serial", KeyCode.BACK)

    assert runner.calls[0][0] == ("shell", "input", "keyevent", "4")


def test_input_text_encodes_spaces() -> None:
    runner = FakeRunner()

    adb_input.input_text(runner, "serial", "hello phone")

    assert runner.calls[0][0] == ("shell", "input text hello%sphone")


def test_input_text_quotes_remote_shell_metacharacters() -> None:
    runner = FakeRunner()

    adb_input.input_text(runner, "serial", "it's & safe")

    assert runner.calls[0][0] == ("shell", "input text 'it'\"'\"'s%s&%ssafe'")


def test_input_text_uses_packaged_helper_for_unicode() -> None:
    runner = FakeRunner()

    result = adb_input.input_text(runner, "serial", "你好")

    assert result.operation == "input_text"
    assert runner.calls[0][0][0] == "push"
    command = runner.calls[1][0]
    assert command[:3] == ("shell", "uiautomator", "runtest")
    encoded = command[command.index("text_base64") + 1]
    assert base64.b64decode(encoded).decode("utf-8") == "你好"
    assert runner.calls[2][0][:3] == ("shell", "rm", "-f")


def test_input_text_rejects_control_characters() -> None:
    with pytest.raises(InputError, match="printable"):
        adb_input.input_text(FakeRunner(), "serial", "first\nsecond")


def test_input_text_reports_unicode_helper_failure_and_cleans_up() -> None:
    class FailingRunner(FakeRunner):
        def run(self, args, **kwargs):
            self.calls.append((tuple(args), kwargs))
            return CommandResult(tuple(args), 0, b"FAILURES!!!\n", b"", 0.1)

    runner = FailingRunner()

    with pytest.raises(InputError, match="rejected Unicode"):
        adb_input.input_text(runner, "serial", "你好")

    assert runner.calls[-1][0][:3] == ("shell", "rm", "-f")
