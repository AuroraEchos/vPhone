"""Persist one visual task's screenshots, decisions, and action outcomes."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vphone.action.models import Action, KeyAction, SwipeAction, TapAction, TextAction
from vphone.device.models import KeyCode
from vphone.perception.models import PageObservation
from vphone.planner.models import (
    ActionDecision,
    ConfirmationDecision,
    Decision,
    FinishDecision,
    StepRecord,
    StopDecision,
)


def _action_data(action: Action) -> dict[str, Any]:
    """Convert a concrete action into JSON-compatible values.

    Args:
        action: L2 action proposed or executed during a task.

    Returns:
        Action type and its exact parameters.
    """
    if isinstance(action, TapAction):
        return {"type": "tap", "x": action.point.x, "y": action.point.y}
    if isinstance(action, SwipeAction):
        return {
            "type": "swipe",
            "start_x": action.start.x,
            "start_y": action.start.y,
            "end_x": action.end.x,
            "end_y": action.end.y,
            "duration_ms": action.duration_ms,
        }
    if isinstance(action, KeyAction):
        key = action.key.name if isinstance(action.key, KeyCode) else action.key
        return {"type": "key", "key": key}
    if isinstance(action, TextAction):
        return {"type": "text", "text": action.text}
    raise TypeError("unsupported action in trajectory")


def _decision_data(decision: Decision) -> dict[str, Any]:
    """Convert one validated model decision into JSON-compatible values.

    Args:
        decision: Action proposal or terminal planner decision.

    Returns:
        Decision type and its arguments.
    """
    if isinstance(decision, ActionDecision):
        return {"type": "action", "action": _action_data(decision.action)}
    if isinstance(decision, FinishDecision):
        return {"type": "finish", "answer": decision.answer}
    if isinstance(decision, StopDecision):
        return {"type": "stop", "reason": decision.reason}
    if isinstance(decision, ConfirmationDecision):
        return {"type": "request_confirmation", "question": decision.question}
    raise TypeError("unsupported decision in trajectory")


class TrajectoryRecorder:
    """Write an incrementally updated JSON trace and its PNG screenshots."""

    def __init__(self, root: Path, *, task: str, model_id: str):
        """Create a private per-task directory and initial JSON record.

        Args:
            root: Project-local directory that contains all task traces.
            task: User-supplied task text.
            model_id: Configured model identifier; no API key is stored.
        """
        run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}-{uuid.uuid4().hex[:8]}"
        root.mkdir(parents=True, exist_ok=True)
        self.directory = root / run_id
        self.directory.mkdir(mode=0o700)
        (self.directory / "screenshots").mkdir(mode=0o700)
        self.json_path = self.directory / "trajectory.json"
        self._data: dict[str, Any] = {
            "schema_version": 1,
            "run_id": run_id,
            "task": task,
            "model_id": model_id,
            "device_id": None,
            "started_at": datetime.now(UTC).isoformat(),
            "finished_at": None,
            "status": "running",
            "message": None,
            "action_count": 0,
            "turns": [],
        }
        self._save()

    def set_device_id(self, device_id: str) -> None:
        """Record which authorized device was selected for the run.

        Args:
            device_id: ADB serial of the selected device.
        """
        self._data["device_id"] = device_id
        self._save()

    def record_observation(self, observation: PageObservation) -> None:
        """Save the screenshot and metadata before requesting a model decision.

        Args:
            observation: Fresh L3 screenshot for the next model turn.
        """
        screen = observation.screen
        index = len(self._data["turns"]) + 1
        image_path = f"screenshots/{index:04d}.png"
        (self.directory / image_path).write_bytes(screen.data)
        self._data["turns"].append(
            {
                "index": index,
                "observation": {
                    "id": observation.observation_id,
                    "screenshot": image_path,
                    "sha256": screen.sha256,
                    "width": screen.width,
                    "height": screen.height,
                    "mime_type": screen.mime_type,
                    "captured_at": screen.captured_at,
                    "duration_seconds": screen.duration_seconds,
                },
                "decision": None,
                "execution": None,
            }
        )
        self._save()

    def record_decision(self, decision: Decision) -> None:
        """Attach a validated model decision to the latest screenshot.

        Args:
            decision: Model decision made from the latest observation.
        """
        self._latest_turn()["decision"] = _decision_data(decision)
        self._save()

    def record_step(self, step: StepRecord) -> None:
        """Attach the actual L2 result to its corresponding decision turn.

        Args:
            step: Executed action, observation identity, and device result.
        """
        turn = self._latest_turn()
        observation = turn["observation"]
        if (step.observation_id, step.screen_sha256) != (
            observation["id"],
            observation["sha256"],
        ):
            raise ValueError("action result does not match the latest observation")
        result = step.result
        turn["execution"] = {
            "action": _action_data(step.action),
            "kind": result.kind.value,
            "completed": result.completed,
            "duration_seconds": result.duration_seconds,
            "primitive": (
                {
                    "operation": result.primitive.operation,
                    "duration_seconds": result.primitive.duration_seconds,
                }
                if result.primitive is not None
                else None
            ),
            "error": (
                {"type": type(result.error).__name__, "message": str(result.error)}
                if result.error is not None
                else None
            ),
        }
        self._data["action_count"] += 1
        self._save()

    def finish(self, *, status: str, message: str) -> None:
        """Persist the terminal result, including stops and failures.

        Args:
            status: Final planner or process status.
            message: Final answer or failure explanation.
        """
        self._data["status"] = status
        self._data["message"] = message
        self._data["finished_at"] = datetime.now(UTC).isoformat()
        self._save()

    def _latest_turn(self) -> dict[str, Any]:
        """Return the current turn or reject an out-of-order callback."""
        if not self._data["turns"]:
            raise ValueError("trajectory has no observation")
        return self._data["turns"][-1]

    def _save(self) -> None:
        """Atomically replace the JSON trace after each lifecycle event."""
        temporary = self.json_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(self.json_path)
