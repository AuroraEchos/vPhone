"""No-touch visual coordinate probe for the configured model."""

from __future__ import annotations

import hashlib
import io
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageDraw

from vphone.device import ScreenFrame
from vphone.perception import PageObservation
from vphone.planner import ModelConfig, OpenAICompatibleDecisionModel
from vphone.planner.models import ActionDecision


def _probe_screen(x: int, y: int) -> ScreenFrame:
    """Create a synthetic PNG with a target centered at the given pixels.

    Args:
        x: Target center's horizontal pixel.
        y: Target center's vertical pixel.

    Returns:
        A screen frame containing only generated test content.
    """
    image = Image.new("RGB", (590, 1280), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((15, 15, 575, 1265), outline="black", width=3)
    draw.ellipse((x - 28, y - 28, x + 28, y + 28), fill="magenta", outline="black", width=3)
    draw.text((28, 40), "Tap the center of the magenta circle", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    data = buffer.getvalue()
    return ScreenFrame(
        data, 590, 1280, "image/png", hashlib.sha256(data).hexdigest(), time.time(), 0
    )


def main() -> None:
    """Check model pixel targeting without interacting with any device."""
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    try:
        config = ModelConfig.from_env()
    except ValueError as exc:
        raise SystemExit(f"Invalid model configuration: {exc}") from exc
    model = OpenAICompatibleDecisionModel(config)
    targets = [(295, 640), (120, 250), (470, 950)]
    for expected_x, expected_y in targets:
        screen = _probe_screen(expected_x, expected_y)
        observation = PageObservation(uuid.uuid4().hex, screen)
        decision = model.decide(
            "Tap the center of the magenta circle shown in this synthetic image. "
            "Do not finish; call tap with its location.",
            observation,
            (),
        )
        if not isinstance(decision, ActionDecision) or not hasattr(decision.action, "point"):
            raise SystemExit(
                f"Coordinate probe failed: unexpected decision {type(decision).__name__}"
            )
        point = decision.action.point
        error = max(abs(point.x - expected_x), abs(point.y - expected_y))
        print(f"target=({expected_x},{expected_y}) model=({point.x},{point.y}) error={error}px")
        if error > 35:
            raise SystemExit("Coordinate probe failed: error exceeds 35 pixels")
    print("Coordinate probe passed; no device action was performed.")


if __name__ == "__main__":
    main()
