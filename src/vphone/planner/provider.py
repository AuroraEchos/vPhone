"""Visual decision adapter for OpenAI-compatible Chat Completions APIs."""

from __future__ import annotations

import base64

from openai import OpenAI, OpenAIError

from vphone.action.models import KeyAction, SwipeAction, TapAction, TextAction
from vphone.perception.models import PageObservation
from vphone.planner.config import ModelConfig
from vphone.planner.errors import InvalidDecisionError, ModelError
from vphone.planner.models import Decision, StepRecord
from vphone.planner.tools import parse_tool_call, tools_for_screen

_INSTRUCTIONS = """You operate an Android phone using ONLY the current screenshot and the task.
The screenshot is the only source of current page truth. It is the FULL image, not a crop.
For tap/swipe, x and y are INTEGER PIXEL coordinates in the full screenshot.
Use the provided screenshot width and height to locate targets.
Call exactly ONE function per response. Do not return plain text or multiple calls.
After an action, a new screenshot will be captured and you will decide again.
Do not assume a prior action changed the screen; inspect the current screenshot.
Use finish only if the current screenshot visibly supports your answer.
If uncertain, call stop. Before sending, deleting, purchasing or another consequential
action, call request_confirmation. Never invent controls or invisible page content.
"""


def _history_line(index: int, step: StepRecord) -> str:
    """Summarize one action without exposing input text or screenshot bytes."""
    action = step.action
    if isinstance(action, TapAction):
        description = f"tap({action.point.x},{action.point.y})"
    elif isinstance(action, SwipeAction):
        description = f"swipe({action.start.x},{action.start.y} -> {action.end.x},{action.end.y})"
    elif isinstance(action, KeyAction):
        description = (
            f"press_key({action.key.name})" if hasattr(action.key, "name") else "press_key"
        )
    elif isinstance(action, TextAction):
        description = f"input_text({len(action.text)} characters)"
    else:
        description = "unknown_action"
    outcome = "device command completed" if step.result.completed else "device command failed"
    return f"{index}. {description}: {outcome}; UI effect not verified"


class OpenAICompatibleDecisionModel:
    """One fresh screenshot and a compact action history per stateless request."""

    def __init__(self, config: ModelConfig, *, client: OpenAI | None = None):
        """Configure a multimodal Chat Completions client.

        Args:
            config: Endpoint, model, and request options; key is never sent in prompt text.
            client: Optional injected client for offline tests.
        """
        self._config = config
        self._client = client or OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.request_timeout_seconds,
            max_retries=0,
        )

    def decide(
        self, task: str, observation: PageObservation, history: tuple[StepRecord, ...]
    ) -> Decision:
        """Request and validate one model decision for the current PNG screenshot.

        An invalid tool response receives one no-action formatting retry.

        Args:
            task: User objective to send alongside the screenshot.
            observation: Current screenshot and its metadata.
            history: Prior actions summarized without screenshot bytes.

        Returns:
            A validated planner decision; this method never executes it.

        Raises:
            ModelError: If the image format is unsupported or the API fails.
            InvalidDecisionError: If both tool responses are invalid.
        """
        screen = observation.screen
        if screen.mime_type != "image/png":
            raise ModelError("model adapter expects a PNG screenshot")
        encoded = base64.b64encode(screen.data).decode("ascii")
        history_text = (
            "\n".join(_history_line(index, step) for index, step in enumerate(history, start=1))
            or "None"
        )
        prompt = (
            f"Task: {task}\n"
            f"Current full screenshot: {screen.width}x{screen.height} pixels.\n"
            f"Previous actions (not proof of UI success):\n{history_text}\n"
            "Choose exactly one next function using this CURRENT screenshot. "
            f"Coordinates must be screenshot pixels: x=0..{screen.width - 1}, "
            f"y=0..{screen.height - 1}."
        )
        for attempt in range(2):
            try:
                image_url = {"url": f"data:image/png;base64,{encoded}"}
                if self._config.image_detail is not None:
                    image_url["detail"] = self._config.image_detail
                request_options = {
                    "model": self._config.model_id,
                    "messages": [
                        {"role": "system", "content": _INSTRUCTIONS},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": image_url,
                                },
                            ],
                        },
                    ],
                    "tools": tools_for_screen(screen),
                    "tool_choice": "auto",
                    "max_tokens": self._config.max_output_tokens,
                }
                if self._config.reasoning_effort is not None:
                    request_options["reasoning_effort"] = self._config.reasoning_effort
                response = self._client.chat.completions.create(**request_options)
            except OpenAIError as exc:
                raise ModelError("model request failed") from exc

            try:
                if len(response.choices) != 1 or response.choices[0].finish_reason != "tool_calls":
                    raise InvalidDecisionError("model did not return one complete tool decision")
                calls = response.choices[0].message.tool_calls
                if calls is None or len(calls) != 1 or calls[0].type != "function":
                    raise InvalidDecisionError("model must return exactly one function call")
                return parse_tool_call(calls[0].function.name, calls[0].function.arguments, screen)
            except InvalidDecisionError as exc:
                if attempt == 1:
                    raise
                prompt += (
                    f"\nYour previous proposal was rejected: {exc}. "
                    "Re-evaluate this same screenshot and provide exactly one complete "
                    "function call with all required fields. No device action has been executed."
                )
        raise AssertionError("unreachable")
