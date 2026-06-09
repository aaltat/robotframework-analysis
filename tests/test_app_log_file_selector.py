"""Tests for App Log File Selection (Rules 0, 1, 1.5, 2, 3)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from robotframework_analysis.mcp.app_log.file_selector import find_app_log_for_test

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_T0 = datetime(2026, 5, 11, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 11, 10, 1, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 11, 10, 2, 0, tzinfo=UTC)
_T3 = datetime(2026, 5, 11, 10, 3, 0, tzinfo=UTC)
_OUTSIDE = datetime(2026, 5, 11, 9, 0, 0, tzinfo=UTC)


def _line(**kwargs: object) -> str:
    return json.dumps(kwargs) + "\n"


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _http(dt: datetime) -> str:
    return _line(
        timestamp=_ts(dt),
        event="http",
        method="GET",
        url="/",
        status=200,
        contentLength=10,
        responseTimeMs=1.0,
    )


def _start_test(dt: datetime, test_id: str) -> str:
    return _line(timestamp=_ts(dt), event="start_test", id=test_id, name="T", pid=1)


def _start_suite(dt: datetime, suite_id: str) -> str:
    return _line(timestamp=_ts(dt), event="start_suite", id=suite_id, name="S", pid=1)


def _write(path: Path, *lines: str) -> Path:
    path.write_text("".join(lines))
    return path


# ---------------------------------------------------------------------------
# Rule 0: file with matching start_test id is the definitive match
# ---------------------------------------------------------------------------


def test_rule0_returns_file_with_matching_test_id(tmp_path: Path) -> None:
    log = _write(tmp_path / "test-app-001.log", _start_test(_T1, "s1-s1-t1"))

    result = find_app_log_for_test(tmp_path, "s1-s1-t1")

    assert result == log


def test_rule0_works_without_time_window(tmp_path: Path) -> None:
    log = _write(tmp_path / "test-app-001.log", _start_test(_T1, "s1-s1-t1"))

    result = find_app_log_for_test(tmp_path, "s1-s1-t1")

    assert result == log


def test_rule0_picks_correct_file_among_multiple(tmp_path: Path) -> None:
    _write(tmp_path / "test-app-001.log", _start_test(_T1, "s1-s1-t2"))
    target = _write(tmp_path / "test-app-002.log", _start_test(_T1, "s1-s1-t1"))
    _write(tmp_path / "test-app-003.log", _start_test(_T1, "s1-s1-t3"))

    result = find_app_log_for_test(tmp_path, "s1-s1-t1")

    assert result == target


# ---------------------------------------------------------------------------
# Rule 2: file with start_test events but none match → excluded
# ---------------------------------------------------------------------------


def test_rule2_excludes_file_with_only_other_test_ids(tmp_path: Path) -> None:
    _write(tmp_path / "test-app-001.log", _start_test(_T1, "s1-s1-t2"))

    result = find_app_log_for_test(tmp_path, "s1-s1-t1", _T0, _T2)

    assert result is None


def test_rule2_excludes_even_when_timestamps_match(tmp_path: Path) -> None:
    _write(
        tmp_path / "test-app-001.log",
        _start_test(_T1, "s1-s1-t2"),
        _http(_T1),
    )

    result = find_app_log_for_test(tmp_path, "s1-s1-t1", _T0, _T2)

    assert result is None


# ---------------------------------------------------------------------------
# Rule 3: no match at all → None
# ---------------------------------------------------------------------------


def test_rule3_returns_none_for_empty_directory(tmp_path: Path) -> None:
    result = find_app_log_for_test(tmp_path, "s1-s1-t1")

    assert result is None


def test_rule3_returns_none_when_no_file_matches(tmp_path: Path) -> None:
    _write(tmp_path / "test-app-001.log", _start_test(_T1, "s1-s1-t2"))
    _write(tmp_path / "test-app-002.log", _start_test(_T1, "s1-s1-t3"))

    result = find_app_log_for_test(tmp_path, "s1-s1-t1")

    assert result is None


# ---------------------------------------------------------------------------
# Rule 1: no lifecycle events in file + time window matches → fallback candidate
# ---------------------------------------------------------------------------


def test_rule1_returns_context_free_file_when_time_matches(tmp_path: Path) -> None:
    log = _write(tmp_path / "test-app-001.log", _http(_T1))

    result = find_app_log_for_test(tmp_path, "s1-s1-t1", _T0, _T2)

    assert result == log


def test_rule1_requires_time_window(tmp_path: Path) -> None:
    _write(tmp_path / "test-app-001.log", _http(_T1))

    result = find_app_log_for_test(tmp_path, "s1-s1-t1")

    assert result is None


def test_rule1_requires_events_inside_window(tmp_path: Path) -> None:
    _write(tmp_path / "test-app-001.log", _http(_OUTSIDE))

    result = find_app_log_for_test(tmp_path, "s1-s1-t1", _T0, _T2)

    assert result is None


# ---------------------------------------------------------------------------
# Rule 1.5: has matching suite_id but no matching test_id + time window matches
# ---------------------------------------------------------------------------


def test_rule1_5_returns_file_with_matching_suite_id(tmp_path: Path) -> None:
    log = _write(
        tmp_path / "test-app-001.log",
        _start_suite(_T1, "s1-s1"),
        _http(_T1),
    )

    result = find_app_log_for_test(tmp_path, "s1-s1-t1", _T0, _T2)

    assert result == log


def test_rule1_5_requires_time_window(tmp_path: Path) -> None:
    _write(tmp_path / "test-app-001.log", _start_suite(_T1, "s1-s1"))

    result = find_app_log_for_test(tmp_path, "s1-s1-t1")

    assert result is None


def test_rule1_5_excluded_when_suite_id_does_not_match(tmp_path: Path) -> None:
    _write(
        tmp_path / "test-app-001.log",
        _start_suite(_T1, "s2"),
        _http(_T1),
    )

    result = find_app_log_for_test(tmp_path, "s1-s1-t1", _T0, _T2)

    assert result is None


# ---------------------------------------------------------------------------
# Priority: Rule 0 overrides Rule 1 / Rule 1.5 candidates
# ---------------------------------------------------------------------------


def test_rule0_overrides_rule1_candidate(tmp_path: Path) -> None:
    _write(tmp_path / "test-app-001.log", _http(_T1))
    rule0 = _write(tmp_path / "test-app-002.log", _start_test(_T1, "s1-s1-t1"))

    result = find_app_log_for_test(tmp_path, "s1-s1-t1", _T0, _T2)

    assert result == rule0


def test_rule0_overrides_rule1_5_candidate(tmp_path: Path) -> None:
    _write(tmp_path / "test-app-001.log", _start_suite(_T1, "s1-s1"), _http(_T1))
    rule0 = _write(tmp_path / "test-app-002.log", _start_test(_T1, "s1-s1-t1"))

    result = find_app_log_for_test(tmp_path, "s1-s1-t1", _T0, _T2)

    assert result == rule0


# ---------------------------------------------------------------------------
# Priority: Rule 1.5 beats Rule 1 when both present
# ---------------------------------------------------------------------------


def test_rule1_5_beats_rule1_when_both_are_fallback_candidates(tmp_path: Path) -> None:
    _write(tmp_path / "test-app-001.log", _http(_T1))
    rule1_5 = _write(
        tmp_path / "test-app-002.log",
        _start_suite(_T1, "s1-s1"),
        _http(_T1),
    )

    result = find_app_log_for_test(tmp_path, "s1-s1-t1", _T0, _T2)

    assert result == rule1_5


# ---------------------------------------------------------------------------
# Tiebreaker: among multiple Rule 1.5 candidates, pick most events in window
# ---------------------------------------------------------------------------


def test_rule1_5_tiebreaker_picks_file_with_most_events_in_window(tmp_path: Path) -> None:
    _write(
        tmp_path / "test-app-001.log",
        _start_suite(_T1, "s1-s1"),
        _http(_T1),
    )
    busier = _write(
        tmp_path / "test-app-002.log",
        _start_suite(_T1, "s1-s1"),
        _http(_T1),
        _http(_T1),
        _http(_T1),
    )

    result = find_app_log_for_test(tmp_path, "s1-s1-t1", _T0, _T2)

    assert result == busier


def test_rule1_tiebreaker_picks_file_with_most_events_in_window(tmp_path: Path) -> None:
    _write(tmp_path / "test-app-001.log", _http(_T1))
    busier = _write(
        tmp_path / "test-app-002.log",
        _http(_T1),
        _http(_T1),
        _http(_T2),
    )

    result = find_app_log_for_test(tmp_path, "s1-s1-t1", _T0, _T3)

    assert result == busier
