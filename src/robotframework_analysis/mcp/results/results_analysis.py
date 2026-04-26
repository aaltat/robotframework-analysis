from __future__ import annotations

import base64
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from robot.api import TestSuiteBuilder
from robot.result import ExecutionResult
from robot.running.builder import ResourceFileBuilder

from robotframework_analysis.mcp.results.models import (
    ErrorGroup,
    FailedTestRef,
    FailureDetail,
    RunTotals,
    TestRunSummary,
)

logger = logging.getLogger("rf_analyst_robotframework_results_analysis")
_PREFIX_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*):\s*")
_TRUNCATE_LIMIT = 300
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_LOG_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+|\d{8} \d{2}:\d{2}:\d{2}\.\d{3}"
)
_HREF_IMG_RE = re.compile(
    r'<a\b[^>]*\bhref="([^"]+\.(?:png|jpg|jpeg|gif|webp))"',
    re.IGNORECASE,
)
_IMG_DATA_URI_RE = re.compile(
    r'<img\b[^>]*\bsrc="(data:image/[^"]+)"',
    re.IGNORECASE,
)
_DATA_URI_PARTS_RE = re.compile(r"data:(image/[^;]+);base64,(.+)", re.DOTALL)


_MIN_BRANCH_DEPTH_FOR_PARENT = 2


@dataclass
class FailedTest:
    suite_name: str
    test_name: str
    source: Path
    start_time: str
    end_time: str
    message: str
    log_messages: list[str]
    keyword_leaf_lines: list[str]
    last_user_keyword_source: Path | None = None
    failing_library_name: str | None = None
    screenshot_refs: list[str] = field(default_factory=list)


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
                start_time=str(getattr(test, "starttime", "") or ""),
                end_time=str(getattr(test, "endtime", "") or ""),
                message=str(test.message),
                log_messages=_collect_log_messages(failing_keyword, str(test.message)),
                keyword_leaf_lines=_build_keyword_leaf_lines(
                    str(test.name), branch, failing_library_name
                ),
                last_user_keyword_source=_find_last_user_keyword_source(branch, keyword_sources),
                failing_library_name=failing_library_name,
                screenshot_refs=_extract_screenshot_refs_from_keyword(failing_keyword),
            )
        )


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


def _index_keywords_from_model(keywords: Any, default_source: Path, index: dict[str, Path]) -> None:
    for keyword in keywords:
        source = Path(str(getattr(keyword, "source", default_source))).resolve()
        index.setdefault(_normalize_keyword_name(keyword.name), source)


def _resource_imports_as_paths(imports: Any) -> list[Path]:
    return [
        (Path(str(imp.directory)) / str(imp.name)).resolve()
        for imp in imports
        if getattr(imp, "type", "") == "RESOURCE"
    ]


def _build_keyword_source_index(suite_source: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}

    try:
        suite_model = TestSuiteBuilder().build(suite_source)
    except Exception:
        return index

    _index_keywords_from_model(suite_model.resource.keywords, suite_source, index)
    stack = _resource_imports_as_paths(suite_model.resource.imports)

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

        _index_keywords_from_model(resource_model.keywords, resource_path, index)
        stack.extend(
            p for p in _resource_imports_as_paths(resource_model.imports) if p not in visited
        )

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


@dataclass
class _BranchRenderContext:
    failing_leaf: Any
    failing_library_name: str | None
    parent: Any | None
    parent_children: list[Any]
    failing_path: list[Any]


def _render_branch_children(
    prefix: str,
    nodes: list[Any],
    ctx: _BranchRenderContext,
) -> list[str]:
    out: list[str] = []
    for idx, node in enumerate(nodes):
        is_last = idx == len(nodes) - 1
        out.append(
            _render_tree_line(
                prefix,
                is_last,
                _render_node_line(node, ctx.failing_leaf, ctx.failing_library_name),
            )
        )
        next_prefix = prefix + ("    " if is_last else "│   ")
        if node is ctx.failing_leaf:
            msg = _short_error(str(getattr(node, "message", "")))
            if msg:
                out.append(f"{next_prefix}Error: {msg}")
            continue
        if node is ctx.parent:
            out.extend(_render_branch_children(next_prefix, ctx.parent_children, ctx))
            continue
        if any(node is p for p in ctx.failing_path):
            child_nodes = _iter_executed_nodes(getattr(node, "body", []))
            path_child = next(
                (ctx.failing_path[i + 1] for i, p in enumerate(ctx.failing_path[:-1]) if node is p),
                None,
            )
            filtered = [c for c in child_nodes if c is path_child]
            out.extend(_render_branch_children(next_prefix, filtered, ctx))
    return out


def _build_keyword_leaf_lines(
    test_name: str, branch: FailingBranch | None, failing_library_name: str | None
) -> list[str]:
    if branch is None:
        return []

    lines = [test_name, _render_tree_line("", True, branch.phase_label)]
    phase_prefix = "    "

    failing_leaf = branch.failing_path[-1]
    path_len = len(branch.failing_path)
    parent = branch.failing_path[-2] if path_len >= _MIN_BRANCH_DEPTH_FOR_PARENT else None
    parent_children = (
        _iter_executed_nodes(getattr(parent, "body", []))
        if parent is not None
        else branch.top_level_nodes
    )
    lines.extend(
        _render_branch_children(
            phase_prefix,
            branch.top_level_nodes,
            _BranchRenderContext(
                failing_leaf=failing_leaf,
                failing_library_name=failing_library_name,
                parent=parent,
                parent_children=parent_children,
                failing_path=branch.failing_path,
            ),
        )
    )
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
    truncated = _truncate_error(sanitized)
    return f"{timestamp} {level}: {truncated}"


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


