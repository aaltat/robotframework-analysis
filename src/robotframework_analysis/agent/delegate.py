import json
import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai import Agent, RunContext

from robotframework_analysis.agent.app_log_analyst import (
    AppLogAnalystContext,
    build_app_log_analyst_agent,
)
from robotframework_analysis.agent.failure_analyst import build_analysis_agent
from robotframework_analysis.agent.ocr import extract_text
from robotframework_analysis.agent.playwright_log_analyst import (
    PlaywrightAnalystContext,
    build_playwright_analyst_agent,
)
from robotframework_analysis.agent.screenshot_analyst import build_screenshot_analyst_agent


@dataclass
class DelegateContext:
    """File paths injected as agent dependencies — never passed through the LLM."""

    output_xml: str
    playwright_log: str | None = None
    app_log: str | None = None


_SYSTEM_PROMPT = """\
You are a Robot Framework test failure analyst. Delegate analysis to specialized \
agents and synthesize their findings into a single report.

Workflow:
1. Call `analyze_failures` to get RF-level error groups.
   Each group includes test_id, test_start_time, test_end_time, and screenshot_paths.
2. If Playwright browser log analysis is available, call `analyze_playwright_failures`
   with the JSON from step 1 to get browser-level evidence for each group.
3. If app server log analysis is available, call `analyze_app_log_failures`
   with the JSON from step 1 to get server-side HTTP evidence for each group.
4. If screenshot_paths are present in any error group, call \
`analyze_screenshot_failures` with the JSON from step 1 to \
get visual evidence from captured screenshots.
5. Merge all reports: for each error group, combine the RF root cause, browser \
evidence, app-level HTTP evidence, and screenshot evidence (if any) and \
produce a concise, actionable summary.

For each error group in the final report:
- State the RF root cause, the Playwright evidence, and the screenshot evidence side-by-side.
- Include the evidence confidence (high/medium/low/no_evidence) from each report.
- Only include recommendations based on evidence when confidence is high or medium.
- When confidence is low or no_evidence, say so explicitly rather than guessing.

Your final report should be clear and actionable for the development team.
You will not do the analysis yourself, but delegate it to specialized agents.
File paths are pre-configured — do NOT pass file path arguments to any tool.
"""

logger = logging.getLogger("rf_analyst_orchestrator_agent")

delegate_agent: Agent[DelegateContext, str] = Agent(
    "ollama:gemma4:e4b",
    system_prompt=_SYSTEM_PROMPT,
    deps_type=DelegateContext,
)


@delegate_agent.tool
async def analyze_failures(ctx: RunContext[DelegateContext]) -> str:
    """Analyse test results from the pre-configured Robot Framework output.xml."""
    output_xml = ctx.deps.output_xml
    logger.info("analyze_failures called: output_xml=%s", output_xml)
    agent = build_analysis_agent()
    result = await agent.run(f"Analyze the Robot Framework test results from: {output_xml}")
    return result.output


@delegate_agent.tool
async def analyze_playwright_failures(
    ctx: RunContext[DelegateContext],
    rf_error_groups_json: str,
) -> str:
    """Analyse browser-level evidence for each RF error group.

    Calls the Playwright log analyst for each error group and returns a JSON
    list of per-group browser findings.

    Args:
        rf_error_groups_json: The full JSON string returned by
            ``analyze_failures``, containing error groups with
            ``test_id``, ``test_start_time``, and ``test_end_time``.
    """
    playwright_log_file = ctx.deps.playwright_log
    if not playwright_log_file:
        logger.info("analyze_playwright_failures: no playwright log configured")
        return "[]"
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
            f"Analyse browser failures for test_id={test_id} window=[{start_time}, {end_time}]."
        )
        group_result = await agent.run(
            prompt, deps=PlaywrightAnalystContext(log_file=playwright_log_file)
        )
        results.append(group_result.output)

    return json.dumps(results)


@delegate_agent.tool
async def analyze_screenshot_failures(
    ctx: RunContext[DelegateContext],
    rf_error_groups_json: str,
) -> str:
    """Analyse screenshot evidence for each RF error group.

    Calls the screenshot analyst for each error group that has screenshot_paths
    and returns a JSON list of per-group screenshot findings.
    Groups without screenshot_paths are skipped with a no_screenshots reason.

    Args:
        rf_error_groups_json: The full JSON string returned by
            ``analyze_failures``, containing error groups with
            ``screenshot_paths``, ``suite_name``, and ``test_name``.
    """
    output_xml = ctx.deps.output_xml
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


@delegate_agent.tool
async def analyze_app_log_failures(
    ctx: RunContext[DelegateContext],
    rf_error_groups_json: str,
) -> str:
    """Analyse server-side HTTP evidence for each RF error group.

    Calls the app log analyst for each error group and returns a JSON list
    of per-group HTTP findings.

    Args:
        rf_error_groups_json: The full JSON string returned by
            ``analyze_failures``, containing error groups with ``test_id``.
    """
    app_log_file = ctx.deps.app_log
    if not app_log_file:
        logger.info("analyze_app_log_failures: no app log configured")
        return "[]"
    logger.info("analyze_app_log_failures called: log_file=%s", app_log_file)
    try:
        rf_report = json.loads(rf_error_groups_json)
        groups = rf_report.get("error_groups", [])
    except (json.JSONDecodeError, AttributeError):
        logger.warning("analyze_app_log_failures: could not parse rf_error_groups_json")
        return "[]"

    agent = build_app_log_analyst_agent()
    results = []
    for group in groups:
        test_id = group.get("test_id", "")
        representative = group.get("representative_test", f"group {group.get('group_id', '?')}")
        if not test_id:
            logger.warning(
                "analyze_app_log_failures: skipping group '%s' — test_id missing in RF report",
                representative,
            )
            results.append(
                json.dumps(
                    {
                        "test_id": None,
                        "confidence": "no_evidence",
                        "summary": "Skipped: test_id not available in RF report",
                    }
                )
            )
            continue
        logger.info(
            "analyze_app_log_failures: analysing %s (test_id=%s)",
            representative,
            test_id,
        )
        prompt = f"Analyse app-level failures for test_id={test_id}."
        group_result = await agent.run(prompt, deps=AppLogAnalystContext(log_file=app_log_file))
        results.append(group_result.output)

    return json.dumps(results)
