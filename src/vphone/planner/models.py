"""Backend-neutral planner decisions and run records."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from vphone.action.models import Action, ActionResult
from vphone.perception.models import PageObservation


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    """Task-relevant interpretation behind one model decision."""

    screen_summary: str = field(repr=False)
    decision_reason: str = field(repr=False)

    def __post_init__(self) -> None:
        """Keep trajectory text concise, printable, and safe for one-line prompts."""
        for field_name in ("screen_summary", "decision_reason"):
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise TypeError(f"{field_name} must be text")
            normalized = value.strip()
            if not normalized or len(value) > 1000 or not normalized.isprintable():
                raise ValueError(
                    f"{field_name} must be non-empty printable text up to 1000 characters"
                )
            object.__setattr__(self, field_name, normalized)


@dataclass(frozen=True, slots=True)
class ActionDecision:
    action: Action
    trace: DecisionTrace


@dataclass(frozen=True, slots=True)
class FinishDecision:
    answer: str
    trace: DecisionTrace


@dataclass(frozen=True, slots=True)
class StopDecision:
    reason: str
    trace: DecisionTrace


@dataclass(frozen=True, slots=True)
class ConfirmationDecision:
    question: str
    trace: DecisionTrace


Decision = ActionDecision | FinishDecision | StopDecision | ConfirmationDecision


@dataclass(frozen=True, slots=True)
class StepRecord:
    observation_id: str
    screen_sha256: str
    action: Action
    result: ActionResult
    trace: DecisionTrace


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
