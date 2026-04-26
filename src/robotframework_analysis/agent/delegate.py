import logging

from pydantic_ai import Agent, RunContext

from robotframework_analysis.agent.failure_analyst import build_agent

_SYSTEM_PROMPT = """\
You are a Robot Framework test failure analyst. Your job is delegate the analysis
of test failures to a specialized agents that can process Robot Framework output.xml file.
Use `analyze_failures` to parse output.xml.
Based in the
information retrieved from the different agents, you should identify root causes
and common patterns across failure groups and produce concise, actionable reports
and provide actions for the problems. Your reports should be clear and actionable
for the development team.

You will not do the analysis yourself, but delegate it to specialized agents.
"""

logger = logging.getLogger("rf_analyst_orchestrator_agent")

delegate_agent = Agent(
    "ollama:gemma4:e4b",
    system_prompt=_SYSTEM_PROMPT,
)


@delegate_agent.tool
async def analyze_failures(_ctx: RunContext, output_xml: str) -> str:
    """Analyse test result from Robot Framework output.xml file.

    Args:
        output_xml: Absolute or cwd-relative path to the Robot Framework
            ``output.xml`` produced by a test run.
    """
    logger.info("analyze_failures called: output_xml=%s", output_xml)
    agent = build_agent()
    result = await agent.run(f"Analyze the Robot Framework test results from: {output_xml}")
    return result.output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the Robot Framework failure analysis agent.")
    parser.add_argument(
        "output_xml", help="Path to the Robot Framework output.xml file to analyze."
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting failure analysis for: %s", args.output_xml)
    result = delegate_agent.run_sync(
        f"Analyze the Robot Framework test results from: {args.output_xml}"
    )
    print(result.output)
