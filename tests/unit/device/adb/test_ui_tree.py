from __future__ import annotations

from vphone.device.adb.ui_tree import capture_ui_tree
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
