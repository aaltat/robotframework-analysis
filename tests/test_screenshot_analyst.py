"""Tests for the screenshot analyst agent."""

from __future__ import annotations

import asyncio

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from robotframework_analysis.agent.screenshot_analyst import (
    _SYSTEM_PROMPT,
    build_screenshot_analyst_agent,
)

_CANNED_RESULT = """\
{
  "test_id": "s1-s1-s1-t3",
  "screenshot_text": "Error: Invalid credentials",
  "visible_error": "Invalid credentials",
  "failure_area": "auth",
  "confidence": "high",
  "evidence_source": "ocr",
  "reason": null
}
"""


def test_system_prompt_mentions_get_failure_detail() -> None:
    assert "get_failure_detail" in _SYSTEM_PROMPT


def test_system_prompt_mentions_confidence() -> None:
    assert "confidence" in _SYSTEM_PROMPT


def test_system_prompt_mentions_no_evidence() -> None:
    assert "no_evidence" in _SYSTEM_PROMPT


def test_system_prompt_mentions_evidence_source() -> None:
    assert "evidence_source" in _SYSTEM_PROMPT


def test_system_prompt_mentions_visible_error() -> None:
    assert "visible_error" in _SYSTEM_PROMPT


def test_system_prompt_mentions_failure_area() -> None:
    assert "failure_area" in _SYSTEM_PROMPT


def test_system_prompt_mentions_ocr() -> None:
    assert "ocr" in _SYSTEM_PROMPT.lower()


def test_build_screenshot_analyst_agent_returns_agent() -> None:
    agent = build_screenshot_analyst_agent(model=TestModel())  # type: ignore[arg-type]
    assert isinstance(agent, Agent)


def test_screenshot_analyst_produces_valid_json() -> None:
    agent: Agent[None, str] = Agent(
        model=TestModel(call_tools=[], custom_output_text=_CANNED_RESULT),
        system_prompt=_SYSTEM_PROMPT,
    )
    output = asyncio.run(
        agent.run(
            "Analyse screenshots for test_id=s1-s1-s1-t3 "
            "output_xml=/tmp/output.xml suite_name=MySuite test_name=MyTest "
            'screenshot_paths=["/tmp/sc1.png"].'
        )
    )
    import json

    result = json.loads(output.output)
    assert result["confidence"] == "high"
    assert result["evidence_source"] == "ocr"
    assert result["test_id"] == "s1-s1-s1-t3"
