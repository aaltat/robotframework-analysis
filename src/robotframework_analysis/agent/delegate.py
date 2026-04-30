import json
import logging

from pydantic_ai import Agent, RunContext

from robotframework_analysis.agent.failure_analyst import build_analysis_agent
from robotframework_analysis.agent.playwright_log_analyst import build_playwright_analyst_agent

_SYSTEM_PROMPT = """\
You are a Robot Framework test failure analyst. Delegate analysis to specialized \
agents and synthesize their findings into a single report.

Workflow:
1. Call `analyze_failures` with the output.xml path to get RF-level error groups.
   Each group includes test_id, test_start_time, and test_end_time.
2. If a playwright_log_file path is provided, call `analyze_playwright_failures`
   with that path and the JSON from step 1 to get browser-level evidence for
   each group.
3. Merge the two reports: for each error group, combine the RF root cause with
   the browser evidence (if any) and produce a concise, actionable summary.

For each error group in the final report:
- State the RF root cause and the Playwright evidence side-by-side.
- Include the evidence confidence (high/medium/low/no_evidence) from the \
Playwright report.
- Only include Playwright-based recommendations when confidence is high or medium.
- When confidence is low or no_evidence, say so explicitly rather than guessing.

Your final report should be clear and actionable for the development team.
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
    agent = build_analysis_agent()
    result = await agent.run(f"Analyze the Robot Framework test results from: {output_xml}")
    return result.output


@delegate_agent.tool
async def analyze_playwright_failures(
    _ctx: RunContext,
    playwright_log_file: str,
    rf_error_groups_json: str,
) -> str:
    """Analyse browser-level evidence for each RF error group.

    Calls the Playwright log analyst for each error group and returns a JSON
    list of per-group browser findings.

    Args:
        playwright_log_file: Absolute or cwd-relative path to the
            playwright-log-*.txt file from the same test run.
        rf_error_groups_json: The full JSON string returned by
            ``analyze_failures``, containing error groups with
            ``test_id``, ``test_start_time``, and ``test_end_time``.
    """
    logger.info(
        "analyze_playwright_failures called: log_file=%s", playwright_log_file
    )
    try:
        rf_report = json.loads(rf_error_groups_json)
        groups = rf_report.get("error_groups", [])
    except (json.JSONDecodeError, AttributeError):
        logger.warning("analyze_playwright_failures: could not parse rf_error_groups_json")
        return "[]"

    agent = build_playwright_analyst_agent()
    results = []
    for group in groups:
        test_id = group.get("test_id", "")
        start_time = group.get("test_start_time", "")
        end_time = group.get("test_end_time", "")
        representative = group.get("representative_test", f"group {group.get('group_id', '?')}")
        if not test_id:
            logger.warning(
                "analyze_playwright_failures: skipping group '%s' — test_id missing in RF report",
                representative,
            )
            results.append(
                json.dumps({
                    "test_id": None,
                    "confidence": "no_evidence",
                    "playwright_error_summary": "Skipped: test_id not available in RF report",
                })
            )
            continue
        if not (start_time and end_time):
            logger.warning(
                "analyze_playwright_failures: skipping group '%s' — time window missing",
                representative,
            )
            continue
        logger.info(
            "analyze_playwright_failures: analysing %s (test_id=%s) window=[%s, %s]",
            representative,
            test_id,
            start_time,
            end_time,
        )
        prompt = (
            f"Analyse browser failures for test_id={test_id} "
            f"in log_file={playwright_log_file} "
            f"window=[{start_time}, {end_time}]."
        )
        group_result = await agent.run(prompt)
        results.append(group_result.output)

    return json.dumps(results)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the Robot Framework failure analysis agent.")
    parser.add_argument(
        "output_xml", help="Path to the Robot Framework output.xml file to analyze."
    )
    parser.add_argument(
        "--playwright-log",
        default=None,
        help="Optional path to playwright-log-*.txt for browser-level analysis.",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("Starting failure analysis for: %s", args.output_xml)
    prompt = f"Analyze the Robot Framework test results from: {args.output_xml}"
    if args.playwright_log:
        prompt += f" Also analyse browser failures from: {args.playwright_log}"
    result = delegate_agent.run_sync(prompt)
    print(result.output)
