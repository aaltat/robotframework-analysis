"""Failure analyst agent: analyses Robot Framework test failures via the MCP server."""

from __future__ import annotations

import logging
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
3. Check the screenshot_paths field in the get_failure_detail response. \
If it is non-empty, you MUST call get_screenshot_analysis for every path in that \
list before proceeding. Do not skip this step.
4. Identify root causes and common patterns across failure groups.
5. Produce a clear, structured report covering:
   - How many tests failed and in how many error groups
   - The root cause of each group with evidence from the logs and keyword tree
   - Specific, actionable suggestions for fixing each group
"""

logger = logging.getLogger("failure_analyst_agent")


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
        model: Override the default ``ollama:gemma4:e4b`` model.  Accepts any
            pydantic-ai model or known model name string.  Pass a
            ``TestModel`` instance for deterministic testing.
    """
    resolved_model = model or "ollama:gemma4:e4b"
    server = MCPServerStdio(
        sys.executable,
        ["-m", "robotframework_analysis.mcp.results.server"],
    )
    summary_agent: Agent[None, str] = Agent(
        resolved_model,
        system_prompt=_SYSTEM_PROMPT,
        toolsets=[server],
    )
    async with server:
        result = await summary_agent.run(
            f"Analyze the Robot Framework test results in: {output_xml}"
        )
    return result.output


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Analyse Robot Framework test failures.")
    parser.add_argument("output_xml", help="Path to the Robot Framework output.xml file")
    parser.add_argument("--model", default="ollama:gemma4:e4b", help="Override the default model")
    args = parser.parse_args()

    analysis = asyncio.run(analyze_failures(args.output_xml, model=args.model))
    print(analysis)
