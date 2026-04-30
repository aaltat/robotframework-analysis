"""Tests for the orchestrator delegate agent tools."""

from __future__ import annotations

import asyncio
import json

from robotframework_analysis.agent.delegate import _SYSTEM_PROMPT, analyze_playwright_failures


def _make_mock_ctx() -> object:
    """Return a minimal stand-in for RunContext (not used by the function)."""
    return object()


def _rf_report(groups: list[dict]) -> str:
    return json.dumps({"total_failed": len(groups), "error_groups": groups})


# ---------------------------------------------------------------------------
# System-prompt contract tests
# ---------------------------------------------------------------------------


def test_system_prompt_mentions_analyze_failures() -> None:
    assert "analyze_failures" in _SYSTEM_PROMPT


def test_system_prompt_mentions_analyze_playwright_failures() -> None:
    assert "analyze_playwright_failures" in _SYSTEM_PROMPT


def test_system_prompt_mentions_confidence() -> None:
    assert "confidence" in _SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# analyze_playwright_failures — missing test_id handling
# ---------------------------------------------------------------------------


def test_analyze_playwright_failures_skips_group_when_test_id_missing() -> None:
    """A group without test_id must NOT fall back to representative_test."""
    groups = [
        {
            "group_id": 1,
            "representative_test": "Suite / Some Test",
            # no test_id key
            "test_start_time": "2026-04-30T18:07:29.071",
            "test_end_time": "2026-04-30T18:07:29.740",
        }
    ]
    result_json = asyncio.run(
        analyze_playwright_failures(_make_mock_ctx(), "playwright-log.txt", _rf_report(groups))  # type: ignore[arg-type]
    )
    results = json.loads(result_json)
    assert len(results) == 1
    item = json.loads(results[0])
    assert item["confidence"] == "no_evidence"
    assert item["test_id"] is None


def test_analyze_playwright_failures_skips_group_when_test_id_empty_string() -> None:
    """An empty-string test_id is treated the same as missing."""
    groups = [
        {
            "group_id": 1,
            "representative_test": "Suite / Some Test",
            "test_id": "",
            "test_start_time": "2026-04-30T18:07:29.071",
            "test_end_time": "2026-04-30T18:07:29.740",
        }
    ]
    result_json = asyncio.run(
        analyze_playwright_failures(_make_mock_ctx(), "playwright-log.txt", _rf_report(groups))  # type: ignore[arg-type]
    )
    results = json.loads(result_json)
    item = json.loads(results[0])
    assert item["confidence"] == "no_evidence"
    assert item["test_id"] is None


def test_analyze_playwright_failures_returns_empty_on_bad_json() -> None:
    result_json = asyncio.run(
        analyze_playwright_failures(_make_mock_ctx(), "playwright-log.txt", "not json")  # type: ignore[arg-type]
    )
    assert result_json == "[]"


def test_analyze_playwright_failures_skips_group_when_times_missing() -> None:
    """Groups with test_id but no time window are silently skipped."""
    groups = [
        {
            "group_id": 1,
            "test_id": "s1-t1",
            # no start/end times
        }
    ]
    result_json = asyncio.run(
        analyze_playwright_failures(_make_mock_ctx(), "playwright-log.txt", _rf_report(groups))  # type: ignore[arg-type]
    )
    results = json.loads(result_json)
    assert results == []
