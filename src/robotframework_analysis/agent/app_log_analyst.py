"""App log analyst agent: analyses Browser library test-app failures via the app log MCP server."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent, RunContext

from robotframework_analysis.mcp.app_log.server import (
    get_app_log_events_for_test as _mcp_get_events,
)
from robotframework_analysis.mcp.app_log.server import (
    get_app_log_http_for_test as _mcp_get_http,
)


@dataclass
class AppLogAnalystContext:
    """Log file path injected as agent dependencies — never passed through the LLM."""

    log_file: str


_SYSTEM_PROMPT = """\
You are an app-level failure analyst. You receive a failing Robot Framework \
test's ID. Your job is to find the server-side HTTP evidence for why the test \
failed.

Workflow:
1. Call get_app_log_http_for_test with the test_id to inspect HTTP traffic \
during the test.
2. If the HTTP pattern is suspicious (polling, 4xx/5xx responses, slow \
response times), that is your primary evidence.
3. If you need fuller context (page loads, clicks, RF lifecycle events), call \
get_app_log_events_for_test.

Output format — return a single JSON object, nothing else:
{
  "test_id": "<test_id>",
  "http_pattern": "<polling | single_request | no_requests | null>",
  "endpoint": "<most relevant URL path or null>",
  "confidence": "high" | "medium" | "low" | "no_evidence",
  "summary": "<one-sentence description of the HTTP evidence, or null>"
}

Rules:
- confidence is "high" when repeated requests to the same endpoint are found \
and the test failed (polling timeout pattern).
- confidence is "high" when a 4xx or 5xx HTTP status is found for the test.
- confidence is "medium" when slow response times are found but status is 2xx.
- confidence is "low" when HTTP events exist but no obvious failure indicator.
- confidence is "no_evidence" when no HTTP events are attributed to the test \
or server_started is false.
- Do not add commentary outside the JSON object.
- The log file path is pre-configured — do NOT pass a log_file argument to any tool.
"""

logger = logging.getLogger("rf_analyst_app_log_analyst_agent")


def build_app_log_analyst_agent(
    model: str = "ollama:gemma4:e4b",
) -> Agent[AppLogAnalystContext, str]:
    """Create and return the app log analyst agent with the given model."""
    agent: Agent[AppLogAnalystContext, str] = Agent(
        model,
        system_prompt=_SYSTEM_PROMPT,
        deps_type=AppLogAnalystContext,
    )

    @agent.tool
    def get_app_log_http_for_test(
        ctx: RunContext[AppLogAnalystContext],
        test_id: str,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        """Return HTTP events from the app log attributed to test_id."""
        return _mcp_get_http(ctx.deps.log_file, test_id, start_time, end_time)

    @agent.tool
    def get_app_log_events_for_test(
        ctx: RunContext[AppLogAnalystContext],
        test_id: str,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        """Return all app log events attributed to test_id."""
        return _mcp_get_events(ctx.deps.log_file, test_id, start_time, end_time)

    return agent
