from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from robotframework_analysis.artifacts.fetcher import fetch_artifact_bundle


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rfanalysis")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Download and inspect a GitHub artifact")
    analyze.add_argument("artifact_url", help="GitHub Actions artifact URL")
    analyze.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Reserved for report output path",
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


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "analyze":
        return asyncio.run(_run_analyze(args.artifact_url, args.output))

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
