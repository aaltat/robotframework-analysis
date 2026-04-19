from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import robot.result as rr
from approvaltests import settings, verify
from approvaltests.core.options import Options
from robot import run as robot_run  # type: ignore[attr-defined]

from robotframework_analysis.mcp.results.results_analysis import (
    FailedTest,
    FailingBranch,
    _build_keyword_source_index,
    _collect_failed_tests,
    _collect_log_messages,
    _error_group_key,
    _extract_screenshot_refs,
    _extract_screenshot_refs_from_keyword,
    _find_failing_library_name,
    _normalize_keyword_name,
    _sanitize_log_payload,
    _truncate_error,
    build_failure_detail,
    build_test_run_summary,
    normalize_log_timestamps,
)

_SCREENSHOT_PATH_RE = re.compile(r'"(/[^"]+screenshot_[^"]+\.(?:png|jpg|jpeg|gif|webp))"')


def _normalize_screenshot_paths(json_str: str) -> str:
    return _SCREENSHOT_PATH_RE.sub('"<screenshot_path>"', json_str)


def _normalize_detail(json_str: str) -> str:
    return _normalize_screenshot_paths(normalize_log_timestamps(json_str))


def _run_fixture(fixture_name: str, tmp_path: Path) -> Path:
    suite_file = Path(__file__).parent / "fixtures" / fixture_name
    output_xml = tmp_path / "output.xml"
    robot_run(
        str(suite_file),
        output=str(output_xml),
        outputdir=str(tmp_path),
        log="NONE",
        report="NONE",
        loglevel="TRACE",
    )
    return output_xml


def test_summary_summary_suite(tmp_path: Path) -> None:
    settings().allow_multiple_verify_calls_for_this_method()
    output_xml = _run_fixture("summary_suite.robot", tmp_path)

    summary = build_test_run_summary(output_xml)

    verify(
        normalize_log_timestamps(summary.model_dump_json(indent=2)),
        options=Options().for_file.with_extension(".json"),
    )


def test_summary_all_passing(tmp_path: Path) -> None:
    settings().allow_multiple_verify_calls_for_this_method()
    output_xml = _run_fixture("all_passing_suite.robot", tmp_path)

    summary = build_test_run_summary(output_xml)

    verify(
        normalize_log_timestamps(summary.model_dump_json(indent=2)),
        options=Options().for_file.with_extension(".json"),
    )


def test_summary_error_groups(tmp_path: Path) -> None:
    settings().allow_multiple_verify_calls_for_this_method()
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)

    summary = build_test_run_summary(output_xml)

    verify(
        normalize_log_timestamps(summary.model_dump_json(indent=2)),
        options=Options().for_file.with_extension(".json"),
    )


def test_summary_suite_setup_failure(tmp_path: Path) -> None:
    settings().allow_multiple_verify_calls_for_this_method()
    output_xml = _run_fixture("suite_setup_failure_suite.robot", tmp_path)

    summary = build_test_run_summary(output_xml)

    verify(
        normalize_log_timestamps(summary.model_dump_json(indent=2)),
        options=Options().for_file.with_extension(".json"),
    )


def test_summary_suite_teardown_failure(tmp_path: Path) -> None:
    settings().allow_multiple_verify_calls_for_this_method()
    output_xml = _run_fixture("suite_teardown_failure_suite.robot", tmp_path)

    summary = build_test_run_summary(output_xml)

    verify(
        normalize_log_timestamps(summary.model_dump_json(indent=2)),
        options=Options().for_file.with_extension(".json"),
    )


def test_detail_summary_suite_failing(tmp_path: Path) -> None:
    settings().allow_multiple_verify_calls_for_this_method()
    output_xml = _run_fixture("summary_suite.robot", tmp_path)

    detail = build_failure_detail(output_xml, "Summary Suite", "Failing")

    verify(
        _normalize_detail(detail.model_dump_json(indent=2)),
        options=Options().for_file.with_extension(".json"),
    )


def test_detail_error_groups_database_error_one(tmp_path: Path) -> None:
    settings().allow_multiple_verify_calls_for_this_method()
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)

    detail = build_failure_detail(output_xml, "Error Groups Suite", "Database Error One")

    verify(
        _normalize_detail(detail.model_dump_json(indent=2)),
        options=Options().for_file.with_extension(".json"),
    )


def test_detail_error_groups_database_error_two(tmp_path: Path) -> None:
    settings().allow_multiple_verify_calls_for_this_method()
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)

    detail = build_failure_detail(output_xml, "Error Groups Suite", "Database Error Two")

    verify(
        _normalize_detail(detail.model_dump_json(indent=2)),
        options=Options().for_file.with_extension(".json"),
    )