def _extract_screenshot_refs(message_text: str) -> list[str]:
    refs: list[str] = []
    refs.extend(m.group(1) for m in _HREF_IMG_RE.finditer(message_text))
    refs.extend(m.group(1) for m in _IMG_DATA_URI_RE.finditer(message_text))
    return refs


def _extract_screenshot_refs_from_keyword(keyword: Any | None) -> list[str]:
    refs: list[str] = []
    for item in getattr(keyword, "body", []):
        if getattr(item, "type", None) != "MESSAGE":
            continue
        refs.extend(_extract_screenshot_refs(getattr(item, "message", "")))
    return refs


def _save_embedded_image(data_uri: str, output_dir: Path) -> Path | None:
    match = _DATA_URI_PARTS_RE.match(data_uri)
    if not match:
        return None
    mime_type = match.group(1)
    ext = mime_type.split("/")[-1]
    try:
        image_bytes = base64.b64decode(match.group(2))
    except Exception:
        return None
    filename = f"screenshot_{uuid.uuid4().hex}.{ext}"
    path = output_dir / filename
    try:
        path.write_bytes(image_bytes)
    except Exception:
        return None
    return path


def _resolve_screenshot_paths(refs: list[str], output_path: Path) -> list[str]:
    paths: list[str] = []
    for ref in refs:
        if ref.startswith("data:"):
            saved = _save_embedded_image(ref, output_path.parent)
            if saved is not None:
                resolved = str(saved.resolve())
                logger.info("screenshot path resolved (embedded): %s", resolved)
                paths.append(resolved)
        else:
            resolved = str((output_path.parent / ref).resolve())
            logger.info("screenshot path resolved: %s", resolved)
            paths.append(resolved)
    return paths


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _build_failed_test_ref(ft: FailedTest) -> FailedTestRef:
    return FailedTestRef(
        suite_name=ft.suite_name,
        test_name=ft.test_name,
        source_path=_display_path(ft.source),
        error_prefix=_error_group_key(ft.message)[0],
        short_error=_short_error(ft.message),
    )


@dataclass
class _ParsedResults:
    suite_name: str
    start_time: str
    end_time: str
    total: int
    passed: int
    failed: int
    skipped: int
    failed_tests: list[FailedTest]


def _parse_output_xml(output_path: Path) -> _ParsedResults:
    result = ExecutionResult(str(output_path))
    totals = result.statistics.total
    return _ParsedResults(
        suite_name=result.suite.name,
        start_time=result.suite.starttime,
        end_time=result.suite.endtime,
        total=totals.total,
        passed=totals.passed,
        failed=totals.failed,
        skipped=totals.skipped,
        failed_tests=_collect_failed_tests(result.suite),
    )


def _build_summary_model(pr: _ParsedResults) -> TestRunSummary:
    groups_map: dict[tuple[str, str], list[FailedTest]] = {}
    for ft in pr.failed_tests:
        key = _error_group_key(ft.message)
        groups_map.setdefault(key, []).append(ft)

    error_groups = [
        ErrorGroup(
            group_id=i,
            error_prefix=key[0],
            representative_error=_truncate_error(tests[0].message),
            tests=[_build_failed_test_ref(ft) for ft in tests],
        )
        for i, (key, tests) in enumerate(groups_map.items(), start=1)
    ]

    return TestRunSummary(
        suite_name=pr.suite_name,
        start_time=pr.start_time,
        end_time=pr.end_time,
        totals=RunTotals(
            total=pr.total,
            passed=pr.passed,
            failed=pr.failed,
            skipped=pr.skipped,
        ),
        error_groups=error_groups,
    )


def _build_detail_model(
    pr: _ParsedResults, output_path: Path, suite_name: str, test_name: str
) -> FailureDetail:
    for ft in pr.failed_tests:
        if ft.suite_name == suite_name and ft.test_name == test_name:
            return FailureDetail(
                suite_name=ft.suite_name,
                test_name=ft.test_name,
                start_time=ft.start_time,
                end_time=ft.end_time,
                message=ft.message,
                log_messages=ft.log_messages,
                keyword_leaf=ft.keyword_leaf_lines,
                test_source=_display_path(ft.source),
                last_user_keyword_source=(
                    _display_path(ft.last_user_keyword_source)
                    if ft.last_user_keyword_source is not None
                    else None
                ),
                failing_library=ft.failing_library_name,
                screenshot_paths=_resolve_screenshot_paths(ft.screenshot_refs, output_path),
            )

    msg = f"Test '{suite_name} / {test_name}' not found in failed tests."
    raise ValueError(msg)


def build_test_run_summary(output_xml: str | Path) -> TestRunSummary:
    """Parse *output_xml* and return a summary with error groups."""
    output_path = Path(output_xml)
    if not output_path.exists():
        msg = f"Robot output.xml not found: {output_path}"
        raise FileNotFoundError(msg)
    return _build_summary_model(_parse_output_xml(output_path))


def build_failure_detail(
    output_xml: str | Path,
    suite_name: str,
    test_name: str,
) -> FailureDetail:
    """Parse *output_xml* and return detail for the named test."""
    output_path = Path(output_xml)
    if not output_path.exists():
        msg = f"Robot output.xml not found: {output_path}"
        raise FileNotFoundError(msg)
    return _build_detail_model(_parse_output_xml(output_path), output_path, suite_name, test_name)
