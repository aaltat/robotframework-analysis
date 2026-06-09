"""App Log File Selection: finds the correct App Log file from an App Log Directory.

Implements Rules 0, 1, 1.5, 2, 3 as defined in CONTEXT.md and ADR-0005.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from robotframework_analysis.mcp.app_log.log_parser import (
    AppLogEvent,
    EndTestEvent,
    StartSuiteEvent,
    StartTestEvent,
    _suite_id_from_test_id,
    parse_log_file,
)

if TYPE_CHECKING:
    from datetime import datetime

logger = logging.getLogger(__name__)

# (priority, events_in_window, path) — used to rank fallback candidates
_Candidate = tuple[int, int, Path]

_RULE_1_5_PRIORITY = 2  # suite-context match
_RULE_1_PRIORITY = 1  # context-free match


class _LogProperties(TypedDict):
    has_any_test_event: bool
    has_matching_test_id: bool
    has_matching_test_name: bool
    has_matching_suite_id: bool
    has_any_lifecycle: bool


def _events_in_window(events: list[AppLogEvent], start: datetime, end: datetime) -> int:
    return sum(1 for e in events if start <= e.timestamp <= end)


def _get_log_properties(
    events: list[AppLogEvent], test_id: str, suite_id: str, test_name: str
) -> _LogProperties:
    props: _LogProperties = {
        "has_any_test_event": False,
        "has_matching_test_id": False,
        "has_matching_test_name": False,
        "has_matching_suite_id": False,
        "has_any_lifecycle": False,
    }
    for e in events:
        if isinstance(e, (StartTestEvent, EndTestEvent)):
            props["has_any_lifecycle"] = True
            props["has_any_test_event"] = True
            if e.id == test_id:
                props["has_matching_test_id"] = True
            if e.name == test_name:
                props["has_matching_test_name"] = True
        elif isinstance(e, StartSuiteEvent):
            props["has_any_lifecycle"] = True
            if e.id == suite_id:
                props["has_matching_suite_id"] = True
    return props


def _classify(  # noqa: PLR0913
    log_file: Path,
    test_id: str,
    suite_id: str,
    test_name: str,
    start_time: datetime | None,
    end_time: datetime | None,
) -> str | _Candidate:
    """Classify *log_file* against the selection rules.

    Returns:
        ``"rule_0"``   — definitive match (stop scanning).
        ``"rule_2"``   — excluded (has test events but none match by id or name).
        ``"no_match"`` — not relevant.
        A ``_Candidate`` tuple — fallback candidate (Rule 1 or 1.5).
    """
    events = parse_log_file(log_file)
    props = _get_log_properties(events, test_id, suite_id, test_name)

    if props["has_matching_test_id"] or props["has_matching_test_name"]:
        return "rule_0"

    if props["has_any_test_event"]:
        return "rule_2"

    if start_time is None or end_time is None:
        return "no_match"

    count = _events_in_window(events, start_time, end_time)
    if count > 0:
        if props["has_matching_suite_id"]:
            return (_RULE_1_5_PRIORITY, count, log_file)
        if not props["has_any_lifecycle"]:
            return (_RULE_1_PRIORITY, count, log_file)

    return "no_match"


def find_app_log_for_test(
    directory: Path,
    test_id: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    test_name: str = "",
) -> Path | None:
    """Find the App Log file in *directory* most relevant for *test_id*.

    Implements App Log File Selection (ADR-0005):
    - Rule 0: file has ``start_test id=<test_id>`` OR ``start_test name=<test_name>``
      → definitive match. Name match covers pabot merged-ID mismatch.
    - Rule 1: file has no RF lifecycle events + time-window overlap → fallback.
    - Rule 1.5: file has matching ``start_suite`` but no ``start_test`` + time-window → fallback.
    - Rule 2: file has ``start_test`` events but none match by id or name → excluded.
    - Rule 3: nothing matched → ``None``.

    Rule 0 always beats fallback candidates. Rule 1.5 beats Rule 1. Ties broken
    by number of events inside the time window.
    """
    suite_id = _suite_id_from_test_id(test_id)
    candidates: list[_Candidate] = []

    for log_file in sorted(directory.glob("*.log")):
        result = _classify(log_file, test_id, suite_id, test_name, start_time, end_time)
        if result == "rule_0":
            logger.info(
                "find_app_log_for_test: Rule 0 match %s for test_id=%s",
                log_file.name,
                test_id,
            )
            return log_file
        if isinstance(result, tuple):
            candidates.append(result)

    if not candidates:
        logger.info("find_app_log_for_test: no match for test_id=%s (Rule 3)", test_id)
        return None

    best_priority, best_count, best_path = max(candidates, key=lambda c: (c[0], c[1]))
    rule_name = "1.5" if best_priority == _RULE_1_5_PRIORITY else "1"
    logger.info(
        "find_app_log_for_test: Rule %s fallback match %s for test_id=%s (%d events in window)",
        rule_name,
        best_path.name,
        test_id,
        best_count,
    )
    return best_path