def test_detail_error_groups_login_timeout(tmp_path: Path) -> None:
    settings().allow_multiple_verify_calls_for_this_method()
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)

    detail = build_failure_detail(output_xml, "Error Groups Suite", "Login Timeout")

    verify(
        _normalize_detail(detail.model_dump_json(indent=2)),
        options=Options().for_file.with_extension(".json"),
    )


def test_detail_error_groups_printed_failure(tmp_path: Path) -> None:
    settings().allow_multiple_verify_calls_for_this_method()
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)

    detail = build_failure_detail(output_xml, "Error Groups Suite", "Printed Failure")

    verify(
        _normalize_detail(detail.model_dump_json(indent=2)),
        options=Options().for_file.with_extension(".json"),
    )


def test_detail_error_groups_setup_failure_case(tmp_path: Path) -> None:
    settings().allow_multiple_verify_calls_for_this_method()
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)

    detail = build_failure_detail(output_xml, "Error Groups Suite", "Setup Failure Case")

    verify(
        _normalize_detail(detail.model_dump_json(indent=2)),
        options=Options().for_file.with_extension(".json"),
    )


def test_detail_error_groups_teardown_failure_case(tmp_path: Path) -> None:
    settings().allow_multiple_verify_calls_for_this_method()
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)

    detail = build_failure_detail(output_xml, "Error Groups Suite", "Teardown Failure Case")

    verify(
        _normalize_detail(detail.model_dump_json(indent=2)),
        options=Options().for_file.with_extension(".json"),
    )


def test_detail_screenshot_via_file_link(tmp_path: Path) -> None:
    output_xml = _run_fixture("screenshot_suite.robot", tmp_path)

    detail = build_failure_detail(output_xml, "Screenshot Suite", "Screenshot Via File Link")

    assert len(detail.screenshot_paths) == 1
    screenshot = Path(detail.screenshot_paths[0])
    assert screenshot.is_absolute()
    assert screenshot.exists()
    assert screenshot.suffix == ".png"


def test_detail_screenshot_via_embedded_image(tmp_path: Path) -> None:
    output_xml = _run_fixture("screenshot_suite.robot", tmp_path)

    detail = build_failure_detail(output_xml, "Screenshot Suite", "Screenshot Via Embedded Image")

    assert len(detail.screenshot_paths) == 1
    screenshot = Path(detail.screenshot_paths[0])
    assert screenshot.is_absolute()
    assert screenshot.exists()
    assert screenshot.read_bytes()[:4] == b"\x89PNG"


def test_extract_screenshot_refs_finds_href_link() -> None:
    html = '<a href="screenshot.png">click</a>'
    assert _extract_screenshot_refs(html) == ["screenshot.png"]


def test_extract_screenshot_refs_finds_embedded_data_uri() -> None:
    html = '<img alt="sc" src="data:image/png;base64,AAAA" />'
    assert _extract_screenshot_refs(html) == ["data:image/png;base64,AAAA"]


def test_extract_screenshot_refs_ignores_non_image_href() -> None:
    html = '<a href="report.html">report</a>'
    assert _extract_screenshot_refs(html) == []


def test_extract_screenshot_refs_returns_empty_for_plain_text() -> None:
    assert _extract_screenshot_refs("no images here") == []


def test_extract_screenshot_refs_from_keyword_collects_all_messages() -> None:
    msg1 = SimpleNamespace(type="MESSAGE", message='<a href="sc1.png">s</a>')
    msg2 = SimpleNamespace(type="MESSAGE", message='<img src="data:image/jpeg;base64,XYZ" />')
    kw = SimpleNamespace(body=[msg1, msg2])

    refs = _extract_screenshot_refs_from_keyword(kw)

    assert refs == ["sc1.png", "data:image/jpeg;base64,XYZ"]


def test_extract_screenshot_refs_from_keyword_returns_empty_for_none() -> None:
    assert _extract_screenshot_refs_from_keyword(None) == []


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


def test_truncate_error_short_message_unchanged() -> None:
    assert _truncate_error("short") == "short"


def test_truncate_error_long_message_hard_cut() -> None:
    long = "x" * 400
    result = _truncate_error(long)
    assert result == "x" * 300 + "…"


def test_truncate_error_exactly_300_chars_unchanged() -> None:
    msg = "x" * 300
    assert _truncate_error(msg) == msg


def test_summary_start_time_and_end_time_contain_real_datetimes(tmp_path: Path) -> None:
    _datetime_re = re.compile(r"\d{8} \d{2}:\d{2}:\d{2}\.\d{3}")
    output_xml = _run_fixture("summary_suite.robot", tmp_path)

    summary = build_test_run_summary(output_xml)

    assert _datetime_re.match(summary.start_time), f"Unexpected start_time: {summary.start_time}"
    assert _datetime_re.match(summary.end_time), f"Unexpected end_time: {summary.end_time}"


def test_summary_missing_xml_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        build_test_run_summary("/nonexistent/output.xml")


