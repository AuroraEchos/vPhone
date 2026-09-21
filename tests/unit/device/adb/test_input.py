from __future__ import annotations

import pytest

from vphone.device.adb import input as adb_input
from vphone.device.errors import InputError
from vphone.device.models import CommandResult, KeyCode, Point


class FakeRunner:
    def __init__(self):
        self.calls: list[tuple[tuple[str, ...], dict]] = []

    def run(self, args, **kwargs):
        self.calls.append((tuple(args), kwargs))
        return CommandResult(tuple(args), 0, b"", b"", 0.1)


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


def test_input_text_rejects_unicode() -> None:
    with pytest.raises(InputError, match="ASCII"):
        adb_input.input_text(FakeRunner(), "serial", "你好")
