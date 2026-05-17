"""Tests for the app log MCP server tools."""

from __future__ import annotations

from pathlib import Path

from approvaltests import verify_as_json

from robotframework_analysis.mcp.app_log.server import (
    _LogCache,
    get_app_log_events_for_test,
    get_app_log_http_for_test,
)

_FIXTURE = str(Path(__file__).parent / "fixtures" / "app-log-slice.log")
_TEST_ID = "s1-s1-s1-t5"


# ---------------------------------------------------------------------------
# get_app_log_http_for_test
# ---------------------------------------------------------------------------


def test_get_http_returns_only_http_dicts() -> None:
    result = get_app_log_http_for_test(_FIXTURE, _TEST_ID)
    assert result["server_started"] is True
    assert result["total_events_in_log"] == 43
    for item in result["events"]:
        assert item["event"] == "http"


def test_get_http_shows_polling_for_failing_test() -> None:
    result = get_app_log_http_for_test(_FIXTURE, _TEST_ID)
    api_hits = [e for e in result["events"] if e["url"] == "/api/get/json"]
    assert len(api_hits) == 4


def test_get_http_approval() -> None:
    result = get_app_log_http_for_test(_FIXTURE, _TEST_ID)
    verify_as_json(result)


# ---------------------------------------------------------------------------
# get_app_log_events_for_test
# ---------------------------------------------------------------------------


def test_get_events_includes_all_event_types() -> None:
    result = get_app_log_events_for_test(_FIXTURE, _TEST_ID)
    event_kinds = {e["event"] for e in result["events"]}
    assert "http" in event_kinds
    assert "load" in event_kinds
    assert "start_test" in event_kinds
    assert "end_test" in event_kinds


def test_get_events_server_not_started_on_empty_log(tmp_path: Path) -> None:
    empty_log = tmp_path / "empty.log"
    empty_log.write_text("")
    result = get_app_log_events_for_test(str(empty_log), "s1-s1-s1-t1")
    assert result["server_started"] is False
    assert result["total_events_in_log"] == 0
    assert result["events"] == []


def test_get_events_approval() -> None:
    result = get_app_log_events_for_test(_FIXTURE, _TEST_ID)
    verify_as_json(result)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def test_cache_returns_same_list_on_second_call() -> None:
    cache = _LogCache()
    first = cache.get(_FIXTURE)
    second = cache.get(_FIXTURE)
    assert first is second


def test_cache_evicts_on_file_change(tmp_path: Path) -> None:
    import time

    log = tmp_path / "test.log"
    log.write_text(
        '{"timestamp":"2026-05-11T19:26:51.485Z","event":"server_start","url":"http://localhost:1"}\n'
    )
    cache = _LogCache()
    first = cache.get(str(log))

    time.sleep(0.01)
    log.write_text(
        '{"timestamp":"2026-05-11T19:26:51.485Z","event":"server_start","url":"http://localhost:2"}\n'
    )
    # Touch mtime
    log.touch()
    second = cache.get(str(log))
    assert first is not second
