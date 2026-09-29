"""Tests for the L4 controller."""

from __future__ import annotations

from vphone.action import ActionKind, TapAction, WaitAction
from vphone.device import Point, PrimitiveResult, ScreenFrame
from vphone.planner.engine import PlannerEngine
from vphone.planner.errors import InvalidDecisionError
from vphone.planner.models import (
    ActionDecision,
    ConfirmationDecision,
    DecisionTrace,
    FinishDecision,
    RunStatus,
)

TRACE = DecisionTrace("A task-relevant screen", "This decision advances the task")


class FakeDevice:
    def __init__(self) -> None:
        """Initialize screenshot and tap counters for planner tests."""
        self.screen_calls = 0
        self.taps: list[Point] = []

    def capture_screen(self, *, timeout: float = 10.0) -> ScreenFrame:
        """Return a distinct synthetic frame for each observation."""
        self.screen_calls += 1
        return ScreenFrame(
            b"png" + bytes([self.screen_calls]),
            100,
            200,
            "image/png",
            str(self.screen_calls) * 64,
            1.0,
            0.0,
        )

    def tap(self, point: Point, *, timeout: float = 5.0) -> PrimitiveResult:
        """Record a tap without touching a real device."""
        self.taps.append(point)
        return PrimitiveResult("tap", 0.0)


class FakeModel:
    def __init__(self, decisions: list) -> None:
        """Queue decisions to return in successive planner turns."""
        self.decisions = decisions
        self.seen: list[tuple[str, int]] = []

    def decide(self, task, observation, history):
        """Record the observation and return the next queued decision."""
        self.seen.append((observation.observation_id, len(history)))
        item = self.decisions.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_one_action_then_fresh_observation_and_finish() -> None:
    """Verify one action then fresh observation and finish."""
    device = FakeDevice()
    model = FakeModel(
        [ActionDecision(TapAction(Point(30, 40)), TRACE), FinishDecision("Battery 80%", TRACE)]
    )

    result = PlannerEngine(model, settle_seconds=0).run("Find battery", device)

    assert result.status is RunStatus.FINISHED
    assert result.message == "Battery 80%"
    assert device.taps == [Point(30, 40)]
    assert device.screen_calls == 2
    assert [item[1] for item in model.seen] == [0, 1]
    assert model.seen[0][0] != model.seen[1][0]
    assert result.steps[0].screen_sha256 == "1" * 64
    assert result.steps[0].trace == TRACE
    assert result.final_observation.screen.sha256 == "2" * 64


def test_step_callback_reports_executed_action() -> None:
    """Report an action result once, while keeping the planner's in-memory history."""
    reported = []
    model = FakeModel(
        [ActionDecision(TapAction(Point(30, 40)), TRACE), FinishDecision("done", TRACE)]
    )
    planner = PlannerEngine(model, settle_seconds=0, on_step=reported.append)

    result = planner.run("Find page", FakeDevice())

    assert result.status is RunStatus.FINISHED
    assert reported == list(result.steps)


def test_action_limit_stops_before_extra_execution() -> None:
    """Verify action limit stops before extra execution."""
    device = FakeDevice()
    proposal = ActionDecision(TapAction(Point(30, 40)), TRACE)
    model = FakeModel([proposal, proposal])

    result = PlannerEngine(model, max_actions=1, settle_seconds=0).run("Find battery", device)

    assert result.status is RunStatus.ACTION_LIMIT
    assert device.taps == [Point(30, 40)]
    assert device.screen_calls == 2


def test_disallowed_action_does_not_reach_device() -> None:
    """Verify disallowed action does not reach device."""
    device = FakeDevice()
    model = FakeModel([ActionDecision(TapAction(Point(30, 40)), TRACE)])

    result = PlannerEngine(model, allowed_kinds=frozenset({ActionKind.KEY}), settle_seconds=0).run(
        "Find battery", device
    )

    assert result.status is RunStatus.STOPPED
    assert device.taps == []


def test_wait_action_is_recorded_and_followed_by_fresh_observation(
    monkeypatch,
) -> None:
    """Treat waiting as a bounded action before observing the loading screen again."""
    waits = []
    monkeypatch.setattr("vphone.action.executor.time.sleep", waits.append)
    device = FakeDevice()
    model = FakeModel([ActionDecision(WaitAction(2), TRACE), FinishDecision("loaded", TRACE)])

    result = PlannerEngine(model, settle_seconds=0).run("Wait for loading", device)

    assert result.status is RunStatus.FINISHED
    assert waits == [2.0]
    assert result.steps[0].result.kind is ActionKind.WAIT
    assert device.screen_calls == 2
    assert device.taps == []


def test_invalid_model_decision_stops_without_action() -> None:
    """Verify invalid model decision stops without action."""
    device = FakeDevice()
    model = FakeModel([InvalidDecisionError("bad coordinates")])

    result = PlannerEngine(model, settle_seconds=0).run("Find battery", device)

    assert result.status is RunStatus.ERROR
    assert "bad coordinates" in result.message
    assert device.taps == []


def test_confirmation_pauses_without_device_action() -> None:
    """Verify confirmation pauses without device action."""
    device = FakeDevice()
    model = FakeModel([ConfirmationDecision("Proceed with a consequential step?", TRACE)])

    result = PlannerEngine(model, settle_seconds=0).run("Do something", device)

    assert result.status is RunStatus.NEEDS_CONFIRMATION
    assert result.completed is False
    assert result.message == "Proceed with a consequential step?"
    assert device.taps == []
