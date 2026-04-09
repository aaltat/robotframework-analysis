from __future__ import annotations

import re
from pathlib import Path

import robot
from approvaltests import verify
from approvaltests.core.options import Options

from robotframework_analysis.report_markdown import (
    FailedTest,
    _collect_failed_tests,
    _error_group_key,
    _format_start_end,
    _truncate_error,
    render_summary_markdown,
)

_WORKSPACE_ROOT = Path(__file__).parent.parent


def _path_normalizer(p: Path) -> str:
    return str(p.relative_to(_WORKSPACE_ROOT))


_FIXED_DATETIME = "20260101 00:00:00.000"


def _time_normalizer(starttime: str, endtime: str) -> str:
    return f"{_FIXED_DATETIME} / {_FIXED_DATETIME}"


def _run_fixture(fixture_name: str, tmp_path: Path) -> Path:
    suite_file = Path(__file__).parent / "fixtures" / fixture_name
    output_xml = tmp_path / "output.xml"
    robot.run(str(suite_file), output=str(output_xml), log="NONE", report="NONE")
    return output_xml


# ---------------------------------------------------------------------------
# Approval tests
# ---------------------------------------------------------------------------


def test_renders_summary_markdown(tmp_path: Path) -> None:
    output_xml = _run_fixture("summary_suite.robot", tmp_path)

    markdown = render_summary_markdown(
        output_xml, path_normalizer=_path_normalizer, time_normalizer=_time_normalizer
    )

    verify(markdown, options=Options().for_file.with_extension(".md"))


def test_renders_error_groups_markdown(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)

    markdown = render_summary_markdown(
        output_xml, path_normalizer=_path_normalizer, time_normalizer=_time_normalizer
    )

    verify(markdown, options=Options().for_file.with_extension(".md"))


# ---------------------------------------------------------------------------
# Unit tests — _error_group_key
# ---------------------------------------------------------------------------


def test_error_group_key_extracts_prefix() -> None:
    assert _error_group_key("ValueError: something went wrong") == (
        "ValueError",
        "something went wrong",
    )


def test_error_group_key_without_prefix() -> None:
    assert _error_group_key("boom") == ("", "boom")


def test_error_group_key_truncates_first_line_at_100_chars() -> None:
    long_rest = "x" * 150
    key = _error_group_key(f"AssertionError: {long_rest}")
    assert key == ("AssertionError", "x" * 100)


def test_error_group_key_uses_first_line_only() -> None:
    assert _error_group_key("ValueError: first line\nsecond line") == (
        "ValueError",
        "first line",
    )


# ---------------------------------------------------------------------------
# Unit tests — _truncate_error
# ---------------------------------------------------------------------------


def test_truncate_error_short_message_unchanged() -> None:
    assert _truncate_error("short") == "short"


def test_truncate_error_long_message_hard_cut() -> None:
    long = "x" * 400
    result = _truncate_error(long)
    assert result == "x" * 300 + "…"


def test_truncate_error_exactly_300_chars_unchanged() -> None:
    msg = "x" * 300
    assert _truncate_error(msg) == msg


# ---------------------------------------------------------------------------
# Unit tests — _format_start_end
# ---------------------------------------------------------------------------


def test_format_start_end_produces_correct_string() -> None:
    assert _format_start_end("20260408 23:09:12.153", "20260408 23:09:12.999") == (
        "20260408 23:09:12.153 / 20260408 23:09:12.999"
    )


def test_start_end_in_rendered_markdown_contains_real_datetime(tmp_path: Path) -> None:
    _DATETIME_RE = re.compile(r"\d{8} \d{2}:\d{2}:\d{2}\.\d{3}")
    output_xml = _run_fixture("summary_suite.robot", tmp_path)

    markdown = render_summary_markdown(output_xml)

    start_end_lines = [line for line in markdown.splitlines() if "Start / end" in line]
    assert len(start_end_lines) == 1
    matches = _DATETIME_RE.findall(start_end_lines[0])
    assert len(matches) == 2, f"Expected two datetimes in: {start_end_lines[0]}"


# ---------------------------------------------------------------------------

# Unit tests — _collect_failed_tests
# ---------------------------------------------------------------------------


def test_collect_failed_tests_path_contains_fixture_filename(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    import robot.result as rr

    result = rr.ExecutionResult(str(output_xml))
    failed: list[FailedTest] = _collect_failed_tests(result.suite)

    assert all("error_groups_suite.robot" in str(ft.source) for ft in failed)


# ---------------------------------------------------------------------------
# Unit tests — render_summary_markdown edge cases
# ---------------------------------------------------------------------------


def test_collect_failed_tests_handles_suite_without_source() -> None:
    from unittest.mock import MagicMock

    mock_test = MagicMock()
    mock_test.status = "FAIL"
    mock_test.name = "My Test"
    mock_test.message = "Some error"

    mock_suite = MagicMock()
    mock_suite.source = None
    mock_suite.name = "My Suite"
    mock_suite.tests = [mock_test]
    mock_suite.suites = []

    failed = _collect_failed_tests(mock_suite)

    assert len(failed) == 1
    assert failed[0].source == Path("")


def test_collect_failed_tests_recurses_into_sub_suites() -> None:
    from unittest.mock import MagicMock

    mock_test = MagicMock()
    mock_test.status = "FAIL"
    mock_test.name = "Child Test"
    mock_test.message = "Error in child"

    child_suite = MagicMock()
    child_suite.source = Path("/some/child.robot")
    child_suite.name = "Child Suite"
    child_suite.tests = [mock_test]
    child_suite.suites = []

    parent_suite = MagicMock()
    parent_suite.tests = []
    parent_suite.suites = [child_suite]

    failed = _collect_failed_tests(parent_suite)

    assert len(failed) == 1
    assert failed[0].suite_name == "Child Suite"
    assert failed[0].test_name == "Child Test"


def test_render_summary_markdown_raises_when_output_is_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing.xml"

    try:
        render_summary_markdown(missing)
    except FileNotFoundError as error:
        assert str(missing) in str(error)
    else:
        raise AssertionError("Expected FileNotFoundError")


def test_render_summary_markdown_path_normalizer_applied(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)

    markdown = render_summary_markdown(output_xml, path_normalizer=lambda _: "mocked/path.robot")

    assert "mocked/path.robot" in markdown
