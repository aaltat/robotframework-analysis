from __future__ import annotations

import re
import shutil
import warnings
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from robot.api import TestSuiteBuilder
from robot.result import ExecutionResult
from robot.running.builder import ResourceFileBuilder

_PREFIX_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*):\s*")
_TRUNCATE_LIMIT = 300
_UNSAFE_RE = re.compile(r"[^A-Za-z0-9]+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_LOG_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+|\d{8} \d{2}:\d{2}:\d{2}\.\d{3}"
)
_APPROVAL_FIXED_DATETIME = "20260101 00:00:00.000"


@dataclass
class FailedTest:
    suite_name: str
    test_name: str
    source: Path
    message: str
    log_messages: list[str]
    keyword_leaf_lines: list[str]
    last_user_keyword_source: Path | None = None
    failing_library_name: str | None = None


@dataclass
class FailingBranch:
    phase_label: str
    top_level_nodes: list[Any]
    failing_path: list[Any]


class _FailedTestCollector:
    def __init__(self) -> None:
        self.failed: list[FailedTest] = []
        self._keyword_source_cache: dict[Path, dict[str, Path]] = {}

    def _keyword_sources_for(self, suite_source: Path) -> dict[str, Path]:
        resolved = suite_source.resolve()
        if resolved not in self._keyword_source_cache:
            self._keyword_source_cache[resolved] = _build_keyword_source_index(resolved)
        return self._keyword_source_cache[resolved]

    def visit_suite(self, suite: Any) -> None:
        for test in getattr(suite, "tests", []):
            self.visit_test(test)
        for child in getattr(suite, "suites", []):
            self.visit_suite(child)

    def visit_test(self, test: Any) -> None:
        if test.status != "FAIL":
            return

        parent_suite = getattr(test, "parent", None)
        source = (
            Path(str(getattr(parent_suite, "source", "")))
            if getattr(parent_suite, "source", None)
            else Path()
        )
        keyword_sources = self._keyword_sources_for(source) if source else {}

        suite_branch = _find_suite_failing_branch(parent_suite) if parent_suite else None
        test_branch = _find_test_failing_branch(test)
        branch = test_branch or suite_branch
        failing_keyword = branch.failing_path[-1] if branch else None
        failing_library_name = _find_failing_library_name(branch)

        self.failed.append(
            FailedTest(
                suite_name=str(getattr(parent_suite, "name", "")),
                test_name=str(test.name),
                source=source,
                message=str(test.message),
                log_messages=_collect_log_messages(failing_keyword, str(test.message)),
                keyword_leaf_lines=_build_keyword_leaf_lines(
                    str(test.name), branch, failing_library_name
                ),
                last_user_keyword_source=_find_last_user_keyword_source(branch, keyword_sources),
                failing_library_name=failing_library_name,
            )
        )


def _format_start_end(starttime: str, endtime: str) -> str:
    return f"{starttime} / {endtime}"


def approval_time_normalizer(starttime: str, endtime: str) -> str:
    del starttime, endtime
    return f"{_APPROVAL_FIXED_DATETIME} / {_APPROVAL_FIXED_DATETIME}"


def normalize_log_timestamps(text: str, replacement: str = "timestamp") -> str:
    return _LOG_TIMESTAMP_RE.sub(replacement, text)


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
    collector = _FailedTestCollector()
    suite.visit(collector)
    return collector.failed


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


def _normalize_keyword_name(name: str) -> str:
    return re.sub(r"[\s_]+", "", name).lower()


def _build_keyword_source_index(suite_source: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}

    try:
        suite_model = TestSuiteBuilder().build(suite_source)
    except Exception:
        return index

    for keyword in suite_model.resource.keywords:
        keyword_source = Path(str(getattr(keyword, "source", suite_source))).resolve()
        index.setdefault(_normalize_keyword_name(keyword.name), keyword_source)

    stack: list[Path] = []
    for imp in suite_model.resource.imports:
        if getattr(imp, "type", "") != "RESOURCE":
            continue
        stack.append((Path(str(imp.directory)) / str(imp.name)).resolve())

    visited: set[Path] = set()
    while stack:
        resource_path = stack.pop()
        if resource_path in visited:
            continue
        visited.add(resource_path)

        try:
            resource_model = ResourceFileBuilder().build(resource_path)
        except Exception:
            continue

        for keyword in resource_model.keywords:
            keyword_source = Path(str(getattr(keyword, "source", resource_path))).resolve()
            index.setdefault(_normalize_keyword_name(keyword.name), keyword_source)

        for imp in resource_model.imports:
            if getattr(imp, "type", "") != "RESOURCE":
                continue
            nested_path = (Path(str(imp.directory)) / str(imp.name)).resolve()
            if nested_path not in visited:
                stack.append(nested_path)

    return index


