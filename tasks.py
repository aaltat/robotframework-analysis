import os

from invoke import task  # type: ignore
from invoke.context import Context

RUNNING_IN_CI = "GITHUB_RUN_ID" in os.environ


@task
def lint(ctx: Context):
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
