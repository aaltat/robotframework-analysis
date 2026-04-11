from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

from approvaltests import verify
from approvaltests.core.options import Options
from robot import run as robot_run  # type: ignore[attr-defined]

from robotframework_analysis.report_markdown import (
    FailedTest,
    FailingBranch,
    _build_detail_filename,
    _build_keyword_source_index,
    _collect_failed_tests,
    _collect_log_messages,
    _error_group_key,
    _find_failing_library_name,
    _format_start_end,
    _normalize_keyword_name,
    _render_detail_markdown,
    _sanitize_log_payload,
    _sanitize_name,
    _truncate_error,
    render_summary_markdown,
)

_WORKSPACE_ROOT = Path(__file__).parent.parent


def _path_normalizer(p: Path) -> str:
    return str(p.relative_to(_WORKSPACE_ROOT))


def _make_path_normalizer(project_root: Path) -> Callable[[Path], str]:
    def _normalize(p: Path) -> str:
        try:
            return str(p.relative_to(_WORKSPACE_ROOT))
        except ValueError:
            return str(p.relative_to(project_root))

    return _normalize


_FIXED_DATETIME = "20260101 00:00:00.000"
_LOG_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+")


def _time_normalizer(starttime: str, endtime: str) -> str:
    return f"{_FIXED_DATETIME} / {_FIXED_DATETIME}"


def _normalize_log_timestamps(text: str) -> str:
    return _LOG_TIMESTAMP_RE.sub("timestamp", text)


def _run_fixture(fixture_name: str, tmp_path: Path) -> Path:
    suite_file = Path(__file__).parent / "fixtures" / fixture_name
    output_xml = tmp_path / "output.xml"
    robot_run(str(suite_file), output=str(output_xml), log="NONE", report="NONE", loglevel="TRACE")
    return output_xml


# ---------------------------------------------------------------------------
# Approval tests
# ---------------------------------------------------------------------------


def test_renders_summary_markdown(tmp_path: Path) -> None:
    output_xml = _run_fixture("summary_suite.robot", tmp_path)
    normalize = _make_path_normalizer(tmp_path)

    markdown = render_summary_markdown(
        output_xml,
        path_normalizer=normalize,
        time_normalizer=_time_normalizer,
        project_root=tmp_path,
    )

    verify(markdown, options=Options().for_file.with_extension(".md"))


def test_renders_all_passing_markdown(tmp_path: Path) -> None:
    output_xml = _run_fixture("all_passing_suite.robot", tmp_path)
    normalize = _make_path_normalizer(tmp_path)

    markdown = render_summary_markdown(
        output_xml,
        path_normalizer=normalize,
        time_normalizer=_time_normalizer,
        project_root=tmp_path,
    )

    verify(markdown, options=Options().for_file.with_extension(".md"))


