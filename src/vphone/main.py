"""Command-line entry point for visual Android tasks."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from vphone.device import AdbDeviceBackend
from vphone.planner import ModelConfig, OpenAICompatibleDecisionModel, PlannerEngine
from vphone.planner.models import StepRecord
from vphone.trajectory import TrajectoryRecorder


def _trajectory_root() -> Path:
    """Use the source project root when available, or the current directory."""
    project_root = Path(__file__).resolve().parents[2]
    if (project_root / "pyproject.toml").is_file():
        return project_root / "traces"
    return Path.cwd() / "traces"


def _report_step(step: StepRecord) -> None:
    """Print one action result without logging text input or screenshots.

    Args:
        step: The completed L2 action and its outcome.
    """
    print(
        f"action={type(step.action).__name__}, command_completed={step.result.completed}",
        flush=True,
    )


def main(argv: list[str] | None = None) -> None:
    """Run a user-supplied visual task on one authorized phone.

    Args:
        argv: Optional arguments for tests; defaults to process arguments.
    """
    parser = argparse.ArgumentParser(description="Run one visual task on an Android phone.")
    parser.add_argument("task", help="Natural-language task to perform on the phone")
    args = parser.parse_args(argv)
    task = args.task.strip()
    if not task:
        parser.error("task must not be empty")

    env_path = find_dotenv(usecwd=True)
    load_dotenv(env_path)
    trajectory = TrajectoryRecorder(
        _trajectory_root(), task=task, model_id=os.getenv("VPHONE_MODEL_ID", "")
    )

    def record_step(step: StepRecord) -> None:
        """Save one executed action and print its non-sensitive progress line."""
        trajectory.record_step(step)
        _report_step(step)

    try:
        try:
            config = ModelConfig.from_env()
            max_actions = int(os.getenv("VPHONE_MAX_ACTIONS", "12"))
            max_seconds = float(os.getenv("VPHONE_MAX_SECONDS", "600"))
            settle_seconds = float(os.getenv("VPHONE_SETTLE_SECONDS", "0.5"))
        except ValueError as exc:
            raise SystemExit(f"Invalid model or runtime configuration: {exc}") from exc

        backend = AdbDeviceBackend()
        device_id = os.getenv("VPHONE_DEVICE_ID")
        if not device_id:
            ready = [item for item in backend.list_devices() if item.state.value == "device"]
            if len(ready) != 1:
                raise SystemExit("Set VPHONE_DEVICE_ID when there is not exactly one ready device")
            device_id = ready[0].device_id
        trajectory.set_device_id(device_id)

        model = OpenAICompatibleDecisionModel(config)
        try:
            planner = PlannerEngine(
                model,
                max_actions=max_actions,
                max_seconds=max_seconds,
                settle_seconds=settle_seconds,
                on_observation=trajectory.record_observation,
                on_decision=trajectory.record_decision,
                on_step=record_step,
            )
        except ValueError as exc:
            raise SystemExit(f"Invalid run limits: {exc}") from exc

        with backend.open(device_id) as device:
            result = planner.run(task, device)
    except KeyboardInterrupt:
        trajectory.finish(status="interrupted", message="Interrupted by user")
        raise
    except SystemExit as exc:
        trajectory.finish(status="error", message=str(exc))
        raise
    except Exception as exc:
        trajectory.finish(status="error", message=f"{type(exc).__name__}: {exc}")
        raise
    else:
        trajectory.finish(status=result.status.value, message=result.message)
        print(f"status={result.status.value}; actions={len(result.steps)}")
        print(result.message)
        if not result.completed:
            raise SystemExit(1)
    finally:
        print(f"trajectory={trajectory.json_path}")


if __name__ == "__main__":
    main()