def _find_last_user_keyword_source(
    branch: FailingBranch | None, keyword_sources: dict[str, Path]
) -> Path | None:
    if branch is None:
        return None

    for node in reversed(branch.failing_path):
        if str(getattr(node, "type", "")) != "KEYWORD":
            continue
        node_name = str(getattr(node, "name", "") or "").strip()
        if not node_name:
            continue
        source = keyword_sources.get(_normalize_keyword_name(node_name))
        if source is not None:
            return source

    return None


def _find_failing_library_name(branch: FailingBranch | None) -> str | None:
    if branch is None:
        return None

    failing_leaf = branch.failing_path[-1]
    libname = getattr(failing_leaf, "libname", None)
    if libname:
        return str(libname)
    owner = getattr(failing_leaf, "owner", None)
    if owner:
        return str(owner)
    return None


def _short_error(message: str, limit: int = 50) -> str:
    first_line = message.splitlines()[0] if message else ""
    if len(first_line) <= limit:
        return first_line
    return first_line[:limit] + "…"


def _render_tree_line(prefix: str, is_last: bool, text: str) -> str:
    branch = "└── " if is_last else "├── "
    return f"{prefix}{branch}{text}"


def _render_node_line(node: Any, failing_leaf: Any, failing_library_name: str | None) -> str:
    label = _node_label(node)
    if node is failing_leaf and failing_library_name:
        label = f"{failing_library_name}.{label}"
    status = str(getattr(node, "status", ""))
    return f"{label}    {status}" if status else label


def _build_keyword_leaf_lines(
    test_name: str, branch: FailingBranch | None, failing_library_name: str | None
) -> list[str]:
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
            out.append(
                _render_tree_line(
                    prefix,
                    is_last,
                    _render_node_line(node, failing_leaf, failing_library_name),
                )
            )

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

    sanitized = _sanitize_log_payload(text)
    return f"{timestamp} {level}: {sanitized}"


def _sanitize_log_payload(text: str) -> str:
    stripped = _HTML_TAG_RE.sub("", text)
    normalized = "\n".join(line.strip() for line in stripped.splitlines())
    cleaned = normalized.strip()
    return cleaned or "<removed html>"


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


def _display_path(path: Path, project_root: Path | None = None) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        if project_root is not None:
            try:
                return str(path.relative_to(project_root))
            except ValueError:
                pass
    return str(path)


def _render_detail_markdown(ft: FailedTest, project_root: Path | None = None) -> str:
    lines = [f"# {ft.suite_name} {ft.test_name} error", "", ft.message]
    if ft.log_messages:
        lines += ["", "# Log message", *ft.log_messages]
    lines += ["", "# Origin"]

    test_file = _display_path(ft.source, project_root)
    lines.append(f"- Test file: {test_file}")

    if ft.last_user_keyword_source is not None:
        last_user_keyword = _display_path(ft.last_user_keyword_source, project_root)
        lines.append(f"- Last user keyword file: {last_user_keyword}")

    if ft.failing_library_name:
        lines.append(f"- Failing library: {ft.failing_library_name}")

    if ft.keyword_leaf_lines:
        keyword_leaf_lines = list(ft.keyword_leaf_lines)
        keyword_leaf_lines[0] = f"{test_file}.{ft.test_name}"
        lines += ["", "# Keyword leaf", *keyword_leaf_lines]
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
    project_root: Path | None = None,
) -> str:
    output_path = Path(output_xml)
    if not output_path.exists():
        msg = f"Robot output.xml not found: {output_path}"
        raise FileNotFoundError(msg)

    result = ExecutionResult(str(output_path))
    totals = result.statistics.total
    suite_name = result.suite.name

    start_end = _format_start_end(result.suite.starttime, result.suite.endtime)

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
                path_str = _display_path(ft.source, project_root)
                if detail_dir is not None:
                    filename = _build_detail_filename(i, ft.suite_name, ft.test_name, j)
                    detail_file = detail_dir / filename
                    try:
                        detail_file.write_text(
                            _render_detail_markdown(ft, project_root=project_root),
                            encoding="utf-8",
                        )
                    except Exception as exc:
                        warnings.warn(f"Could not write {detail_file}: {exc}.", stacklevel=2)
                    detail_str = _display_path(detail_file, project_root)
                    lines.append(
                        f"| {ft.suite_name} | {ft.test_name} | {path_str} | {detail_str} |"
                    )
                else:
                    lines.append(f"| {ft.suite_name} | {ft.test_name} | {path_str} |")

    return "\n".join(lines) + "\n"