def test_renders_error_groups_markdown(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    normalize = _make_path_normalizer(tmp_path)

    markdown = render_summary_markdown(
        output_xml,
        path_normalizer=normalize,
        time_normalizer=_time_normalizer,
        project_root=tmp_path,
    )

    verify(markdown, options=Options().for_file.with_extension(".md"))


def test_renders_suite_setup_failure_markdown(tmp_path: Path) -> None:
    output_xml = _run_fixture("suite_setup_failure_suite.robot", tmp_path)
    normalize = _make_path_normalizer(tmp_path)

    markdown = render_summary_markdown(
        output_xml,
        path_normalizer=normalize,
        time_normalizer=_time_normalizer,
        project_root=tmp_path,
    )

    verify(markdown, options=Options().for_file.with_extension(".md"))


def test_renders_suite_teardown_failure_markdown(tmp_path: Path) -> None:
    output_xml = _run_fixture("suite_teardown_failure_suite.robot", tmp_path)
    normalize = _make_path_normalizer(tmp_path)

    markdown = render_summary_markdown(
        output_xml,
        path_normalizer=normalize,
        time_normalizer=_time_normalizer,
        project_root=tmp_path,
    )

    verify(markdown, options=Options().for_file.with_extension(".md"))


# ---------------------------------------------------------------------------
# Approval tests — detail files
# ---------------------------------------------------------------------------


def test_detail_file_summary_suite_failing(tmp_path: Path) -> None:
    output_xml = _run_fixture("summary_suite.robot", tmp_path)
    normalize = _make_path_normalizer(tmp_path)
    render_summary_markdown(
        output_xml,
        path_normalizer=normalize,
        time_normalizer=_time_normalizer,
        project_root=tmp_path,
    )
    detail_file = tmp_path / ".robotframework_analysis" / "group_001_Summary_Suite_Failing_001.md"
    verify(
        _normalize_log_timestamps(detail_file.read_text(encoding="utf-8")),
        options=Options().for_file.with_extension(".md"),
    )


def test_detail_file_error_groups_database_error_one(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    normalize = _make_path_normalizer(tmp_path)
    render_summary_markdown(
        output_xml,
        path_normalizer=normalize,
        time_normalizer=_time_normalizer,
        project_root=tmp_path,
    )
    detail_file = (
        tmp_path
        / ".robotframework_analysis"
        / "group_001_Error_Groups_Suite_Database_Error_One_001.md"
    )
    verify(
        _normalize_log_timestamps(detail_file.read_text(encoding="utf-8")),
        options=Options().for_file.with_extension(".md"),
    )


def test_detail_file_error_groups_database_error_two(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    normalize = _make_path_normalizer(tmp_path)
    render_summary_markdown(
        output_xml,
        path_normalizer=normalize,
        time_normalizer=_time_normalizer,
        project_root=tmp_path,
    )
    detail_file = (
        tmp_path
        / ".robotframework_analysis"
        / "group_001_Error_Groups_Suite_Database_Error_Two_002.md"
    )
    verify(
        _normalize_log_timestamps(detail_file.read_text(encoding="utf-8")),
        options=Options().for_file.with_extension(".md"),
    )


def test_detail_file_error_groups_login_timeout(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    normalize = _make_path_normalizer(tmp_path)
    render_summary_markdown(
        output_xml,
        path_normalizer=normalize,
        time_normalizer=_time_normalizer,
        project_root=tmp_path,
    )
    detail_file = (
        tmp_path / ".robotframework_analysis" / "group_002_Error_Groups_Suite_Login_Timeout_001.md"
    )
    verify(
        _normalize_log_timestamps(detail_file.read_text(encoding="utf-8")),
        options=Options().for_file.with_extension(".md"),
    )


def test_detail_file_error_groups_printed_failure(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    normalize = _make_path_normalizer(tmp_path)
    render_summary_markdown(
        output_xml,
        path_normalizer=normalize,
        time_normalizer=_time_normalizer,
        project_root=tmp_path,
    )
    detail_file = (
        tmp_path
        / ".robotframework_analysis"
        / "group_003_Error_Groups_Suite_Printed_Failure_001.md"
    )
    verify(
        _normalize_log_timestamps(detail_file.read_text(encoding="utf-8")),
        options=Options().for_file.with_extension(".md"),
    )


def test_detail_file_error_groups_setup_failure_case(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    normalize = _make_path_normalizer(tmp_path)
    render_summary_markdown(
        output_xml,
        path_normalizer=normalize,
        time_normalizer=_time_normalizer,
        project_root=tmp_path,
    )
    detail_file = (
        tmp_path
        / ".robotframework_analysis"
        / "group_004_Error_Groups_Suite_Setup_Failure_Case_001.md"
    )
    verify(
        _normalize_log_timestamps(detail_file.read_text(encoding="utf-8")),
        options=Options().for_file.with_extension(".md"),
    )


def test_detail_file_error_groups_teardown_failure_case(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    normalize = _make_path_normalizer(tmp_path)
    render_summary_markdown(
        output_xml,
        path_normalizer=normalize,
        time_normalizer=_time_normalizer,
        project_root=tmp_path,
    )
    detail_file = (
        tmp_path
        / ".robotframework_analysis"
        / "group_005_Error_Groups_Suite_Teardown_Failure_Case_001.md"
    )
    verify(
        _normalize_log_timestamps(detail_file.read_text(encoding="utf-8")),
        options=Options().for_file.with_extension(".md"),
    )


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
# Unit tests — _sanitize_name
# ---------------------------------------------------------------------------


def test_sanitize_name_replaces_spaces() -> None:
    assert _sanitize_name("Summary Suite") == "Summary_Suite"


def test_sanitize_name_replaces_special_chars() -> None:
    assert _sanitize_name("Error (test)") == "Error_test"


def test_sanitize_name_strips_leading_trailing_underscores() -> None:
    assert _sanitize_name(" Suite ") == "Suite"


def test_sanitize_name_collapses_consecutive_separators() -> None:
    assert _sanitize_name("My  Suite") == "My_Suite"


# ---------------------------------------------------------------------------
# Unit tests — _build_detail_filename
# ---------------------------------------------------------------------------


def test_build_detail_filename_produces_correct_name() -> None:
    assert _build_detail_filename(1, "Summary Suite", "Failing", 1) == (
        "group_001_Summary_Suite_Failing_001.md"
    )


def test_build_detail_filename_pads_numbers() -> None:
    assert _build_detail_filename(2, "My Suite", "Test", 10) == ("group_002_My_Suite_Test_010.md")


# ---------------------------------------------------------------------------

# Unit tests — _collect_failed_tests
# ---------------------------------------------------------------------------


def test_collect_failed_tests_path_contains_fixture_filename(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    import robot.result as rr

    result = rr.ExecutionResult(str(output_xml))
    failed: list[FailedTest] = _collect_failed_tests(result.suite)

    assert all("error_groups_suite.robot" in str(ft.source) for ft in failed)


def test_collect_failed_tests_includes_only_failing_keyword_logs(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    import robot.result as rr

    result = rr.ExecutionResult(str(output_xml))
    failed = _collect_failed_tests(result.suite)

    login_timeout = next(ft for ft in failed if ft.test_name == "Login Timeout")
    normalized = [_normalize_log_timestamps(line) for line in login_timeout.log_messages]
    assert normalized == [
        "timestamp INFO: log messages goes here 1",
        "timestamp INFO: html info message",
        "timestamp DEBUG: log messages goes here 2",
        "timestamp DEBUG: html debug message",
        "timestamp WARN: log messages goes here 3",
        "timestamp WARN: <removed html>",
        "timestamp TRACE: log messages goes here 4",
    ]


def test_sanitize_log_payload_strips_html_tags() -> None:
    assert _sanitize_log_payload("<div><b>hello</b> world</div>") == "hello world"


def test_sanitize_log_payload_returns_marker_for_tags_only() -> None:
    assert _sanitize_log_payload('<img src="data:image/png;base64,AAAA" />') == "<removed html>"


def test_collect_failed_tests_contains_keyword_leaf_for_nested_failure(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    import robot.result as rr

    result = rr.ExecutionResult(str(output_xml))
    failed = _collect_failed_tests(result.suite)

    login_timeout = next(ft for ft in failed if ft.test_name == "Login Timeout")
    leaf = "\n".join(login_timeout.keyword_leaf_lines)
    assert "Keyword One    PASS" in leaf
    assert "Keyword Two    PASS" in leaf
    assert "Keyword Three    FAIL" in leaf
    assert "Sub Keyword 3.1    FAIL" in leaf
    assert "Sub Keyword 3.1.1    FAIL" in leaf
    assert "Raise Logged Type Error    FAIL" in leaf
    assert "Error: TypeError: TypeError: expected argument of type st…" in leaf


def test_collect_failed_tests_includes_print_output_in_log_section(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    import robot.result as rr

    result = rr.ExecutionResult(str(output_xml))
    failed = _collect_failed_tests(result.suite)

    printed_failure = next(ft for ft in failed if ft.test_name == "Printed Failure")
    normalized = [_normalize_log_timestamps(line) for line in printed_failure.log_messages]
    assert normalized == [
        "timestamp INFO: printed output goes here 1\nprinted output goes here 2",
    ]


def test_collect_failed_tests_uses_test_setup_branch_when_setup_fails(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    import robot.result as rr

    result = rr.ExecutionResult(str(output_xml))
    failed = _collect_failed_tests(result.suite)

    setup_failure = next(ft for ft in failed if ft.test_name == "Setup Failure Case")
    leaf = "\n".join(setup_failure.keyword_leaf_lines)
    assert "└── Test Setup" in leaf
    assert "SETUP    FAIL" in leaf


def test_collect_failed_tests_uses_test_teardown_branch_when_teardown_fails(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    import robot.result as rr

    result = rr.ExecutionResult(str(output_xml))
    failed = _collect_failed_tests(result.suite)

    teardown_failure = next(ft for ft in failed if ft.test_name == "Teardown Failure Case")
    leaf = "\n".join(teardown_failure.keyword_leaf_lines)
    assert "└── Test Teardown" in leaf
    assert "TEARDOWN    FAIL" in leaf


# ---------------------------------------------------------------------------
# Unit tests — render_summary_markdown edge cases
# ---------------------------------------------------------------------------


def test_collect_failed_tests_uses_robot_suite_models_only(tmp_path: Path) -> None:
    output_xml = _run_fixture("summary_suite.robot", tmp_path)
    import robot.result as rr

    result = rr.ExecutionResult(str(output_xml))
    failed = _collect_failed_tests(result.suite)

    assert len(failed) == 1
    assert failed[0].suite_name == "Summary Suite"
    assert failed[0].test_name == "Failing"


def test_collect_failed_tests_visits_nested_suites(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    import robot.result as rr

    result = rr.ExecutionResult(str(output_xml))
    failed = _collect_failed_tests(result.suite)

    assert any(ft.suite_name == "Error Groups Suite" for ft in failed)
    assert any(ft.test_name == "Printed Failure" for ft in failed)


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


def test_render_summary_markdown_without_project_root_omits_detail_column(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)

    markdown = render_summary_markdown(output_xml, path_normalizer=_path_normalizer)

    assert "| Suite Name | Test Name | Path |" in markdown
    assert "| Suite Name | Test Name | Path | More Details |" not in markdown


def test_build_keyword_source_index_returns_empty_for_missing_suite_file(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.robot"

    index = _build_keyword_source_index(missing)

    assert index == {}


def test_build_keyword_source_index_finds_inline_suite_keywords(tmp_path: Path) -> None:
    suite_file = tmp_path / "inline_kw_suite.robot"
    suite_file.write_text(
        "*** Test Cases ***\n"
        "Dummy\n"
        "    My Suite Keyword\n"
        "\n"
        "*** Keywords ***\n"
        "My Suite Keyword\n"
        "    No Operation\n",
        encoding="utf-8",
    )

    index = _build_keyword_source_index(suite_file)

    assert _normalize_keyword_name("My Suite Keyword") in index


def test_find_failing_library_name_falls_back_to_owner() -> None:
    leaf = SimpleNamespace(owner="LegacyLib")
    branch = FailingBranch(phase_label="Test Body", top_level_nodes=[leaf], failing_path=[leaf])

    assert _find_failing_library_name(branch) == "LegacyLib"


def test_collect_log_messages_returns_empty_when_keyword_is_none() -> None:
    assert _collect_log_messages(None, "boom") == []


def test_collect_log_messages_skips_non_message_items() -> None:
    keyword = SimpleNamespace(
        body=[
            SimpleNamespace(type="KEYWORD", message="not a message"),
            SimpleNamespace(type="MESSAGE", level="INFO", message="keep this", timestamp="t"),
        ]
    )

    assert _collect_log_messages(keyword, "boom") == ["t INFO: keep this"]


def test_collect_log_messages_skips_message_equal_to_failure_message() -> None:
    keyword = SimpleNamespace(
        body=[
            SimpleNamespace(type="MESSAGE", level="INFO", message="boom", timestamp="t"),
            SimpleNamespace(type="MESSAGE", level="WARN", message="other", timestamp="t2"),
        ]
    )

    assert _collect_log_messages(keyword, "boom") == ["t2 WARN: other"]


# ---------------------------------------------------------------------------
# Unit tests — project_root / detail files
# ---------------------------------------------------------------------------


def test_no_project_root_produces_no_more_details_column(tmp_path: Path) -> None:
    output_xml = _run_fixture("summary_suite.robot", tmp_path)

    markdown = render_summary_markdown(output_xml)

    assert "More Details" not in markdown


def test_project_root_creates_detail_directory(tmp_path: Path) -> None:
    output_xml = _run_fixture("summary_suite.robot", tmp_path)

    render_summary_markdown(output_xml, project_root=tmp_path)

    assert (tmp_path / ".robotframework_analysis").is_dir()


def test_project_root_creates_correct_number_of_detail_files(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)

    render_summary_markdown(output_xml, project_root=tmp_path)

    detail_files = list((tmp_path / ".robotframework_analysis").glob("*.md"))
    assert len(detail_files) == 6


def test_project_root_cleans_old_files_on_rerun(tmp_path: Path) -> None:
    output_xml = _run_fixture("summary_suite.robot", tmp_path)
    detail_dir = tmp_path / ".robotframework_analysis"
    detail_dir.mkdir()
    (detail_dir / "old_file.md").write_text("old content")

    render_summary_markdown(output_xml, project_root=tmp_path)

    assert not (detail_dir / "old_file.md").exists()


def test_render_detail_markdown_omits_log_section_when_logs_missing() -> None:
    ft = FailedTest("Summary Suite", "Failing", Path("suite.robot"), "boom", [], [])

    markdown = _normalize_log_timestamps(_render_detail_markdown(ft))

    assert (
        markdown == "# Summary Suite Failing error\n\nboom\n\n# Origin\n- Test file: suite.robot\n"
    )


def test_render_detail_markdown_includes_keyword_leaf_section() -> None:
    ft = FailedTest(
        "Summary Suite",
        "Failing",
        Path("suite.robot"),
        "boom",
        [],
        ["Failing", "└── Test Body", "    └── Fail    FAIL", "        Error: boom"],
    )

    markdown = _render_detail_markdown(ft)

    assert "# Keyword leaf" in markdown
    assert "└── Test Body" in markdown
