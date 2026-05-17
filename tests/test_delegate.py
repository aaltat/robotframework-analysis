"""Tests for the orchestrator delegate agent tools."""

from __future__ import annotations

import asyncio
import json

from robotframework_analysis.agent.delegate import (
    _SYSTEM_PROMPT,
    DelegateContext,
    analyze_app_log_failures,
    analyze_playwright_failures,
    analyze_screenshot_failures,
)


def _make_mock_ctx(
    output_xml: str = "/tmp/output.xml",
    playwright_log: str | None = "playwright-log.txt",
    app_log: str | None = "/tmp/test-app.log",
) -> object:
    """Return a minimal stand-in for RunContext with pre-configured deps."""

    class _Ctx:
        deps = DelegateContext(
            output_xml=output_xml,
            playwright_log=playwright_log,
            app_log=app_log,
        )

    return _Ctx()


def _rf_report(groups: list[dict[str, object]]) -> str:
    return json.dumps({"total_failed": len(groups), "error_groups": groups})


# ---------------------------------------------------------------------------
# System-prompt contract tests
# ---------------------------------------------------------------------------


def test_system_prompt_mentions_analyze_failures() -> None:
    assert "analyze_failures" in _SYSTEM_PROMPT


def test_system_prompt_mentions_analyze_playwright_failures() -> None:
    assert "analyze_playwright_failures" in _SYSTEM_PROMPT


def test_system_prompt_mentions_analyze_screenshot_failures() -> None:
    assert "analyze_screenshot_failures" in _SYSTEM_PROMPT


def test_system_prompt_no_file_path_instructions() -> None:
    """System prompt must tell the LLM not to pass file paths to tools."""
    assert "pre-configured" in _SYSTEM_PROMPT


def test_system_prompt_mentions_confidence() -> None:
    assert "confidence" in _SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# analyze_playwright_failures — missing test_id handling
# ---------------------------------------------------------------------------


def test_analyze_playwright_failures_returns_empty_when_no_log_configured() -> None:
    """When no playwright log is in deps, return '[]' without calling LLM."""
    result_json = asyncio.run(
        analyze_playwright_failures(_make_mock_ctx(playwright_log=None), _rf_report([]))  # type: ignore[arg-type]
    )
    assert result_json == "[]"


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
        analyze_playwright_failures(_make_mock_ctx(), _rf_report(groups))  # type: ignore[arg-type]
    )
    results = json.loads(result_json)
    item = json.loads(results[0])
    assert item["confidence"] == "no_evidence"
    assert item["test_id"] is None


def test_analyze_playwright_failures_returns_empty_on_bad_json() -> None:
    result_json = asyncio.run(
        analyze_playwright_failures(_make_mock_ctx(), "not json")  # type: ignore[arg-type]
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
        analyze_playwright_failures(_make_mock_ctx(), _rf_report(groups))  # type: ignore[arg-type]
    )
    results = json.loads(result_json)
    assert results == []


# ---------------------------------------------------------------------------
# analyze_screenshot_failures — skip and routing logic
# ---------------------------------------------------------------------------


def test_analyze_screenshot_failures_skips_group_when_no_screenshots() -> None:
    """A group with empty screenshot_paths list must be skipped."""
    groups = [
        {
            "group_id": 1,
            "test_id": "s1-t1",
            "representative_test": "Suite / Test",
            "suite_name": "Suite",
            "test_name": "Test",
            "screenshot_paths": [],
        }
    ]
    result_json = asyncio.run(
        analyze_screenshot_failures(_make_mock_ctx(), _rf_report(groups))  # type: ignore[arg-type]
    )
    results = json.loads(result_json)
    assert len(results) == 1
    item = json.loads(results[0])
    assert item["confidence"] == "no_evidence"
    assert item["reason"] == "no_screenshots"
    assert item["test_id"] is None


def test_analyze_screenshot_failures_skips_group_when_screenshots_key_missing() -> None:
    """A group without screenshot_paths key is treated as no screenshots."""
    groups = [
        {
            "group_id": 1,
            "test_id": "s1-t1",
            "representative_test": "Suite / Test",
            "suite_name": "Suite",
            "test_name": "Test",
            # no screenshot_paths key
        }
    ]
    result_json = asyncio.run(
        analyze_screenshot_failures(_make_mock_ctx(), _rf_report(groups))  # type: ignore[arg-type]
    )
    results = json.loads(result_json)
    item = json.loads(results[0])
    assert item["confidence"] == "no_evidence"
    assert item["reason"] == "no_screenshots"


def test_analyze_screenshot_failures_returns_empty_on_bad_json() -> None:
    result_json = asyncio.run(
        analyze_screenshot_failures(_make_mock_ctx(), "not json")  # type: ignore[arg-type]
    )
    assert result_json == "[]"


def test_system_prompt_mentions_analyze_app_log_failures() -> None:
    assert "analyze_app_log_failures" in _SYSTEM_PROMPT


def test_analyze_app_log_failures_skips_group_when_test_id_missing() -> None:
    """A group without test_id must produce a no_evidence entry."""
    groups = [
        {
            "group_id": 1,
            "representative_test": "Suite / Some Test",
            # no test_id key
        }
    ]
    result_json = asyncio.run(
        analyze_app_log_failures(_make_mock_ctx(), _rf_report(groups))  # type: ignore[arg-type]
    )
    results = json.loads(result_json)
    assert len(results) == 1
    item = json.loads(results[0])
    assert item["confidence"] == "no_evidence"
    assert item["test_id"] is None


def test_analyze_app_log_failures_returns_empty_on_bad_json() -> None:
    result_json = asyncio.run(
        analyze_app_log_failures(_make_mock_ctx(), "not json")  # type: ignore[arg-type]
    )
    assert result_json == "[]"


def test_analyze_app_log_failures_returns_empty_when_no_log_configured() -> None:
    """When no app log is in deps, return '[]' without calling LLM."""
    result_json = asyncio.run(
        analyze_app_log_failures(_make_mock_ctx(app_log=None), _rf_report([]))  # type: ignore[arg-type]
    )
    assert result_json == "[]"
