"""Failure analyst agent: analyses Robot Framework test failures via the MCP server."""

from __future__ import annotations

import sys
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio

_SYSTEM_PROMPT = """\
You are a Robot Framework test failure analyst. Your job is to analyse test \
failures from a Robot Framework output.xml file and produce a concise, actionable \
report for the development team.

Workflow:
1. Call get_test_run_summary with the provided output.xml path to get an overview \
of all failures grouped by error pattern.
2. For each failure group that needs deeper investigation, call get_failure_detail \
to retrieve the full log messages and keyword call tree for one representative test.
3. Identify root causes and common patterns across failure groups.
4. Produce a clear, structured report covering:
   - How many tests failed and in how many error groups
   - The root cause of each group with evidence from the logs and keyword tree
   - Specific, actionable suggestions for fixing each group
"""


async def analyze_failures(
    output_xml: str,
    *,
    model: Any = None,
) -> str:
    """Analyse Robot Framework test failures using the MCP server.

    Starts an MCP server subprocess, runs the failure analyst agent against
    *output_xml*, and returns the resulting analysis as a plain string.

    Args:
        output_xml: Absolute or cwd-relative path to the Robot Framework
            ``output.xml`` produced by a test run.
        model: Override the default ``openai:gpt-4o`` model.  Accepts any
            pydantic-ai model or known model name string.  Pass a
            ``TestModel`` instance for deterministic testing.
    """
    server = MCPServerStdio(
        sys.executable,
        ["-m", "robotframework_analysis.mcp.results.server"],
    )
    agent: Agent[None, str] = Agent(
        model or "openai:gpt-4o",
        system_prompt=_SYSTEM_PROMPT,
        toolsets=[server],
    )
    async with server:
        result = await agent.run(f"Analyze the Robot Framework test results in: {output_xml}")
    return result.output
