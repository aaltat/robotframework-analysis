"""Tests for the Playwright log analyst agent."""

from __future__ import annotations

import asyncio
from pathlib import Path

from approvaltests import settings, verify
from approvaltests.core.options import Options
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from robotframework_analysis.agent.playwright_log_analyst import (
    _SYSTEM_PROMPT,
    build_playwright_analyst_agent,
)

_FIXTURE_LOG = str(Path(__file__).parent / "fixtures" / "playwright-log-slice.txt")

_CANNED_RESULT = """\
{
  "test_id": "s1-s1-s1-t3",
  "playwright_error_type": "Error",
  "playwright_action": "savePageAsPdf",
  "playwright_error_summary": "page.pdf: Failed to parse parameter value: other",
  "confidence": "high",
  "evidence": "seq 127 grpc_error Error: page.pdf: Failed to parse parameter value: other"
}
"""


def test_system_prompt_mentions_get_playwright_errors_for_test() -> None:
    assert "get_playwright_errors_for_test" in _SYSTEM_PROMPT


def test_system_prompt_mentions_get_playwright_events_for_test() -> None:
    assert "get_playwright_events_for_test" in _SYSTEM_PROMPT


def test_system_prompt_mentions_confidence() -> None:
    assert "confidence" in _SYSTEM_PROMPT


def test_system_prompt_mentions_no_evidence() -> None:
    assert "no_evidence" in _SYSTEM_PROMPT


def test_analyze_playwright_failures_approval() -> None:
    settings().allow_multiple_verify_calls_for_this_method()

    test_agent: Agent[None, str] = Agent(
        model=TestModel(call_tools=[], custom_output_text=_CANNED_RESULT),
        system_prompt=_SYSTEM_PROMPT,
    )
    output = asyncio.run(
        test_agent.run(
            f"Analyse browser failures for test_id=s1-s1-s1-t3 "
            f"in log_file={_FIXTURE_LOG} "
            f"window=[2026-04-30T18:07:24.149Z, 2026-04-30T18:07:24.200Z]."
        )
    )

    verify(output.output, options=Options().for_file.with_extension(".txt"))


def test_build_playwright_analyst_agent_returns_agent() -> None:
    from pydantic_ai.models.test import TestModel

    agent = build_playwright_analyst_agent(model=TestModel())  # type: ignore[arg-type]
    assert isinstance(agent, Agent)
