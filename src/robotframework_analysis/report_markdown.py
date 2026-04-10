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
    log_messages: list[str]
    keyword_leaf_lines: list[str]


@dataclass
class FailingBranch:
    phase_label: str
    top_level_nodes: list[Any]
    failing_path: list[Any]


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
    suite_branch = _find_suite_failing_branch(suite)

    for test in suite.tests:
        if test.status == "FAIL":
            source = Path(str(suite.source)) if suite.source else Path("")
            test_branch = _find_test_failing_branch(test)
            branch = test_branch or suite_branch
            failing_keyword = branch.failing_path[-1] if branch else _find_failing_keyword(test)
            failed.append(
                FailedTest(
                    suite_name=suite.name,
                    test_name=test.name,
                    source=source,
                    message=test.message,
                    log_messages=_collect_log_messages(failing_keyword, test.message),
                    keyword_leaf_lines=_build_keyword_leaf_lines(test.name, branch),
                )
            )
    for sub_suite in suite.suites:
        failed.extend(_collect_failed_tests(sub_suite))
    return failed


def _find_failing_keyword(container: Any) -> Any | None:
    for item in getattr(container, "body", []):
        if getattr(item, "type", None) != "KEYWORD":
            continue
        if getattr(item, "status", None) != "FAIL":
            continue
        nested = _find_failing_keyword(item)
        return nested if nested is not None else item
    return None


def _is_executed(item: Any) -> bool:
    return getattr(item, "status", None) != "NOT RUN"


def _iter_executed_nodes(body: Any) -> list[Any]:
    nodes: list[Any] = []
    for item in body:
        if getattr(item, "type", None) == "MESSAGE":
            continue
        if not _is_executed(item):
            continue
        nodes.append(item)
    return nodes


def _find_first_failing_path(nodes: list[Any]) -> list[Any] | None:
    for node in nodes:
        if getattr(node, "status", None) != "FAIL":
            continue
        child_nodes = _iter_executed_nodes(getattr(node, "body", []))
        child_path = _find_first_failing_path(child_nodes)
        if child_path:
            return [node, *child_path]
        return [node]
    return None


def _find_branch_in_nodes(phase_label: str, nodes: list[Any]) -> FailingBranch | None:
    executed = _iter_executed_nodes(nodes)
    path = _find_first_failing_path(executed)
    if not path:
        return None

    top_level_nodes: list[Any] = []
    root = path[0]
    for node in executed:
        top_level_nodes.append(node)
        if node is root:
            break

    return FailingBranch(
        phase_label=phase_label, top_level_nodes=top_level_nodes, failing_path=path
    )


def _find_test_failing_branch(test: Any) -> FailingBranch | None:
    setup = getattr(test, "setup", None)
    if setup and _is_executed(setup):
        branch = _find_branch_in_nodes("Test Setup", [setup])
        if branch:
            return branch

    branch = _find_branch_in_nodes("Test Body", list(getattr(test, "body", [])))
    if branch:
        return branch

    teardown = getattr(test, "teardown", None)
    if teardown and _is_executed(teardown):
        branch = _find_branch_in_nodes("Test Teardown", [teardown])
        if branch:
            return branch

    return None


def _find_suite_failing_branch(suite: Any) -> FailingBranch | None:
    setup = getattr(suite, "setup", None)
    if setup and _is_executed(setup):
        branch = _find_branch_in_nodes("Suite Setup", [setup])
        if branch:
            return branch

    teardown = getattr(suite, "teardown", None)
    if teardown and _is_executed(teardown):
        branch = _find_branch_in_nodes("Suite Teardown", [teardown])
        if branch:
            return branch

    return None


def _node_label(node: Any) -> str:
    node_type = str(getattr(node, "type", ""))
    if node_type == "KEYWORD":
        name = str(getattr(node, "name", "") or "").strip()
        if name:
            return name
    return node_type


def _short_error(message: str, limit: int = 50) -> str:
    first_line = message.splitlines()[0] if message else ""
    if len(first_line) <= limit:
        return first_line
    return first_line[:limit] + "…"


def _render_tree_line(prefix: str, is_last: bool, text: str) -> str:
    branch = "└── " if is_last else "├── "
    return f"{prefix}{branch}{text}"


def _render_node_line(node: Any, failing_leaf: Any) -> str:
    label = _node_label(node)
    status = str(getattr(node, "status", ""))
    return f"{label}    {status}" if status else label


def _build_keyword_leaf_lines(test_name: str, branch: FailingBranch | None) -> list[str]:
    if branch is None:
        return []

    lines = [test_name, _render_tree_line("", True, branch.phase_label)]
    phase_prefix = "    "

    failing_leaf = branch.failing_path[-1]
    parent = branch.failing_path[-2] if len(branch.failing_path) >= 2 else None
    parent_children = (
        _iter_executed_nodes(getattr(parent, "body", []))
        if parent is not None
        else branch.top_level_nodes
    )

    def in_path(node: Any) -> bool:
        return any(node is path_node for path_node in branch.failing_path)

    def next_path_node(current: Any) -> Any | None:
        for idx, path_node in enumerate(branch.failing_path[:-1]):
            if current is path_node:
                return branch.failing_path[idx + 1]
        return None

    def render_children(prefix: str, nodes: list[Any]) -> list[str]:
        out: list[str] = []
        for idx, node in enumerate(nodes):
            is_last = idx == len(nodes) - 1
            out.append(_render_tree_line(prefix, is_last, _render_node_line(node, failing_leaf)))

            next_prefix = prefix + ("    " if is_last else "│   ")
            if node is failing_leaf:
                msg = _short_error(str(getattr(node, "message", "")))
                if msg:
                    out.append(f"{next_prefix}Error: {msg}")
                continue

            if node is parent:
                out.extend(render_children(next_prefix, parent_children))
                continue

            if in_path(node):
                child_nodes = _iter_executed_nodes(getattr(node, "body", []))
                path_child = next_path_node(node)
                filtered = [child for child in child_nodes if child is path_child]
                out.extend(render_children(next_prefix, filtered))

        return out

    lines.extend(render_children(phase_prefix, branch.top_level_nodes))
    return lines


def _format_log_message(message: Any) -> str | None:
    level = getattr(message, "level", "")
    text = getattr(message, "message", "")
    timestamp = getattr(message, "timestamp", "")

    if level == "FAIL":
        return None
    if text.startswith("Arguments: ["):
        return None
    if text.startswith("Return: "):
        return None
    if text.startswith("Traceback (most recent call last):"):
        return None

    return f"{timestamp} {level}: {text}"


def _collect_log_messages(keyword: Any | None, failure_message: str) -> list[str]:
    if keyword is None:
        return []

    logs: list[str] = []
    for item in getattr(keyword, "body", []):
        if getattr(item, "type", None) != "MESSAGE":
            continue
        formatted = _format_log_message(item)
        if formatted is None:
            continue
        if getattr(item, "message", "") == failure_message:
            continue
        logs.append(formatted)
    return logs


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
    lines = [f"# {ft.suite_name} {ft.test_name} error", "", ft.message]
    if ft.log_messages:
        lines += ["", "# Log message", *ft.log_messages]
    if ft.keyword_leaf_lines:
        lines += ["", "# Keyword leaf", *ft.keyword_leaf_lines]
    return "\n".join(lines) + "\n"


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
