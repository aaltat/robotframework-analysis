import os
import shlex
import shutil
import sys
from pathlib import Path

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
    ctx.run("mypy src tests")


@task
def atest_example(ctx: Context) -> None:
    """Run example tests."""
    ctx.run("robot -L debug -d results example.robot")


@task(
    help={
        "artifact_url": "GitHub Actions artifact URL to download and analyze.",
        "output": "Extraction destination directory.",
    }
)
def download_artifact(
    ctx: Context,
    artifact_url: str,
    output: str = ".robotframework_analysis",
) -> None:
    """Run the artifact downloader via rfanalysis analyze."""
    destination = Path(output)
    shutil.rmtree(destination, ignore_errors=True)

    command_parts = [
        shlex.quote(sys.executable),
        "-m",
        "robotframework_analysis.cli",
        "analyze",
        shlex.quote(artifact_url),
        "--output",
        shlex.quote(str(destination)),
    ]
    ctx.run(" ".join(command_parts))
