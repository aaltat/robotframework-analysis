"""Playwright log analyst agent: analyses browser-level failures via the Playwright MCP server."""

from __future__ import annotations

import logging

from pydantic_ai import Agent
from pydantic_ai.toolsets.fastmcp import FastMCPToolset

from robotframework_analysis.mcp.playwright.server import mcp as playwright_mcp

_SYSTEM_PROMPT = """\
You are a browser-level failure analyst. You receive a failing Robot Framework \
test's ID, time window, and the path to its Playwright log file. Your job is to \
find the browser-side evidence for why the test failed.

Workflow:
1. Call get_playwright_errors_for_test with the provided log_file, test_id, \
start_time, and end_time.
2. If errors are found, that is your primary evidence.
3. If you need more context, call get_playwright_events_for_test to inspect the \
surrounding events.

Output format — return a single JSON object, nothing else:
{
  "test_id": "<test_id>",
  "playwright_error_type": "<error_type or null>",
  "playwright_action": "<failing browser action or null>",
  "playwright_error_summary": "<first line of error msg or null>",
  "confidence": "high" | "medium" | "low" | "no_evidence",
  "evidence": "<seq number and key phrase that proves it, or null>"
}

Rules:
- confidence is "high" when a grpc_error with a matching test_id is found.
- confidence is "medium" when only a no-context error is found in the time window.
- confidence is "low" when no errors are found but suspicious events exist.
- confidence is "no_evidence" when nothing relevant is in the log.
- Do not add commentary outside the JSON object.
"""

logger = logging.getLogger("rf_analyst_playwright_log_analyst_agent")


def build_playwright_analyst_agent(model: str = "ollama:gemma4:e4b") -> Agent[None, str]:
    """Create and return the Playwright log analyst agent with the given model."""
    server = FastMCPToolset(playwright_mcp)
    return Agent(
        model,
        system_prompt=_SYSTEM_PROMPT,
        toolsets=[server],
    )
