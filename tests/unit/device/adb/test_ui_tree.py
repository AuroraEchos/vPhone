from __future__ import annotations

import pytest

from vphone.device.adb import ui_tree
from vphone.device.adb.ui_tree import capture_ui_tree
from vphone.device.errors import UiTreeError
from vphone.device.models import CommandResult


class FakeRunner:
    def __init__(self):
        self.calls: list[tuple[tuple[str, ...], dict]] = []

    def run(self, args, **kwargs):
        self.calls.append((tuple(args), kwargs))
        stdout = (
            b'<hierarchy rotation="0"><node class="android.view.View" '
            b'bounds="[0,0][100,200]" /></hierarchy>'
            if tuple(args[:2]) == ("exec-out", "cat")
            else b""
        )
        return CommandResult(tuple(args), 0, stdout, b"", 0.1)


def test_capture_ui_tree_dumps_reads_and_cleans_up() -> None:
    runner = FakeRunner()

    snapshot = capture_ui_tree(runner, "serial")

    assert len(snapshot.nodes) == 1
    assert runner.calls[0][0][:3] == ("shell", "uiautomator", "dump")
    assert runner.calls[1][0][:2] == ("exec-out", "cat")
    assert runner.calls[2][0][:3] == ("shell", "rm", "-f")
    assert all(call[1]["serial"] == "serial" for call in runner.calls)


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def monotonic(self) -> float:
        return self.now


class TimedRunner(FakeRunner):
    def __init__(self, clock: FakeClock, durations: list[float]) -> None:
        super().__init__()
        self.clock = clock
        self.durations = iter(durations)

    def run(self, args, **kwargs):
        result = super().run(args, **kwargs)
        self.clock.now += next(self.durations)
        return result


def test_capture_ui_tree_shares_timeout_budget_across_commands(monkeypatch) -> None:
    clock = FakeClock()
    runner = TimedRunner(clock, [4.0, 1.0, 0.0])
    monkeypatch.setattr(ui_tree.time, "monotonic", clock.monotonic)

    capture_ui_tree(runner, "serial", timeout=10.0)

    assert runner.calls[0][1]["timeout"] == pytest.approx(10.0)
    assert runner.calls[1][1]["timeout"] == pytest.approx(6.0)
    assert runner.calls[2][1]["timeout"] == pytest.approx(2.0)


def test_capture_ui_tree_stops_when_timeout_budget_is_exhausted(monkeypatch) -> None:
    clock = FakeClock()
    runner = TimedRunner(clock, [10.0])
    monkeypatch.setattr(ui_tree.time, "monotonic", clock.monotonic)

    with pytest.raises(UiTreeError, match="exhausted its timeout budget"):
        capture_ui_tree(runner, "serial", timeout=10.0)

    assert len(runner.calls) == 1


def test_capture_ui_tree_rejects_non_positive_timeout() -> None:
    runner = FakeRunner()

    with pytest.raises(ValueError, match="timeout must be positive"):
        capture_ui_tree(runner, "serial", timeout=0)

    assert runner.calls == []
