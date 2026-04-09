from __future__ import annotations

import re
import shutil
import warnings
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from robot.result import ExecutionResult

_PREFIX_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*):\s*")
_TRUNCATE_LIMIT = 300
_UNSAFE_RE = re.compile(r"[^A-Za-z0-9]+")


@dataclass
class FailedTest:
    suite_name: str
    test_name: str
    source: Path
    message: str


def _format_start_end(starttime: str, endtime: str) -> str:
    return f"{starttime} / {endtime}"


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


def _sanitize_name(s: str) -> str:
    return _UNSAFE_RE.sub("_", s).strip("_")


def _build_detail_filename(
    group_num: int, suite_name: str, test_name: str, running_num: int
) -> str:
    return (
        f"group_{group_num:03d}"
        f"_{_sanitize_name(suite_name)}"
        f"_{_sanitize_name(test_name)}"
        f"_{running_num:03d}.md"
    )


def _render_detail_markdown(ft: FailedTest) -> str:
    return f"# {ft.suite_name} {ft.test_name} error\n\n{ft.message}\n"


def _prepare_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        try:
            shutil.rmtree(output_dir)
        except Exception as exc:
            warnings.warn(
                f"Could not delete {output_dir}: {exc}. Please delete manually.",
                stacklevel=2,
            )
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        warnings.warn(
            f"Could not create {output_dir}: {exc}. Please create manually.",
            stacklevel=2,
        )


def render_summary_markdown(
    output_xml: str | Path,
    path_normalizer: Callable[[Path], str] | None = None,
    time_normalizer: Callable[[str, str], str] | None = None,
    project_root: Path | None = None,
) -> str:
    output_path = Path(output_xml)
    if not output_path.exists():
        msg = f"Robot output.xml not found: {output_path}"
        raise FileNotFoundError(msg)

    result = ExecutionResult(str(output_path))
    totals = result.statistics.total
    suite_name = result.suite.name

    start_end = (
        time_normalizer(result.suite.starttime, result.suite.endtime)
        if time_normalizer
        else _format_start_end(result.suite.starttime, result.suite.endtime)
    )

    lines = [
        f"# {suite_name} Test Summary",
        "",
        f"- Total: {totals.total}",
        f"- Passed: {totals.passed}",
        f"- Failed: {totals.failed}",
        f"- Skipped: {totals.skipped}",
        f"- Start / end: {start_end}",
    ]

    failed_tests = _collect_failed_tests(result.suite)
    if failed_tests:
        groups: dict[tuple[str, str], list[FailedTest]] = defaultdict(list)
        for ft in failed_tests:
            groups[_error_group_key(ft.message)].append(ft)

        detail_dir: Path | None = None
        if project_root is not None:
            detail_dir = project_root / ".robotframework_analysis"
            _prepare_output_dir(detail_dir)

        for i, (key, tests) in enumerate(groups.items(), start=1):
            prefix_label = f": {key[0]}" if key[0] else ""
            if detail_dir is not None:
                table_header = "| Suite Name | Test Name | Path | More Details |"
                table_sep = "| --- | --- | --- | --- |"
            else:
                table_header = "| Suite Name | Test Name | Path |"
                table_sep = "| --- | --- | --- |"
            lines += [
                "",
                f"# Error Group {i}{prefix_label}",
                "",
                _truncate_error(tests[0].message),
                "",
                f"## Group {i} Tests",
                table_header,
                table_sep,
            ]
            for j, ft in enumerate(tests, start=1):
                path_str = path_normalizer(ft.source) if path_normalizer else str(ft.source)
                if detail_dir is not None:
                    filename = _build_detail_filename(i, ft.suite_name, ft.test_name, j)
                    detail_file = detail_dir / filename
                    try:
                        detail_file.write_text(_render_detail_markdown(ft), encoding="utf-8")
                    except Exception as exc:
                        warnings.warn(f"Could not write {detail_file}: {exc}.", stacklevel=2)
                    detail_str = (
                        path_normalizer(detail_file) if path_normalizer else str(detail_file)
                    )
                    lines.append(
                        f"| {ft.suite_name} | {ft.test_name} | {path_str} | {detail_str} |"
                    )
                else:
                    lines.append(f"| {ft.suite_name} | {ft.test_name} | {path_str} |")

    return "\n".join(lines) + "\n"
