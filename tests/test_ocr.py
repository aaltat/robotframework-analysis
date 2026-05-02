"""Tests for the OCR extraction layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from PIL import Image, ImageDraw

from robotframework_analysis.agent.ocr import extract_text


def _make_png(tmp_path: Path, text: str) -> Path:
    """Create a simple white PNG image with black text and return its path."""
    img = Image.new("RGB", (400, 100), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 30), text, fill="black")
    path = tmp_path / "screenshot.png"
    img.save(path)
    return path


# ---------------------------------------------------------------------------
# Slice 1 — happy path: readable image with text
# ---------------------------------------------------------------------------


def test_extract_text_returns_nonempty_text_for_readable_image(tmp_path: Path) -> None:
    path = _make_png(tmp_path, "Login failed: invalid credentials")
    text, confidence = extract_text(path)
    assert len(text) > 0
    assert 0.0 < confidence <= 1.0


def test_extract_text_confidence_is_float_in_unit_range(tmp_path: Path) -> None:
    path = _make_png(tmp_path, "Error 403 Forbidden")
    _, confidence = extract_text(path)
    assert 0.0 <= confidence <= 1.0


# ---------------------------------------------------------------------------
# Slice 2 — resilience: never raise
# ---------------------------------------------------------------------------


def test_extract_text_returns_empty_on_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "nonexistent.png"
    text, confidence = extract_text(path)
    assert text == ""
    assert confidence == 0.0


def test_extract_text_returns_empty_on_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.png"
    path.write_bytes(b"\x00\x01\x02\x03garbage")
    text, confidence = extract_text(path)
    assert text == ""
    assert confidence == 0.0


# ---------------------------------------------------------------------------
# Slice 3 — blank image produces no text
# ---------------------------------------------------------------------------


def test_extract_text_on_blank_image_returns_empty_text(tmp_path: Path) -> None:
    img = Image.new("RGB", (400, 100), color="white")
    path = tmp_path / "blank.png"
    img.save(path)
    text, _confidence = extract_text(path)
    assert text == ""
