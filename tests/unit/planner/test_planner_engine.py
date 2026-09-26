"""Tests for the L4 controller."""

from __future__ import annotations

from vphone.action import ActionKind, TapAction
from vphone.device import Point, PrimitiveResult, ScreenFrame
from vphone.planner.engine import PlannerEngine
from vphone.planner.errors import InvalidDecisionError
from vphone.planner.models import (
    ActionDecision,
    ConfirmationDecision,
    FinishDecision,
    RunStatus,
)


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
    model = FakeModel([ActionDecision(TapAction(Point(30, 40))), FinishDecision("Battery 80%")])

    result = PlannerEngine(model, settle_seconds=0).run("Find battery", device)

    assert result.status is RunStatus.FINISHED
    assert result.message == "Battery 80%"
    assert device.taps == [Point(30, 40)]
    assert device.screen_calls == 2
    assert [item[1] for item in model.seen] == [0, 1]
    assert model.seen[0][0] != model.seen[1][0]
    assert result.steps[0].screen_sha256 == "1" * 64
    assert result.final_observation.screen.sha256 == "2" * 64


def test_callbacks_follow_observation_decision_execution_order() -> None:
    """Expose each turn to trajectory recording in chronological order."""
    events: list[str] = []
    model = FakeModel([ActionDecision(TapAction(Point(30, 40))), FinishDecision("done")])
    planner = PlannerEngine(
        model,
        settle_seconds=0,
        on_observation=lambda observation: events.append("observation"),
        on_decision=lambda decision: events.append("decision"),
        on_step=lambda step: events.append("execution"),
    )

    result = planner.run("Find page", FakeDevice())

    assert result.status is RunStatus.FINISHED
    assert events == ["observation", "decision", "execution", "observation", "decision"]


def test_action_limit_stops_before_extra_execution() -> None:
    """Verify action limit stops before extra execution."""
    device = FakeDevice()
    proposal = ActionDecision(TapAction(Point(30, 40)))
    model = FakeModel([proposal, proposal])

    result = PlannerEngine(model, max_actions=1, settle_seconds=0).run("Find battery", device)

    assert result.status is RunStatus.ACTION_LIMIT
    assert device.taps == [Point(30, 40)]
    assert device.screen_calls == 2


def test_disallowed_action_does_not_reach_device() -> None:
    """Verify disallowed action does not reach device."""
    device = FakeDevice()
    model = FakeModel([ActionDecision(TapAction(Point(30, 40)))])

    result = PlannerEngine(model, allowed_kinds=frozenset({ActionKind.KEY}), settle_seconds=0).run(
        "Find battery", device
    )

    assert result.status is RunStatus.STOPPED
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
    model = FakeModel([ConfirmationDecision("Proceed with a consequential step?")])

    result = PlannerEngine(model, settle_seconds=0).run("Do something", device)

    assert result.status is RunStatus.NEEDS_CONFIRMATION
    assert result.completed is False
    assert result.message == "Proceed with a consequential step?"
    assert device.taps == []
