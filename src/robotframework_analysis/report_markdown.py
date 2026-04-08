from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from robot.result import ExecutionResult

_PREFIX_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*):\s*")
_TRUNCATE_LIMIT = 300


@dataclass
class FailedTest:
    suite_name: str
    test_name: str
    source: Path
    message: str


def _format_duration(milliseconds: int) -> str:
    seconds = milliseconds // 1000
    return f"{seconds}s"


def _error_group_key(message: str) -> tuple[str, str]:
    match = _PREFIX_RE.match(message)
    if match:
        prefix = match.group(1)
        rest = message[match.end() :]
    else:
        prefix = ""
        rest = message
    first_line = rest.split("\n")[0]
    return (prefix, first_line[:100])


def _truncate_error(message: str) -> str:
    if len(message) <= _TRUNCATE_LIMIT:
        return message
    return message[:_TRUNCATE_LIMIT] + "…"


def _collect_failed_tests(suite: Any) -> list[FailedTest]:
    failed: list[FailedTest] = []
    for test in suite.tests:
        if test.status == "FAIL":
            source = Path(str(suite.source)) if suite.source else Path("")
            failed.append(
                FailedTest(
                    suite_name=suite.name,
                    test_name=test.name,
                    source=source,
                    message=test.message,
                )
            )
    for sub_suite in suite.suites:
        failed.extend(_collect_failed_tests(sub_suite))
    return failed


def render_summary_markdown(
    output_xml: str | Path,
    path_normalizer: Callable[[Path], str] | None = None,
) -> str:
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

    failed_tests = _collect_failed_tests(result.suite)
    if failed_tests:
        groups: dict[tuple[str, str], list[FailedTest]] = defaultdict(list)
        for ft in failed_tests:
            groups[_error_group_key(ft.message)].append(ft)

        for i, (key, tests) in enumerate(groups.items(), start=1):
            prefix_label = f": {key[0]}" if key[0] else ""
            lines += [
                "",
                f"# Error Group {i}{prefix_label}",
                "",
                _truncate_error(tests[0].message),
                "",
                f"## Group {i} Tests",
                "| Suite Name | Test Name | Path |",
                "| --- | --- | --- |",
            ]
            for ft in tests:
                path_str = path_normalizer(ft.source) if path_normalizer else str(ft.source)
                lines.append(f"| {ft.suite_name} | {ft.test_name} | {path_str} |")

    return "\n".join(lines) + "\n"
