"""Configuration for an OpenAI-compatible multimodal decision endpoint."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ModelConfig:
    """Connection and request options for a tool-capable vision model."""

    api_key: str
    base_url: str
    model_id: str
    request_timeout_seconds: float = 90.0
    max_output_tokens: int = 4096
    reasoning_effort: str | None = None
    image_detail: str | None = None

    def __post_init__(self) -> None:
        """Reject missing or malformed endpoint and request options."""
        if not isinstance(self.api_key, str) or not self.api_key.strip():
            raise ValueError("API_KEY is required")
        if not isinstance(self.base_url, str):
            raise TypeError("VPHONE_MODEL_BASE_URL must be an HTTP(S) URL")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("VPHONE_MODEL_BASE_URL must be an HTTP(S) URL")
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ValueError("VPHONE_MODEL_ID is required")
        if (
            isinstance(self.request_timeout_seconds, bool)
            or not isinstance(self.request_timeout_seconds, (int, float))
            or not math.isfinite(self.request_timeout_seconds)
            or self.request_timeout_seconds <= 0
        ):
            raise ValueError("request timeout must be a positive finite number")
        if type(self.max_output_tokens) is not int or self.max_output_tokens < 1:
            raise ValueError("max output tokens must be a positive integer")
        if self.reasoning_effort is not None and (
            not isinstance(self.reasoning_effort, str) or not self.reasoning_effort.strip()
        ):
            raise ValueError("reasoning effort cannot be blank")
        if self.image_detail is not None and self.image_detail not in {
            "auto",
            "low",
            "high",
            "original",
        }:
            raise ValueError("image detail must be auto, low, high, or original")

    @classmethod
    def from_env(cls) -> ModelConfig:
        """Read model configuration from the process environment.

        Callers may load a project ``.env`` before invoking this method.

        Returns:
            Validated model configuration.

        Raises:
            ValueError: If a required setting is missing or invalid.
        """
        try:
            timeout = float(os.getenv("VPHONE_MODEL_TIMEOUT_SECONDS", "90"))
            max_tokens = int(os.getenv("VPHONE_MODEL_MAX_OUTPUT_TOKENS", "4096"))
        except ValueError as exc:
            raise ValueError("model timeout or output token limit is invalid") from exc
        return cls(
            api_key=os.getenv("API_KEY", ""),
            base_url=os.getenv("VPHONE_MODEL_BASE_URL", ""),
            model_id=os.getenv("VPHONE_MODEL_ID", ""),
            request_timeout_seconds=timeout,
            max_output_tokens=max_tokens,
            reasoning_effort=os.getenv("VPHONE_MODEL_REASONING_EFFORT") or None,
            image_detail=os.getenv("VPHONE_MODEL_IMAGE_DETAIL") or None,
        )
