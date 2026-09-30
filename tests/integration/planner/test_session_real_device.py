"""Real-device coverage for the single-step planning session."""

from __future__ import annotations

import os

import pytest

from vphone.action import KeyAction
from vphone.device import AdbDeviceBackend, KeyCode
from vphone.planner.models import (
    ActionDecision,
    DecisionTrace,
    FinishDecision,
    SessionStatus,
)
from vphone.planner.session import PlannerSession

DEVICE_ID = os.getenv("VPHONE_DEVICE_ID")
TRACE = DecisionTrace("A current Android screen", "Exercise one safe device action")


class SequenceModel:
    def __init__(self) -> None:
        self.decisions = [
            ActionDecision(KeyAction(KeyCode.HOME), TRACE),
            FinishDecision("home action completed", TRACE),
        ]
        self.history_lengths: list[int] = []

    def decide(self, task, observation, history):
        """Return one safe action followed by a terminal decision."""
        assert task == "Return to the Android home screen"
        assert observation.screen.width > 0
        assert observation.screen.height > 0
        self.history_lengths.append(len(history))
        return self.decisions.pop(0)


@pytest.mark.android
@pytest.mark.skipif(not DEVICE_ID, reason="VPHONE_DEVICE_ID is not configured")
def test_session_steps_once_then_finishes_on_fresh_real_screenshot() -> None:
    """Run one safe action and one terminal turn through a real device session."""
    model = SequenceModel()
    with AdbDeviceBackend().open(DEVICE_ID) as device:
        session = PlannerSession(
            model,
            "Return to the Android home screen",
            device,
            settle_seconds=0,
        )

        first = session.step()
        second = session.step()

    assert first.status is SessionStatus.RUNNING
    assert len(first.steps) == 1
    assert first.steps[0].result.completed is True
    assert second.status is SessionStatus.FINISHED
    assert second.terminal is True
    assert model.history_lengths == [0, 1]
    assert first.latest_observation.observation_id != second.latest_observation.observation_id
