from __future__ import annotations

from pathlib import Path

from robot.result import ExecutionResult


def _format_duration(milliseconds: int) -> str:
    seconds = milliseconds // 1000
    return f"{seconds}s"


def render_summary_markdown(output_xml: str | Path) -> str:
    output_path = Path(output_xml)
    if not output_path.exists():
        msg = f"Robot output.xml not found: {output_path}"
        raise FileNotFoundError(msg)

    result = ExecutionResult(str(output_path))
    totals = result.statistics.total
    suite_name = result.suite.name

    lines = [
        f"# {suite_name} Test Summary",
        "",
        f"- Total: {totals.total}",
        f"- Passed: {totals.passed}",
        f"- Failed: {totals.failed}",
        f"- Skipped: {totals.skipped}",
        f"- Duration: {_format_duration(result.suite.elapsedtime)}",
    ]
    return "\n".join(lines) + "\n"
