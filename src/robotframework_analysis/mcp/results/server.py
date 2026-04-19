"""FastMCP server exposing Robot Framework results analysis tools."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from fastmcp import FastMCP

from robotframework_analysis.mcp.results.models import FailureDetail, TestRunSummary
from robotframework_analysis.mcp.results.results_analysis import (
    _build_detail_model,
    _build_summary_model,
    _parse_output_xml,
    _ParsedResults,
)

name = "robotframework-results-analysis"
logger = logging.getLogger(name)

mcp = FastMCP(name)


@dataclass
class _ResultsCache:
    _store: dict[tuple[Path, float], _ParsedResults] = field(default_factory=dict)

    def get(self, output_xml: str) -> _ParsedResults:
        path = Path(output_xml).resolve()
        if not path.exists():
            msg = f"Robot output.xml not found: {path}"
            raise FileNotFoundError(msg)
        mtime = path.stat().st_mtime
        key = (path, mtime)
        if key not in self._store:
            self._store.clear()  # evict stale entries when file changes
            self._store[key] = _parse_output_xml(path)
        return self._store[key]


_cache = _ResultsCache()


@mcp.tool()
def get_test_run_summary(output_xml: str) -> TestRunSummary:
    """Return a summary of the Robot Framework test run including error groups.

    Returns totals (total/passed/failed/skipped) and groups of failing tests
    sharing the same error pattern.  Each failing test is represented as a
    lightweight ``FailedTestRef`` — no log messages or keyword trees — so the
    LLM context stays small.  Use ``get_failure_detail`` to fetch full detail
    for individual tests.

    Args:
        output_xml: Absolute or cwd-relative path to the Robot Framework
            output.xml produced by a test run.
    """
    logger.info("get_test_run_summary called: output_xml=%s", output_xml)
    parsed = _cache.get(output_xml)
    summary = _build_summary_model(parsed)
    logger.info(
        "get_test_run_summary result: %d total, %d failed, %d error group(s)",
        summary.totals.total,
        summary.totals.failed,
        len(summary.error_groups),
    )
    return summary


@mcp.tool()
def get_failure_detail(output_xml: str, suite_name: str, test_name: str) -> FailureDetail:
    """Return full failure detail for one test including log messages and keyword tree.

    This is a cache hit after ``get_test_run_summary`` has been called for the
    same ``output_xml`` — no additional parsing is needed.

    Args:
        output_xml: Same path as passed to ``get_test_run_summary``.
        suite_name: Exact ``suite_name`` from the ``FailedTestRef`` returned by
            ``get_test_run_summary``.
        test_name: Exact ``test_name`` from the ``FailedTestRef``.
    """
    logger.info(
        "get_failure_detail called: output_xml=%s suite=%s test=%s",
        output_xml,
        suite_name,
        test_name,
    )
    parsed = _cache.get(output_xml)
    detail = _build_detail_model(parsed, suite_name, test_name)
    logger.info(
        "get_failure_detail result: %d log message(s), %d keyword(s) in leaf",
        len(detail.log_messages),
        len(detail.keyword_leaf),
    )
    return detail


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    mcp.run()


if __name__ == "__main__":
    main()
