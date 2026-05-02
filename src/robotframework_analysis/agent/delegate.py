import json
import logging
from pathlib import Path

from pydantic_ai import Agent, RunContext

from robotframework_analysis.agent.failure_analyst import build_analysis_agent
from robotframework_analysis.agent.ocr import extract_text
from robotframework_analysis.agent.playwright_log_analyst import build_playwright_analyst_agent
from robotframework_analysis.agent.screenshot_analyst import build_screenshot_analyst_agent

_SYSTEM_PROMPT = """\
You are a Robot Framework test failure analyst. Delegate analysis to specialized \
agents and synthesize their findings into a single report.

Workflow:
1. Call `analyze_failures` with the output.xml path to get RF-level error groups.
   Each group includes test_id, test_start_time, test_end_time, and screenshot_paths.
2. If a playwright_log_file path is provided, call `analyze_playwright_failures`
   with that path and the JSON from step 1 to get browser-level evidence for
   each group.
3. If screenshot_paths are present in any error group, call \
`analyze_screenshot_failures` with the output_xml and the JSON from step 1 to \
get visual evidence from captured screenshots.
4. Merge all reports: for each error group, combine the RF root cause, browser \
evidence, and screenshot evidence (if any) and produce a concise, actionable summary.

For each error group in the final report:
- State the RF root cause, the Playwright evidence, and the screenshot evidence side-by-side.
- Include the evidence confidence (high/medium/low/no_evidence) from each report.
- Only include recommendations based on evidence when confidence is high or medium.
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
    logger.info("analyze_playwright_failures called: log_file=%s", playwright_log_file)
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
                json.dumps(
                    {
                        "test_id": None,
                        "confidence": "no_evidence",
                        "playwright_error_summary": "Skipped: test_id not available in RF report",
                    }
                )
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


@delegate_agent.tool
async def analyze_screenshot_failures(
    _ctx: RunContext,
    output_xml: str,
    rf_error_groups_json: str,
) -> str:
    """Analyse screenshot evidence for each RF error group.

    Calls the screenshot analyst for each error group that has screenshot_paths
    and returns a JSON list of per-group screenshot findings.
    Groups without screenshot_paths are skipped with a no_screenshots reason.

    Args:
        output_xml: Absolute or cwd-relative path to the Robot Framework
            output.xml produced by a test run.
        rf_error_groups_json: The full JSON string returned by
            ``analyze_failures``, containing error groups with
            ``screenshot_paths``, ``suite_name``, and ``test_name``.
    """
    logger.info("analyze_screenshot_failures called: output_xml=%s", output_xml)
    try:
        rf_report = json.loads(rf_error_groups_json)
        groups = rf_report.get("error_groups", [])
    except (json.JSONDecodeError, AttributeError):
        logger.warning("analyze_screenshot_failures: could not parse rf_error_groups_json")
        return "[]"

    agent = build_screenshot_analyst_agent()
    results = []
    for group in groups:
        test_id = group.get("test_id") or None
        screenshot_paths = group.get("screenshot_paths") or []
        representative = group.get("representative_test", f"group {group.get('group_id', '?')}")

        # suite_name / test_name may be at group root or inside the first test entry
        representative_test: dict[str, object] = (group.get("tests") or [{}])[0]
        suite_name = group.get("suite_name") or representative_test.get("suite_name", "")
        test_name = group.get("test_name") or representative_test.get("test_name", "")

        if not screenshot_paths:
            logger.info(
                "analyze_screenshot_failures: skipping group '%s' — no screenshots",
                representative,
            )
            results.append(
                json.dumps(
                    {
                        "test_id": None,
                        "screenshot_text": None,
                        "visible_error": None,
                        "failure_area": "unknown",
                        "confidence": "no_evidence",
                        "evidence_source": "none",
                        "reason": "no_screenshots",
                    }
                )
            )
            continue

        logger.info(
            "analyze_screenshot_failures: analysing %s (%d screenshot(s))",
            representative,
            len(screenshot_paths),
        )
        ocr_sections: list[str] = []
        for p in screenshot_paths:
            ocr_text, ocr_confidence = extract_text(Path(p))
            ocr_sections.append(
                f"Path: {p}\nOCR confidence: {ocr_confidence:.2f}\nOCR text: {ocr_text or '(none)'}"
            )
        ocr_block = "\n\n".join(ocr_sections)
        context_lines = [
            f"test_id: {test_id or '(unknown)'}",
            f"output_xml: {output_xml}",
            f"suite_name: {suite_name or '(unknown)'}",
            f"test_name: {test_name or '(unknown)'}",
        ]
        context_block = "\n".join(context_lines)
        get_detail_instruction = (
            f"You may call get_failure_detail(output_xml={output_xml!r}, "
            f"suite_name={suite_name!r}, test_name={test_name!r}) for broader context."
            if suite_name and test_name
            else "Do not call get_failure_detail — suite_name and test_name are not available."
        )
        prompt = (
            f"Analyse screenshots for the failing test below.\n\n"
            f"Context:\n{context_block}\n\n"
            f"{get_detail_instruction}\n\n"
            f"Screenshots OCR results:\n{ocr_block}"
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
