from __future__ import annotations

from pathlib import Path

import pytest
from approvaltests import settings, verify
from approvaltests.core.options import Options
from robot import run as robot_run  # type: ignore[attr-defined]

from robotframework_analysis.mcp.results.results_analysis import normalize_log_timestamps
from robotframework_analysis.mcp.results.server import (
    _ResultsCache,
    get_failure_detail,
    get_test_run_summary,
)


def _run_fixture(fixture_name: str, tmp_path: Path) -> str:
    suite_file = Path(__file__).parent / "fixtures" / fixture_name
    output_xml = tmp_path / "output.xml"
    robot_run(str(suite_file), output=str(output_xml), log="NONE", report="NONE", loglevel="TRACE")
    return str(output_xml)


def test_server_summary_error_groups(tmp_path: Path) -> None:
    settings().allow_multiple_verify_calls_for_this_method()
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)

    summary = get_test_run_summary(output_xml)

    verify(
        normalize_log_timestamps(summary.model_dump_json(indent=2)),
        options=Options().for_file.with_extension(".json"),
    )


def test_server_summary_all_passing(tmp_path: Path) -> None:
    settings().allow_multiple_verify_calls_for_this_method()
    output_xml = _run_fixture("all_passing_suite.robot", tmp_path)

    summary = get_test_run_summary(output_xml)

    verify(
        normalize_log_timestamps(summary.model_dump_json(indent=2)),
        options=Options().for_file.with_extension(".json"),
    )


def test_server_detail_login_timeout(tmp_path: Path) -> None:
    settings().allow_multiple_verify_calls_for_this_method()
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)

    detail = get_failure_detail(output_xml, "Error Groups Suite", "Login Timeout")

    verify(
        normalize_log_timestamps(detail.model_dump_json(indent=2)),
        options=Options().for_file.with_extension(".json"),
    )


def test_cache_returns_same_object_on_second_call(tmp_path: Path) -> None:
    output_xml = _run_fixture("summary_suite.robot", tmp_path)
    cache = _ResultsCache()

    first = cache.get(output_xml)
    second = cache.get(output_xml)

    assert first is second


def test_cache_evicts_stale_entry_when_mtime_changes(tmp_path: Path) -> None:
    output_xml = _run_fixture("summary_suite.robot", tmp_path)
    cache = _ResultsCache()

    first = cache.get(output_xml)

    Path(output_xml).touch()

    second = cache.get(output_xml)

    assert first is not second


def test_cache_raises_for_missing_file() -> None:
    cache = _ResultsCache()
    with pytest.raises(FileNotFoundError):
        cache.get("/nonexistent/output.xml")


def test_get_test_run_summary_raises_for_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        get_test_run_summary("/nonexistent/output.xml")


def test_get_failure_detail_raises_when_test_not_found(tmp_path: Path) -> None:
    output_xml = _run_fixture("summary_suite.robot", tmp_path)
    with pytest.raises(ValueError, match="not found"):
        get_failure_detail(output_xml, "Summary Suite", "Nonexistent Test")


def test_summary_and_detail_use_shared_cache(tmp_path: Path) -> None:
    from robotframework_analysis.mcp.results import server as srv

    output_xml = _run_fixture("summary_suite.robot", tmp_path)
    srv._cache = _ResultsCache()

    srv.get_test_run_summary(output_xml)
    assert len(srv._cache._store) == 1

    srv.get_failure_detail(output_xml, "Summary Suite", "Failing")
    assert len(srv._cache._store) == 1
