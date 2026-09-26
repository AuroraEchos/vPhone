"""Failures at the model/decision boundary."""


class PlannerError(Exception):
    """A planner decision could not be safely used."""


class ModelError(PlannerError):
    """The remote model request failed."""


class InvalidDecisionError(PlannerError):
    """The model returned an unsupported or malformed decision."""
