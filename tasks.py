import os
import shlex
import shutil
import sys
from pathlib import Path

import dotenv
from invoke import task  # type: ignore
from invoke.context import Context

RUNNING_IN_CI = "GITHUB_RUN_ID" in os.environ


@task
def lint(ctx: Context) -> None:
    """Run linters."""
    print("Running ruff format...")
    ctx.run("ruff format src tests")
    print("Running ruff check...")
    ruff_format_cmd = ["ruff", "check"]
    if not RUNNING_IN_CI:
        ruff_format_cmd.append("--fix")
    ruff_format_cmd.extend(["src", "tests"])
    ctx.run(" ".join(ruff_format_cmd))
    print("Running mypy...")
    ctx.run("mypy src")


@task
def atest_example(ctx: Context) -> None:
    """Run example tests."""
    ctx.run("robot -L debug -d results example.robot")


@task
def download(
    ctx: Context,
    artifact_url: str,
    output: str = ".robotframework_analysis",
) -> None:
    """Run the artifact downloader via rfanalysis download."""
    dotenv.load_dotenv()
    destination = Path(output)
    shutil.rmtree(destination, ignore_errors=True)

    command_parts = [
        shlex.quote(sys.executable),
        "-m",
        "robotframework_analysis.cli",
        "download",
        shlex.quote(artifact_url),
        "--output",
        shlex.quote(str(destination)),
    ]
    ctx.run(" ".join(command_parts))


@task
def analyze(
    ctx: Context,
    output_xml: str,
    playwright_log: str | None = None,
    app_log: str | None = None,
) -> None:
    """Run the analysis agent via rfanalysis analyze."""
    dotenv.load_dotenv()

    command_parts = [
        shlex.quote(sys.executable),
        "-m",
        "robotframework_analysis.cli",
        "analyze",
        shlex.quote(output_xml),
    ]
    if playwright_log:
        command_parts.extend(["--playwright-log", shlex.quote(playwright_log)])
    if app_log:
        command_parts.extend(["--app-log", shlex.quote(app_log)])
    ctx.run(" ".join(command_parts))
