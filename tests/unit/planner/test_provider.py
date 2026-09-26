"""Unit tests for model request construction and decision parsing."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from vphone.device import Point, ScreenFrame
from vphone.perception import PageObservation
from vphone.planner.config import ModelConfig
from vphone.planner.errors import InvalidDecisionError
from vphone.planner.models import ActionDecision
from vphone.planner.provider import OpenAICompatibleDecisionModel


class FakeCompletions:
    def __init__(self, calls: list[tuple[str, str]]) -> None:
        """Store tool calls for a fixed synthetic model response."""
        self.calls = calls
        self.kwargs = None

    def create(self, **kwargs):
        """Capture request arguments and return the configured tool calls."""
        self.kwargs = kwargs
        tool_calls = [
            SimpleNamespace(type="function", function=SimpleNamespace(name=name, arguments=args))
            for name, args in self.calls
        ]
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="tool_calls",
                    message=SimpleNamespace(tool_calls=tool_calls),
                )
            ]
        )


class SequenceCompletions:
    def __init__(self, responses: list[list[tuple[str, str]]]) -> None:
        """Queue different tool-call sets for retry-path testing."""
        self.responses = responses
        self.prompts: list[str] = []

    def create(self, **kwargs):
        """Record the prompt and return the next queued response."""
        self.prompts.append(kwargs["messages"][1]["content"][0]["text"])
        calls = self.responses.pop(0)
        tool_calls = [
            SimpleNamespace(type="function", function=SimpleNamespace(name=name, arguments=args))
            for name, args in calls
        ]
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="tool_calls",
                    message=SimpleNamespace(tool_calls=tool_calls),
                )
            ]
        )


def _model(calls):
    """Build a provider with an injected fixed-response client."""
    completions = FakeCompletions(calls)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    config = ModelConfig("test-key", "https://example.test", "vision-test", image_detail="original")
    return OpenAICompatibleDecisionModel(config, client=client), completions


def _observation():
    """Build a synthetic PNG observation for provider tests."""
    screen = ScreenFrame(b"png", 100, 200, "image/png", "a" * 64, 1.0, 0.0)
    return PageObservation("obs", screen)


def test_provider_sends_png_as_original_and_returns_validated_action() -> None:
    """Verify provider sends png as original and returns validated action."""
    model, completions = _model([("tap", '{"x":99,"y":199}')])

    decision = model.decide("Tap icon", _observation(), ())

    assert isinstance(decision, ActionDecision)
    assert decision.action.point == Point(99, 199)
    assert completions.kwargs["model"] == "vision-test"
    assert completions.kwargs["max_tokens"] == 4096
    assert "reasoning_effort" not in completions.kwargs
    tap_tool = next(
        item for item in completions.kwargs["tools"] if item["function"]["name"] == "tap"
    )
    assert tap_tool["function"]["parameters"]["properties"]["y"]["maximum"] == 199
    image = completions.kwargs["messages"][1]["content"][1]["image_url"]
    assert image["detail"] == "original"
    assert image["url"].startswith("data:image/png;base64,")


def test_provider_rejects_multiple_tool_calls() -> None:
    """Verify provider rejects multiple tool calls."""
    model, _ = _model([("tap", '{"x":1,"y":2}'), ("tap", '{"x":3,"y":4}')])

    with pytest.raises(InvalidDecisionError, match="exactly one"):
        model.decide("Tap icon", _observation(), ())


def test_provider_sends_configured_optional_reasoning_effort() -> None:
    """Include the optional reasoning parameter only when configured."""
    completions = FakeCompletions([("tap", '{"x":1,"y":2}')])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    config = ModelConfig("test-key", "https://example.test", "another-model", 20, 512, "medium")
    model = OpenAICompatibleDecisionModel(config, client=client)

    model.decide("Tap icon", _observation(), ())

    assert completions.kwargs["model"] == "another-model"
    assert completions.kwargs["max_tokens"] == 512
    assert completions.kwargs["reasoning_effort"] == "medium"
    assert "detail" not in completions.kwargs["messages"][1]["content"][1]["image_url"]


def test_provider_constructs_client_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pass the configured endpoint and timeout to the SDK client."""
    captured = {}

    def fake_client(**kwargs):
        """Capture SDK constructor options without contacting a service."""
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr("vphone.planner.provider.OpenAI", fake_client)
    config = ModelConfig("test-key", "https://example.test/v1", "vision-test", 25)

    OpenAICompatibleDecisionModel(config)

    assert captured == {
        "api_key": "test-key",
        "base_url": "https://example.test/v1",
        "timeout": 25,
        "max_retries": 0,
    }


def test_provider_repairs_missing_field_once_without_action() -> None:
    """Verify provider repairs missing field once without action."""
    completions = SequenceCompletions(
        [
            [("tap", '{"x":50}')],
            [("tap", '{"x":50,"y":70}')],
        ]
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    config = ModelConfig("test-key", "https://example.test", "vision-test")
    model = OpenAICompatibleDecisionModel(config, client=client)

    decision = model.decide("Tap icon", _observation(), ())

    assert isinstance(decision, ActionDecision)
    assert decision.action.point == Point(50, 70)
    assert len(completions.prompts) == 2
    assert "previous proposal was rejected" in completions.prompts[1]
