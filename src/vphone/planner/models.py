"""Backend-neutral planner decisions and run records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from vphone.action.models import Action, ActionResult
from vphone.perception.models import PageObservation


@dataclass(frozen=True, slots=True)
class ActionDecision:
    action: Action


@dataclass(frozen=True, slots=True)
class FinishDecision:
    answer: str


@dataclass(frozen=True, slots=True)
class StopDecision:
    reason: str


@dataclass(frozen=True, slots=True)
class ConfirmationDecision:
    question: str


Decision = ActionDecision | FinishDecision | StopDecision | ConfirmationDecision


@dataclass(frozen=True, slots=True)
class StepRecord:
    observation_id: str
    screen_sha256: str
    action: Action
    result: ActionResult


class RunStatus(StrEnum):
    FINISHED = "finished"
    STOPPED = "stopped"
    NEEDS_CONFIRMATION = "needs_confirmation"
    ACTION_LIMIT = "action_limit"
    TIME_LIMIT = "time_limit"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class RunResult:
    status: RunStatus
    message: str
    steps: tuple[StepRecord, ...]
    final_observation: PageObservation | None

    @property
    def completed(self) -> bool:
        """Model reported task completion; not an independent UI proof."""
        return self.status is RunStatus.FINISHED
