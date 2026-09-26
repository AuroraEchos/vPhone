"""One current screenshot prepared for visual decision-making."""

from __future__ import annotations

from dataclasses import dataclass

from vphone.device.models import ScreenFrame


@dataclass(frozen=True, slots=True)
class PageObservation:
    """Screenshot-based page observation; no extracted UI metadata is implied."""

    observation_id: str
    screen: ScreenFrame

    def __post_init__(self) -> None:
        """Reject an observation without a tracking identifier."""
        if not self.observation_id:
            raise ValueError("observation_id cannot be empty")
