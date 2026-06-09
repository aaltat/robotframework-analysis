from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from robotframework_analysis.artifacts.fetcher import fetch_artifact_bundle


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rfanalysis")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="Download and inspect a GitHub artifact")
    download.add_argument("artifact_url", help="GitHub Actions artifact URL")
    download.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Reserved for report output path",
    )

    analyze = subparsers.add_parser(
        "analyze", help="Run the Robot Framework failure analysis agent"
    )
    analyze.add_argument(
        "output_xml", help="Path to the Robot Framework output.xml file to analyze."
    )
    analyze.add_argument(
        "--playwright-log",
        default=None,
        help="Optional path to playwright-log-*.txt for browser-level analysis.",
    )
    analyze.add_argument(
        "--app-log",
        default=None,
        help="Optional path to the folder containing Browser library test-app NDJSON log files.",
    )
    return parser


async def _run_analyze(artifact_url: str, output: Path | None = None) -> int:
    bundle = await fetch_artifact_bundle(artifact_url, extract_dir=output)
    print(f"Artifact: {bundle.artifact_filename}")
    print(f"Run ID: {bundle.run_id}")
    print(f"Job ID: {bundle.job_id}")
    print(f"output.xml: {bundle.output_xml}")
    print(f"Extracted to: {bundle.temp_dir}")
    return 0


def _run_delegate(output_xml: str, playwright_log: str | None, app_log: str | None) -> int:
    from robotframework_analysis.agent.delegate import (  # noqa: PLC0415
        DelegateContext,
        delegate_agent,
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("rf_analyst_orchestrator_agent")

    output_xml_abs = str(Path(output_xml).resolve())
    playwright_log_abs = str(Path(playwright_log).resolve()) if playwright_log else None
    app_log_dir_abs = str(Path(app_log).resolve()) if app_log else None
    deps = DelegateContext(
        output_xml=output_xml_abs,
        playwright_log=playwright_log_abs,
        app_log_dir=app_log_dir_abs,
    )

    logger.info("Starting failure analysis for: %s", output_xml_abs)
    prompt = "Analyze the Robot Framework test failures."
    if playwright_log_abs:
        prompt += " Playwright browser log analysis is available."
    if app_log_dir_abs:
        prompt += " App server log analysis is available."
    result = delegate_agent.run_sync(prompt, deps=deps)
    print(result.output)
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "download":
        return asyncio.run(_run_analyze(args.artifact_url, args.output))

    if args.command == "analyze":
        return _run_delegate(args.output_xml, args.playwright_log, args.app_log)

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
