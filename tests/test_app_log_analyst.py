"""Tests for the app log analyst agent."""

from __future__ import annotations

import asyncio

from approvaltests import settings, verify
from approvaltests.core.options import Options
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from robotframework_analysis.agent.app_log_analyst import (
    _SYSTEM_PROMPT,
    build_app_log_analyst_agent,
)

_CANNED_RESULT = """\
{
  "test_id": "s1-s1-s1-t5",
  "http_pattern": "polling",
  "endpoint": "/api/get/json",
  "confidence": "high",
  "summary": "Test polled GET /api/get/json 4 times. Final response was 503."
}
"""


def test_system_prompt_mentions_get_app_log_http_for_test() -> None:
    assert "get_app_log_http_for_test" in _SYSTEM_PROMPT


def test_system_prompt_mentions_get_app_log_events_for_test() -> None:
    assert "get_app_log_events_for_test" in _SYSTEM_PROMPT


def test_system_prompt_mentions_confidence() -> None:
    assert "confidence" in _SYSTEM_PROMPT


def test_system_prompt_mentions_no_evidence() -> None:
    assert "no_evidence" in _SYSTEM_PROMPT


def test_analyze_app_log_failures_approval() -> None:
    settings().allow_multiple_verify_calls_for_this_method()

    test_agent: Agent[None, str] = Agent(
        model=TestModel(call_tools=[], custom_output_text=_CANNED_RESULT),
        system_prompt=_SYSTEM_PROMPT,
    )
    output = asyncio.run(
        test_agent.run(
            "Analyse app-level failures for test_id=s1-s1-s1-t5 in log_file=/tmp/test-app.log."
        )
    )

    verify(output.output, options=Options().for_file.with_extension(".txt"))


def test_build_app_log_analyst_agent_returns_agent() -> None:
    agent = build_app_log_analyst_agent(model=TestModel())  # type: ignore[arg-type]
    assert isinstance(agent, Agent)
