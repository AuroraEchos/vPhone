"""Tests for the task-based package and console entry points."""

from __future__ import annotations

import json
import tomllib
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

import vphone.main as cli
from vphone.action import ActionKind, ActionResult, TextAction
from vphone.planner.models import RunResult, RunStatus, StepRecord


def test_console_entry_point_targets_main() -> None:
    """Keep the project command mapped to the package-level main function."""
    project_file = Path(__file__).resolve().parents[2] / "pyproject.toml"
    project = tomllib.loads(project_file.read_text(encoding="utf-8"))
    assert project["project"]["scripts"]["vphone"] == "vphone.main:main"


def test_main_wires_task_config_device_and_planner(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Exercise the complete entry-point wiring without a phone or network."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "_trajectory_root", lambda: tmp_path / "traces")
    monkeypatch.setattr(cli, "find_dotenv", lambda **kwargs: "")
    monkeypatch.setattr(cli, "load_dotenv", lambda path: None)
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("VPHONE_MODEL_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("VPHONE_MODEL_ID", "vision-test")
    monkeypatch.setenv("VPHONE_MAX_ACTIONS", "3")
    monkeypatch.setenv("VPHONE_MAX_SECONDS", "30")
    monkeypatch.setenv("VPHONE_SETTLE_SECONDS", "0")
    monkeypatch.delenv("VPHONE_DEVICE_ID", raising=False)
    observed: dict = {}
    phone = object()

    class FakeBackend:
        """Return one authorized synthetic device."""

        def list_devices(self):
            """Expose one ready device for automatic selection."""
            return [SimpleNamespace(device_id="test-device", state=SimpleNamespace(value="device"))]

        def open(self, device_id):
            """Open the selected synthetic device as a context manager."""
            observed["device_id"] = device_id
            return nullcontext(phone)

    def fake_model(config):
        """Capture the configured model without creating an SDK client."""
        observed["config"] = config
        return object()

    def fake_planner(model, **options):
        """Capture limits and return a successful task result."""
        observed["planner_model"] = model
        observed["options"] = options

        def run(task, device):
            """Record the task and device selected by the entry point."""
            observed["task"] = task
            observed["device"] = device
            return RunResult(RunStatus.FINISHED, "Battery 80%", (), None)

        return SimpleNamespace(run=run)

    monkeypatch.setattr(cli, "AdbDeviceBackend", FakeBackend)
    monkeypatch.setattr(cli, "OpenAICompatibleDecisionModel", fake_model)
    monkeypatch.setattr(cli, "PlannerEngine", fake_planner)

    cli.main(["查看当前电量"])

    assert observed["config"].model_id == "vision-test"
    assert observed["device_id"] == "test-device"
    assert observed["device"] is phone
    assert observed["task"] == "查看当前电量"
    assert observed["options"]["max_actions"] == 3
    assert observed["options"]["max_seconds"] == 30
    assert observed["options"]["settle_seconds"] == 0
    assert "allowed_kinds" not in observed["options"]
    output = capsys.readouterr().out
    assert "status=finished; actions=0" in output
    trace_file = next((tmp_path / "traces").glob("*/trajectory.json"))
    assert f"trajectory={trace_file}" in output
    trace = json.loads(trace_file.read_text(encoding="utf-8"))
    assert trace["task"] == "查看当前电量"
    assert trace["status"] == "finished"
    assert trace["device_id"] == "test-device"


def test_main_requires_task(capsys: pytest.CaptureFixture[str]) -> None:
    """Reject a missing task before loading credentials or opening a device."""
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 2
    assert "task" in capsys.readouterr().err


def test_configuration_failure_is_saved_as_trajectory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Write an error trace even when a task cannot reach the device."""
    monkeypatch.setattr(cli, "find_dotenv", lambda **kwargs: "")
    monkeypatch.setattr(cli, "load_dotenv", lambda path: None)
    monkeypatch.setattr(cli, "_trajectory_root", lambda: tmp_path / "traces")
    monkeypatch.setenv("API_KEY", "")
    monkeypatch.setenv("VPHONE_MODEL_ID", "vision-test")

    with pytest.raises(SystemExit, match="Invalid model or runtime configuration"):
        cli.main(["查看电量"])

    trace_file = next((tmp_path / "traces").glob("*/trajectory.json"))
    trace = json.loads(trace_file.read_text(encoding="utf-8"))
    assert trace["status"] == "error"
    assert trace["task"] == "查看电量"
    assert trace["turns"] == []


def test_progress_output_hides_text_input(capsys: pytest.CaptureFixture[str]) -> None:
    """Never print the contents of a text action in progress logs."""
    step = StepRecord(
        "obs", "a" * 64, TextAction("private value"), ActionResult(ActionKind.TEXT, 0.1)
    )
    cli._report_step(step)
    output = capsys.readouterr().out
    assert "TextAction" in output
    assert "private value" not in output
