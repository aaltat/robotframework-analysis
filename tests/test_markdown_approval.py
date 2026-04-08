from __future__ import annotations

from pathlib import Path

import robot
from approvaltests import verify
from approvaltests.core.options import Options

from robotframework_analysis.report_markdown import _format_duration, render_summary_markdown


def _create_output_xml(tmp_path: Path) -> Path:
    suite_file = Path(__file__).parent / "fixtures" / "summary_suite.robot"

    output_xml = tmp_path / "output.xml"
    robot.run(str(suite_file), output=str(output_xml), log="NONE", report="NONE")
    return output_xml


def test_renders_summary_markdown(tmp_path: Path) -> None:
    output_xml = _create_output_xml(tmp_path)

    markdown = render_summary_markdown(output_xml)

    verify(markdown, options=Options().for_file.with_extension(".md"))


def test_format_duration_rounds_down_to_seconds() -> None:
    assert _format_duration(1999) == "1s"


def test_render_summary_markdown_raises_when_output_is_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing.xml"

    try:
        render_summary_markdown(missing)
    except FileNotFoundError as error:
        assert str(missing) in str(error)
    else:
        raise AssertionError("Expected FileNotFoundError")
