"""Visual decision adapter for OpenAI-compatible Chat Completions APIs."""

from __future__ import annotations

import base64
from dataclasses import replace

from openai import OpenAI, OpenAIError

from vphone.perception.models import PageObservation
from vphone.planner.config import ModelConfig
from vphone.planner.errors import InvalidDecisionError, ModelError
from vphone.planner.models import Decision, StepRecord, TokenUsage
from vphone.planner.tools import parse_tool_call, tools_for_screen

_INSTRUCTIONS = """You operate an Android phone using ONLY the current screenshot and the task.
The screenshot is the only source of current page truth. It is the FULL image, not a crop.
For tap/swipe, x and y are INTEGER PIXEL coordinates in the full screenshot.
Use the provided screenshot width and height to locate targets.
Call exactly ONE function per response. Do not return plain text or multiple calls.
Every function call must include a concise screen_summary grounded in the current screenshot
and a concise decision_reason that connects the decision to the task and prior trajectory.
Do not copy passwords, tokens, or other sensitive values into either trajectory field.
Treat prior trajectory as past context only; the current screenshot is authoritative.
After an action, a new screenshot will be captured and you will decide again.
If the current screenshot visibly shows a loading indicator or another in-progress state,
use wait for a short duration before inspecting a fresh screenshot. Do not wait merely because
an expected control is absent, and do not repeat waits when the screen is no longer loading.
Do not assume a prior action changed the screen; inspect the current screenshot.
Use the trajectory to understand why you reached the current screen. If the current screenshot
shows that the latest attempt did not achieve its stated purpose, do not repeat the same action
for the same reason; choose a different visible strategy or stop if none is justified.
An Android home screen may have several horizontally paged screens. If the target app is not
visible on the current home page, search an adjacent page with one horizontal swipe left or right
instead of assuming that a vertical swipe opens an app drawer. Use the trajectory to avoid
revisiting the same page; if one direction does not help, try the opposite direction.
Use finish only if the current screenshot visibly supports your answer.
This device is a controlled test environment. Do not pause for user confirmation; carry out
actions explicitly required by the task, including sending or deleting when requested.
If uncertain, call stop. Never invent controls or invisible page content.
"""


def _token_usage(response: object) -> TokenUsage | None:
    """Extract portable token counts without making diagnostics response-critical."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    total = getattr(usage, "total_tokens", None)
    if any(type(value) is not int or value < 0 for value in (prompt, completion, total)):
        return None

    def optional_count(name: str) -> int | None:
        value = getattr(usage, name, None)
        return value if type(value) is int and value >= 0 else None

    return TokenUsage(
        prompt,
        completion,
        total,
        optional_count("prompt_cache_hit_tokens"),
        optional_count("prompt_cache_miss_tokens"),
    )


def _history_line(index: int, step: StepRecord) -> str:
    """Render one task-aware trajectory entry without sensitive action details."""
    return (
        f"{index}. Saw: {step.trace.screen_summary} "
        f"Decision: {step.trace.decision_reason} "
        f"Action: {step.describe_action()}; result: {step.result_description}; "
        "UI effect was not verified at that time"
    )


class OpenAICompatibleDecisionModel:
    """One fresh screenshot and a task-aware trajectory per stateless request."""

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
            history: Prior screen interpretations, decisions, actions, and outcomes.

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
            f"Task-aware trajectory (past context, not proof of current UI):\n{history_text}\n"
            "Choose exactly one next function using this CURRENT screenshot. "
            f"Coordinates must be screenshot pixels: x=0..{screen.width - 1}, "
            f"y=0..{screen.height - 1}."
        )
        accumulated_usage: TokenUsage | None = None
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
                current_usage = _token_usage(response)
                if current_usage is not None:
                    accumulated_usage = (
                        current_usage
                        if accumulated_usage is None
                        else accumulated_usage + current_usage
                    )
            except OpenAIError as exc:
                raise ModelError("model request failed") from exc

            try:
                if len(response.choices) != 1 or response.choices[0].finish_reason != "tool_calls":
                    raise InvalidDecisionError("model did not return one complete tool decision")
                calls = response.choices[0].message.tool_calls
                if calls is None or len(calls) != 1 or calls[0].type != "function":
                    raise InvalidDecisionError("model must return exactly one function call")
                decision = parse_tool_call(
                    calls[0].function.name,
                    calls[0].function.arguments,
                    screen,
                )
                return replace(decision, usage=accumulated_usage)
            except InvalidDecisionError as exc:
                if attempt == 1:
                    raise
                prompt += (
                    f"\nYour previous proposal was rejected: {exc}. "
                    "Re-evaluate this same screenshot and provide exactly one complete "
                    "function call with all required fields. No device action has been executed."
                )
        raise AssertionError("unreachable")
