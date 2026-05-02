"""OCR extraction layer for screenshot analysis."""

from __future__ import annotations

import logging
import statistics
from typing import TYPE_CHECKING

import pytesseract
from PIL import Image
from pytesseract import Output

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text(path: Path) -> tuple[str, float]:
    """Extract text and median confidence from a screenshot image.

    Returns (text, confidence) where confidence is in [0.0, 1.0].
    Returns ("", 0.0) for missing, unreadable, or blank images — never raises.
    """
    try:
        data = pytesseract.image_to_data(Image.open(path), output_type=Output.DICT)
    except OSError:
        logger.debug("OCR failed for %s", path, exc_info=True)
        return "", 0.0

    confs: list[int] = [c for c in data["conf"] if c != -1]
    if not confs:
        return "", 0.0

    median_conf = statistics.median(confs) / 100.0
    words = [w for w, c in zip(data["text"], data["conf"], strict=True) if c > 0 and w.strip()]
    text = " ".join(words)
    return text, median_conf
