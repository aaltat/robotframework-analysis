"""Playwright log analyst agent: analyses browser-level failures via the Playwright MCP server."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

from robotframework_analysis.mcp.playwright.server import (
    PlaywrightErrorItem,
    PlaywrightEventItem,
)
from robotframework_analysis.mcp.playwright.server import (
    get_playwright_errors_for_test as _mcp_get_errors,
)
from robotframework_analysis.mcp.playwright.server import (
    get_playwright_events_for_test as _mcp_get_events,
)


@dataclass
class PlaywrightAnalystContext:
    """Log file path injected as agent dependencies — never passed through the LLM."""

    log_file: str


_SYSTEM_PROMPT = """\
You are a browser-level failure analyst. You receive a failing Robot Framework \
test's ID and time window. Your job is to find the browser-side evidence for \
why the test failed.

Workflow:
1. Call get_playwright_errors_for_test with the test_id, start_time, and end_time.
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
- The log file path is pre-configured — do NOT pass a log_file argument to any tool.
"""

logger = logging.getLogger("rf_analyst_playwright_log_analyst_agent")


def build_playwright_analyst_agent(
    model: str = "ollama:gemma4:e4b",
) -> Agent[PlaywrightAnalystContext, str]:
    """Create and return the Playwright log analyst agent with the given model."""
    agent: Agent[PlaywrightAnalystContext, str] = Agent(
        model,
        system_prompt=_SYSTEM_PROMPT,
        deps_type=PlaywrightAnalystContext,
    )

    @agent.tool
    def get_playwright_errors_for_test(
        ctx: RunContext[PlaywrightAnalystContext],
        test_id: str,
        start_time: str,
        end_time: str,
    ) -> list[PlaywrightErrorItem]:
        """Return error events from the playwright log for the given test window."""
        return _mcp_get_errors(ctx.deps.log_file, test_id, start_time, end_time)

    @agent.tool
    def get_playwright_events_for_test(
        ctx: RunContext[PlaywrightAnalystContext],
        test_id: str,
        start_time: str,
        end_time: str,
    ) -> list[PlaywrightEventItem]:
        """Return all events from the playwright log for the given test window."""
        return _mcp_get_events(ctx.deps.log_file, test_id, start_time, end_time)

    return agent
