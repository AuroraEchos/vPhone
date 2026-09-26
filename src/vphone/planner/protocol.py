"""Interface for any visual decision provider."""

from __future__ import annotations

from typing import Protocol

from vphone.perception.models import PageObservation
from vphone.planner.models import Decision, StepRecord


class DecisionModel(Protocol):
    def decide(
        self, task: str, observation: PageObservation, history: tuple[StepRecord, ...]
    ) -> Decision:
        """Propose one decision from the task and current screenshot.

        Args:
            task: User's natural-language objective.
            observation: Fresh screenshot observation.
            history: Prior dispatched actions and their device outcomes.

        Returns:
            One action, finish, stop, or confirmation decision.
        """
        ...
