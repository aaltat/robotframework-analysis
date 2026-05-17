"""Parser for Browser library test-app NDJSON log files.

Each line is a JSON object with a ``timestamp`` (ISO 8601 UTC) and ``event``
field.  Known event types:

- ``server_start``   — server started, carries ``url``
- ``http``           — HTTP request served, carries ``method``, ``url``,
                       ``status``, ``contentLength``, ``responseTimeMs``
- ``load``           — page load event, carries ``url``, ``title``
- ``click``          — browser click, carries ``url``, ``tag``, ``text``
- ``hover``          — browser hover, carries ``url``, ``tag``, ``text``
- ``start_suite``    — RF suite started, carries ``id``, ``name``, ``pid``
- ``end_suite``      — RF suite ended, carries ``id``, ``name``, ``pid``,
                       ``status``
- ``start_test``     — RF test started, carries ``id``, ``name``, ``pid``
- ``end_test``       — RF test ended, carries ``id``, ``name``, ``pid``,
                       ``status``
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServerStartEvent:
    timestamp: datetime
    url: str
    raw: str = field(compare=False, repr=False)


@dataclass(frozen=True)
class HttpEvent:
    timestamp: datetime
    method: str
    url: str
    status: int
    content_length: int | None
    response_time_ms: float
    raw: str = field(compare=False, repr=False)


@dataclass(frozen=True)
class LoadEvent:
    timestamp: datetime
    url: str
    title: str
    raw: str = field(compare=False, repr=False)


@dataclass(frozen=True)
class ClickEvent:
    timestamp: datetime
    url: str
    tag: str
    text: str
    raw: str = field(compare=False, repr=False)


@dataclass(frozen=True)
class HoverEvent:
    timestamp: datetime
    url: str
    tag: str
    text: str
    raw: str = field(compare=False, repr=False)


@dataclass(frozen=True)
class StartSuiteEvent:
    timestamp: datetime
    id: str
    name: str
    pid: int
    raw: str = field(compare=False, repr=False)


@dataclass(frozen=True)
class EndSuiteEvent:
    timestamp: datetime
    id: str
    name: str
    pid: int
    status: str
    raw: str = field(compare=False, repr=False)


@dataclass(frozen=True)
class StartTestEvent:
    timestamp: datetime
    id: str
    name: str
    pid: int
    raw: str = field(compare=False, repr=False)


@dataclass(frozen=True)
class EndTestEvent:
    timestamp: datetime
    id: str
    name: str
    pid: int
    status: str
    raw: str = field(compare=False, repr=False)


@dataclass(frozen=True)
class UnknownEvent:
    timestamp: datetime
    event: str
    raw: str = field(compare=False, repr=False)


AppLogEvent = (
    ServerStartEvent
    | HttpEvent
    | LoadEvent
    | ClickEvent
    | HoverEvent
    | StartSuiteEvent
    | EndSuiteEvent
    | StartTestEvent
    | EndTestEvent
    | UnknownEvent
)


# ---------------------------------------------------------------------------
# Filter result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FilterResult:
    """Result returned by filter functions.

    Attributes:
        server_started: Whether a ``server_start`` event was found in the log.
        total_events_in_log: Total number of parsed events in the full log.
        events: Events attributed to the requested test / time range.
    """

    server_started: bool
    total_events_in_log: int
    events: list[AppLogEvent]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _parse_timestamp(ts: str) -> datetime:
    return datetime.fromisoformat(ts).astimezone(UTC)


def _parse_line(raw: str) -> AppLogEvent | None:  # noqa: C901, PLR0911
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        logger.debug("Skipping non-JSON line: %r", raw[:80])
        return None

    ts_str = d.get("timestamp", "")
    if not ts_str:
        logger.debug("Skipping line without timestamp: %r", raw[:80])
        return None

    try:
        ts = _parse_timestamp(ts_str)
    except ValueError:
        logger.debug("Skipping line with unparseable timestamp: %r", raw[:80])
        return None

    event = d.get("event", "")

    if event == "server_start":
        return ServerStartEvent(timestamp=ts, url=d.get("url", ""), raw=raw)

    if event == "http":
        cl = d.get("contentLength")
        return HttpEvent(
            timestamp=ts,
            method=d.get("method", ""),
            url=d.get("url", ""),
            status=int(d.get("status", 0)),
            content_length=int(cl) if cl is not None else None,
            response_time_ms=float(d.get("responseTimeMs", 0.0)),
            raw=raw,
        )

    if event == "load":
        return LoadEvent(
            timestamp=ts,
            url=d.get("url", ""),
            title=d.get("title", ""),
            raw=raw,
        )

    if event == "click":
        return ClickEvent(
            timestamp=ts,
            url=d.get("url", ""),
            tag=d.get("tag", ""),
            text=d.get("text", ""),
            raw=raw,
        )

    if event == "hover":
        return HoverEvent(
            timestamp=ts,
            url=d.get("url", ""),
            tag=d.get("tag", ""),
            text=d.get("text", ""),
            raw=raw,
        )

    if event == "start_suite":
        return StartSuiteEvent(
            timestamp=ts,
            id=d.get("id", ""),
            name=d.get("name", ""),
            pid=int(d.get("pid", 0)),
            raw=raw,
        )

    if event == "end_suite":
        return EndSuiteEvent(
            timestamp=ts,
            id=d.get("id", ""),
            name=d.get("name", ""),
            pid=int(d.get("pid", 0)),
            status=d.get("status", ""),
            raw=raw,
        )

    if event == "start_test":
        return StartTestEvent(
            timestamp=ts,
            id=d.get("id", ""),
            name=d.get("name", ""),
            pid=int(d.get("pid", 0)),
            raw=raw,
        )

    if event == "end_test":
        return EndTestEvent(
            timestamp=ts,
            id=d.get("id", ""),
            name=d.get("name", ""),
            pid=int(d.get("pid", 0)),
            status=d.get("status", ""),
            raw=raw,
        )

    return UnknownEvent(timestamp=ts, event=event, raw=raw)


def parse_log_file(path: Path) -> list[AppLogEvent]:
    """Parse a test-app NDJSON log file into typed events."""
    events: list[AppLogEvent] = []
    with path.open(encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")
            if not line.strip():
                continue
            parsed = _parse_line(line)
            if parsed is not None:
                events.append(parsed)
    return events


# ---------------------------------------------------------------------------
# State-machine correlation helpers
# ---------------------------------------------------------------------------

_SUITE_ID_RE = re.compile(r"^(.*)-t\d+$")


def _suite_id_from_test_id(test_id: str) -> str:
    """Return the suite ID embedded in *test_id*.

    Robot Framework encodes suite membership in the test ID: ``s1-s1-s1-t5``
    → suite ``s1-s1-s1``.  This reads the RF-defined structure; it is not
    algorithmic derivation (see CONTEXT.md — RF Hierarchical ID).
    """
    m = _SUITE_ID_RE.match(test_id)
    return m.group(1) if m else ""


def _build_health(events: list[AppLogEvent]) -> tuple[bool, int]:
    server_started = any(isinstance(e, ServerStartEvent) for e in events)
    return server_started, len(events)


def _suite_setup_events(all_events: list[AppLogEvent], suite_id: str) -> list[AppLogEvent]:
    """Return events in the suite-setup region for *suite_id*.

    Suite setup = events from ``start_suite`` (inclusive) up to (but not
    including) the first ``start_test`` in that suite, plus any events that
    occurred before ``start_suite`` for the same suite.
    """
    # Find start_suite index for this suite_id
    suite_start_idx: int | None = None
    for i, e in enumerate(all_events):
        if isinstance(e, StartSuiteEvent) and e.id == suite_id:
            suite_start_idx = i
            break

    # Find first start_test in this suite
    first_test_idx: int | None = None
    for i, e in enumerate(all_events):
        if isinstance(e, StartTestEvent) and e.id.startswith(suite_id + "-t"):
            first_test_idx = i
            break

    if suite_start_idx is None and first_test_idx is None:
        return []

    # Events before first_test_idx (from start_suite or log beginning)
    end = first_test_idx if first_test_idx is not None else len(all_events)

    # Include everything from log start up to (not including) first test,
    # plus server_start which precedes suite_start
    setup: list[AppLogEvent] = []
    for i, e in enumerate(all_events):
        if i >= end:
            break
        setup.append(e)
    return setup


def _suite_teardown_events(all_events: list[AppLogEvent], suite_id: str) -> list[AppLogEvent]:
    """Return events in the suite-teardown region for *suite_id*.

    Teardown = events after the last ``end_test`` in that suite up to and
    including ``end_suite``.
    """
    last_test_end_idx: int | None = None
    for i, e in enumerate(all_events):
        if isinstance(e, EndTestEvent) and e.id.startswith(suite_id + "-t"):
            last_test_end_idx = i

    if last_test_end_idx is None:
        return []

    teardown: list[AppLogEvent] = []
    for e in all_events[last_test_end_idx + 1 :]:
        teardown.append(e)
        if isinstance(e, EndSuiteEvent):
            break
    return teardown


def filter_events_for_test(
    all_events: list[AppLogEvent],
    *,
    test_id: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> FilterResult:
    """Return all app log events attributed to *test_id*.

    Uses the **App Log State Machine**: walks events in order, tracking the
    active test via ``start_test``/``end_test`` pairs.  Always prepends suite
    setup events and appends suite teardown events (Suite Context Inclusion).

    Falls back to *start_time*/*end_time* window if no matching lifecycle pair
    is found (App Log Time-Range Fallback).
    """
    server_started, total = _build_health(all_events)

    # --- Find the start_test / end_test boundaries for this test_id ---
    start_idx: int | None = None
    end_idx: int | None = None
    for i, e in enumerate(all_events):
        if isinstance(e, StartTestEvent) and e.id == test_id:
            start_idx = i
        if isinstance(e, EndTestEvent) and e.id == test_id:
            end_idx = i

    if start_idx is None:
        # Time-range fallback
        if start_time is not None and end_time is not None:
            matched = [e for e in all_events if start_time <= e.timestamp <= end_time]
        else:
            matched = []
        return FilterResult(
            server_started=server_started,
            total_events_in_log=total,
            events=matched,
        )

    # Inclusive slice from start_test to end_test
    slice_end = (end_idx + 1) if end_idx is not None else (start_idx + 1)
    test_events = all_events[start_idx:slice_end]

    # Suite context
    suite_id = _suite_id_from_test_id(test_id)
    setup = _suite_setup_events(all_events, suite_id)
    teardown = _suite_teardown_events(all_events, suite_id)

    # Merge: setup + test_events + teardown, deduplicating by identity
    seen: set[int] = set()
    merged: list[AppLogEvent] = []
    for e in setup + test_events + teardown:
        if id(e) not in seen:
            seen.add(id(e))
            merged.append(e)

    return FilterResult(
        server_started=server_started,
        total_events_in_log=total,
        events=merged,
    )


def filter_http_for_test(
    all_events: list[AppLogEvent],
    *,
    test_id: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> FilterResult:
    """Return only :class:`HttpEvent` items attributed to *test_id*.

    Uses the same state-machine attribution as :func:`filter_events_for_test`
    and then filters down to HTTP events only.  Server health metadata is
    preserved on the result.
    """
    full = filter_events_for_test(
        all_events, test_id=test_id, start_time=start_time, end_time=end_time
    )
    http_only = cast("list[AppLogEvent]", [e for e in full.events if isinstance(e, HttpEvent)])
    return FilterResult(
        server_started=full.server_started,
        total_events_in_log=full.total_events_in_log,
        events=http_only,
    )
