"""Tests for the Playwright log MCP server tools."""

from __future__ import annotations

from pathlib import Path

import pytest
from approvaltests import verify_as_json

from robotframework_analysis.mcp.playwright.server import (
    _LogCache,
    get_playwright_errors_for_test,
    get_playwright_events_for_test,
)

_FIXTURE = str(Path(__file__).parent / "fixtures" / "playwright-log-slice.txt")

_TEST_ID = "s1-s1-s1-t3"
_START = "2026-04-30T18:07:24.149Z"
_END = "2026-04-30T18:07:24.200Z"

# ---------------------------------------------------------------------------
# get_playwright_events_for_test
# ---------------------------------------------------------------------------


def test_get_events_returns_events_in_window() -> None:
    items = get_playwright_events_for_test(_FIXTURE, _TEST_ID, _START, _END)
    assert len(items) > 0
    # All events must be within the window
    for item in items:
        assert item.time >= "2026-04-30T18:07:24.149"
        assert item.time <= "2026-04-30T18:07:24.200"


def test_get_events_excludes_different_test_id() -> None:
    items = get_playwright_events_for_test(_FIXTURE, _TEST_ID, _START, _END)
    for item in items:
        if item.test_id is not None:
            assert item.test_id == _TEST_ID


def test_get_events_includes_pwapi_lines() -> None:
    items = get_playwright_events_for_test(_FIXTURE, _TEST_ID, _START, _END)
    pwapi = [i for i in items if i.type == "pwapi"]
    assert len(pwapi) >= 2


def test_get_events_approval() -> None:
    items = get_playwright_events_for_test(_FIXTURE, _TEST_ID, _START, _END)
    verify_as_json([i.model_dump(exclude_none=True) for i in items])


# ---------------------------------------------------------------------------
# get_playwright_errors_for_test
# ---------------------------------------------------------------------------


def test_get_errors_returns_only_errors() -> None:
    errors = get_playwright_errors_for_test(_FIXTURE, _TEST_ID, _START, _END)
    assert len(errors) == 1
    assert errors[0].error_type == "Error"
    assert "page.pdf" in errors[0].msg
    assert errors[0].test_id == _TEST_ID


def test_get_errors_wide_window_includes_no_context_error() -> None:
    errors = get_playwright_errors_for_test(
        _FIXTURE, _TEST_ID, _START, "2026-04-30T18:07:25.100Z"
    )
    seqs = {e.seq for e in errors}
    assert 127 in seqs
    assert 252 in seqs


def test_get_errors_approval() -> None:
    errors = get_playwright_errors_for_test(_FIXTURE, _TEST_ID, _START, _END)
    verify_as_json([e.model_dump(exclude_none=True) for e in errors])


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def test_cache_returns_same_list_on_second_call() -> None:
    cache = _LogCache()
    first = cache.get(_FIXTURE)
    second = cache.get(_FIXTURE)
    assert first is second


def test_cache_raises_for_missing_file() -> None:
    cache = _LogCache()
    with pytest.raises(FileNotFoundError):
        cache.get("/nonexistent/playwright-log.txt")
