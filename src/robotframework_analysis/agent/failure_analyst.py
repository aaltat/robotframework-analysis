"""Failure analyst agent: analyses Robot Framework test failures via the MCP server."""

from __future__ import annotations

import logging

from pydantic_ai import Agent
from pydantic_ai.toolsets.fastmcp import FastMCPToolset

from robotframework_analysis.mcp.results.server import mcp as results_mcp

_SYSTEM_PROMPT = """\
You are a Robot Framework test failure analyst. Analyse test failures from a \
Robot Framework output.xml and return a concise, structured JSON report.

Workflow:
1. Call get_test_run_summary with the provided output.xml path.
2. For each error group, call get_failure_detail for the representative test.
3. Identify root causes from the log messages and keyword call tree.

Output format — return a single JSON object, nothing else:
{
  "total_failed": <int>,
  "error_groups": [
    {
      "group_id": <int>,
      "error_pattern": "<short pattern>",
      "affected_tests": <int>,
      "representative_test": "<suite_name> / <test_name>",
      "test_id": "<test_id from get_failure_detail, e.g. s1-s1-s1-t8>",
      "test_start_time": "<start_time from get_failure_detail>",
      "test_end_time": "<end_time from get_failure_detail>",
      "failure_time": "<timestamp of last log message before failure>",
      "root_cause": "<one sentence>",
      "evidence": "<key log line or keyword that proves it>",
      "suggested_fix": "<one sentence>",
      "screenshot_paths": ["<path>", ...]
    }
  ]
}

Rules:
- root_cause and suggested_fix must each fit in one sentence.
- screenshot_paths must be copied verbatim from the get_failure_detail response.
- Do not include passing tests or skip reasons.
- Do not add commentary outside the JSON object.
"""

logger = logging.getLogger("rf_analyst_failure_analyst_agent")


def build_analysis_agent(model: str = "ollama:gemma4:e4b") -> Agent[None, str]:
    """Create and return the failure analyst agent with the given model."""
    server = FastMCPToolset(results_mcp)
    return Agent(
        model,
        system_prompt=_SYSTEM_PROMPT,
        toolsets=[server],
    )