def test_collect_failed_tests_path_contains_fixture_filename(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    result = rr.ExecutionResult(str(output_xml))
    failed: list[FailedTest] = _collect_failed_tests(result.suite)

    assert all("error_groups_suite.robot" in str(ft.source) for ft in failed)


def test_collect_failed_tests_includes_only_failing_keyword_logs(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    result = rr.ExecutionResult(str(output_xml))
    failed = _collect_failed_tests(result.suite)

    login_timeout = next(ft for ft in failed if ft.test_name == "Login Timeout")
    normalized = [normalize_log_timestamps(line) for line in login_timeout.log_messages]
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
    result = rr.ExecutionResult(str(output_xml))
    failed = _collect_failed_tests(result.suite)

    printed_failure = next(ft for ft in failed if ft.test_name == "Printed Failure")
    normalized = [normalize_log_timestamps(line) for line in printed_failure.log_messages]
    assert normalized == [
        "timestamp INFO: printed output goes here 1\nprinted output goes here 2",
    ]


def test_collect_failed_tests_uses_test_setup_branch_when_setup_fails(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    result = rr.ExecutionResult(str(output_xml))
    failed = _collect_failed_tests(result.suite)

    setup_failure = next(ft for ft in failed if ft.test_name == "Setup Failure Case")
    leaf = "\n".join(setup_failure.keyword_leaf_lines)
    assert "└── Test Setup" in leaf
    assert "SETUP    FAIL" in leaf


def test_collect_failed_tests_uses_test_teardown_branch_when_teardown_fails(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    result = rr.ExecutionResult(str(output_xml))
    failed = _collect_failed_tests(result.suite)

    teardown_failure = next(ft for ft in failed if ft.test_name == "Teardown Failure Case")
    leaf = "\n".join(teardown_failure.keyword_leaf_lines)
    assert "└── Test Teardown" in leaf
    assert "TEARDOWN    FAIL" in leaf


def test_collect_failed_tests_uses_robot_suite_models_only(tmp_path: Path) -> None:
    output_xml = _run_fixture("summary_suite.robot", tmp_path)
    result = rr.ExecutionResult(str(output_xml))
    failed = _collect_failed_tests(result.suite)

    assert len(failed) == 1
    assert failed[0].suite_name == "Summary Suite"
    assert failed[0].test_name == "Failing"


def test_collect_failed_tests_visits_nested_suites(tmp_path: Path) -> None:
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)
    result = rr.ExecutionResult(str(output_xml))
    failed = _collect_failed_tests(result.suite)

    assert any(ft.suite_name == "Error Groups Suite" for ft in failed)
    assert any(ft.test_name == "Printed Failure" for ft in failed)


def test_collect_log_messages_returns_empty_for_none_keyword() -> None:
    assert _collect_log_messages(None, "some error") == []


def test_collect_log_messages_skips_fail_level_messages() -> None:
    msg = SimpleNamespace(type="MESSAGE", level="FAIL", message="the error", timestamp="ts")
    kw = SimpleNamespace(body=[msg])
    assert _collect_log_messages(kw, "other error") == []


def test_collect_log_messages_skips_matching_failure_message() -> None:
    msg = SimpleNamespace(type="MESSAGE", level="INFO", message="duplicate", timestamp="ts")
    kw = SimpleNamespace(body=[msg])
    assert _collect_log_messages(kw, "duplicate") == []


def test_find_failing_library_name_returns_none_for_none_branch() -> None:
    assert _find_failing_library_name(None) is None


def test_find_failing_library_name_reads_libname() -> None:
    leaf = SimpleNamespace(libname="SeleniumLibrary", owner=None)
    branch = FailingBranch(
        phase_label="Test Body",
        top_level_nodes=[leaf],
        failing_path=[leaf],
    )
    assert _find_failing_library_name(branch) == "SeleniumLibrary"


def test_find_failing_library_name_falls_back_to_owner() -> None:
    leaf = SimpleNamespace(libname=None, owner="RequestsLibrary")
    branch = FailingBranch(
        phase_label="Test Body",
        top_level_nodes=[leaf],
        failing_path=[leaf],
    )
    assert _find_failing_library_name(branch) == "RequestsLibrary"


def test_normalize_keyword_name_strips_whitespace_and_underscores() -> None:
    assert _normalize_keyword_name("My Keyword") == "mykeyword"


def test_normalize_keyword_name_collapses_underscores_and_spaces() -> None:
    assert _normalize_keyword_name("my_keyword_name") == "mykeywordname"


def test_build_keyword_source_index_returns_empty_for_nonexistent_source() -> None:
    index = _build_keyword_source_index(Path("/nonexistent/file.robot"))
    assert index == {}


def test_build_keyword_source_index_indexes_inline_keywords() -> None:
    suite_file = Path(__file__).parent / "fixtures" / "error_groups_suite.robot"
    index = _build_keyword_source_index(suite_file)
    assert index != {}
