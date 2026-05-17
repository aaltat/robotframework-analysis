"""Tests for the CLI entry-point - delegate subcommand path resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path


def _run_delegate_with_mock(
    output_xml: str,
    playwright_log: str | None,
) -> tuple[str, object]:
    """Call _run_delegate with a mocked delegate_agent; return (prompt, deps)."""
    mock_result = MagicMock()
    mock_result.output = "report"

    with patch("robotframework_analysis.agent.delegate.delegate_agent") as mock_agent:
        mock_agent.run_sync.return_value = mock_result
        from robotframework_analysis.cli import _run_delegate

        _run_delegate(output_xml, playwright_log)
        prompt = mock_agent.run_sync.call_args[0][0]
        deps = mock_agent.run_sync.call_args.kwargs.get("deps")
        return prompt, deps


# ---------------------------------------------------------------------------
# Path resolution - output_xml
# ---------------------------------------------------------------------------


def test_delegate_resolves_relative_output_xml_to_absolute(tmp_path: Path, monkeypatch) -> None:
    output_xml = tmp_path / "output.xml"
    output_xml.touch()
    monkeypatch.chdir(tmp_path)

    _, deps = _run_delegate_with_mock("output.xml", None)

    assert deps.output_xml == str(output_xml)


def test_delegate_absolute_output_xml_passes_through(tmp_path: Path) -> None:
    output_xml = tmp_path / "output.xml"
    output_xml.touch()

    _, deps = _run_delegate_with_mock(str(output_xml), None)

    assert deps.output_xml == str(output_xml)


# ---------------------------------------------------------------------------
# Path resolution - playwright_log
# ---------------------------------------------------------------------------


def test_delegate_resolves_relative_playwright_log_to_absolute(tmp_path: Path, monkeypatch) -> None:
    output_xml = tmp_path / "output.xml"
    output_xml.touch()
    pw_log_dir = tmp_path / ".robotframework_analysis"
    pw_log_dir.mkdir()
    pw_log = pw_log_dir / "playwright-log.txt"
    pw_log.touch()
    monkeypatch.chdir(tmp_path)

    _, deps = _run_delegate_with_mock("output.xml", ".robotframework_analysis/playwright-log.txt")

    assert deps.playwright_log == str(pw_log)


def test_delegate_omits_playwright_from_prompt_when_not_given(tmp_path: Path) -> None:
    output_xml = tmp_path / "output.xml"
    output_xml.touch()

    _, deps = _run_delegate_with_mock(str(output_xml), None)

    assert deps.playwright_log is None


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def test_build_parser_includes_analyze_subcommand() -> None:
    from robotframework_analysis.cli import _build_parser

    args = _build_parser().parse_args(["analyze", "output.xml"])
    assert args.command == "analyze"
    assert args.output_xml == "output.xml"
    assert args.playwright_log is None


def test_build_parser_analyze_accepts_playwright_log() -> None:
    from robotframework_analysis.cli import _build_parser

    args = _build_parser().parse_args(
        ["analyze", "output.xml", "--playwright-log", "playwright-log.txt"]
    )
    assert args.playwright_log == "playwright-log.txt"
