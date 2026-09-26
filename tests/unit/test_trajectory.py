"""Tests for persisted task trajectories and screenshot references."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vphone.action import ActionKind, ActionResult, KeyAction, SwipeAction, TapAction, TextAction
from vphone.device import KeyCode, Point, PrimitiveResult, ScreenFrame
from vphone.perception import PageObservation
from vphone.planner.models import ActionDecision, FinishDecision, StepRecord
from vphone.trajectory import TrajectoryRecorder


def _observation(index: int) -> PageObservation:
    """Build a distinct synthetic screenshot for one planner turn.

    Args:
        index: Sequential observation number.

    Returns:
        Observation with unique screenshot bytes and hash.
    """
    return PageObservation(
        f"obs-{index}",
        ScreenFrame(
            b"png" + bytes([index]), 100, 200, "image/png", str(index) * 64, 10.0 + index, 0.2
        ),
    )


def test_trajectory_saves_each_screen_decision_and_execution(tmp_path: Path) -> None:
    """Persist two turns and link the first action to its screenshot."""
    recorder = TrajectoryRecorder(tmp_path / "traces", task="Find battery", model_id="vision-test")
    recorder.set_device_id("phone-1")
    first = _observation(1)
    recorder.record_observation(first)
    action = TapAction(Point(30, 40))
    recorder.record_decision(ActionDecision(action))
    recorder.record_step(
        StepRecord(
            first.observation_id,
            first.screen.sha256,
            action,
            ActionResult(ActionKind.TAP, 0.1, PrimitiveResult("tap", 0.08)),
        )
    )
    second = _observation(2)
    recorder.record_observation(second)
    recorder.record_decision(FinishDecision("Battery 80%"))
    recorder.finish(status="finished", message="Battery 80%")

    trace = json.loads(recorder.json_path.read_text(encoding="utf-8"))
    assert trace["schema_version"] == 1
    assert trace["task"] == "Find battery"
    assert trace["model_id"] == "vision-test"
    assert trace["device_id"] == "phone-1"
    assert trace["status"] == "finished"
    assert trace["action_count"] == 1
    assert trace["finished_at"] is not None
    assert len(trace["turns"]) == 2
    first_turn = trace["turns"][0]
    assert first_turn["observation"]["sha256"] == first.screen.sha256
    assert first_turn["decision"] == {"type": "action", "action": {"type": "tap", "x": 30, "y": 40}}
    assert first_turn["execution"]["completed"] is True
    assert first_turn["execution"]["primitive"]["operation"] == "tap"
    assert (recorder.directory / first_turn["observation"]["screenshot"]).read_bytes() == (
        first.screen.data
    )
    assert trace["turns"][1]["decision"] == {"type": "finish", "answer": "Battery 80%"}
    assert trace["turns"][1]["execution"] is None


def test_trajectory_keeps_screen_when_decision_fails(tmp_path: Path) -> None:
    """Keep the most recent screenshot even when no model decision is available."""
    recorder = TrajectoryRecorder(tmp_path / "traces", task="Find page", model_id="vision-test")
    recorder.record_observation(_observation(1))
    recorder.finish(status="error", message="model request failed")

    trace = json.loads(recorder.json_path.read_text(encoding="utf-8"))
    assert trace["status"] == "error"
    assert trace["turns"][0]["decision"] is None
    assert (recorder.directory / trace["turns"][0]["observation"]["screenshot"]).exists()


def test_trajectory_rejects_mismatched_action_result(tmp_path: Path) -> None:
    """Never attach an action result to a different screenshot."""
    recorder = TrajectoryRecorder(tmp_path / "traces", task="Find page", model_id="vision-test")
    recorder.record_observation(_observation(1))
    with pytest.raises(ValueError, match="latest observation"):
        recorder.record_step(
            StepRecord(
                "other-observation",
                "2" * 64,
                TextAction("hello"),
                ActionResult(ActionKind.TEXT, 0.1),
            )
        )


@pytest.mark.parametrize(
    "action,expected",
    [
        (TapAction(Point(5, 6)), {"type": "tap", "x": 5, "y": 6}),
        (
            SwipeAction(Point(1, 2), Point(3, 4), 300),
            {
                "type": "swipe",
                "start_x": 1,
                "start_y": 2,
                "end_x": 3,
                "end_y": 4,
                "duration_ms": 300,
            },
        ),
        (KeyAction(KeyCode.BACK), {"type": "key", "key": "BACK"}),
        (TextAction("hello"), {"type": "text", "text": "hello"}),
    ],
)
def test_trajectory_records_all_action_parameters(tmp_path: Path, action, expected: dict) -> None:
    """Preserve the exact validated parameters of every supported action."""
    recorder = TrajectoryRecorder(tmp_path / "traces", task="Test actions", model_id="vision-test")
    recorder.record_observation(_observation(1))
    recorder.record_decision(ActionDecision(action))

    trace = json.loads(recorder.json_path.read_text(encoding="utf-8"))

    assert trace["turns"][0]["decision"]["action"] == expected
