"""Unit tests for model endpoint settings and environment loading."""

from __future__ import annotations

import pytest

from vphone.planner.config import ModelConfig


def test_model_config_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Load endpoint and request options without a hard-coded provider."""
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("VPHONE_MODEL_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("VPHONE_MODEL_ID", "vision-test")
    monkeypatch.setenv("VPHONE_MODEL_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("VPHONE_MODEL_MAX_OUTPUT_TOKENS", "2048")
    monkeypatch.setenv("VPHONE_MODEL_REASONING_EFFORT", "medium")
    monkeypatch.setenv("VPHONE_MODEL_IMAGE_DETAIL", "original")

    config = ModelConfig.from_env()

    assert config.api_key == "test-key"
    assert config.base_url == "https://example.test/v1"
    assert config.model_id == "vision-test"
    assert config.request_timeout_seconds == 45
    assert config.max_output_tokens == 2048
    assert config.reasoning_effort == "medium"
    assert config.image_detail == "original"


@pytest.mark.parametrize(
    "base_url,model_id",
    [("", "vision-test"), ("not-a-url", "vision-test"), ("https://example.test", "")],
)
def test_model_config_rejects_missing_endpoint_or_model(base_url: str, model_id: str) -> None:
    """Require an explicit valid endpoint and model identifier."""
    with pytest.raises(ValueError):
        ModelConfig("test-key", base_url, model_id)


def test_model_config_rejects_invalid_limits() -> None:
    """Reject malformed timeout and output-token options."""
    with pytest.raises(ValueError):
        ModelConfig("test-key", "https://example.test", "vision-test", request_timeout_seconds=0)
    with pytest.raises(ValueError):
        ModelConfig("test-key", "https://example.test", "vision-test", max_output_tokens=-1)


def test_model_config_rejects_invalid_environment_number(monkeypatch: pytest.MonkeyPatch) -> None:
    """Report an invalid environment number before a network request."""
    monkeypatch.setenv("VPHONE_MODEL_TIMEOUT_SECONDS", "later")
    with pytest.raises(ValueError, match="timeout or output token"):
        ModelConfig.from_env()
