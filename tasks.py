from invoke import task # type: ignore
from invoke.context import Context


@task
def lint(ctx: Context):
    """Run linters."""
    ctx.run("ruff format src tests")
    ctx.run("ruff check --fix src tests")
