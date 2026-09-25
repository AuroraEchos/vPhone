"""Capture the current page for a future multimodal planner."""

from __future__ import annotations

import uuid

from vphone.device.errors import DeviceError
from vphone.device.protocol import DeviceSession
from vphone.perception.errors import PerceptionError
from vphone.perception.models import PageObservation


class PerceptionEngine:
    """L3 delivers screenshots; L4 decides and L2 executes actions."""

    def observe(self, device: DeviceSession, *, screen_timeout: float = 10.0) -> PageObservation:
        """Capture one current screenshot without querying app metadata."""
        try:
            screen = device.capture_screen(timeout=screen_timeout)
        except DeviceError as exc:
            raise PerceptionError("screenshot capture failed") from exc
        return PageObservation(observation_id=uuid.uuid4().hex, screen=screen)
