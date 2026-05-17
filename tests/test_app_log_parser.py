"""Tests for the Browser library app log parser."""

from __future__ import annotations

from pathlib import Path

from robotframework_analysis.mcp.app_log.log_parser import (
    EndTestEvent,
    FilterResult,
    HttpEvent,
    ServerStartEvent,
    StartSuiteEvent,
    StartTestEvent,
    filter_events_for_test,
    filter_http_for_test,
    parse_log_file,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "app-log-slice.log"


def test_parse_returns_all_lines() -> None:
    events = parse_log_file(_FIXTURE)
    assert len(events) == 43


def test_parse_server_start_event() -> None:
    events = parse_log_file(_FIXTURE)
    first = events[0]
    assert isinstance(first, ServerStartEvent)
    assert first.url == "http://localhost:55343"


def test_parse_http_event() -> None:
    events = parse_log_file(_FIXTURE)
    http_events = [e for e in events if isinstance(e, HttpEvent)]
    assert len(http_events) > 0
    first_http = http_events[0]
    assert first_http.method == "GET"
    assert first_http.url == "/prefilled_email_form.html"
    assert first_http.status == 200
    assert first_http.response_time_ms == 2.221


# ---------------------------------------------------------------------------
# filter_events_for_test — state machine
# ---------------------------------------------------------------------------


def test_filter_events_includes_server_health_metadata() -> None:
    events = parse_log_file(_FIXTURE)
    result = filter_events_for_test(events, test_id="s1-s1-s1-t1")
    assert isinstance(result, FilterResult)
    assert result.server_started is True
    assert result.total_events_in_log == 43


def test_filter_events_for_passing_test_returns_test_events() -> None:
    events = parse_log_file(_FIXTURE)
    result = filter_events_for_test(events, test_id="s1-s1-s1-t1")
    # Should include events inside the t1 start/end window
    event_types = {type(e).__name__ for e in result.events}
    assert "HttpEvent" in event_types
    assert "LoadEvent" in event_types


def test_filter_events_includes_suite_setup_context() -> None:
    # Events before the first start_test belong to suite setup and must be
    # included for any test in that suite.
    events = parse_log_file(_FIXTURE)
    result = filter_events_for_test(events, test_id="s1-s1-s1-t1")
    # start_suite is in setup region; it must appear
    suite_starts = [e for e in result.events if isinstance(e, StartSuiteEvent)]
    assert len(suite_starts) >= 1
    assert suite_starts[0].id == "s1-s1-s1"


def test_filter_events_does_not_include_other_test_events() -> None:
    # Events attributed to t2 must not appear when filtering for t1
    events = parse_log_file(_FIXTURE)
    result = filter_events_for_test(events, test_id="s1-s1-s1-t1")
    test_starts = [e for e in result.events if isinstance(e, StartTestEvent)]
    test_ids = {e.id for e in test_starts}
    assert "s1-s1-s1-t2" not in test_ids


def test_filter_events_for_failing_test_returns_polling_http() -> None:
    events = parse_log_file(_FIXTURE)
    result = filter_events_for_test(events, test_id="s1-s1-s1-t5")
    api_hits = [e for e in result.events if isinstance(e, HttpEvent) and e.url == "/api/get/json"]
    assert len(api_hits) == 4


def test_filter_events_for_failing_test_includes_end_test_with_fail_status() -> None:
    events = parse_log_file(_FIXTURE)
    result = filter_events_for_test(events, test_id="s1-s1-s1-t5")
    end_events = [e for e in result.events if isinstance(e, EndTestEvent) and e.id == "s1-s1-s1-t5"]
    assert len(end_events) == 1
    assert end_events[0].status == "FAIL"


def test_filter_events_unknown_test_id_returns_empty_with_metadata() -> None:
    events = parse_log_file(_FIXTURE)
    result = filter_events_for_test(events, test_id="s1-s1-s1-t99")
    assert result.events == []
    assert result.server_started is True
    assert result.total_events_in_log == 43


# ---------------------------------------------------------------------------
# filter_http_for_test — HTTP events only
# ---------------------------------------------------------------------------


def test_filter_http_returns_only_http_events() -> None:
    events = parse_log_file(_FIXTURE)
    result = filter_http_for_test(events, test_id="s1-s1-s1-t5")
    assert all(isinstance(e, HttpEvent) for e in result.events)


def test_filter_http_includes_server_health_metadata() -> None:
    events = parse_log_file(_FIXTURE)
    result = filter_http_for_test(events, test_id="s1-s1-s1-t5")
    assert result.server_started is True
    assert result.total_events_in_log == 43


def test_filter_http_shows_polling_pattern_for_failing_test() -> None:
    events = parse_log_file(_FIXTURE)
    result = filter_http_for_test(events, test_id="s1-s1-s1-t5")
    api_hits = [e for e in result.events if e.url == "/api/get/json"]
    assert len(api_hits) == 4


def test_filter_http_excludes_non_http_events() -> None:
    events = parse_log_file(_FIXTURE)
    result = filter_http_for_test(events, test_id="s1-s1-s1-t1")
    # LoadEvent and lifecycle events must not appear
    from robotframework_analysis.mcp.app_log.log_parser import LoadEvent

    assert not any(isinstance(e, LoadEvent) for e in result.events)
    assert not any(isinstance(e, StartTestEvent) for e in result.events)
