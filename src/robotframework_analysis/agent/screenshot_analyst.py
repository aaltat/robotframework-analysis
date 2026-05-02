"""Screenshot analyst agent: analyses screenshot evidence for Robot Framework test failures."""

from __future__ import annotations

import logging

from pydantic_ai import Agent
from pydantic_ai.toolsets.fastmcp import FastMCPToolset

from robotframework_analysis.mcp.results.server import mcp as results_mcp

_SYSTEM_PROMPT = """\
You are a screenshot evidence analyst. You receive a failing Robot Framework \
test's ID, suite name, test name, and a list of screenshot paths captured during \
the test run. Your job is to extract visible error evidence from the screenshots \
to help explain why the test failed.

Workflow:
1. You may call get_failure_detail with output_xml, suite_name, and test_name to \
get broader failure context (log messages, keyword tree) that helps interpret \
what the screenshot shows.
2. For each screenshot path, the OCR text will be provided to you in the prompt. \
Analyse the text to find visible error messages on screen.
3. Determine whether the OCR-extracted text matches or explains the RF failure.

Output format — return a single JSON object, nothing else:
{
  "test_id": "<test_id>",
  "screenshot_text": "<raw OCR text or null>",
  "visible_error": "<short extracted error message visible on screen or null>",
  "failure_area": "auth" | "navigation" | "validation" | "network" | "dialog" | "unknown",
  "confidence": "high" | "medium" | "low" | "no_evidence",
  "evidence_source": "ocr" | "multimodal" | "none",
  "reason": "<no_screenshots | screenshot_unreadable | null>"
}

Confidence rules:
- confidence is "high" when OCR text contains a visible error matching the RF \
failure message or a known error keyword: error, failed, invalid, denied, timeout.
- confidence is "medium" when OCR text is present and plausible but does not \
directly match the RF failure (e.g. a generic dialog is visible).
- confidence is "low" when OCR quality passed threshold but no clear failure \
signal is found in the text.
- confidence is "no_evidence" when no screenshots are available, the image is \
unreadable, or OCR quality is below threshold with no fallback.

Rules:
- Do not guess a root cause when confidence is no_evidence.
- Do not add commentary outside the JSON object.
- reason is null when confidence is not no_evidence.
"""

logger = logging.getLogger("rf_analyst_screenshot_analyst_agent")


def build_screenshot_analyst_agent(model: str = "ollama:gemma4:e4b") -> Agent[None, str]:
    """Create and return the screenshot analyst agent with the given model."""
    server = FastMCPToolset(results_mcp)
    return Agent(
        model,
        system_prompt=_SYSTEM_PROMPT,
        toolsets=[server],
    )
