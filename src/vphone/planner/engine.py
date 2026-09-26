"""Bounded observe-decide-act loop with one action per screenshot."""

from __future__ import annotations

import math
import time
from collections.abc import Callable

from vphone.action import ActionExecutor
from vphone.action.models import ActionKind, KeyAction, SwipeAction, TapAction, TextAction
from vphone.device.protocol import DeviceSession
from vphone.perception import PerceptionEngine
from vphone.perception.errors import PerceptionError
from vphone.perception.models import PageObservation
from vphone.planner.errors import PlannerError
from vphone.planner.models import (
    ActionDecision,
    ConfirmationDecision,
    Decision,
    FinishDecision,
    RunResult,
    RunStatus,
    StepRecord,
    StopDecision,
)
from vphone.planner.protocol import DecisionModel


class PlannerEngine:
    def __init__(
        self,
        model: DecisionModel,
        *,
        max_actions: int = 12,
        max_seconds: float = 600.0,
        settle_seconds: float = 0.5,
        allowed_kinds: frozenset[ActionKind] | None = None,
        on_observation: Callable[[PageObservation], None] | None = None,
        on_decision: Callable[[Decision], None] | None = None,
        on_step: Callable[[StepRecord], None] | None = None,
    ):
        """Configure a bounded visual decision loop.

        Args:
            model: Provider that proposes one decision per observation.
            max_actions: Maximum number of actions to dispatch.
            max_seconds: Overall run budget in seconds.
            settle_seconds: Wait after each completed action before re-observation.
            allowed_kinds: Permitted L2 action kinds, or all kinds by default.
            on_observation: Optional callback after each screenshot capture.
            on_decision: Optional callback after each model decision.
            on_step: Optional callback after each dispatched action.

        Raises:
            ValueError: If action or time limits are invalid.
        """
        if type(max_actions) is not int or max_actions < 1:
            raise ValueError("max_actions must be a positive integer")
        if (
            isinstance(max_seconds, bool)
            or not isinstance(max_seconds, (int, float))
            or not math.isfinite(max_seconds)
            or max_seconds <= 0
            or isinstance(settle_seconds, bool)
            or not isinstance(settle_seconds, (int, float))
            or not math.isfinite(settle_seconds)
            or settle_seconds < 0
        ):
            raise ValueError("time limits must be valid")
        self._model = model
        self._max_actions = max_actions
        self._max_seconds = max_seconds
        self._settle_seconds = settle_seconds
        self._allowed_kinds = frozenset(ActionKind) if allowed_kinds is None else allowed_kinds
        self._on_observation = on_observation
        self._on_decision = on_decision
        self._on_step = on_step

    def run(self, task: str, device: DeviceSession) -> RunResult:
        """Observe, request one decision, and execute at most one action per cycle.

        Args:
            task: Nonempty natural-language task.
            device: Session shared by perception and action execution.

        Returns:
            Terminal status, action trace, and last observed screenshot.

        Raises:
            ValueError: If the task is empty or not text.
        """
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be non-empty text")
        started = time.monotonic()
        steps: list[StepRecord] = []
        latest = None
        executor = ActionExecutor(device)
        perception = PerceptionEngine()

        while True:
            if time.monotonic() - started >= self._max_seconds:
                return RunResult(RunStatus.TIME_LIMIT, "time limit reached", tuple(steps), latest)
            try:
                latest = perception.observe(device)
                if self._on_observation is not None:
                    self._on_observation(latest)
                decision = self._model.decide(task, latest, tuple(steps))
                if self._on_decision is not None:
                    self._on_decision(decision)
            except (PerceptionError, PlannerError) as exc:
                return RunResult(RunStatus.ERROR, str(exc), tuple(steps), latest)
            if time.monotonic() - started >= self._max_seconds:
                return RunResult(RunStatus.TIME_LIMIT, "time limit reached", tuple(steps), latest)
            if isinstance(decision, FinishDecision):
                return RunResult(RunStatus.FINISHED, decision.answer, tuple(steps), latest)
            if isinstance(decision, StopDecision):
                return RunResult(RunStatus.STOPPED, decision.reason, tuple(steps), latest)
            if isinstance(decision, ConfirmationDecision):
                return RunResult(
                    RunStatus.NEEDS_CONFIRMATION, decision.question, tuple(steps), latest
                )
            if not isinstance(decision, ActionDecision):
                return RunResult(RunStatus.ERROR, "unsupported decision", tuple(steps), latest)
            if len(steps) >= self._max_actions:
                return RunResult(
                    RunStatus.ACTION_LIMIT, "action limit reached", tuple(steps), latest
                )
            action = decision.action
            kind = (
                ActionKind.TAP
                if isinstance(action, TapAction)
                else ActionKind.SWIPE
                if isinstance(action, SwipeAction)
                else ActionKind.KEY
                if isinstance(action, KeyAction)
                else ActionKind.TEXT
                if isinstance(action, TextAction)
                else None
            )
            if kind not in self._allowed_kinds:
                return RunResult(RunStatus.STOPPED, "action kind not allowed", tuple(steps), latest)
            outcome = executor.execute(action)
            record = StepRecord(latest.observation_id, latest.screen.sha256, action, outcome)
            steps.append(record)
            if self._on_step is not None:
                self._on_step(record)
            if not outcome.completed:
                return RunResult(RunStatus.ERROR, "device action failed", tuple(steps), latest)
            if self._settle_seconds:
                time.sleep(self._settle_seconds)
