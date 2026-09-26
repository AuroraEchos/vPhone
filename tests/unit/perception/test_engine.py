"""Screenshot-only observation contract and error boundary."""

from __future__ import annotations

import pytest

from vphone.device import ScreenFrame, ScreenshotError
from vphone.perception import PageObservation, PerceptionEngine, PerceptionError


def frame() -> ScreenFrame:
    """Build a synthetic screenshot frame for perception tests."""
    return ScreenFrame(b"fake-png", 100, 200, "image/png", "a" * 64, 100, 0.1)


class FakeSession:
    def __init__(self, *, fail_screen: bool = False) -> None:
        """Configure whether screenshot capture should fail."""
        self.fail_screen = fail_screen
        self.screen_calls = 0

    def capture_screen(self, *, timeout: float = 10.0) -> ScreenFrame:
        """Count and return one frame or raise a synthetic failure."""
        self.screen_calls += 1
        if self.fail_screen:
            raise ScreenshotError("synthetic screen failure")
        return frame()


def test_observe_captures_only_one_screenshot() -> None:
    """Verify observe captures only one screenshot."""
    session = FakeSession()

    result = PerceptionEngine().observe(session)

    assert session.screen_calls == 1
    assert result.screen == frame()
    assert len(result.observation_id) == 32
    assert not hasattr(result, "text_candidates")


def test_observation_ids_are_unique() -> None:
    """Verify observation ids are unique."""
    engine = PerceptionEngine()
    session = FakeSession()

    first = engine.observe(session)
    second = engine.observe(session)

    assert session.screen_calls == 2
    assert first.observation_id != second.observation_id


def test_screenshot_failure_does_not_create_observation() -> None:
    """Verify screenshot failure does not create observation."""
    session = FakeSession(fail_screen=True)

    with pytest.raises(PerceptionError, match="screenshot capture failed"):
        PerceptionEngine().observe(session)

    assert session.screen_calls == 1


def test_page_observation_rejects_empty_identifier() -> None:
    """Verify page observation rejects empty identifier."""
    with pytest.raises(ValueError, match="observation_id"):
        PageObservation("", frame())
