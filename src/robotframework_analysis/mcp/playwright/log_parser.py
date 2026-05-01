"""Parser for Browser library Playwright log files.

Each log file contains two interleaved line types:

- JSON lines emitted by the Browser library (``{"level":...,"time":...,...}``)
- Plain ``pw:api`` lines emitted by Playwright itself
  (``2026-04-30T18:07:23.734Z pw:api => browser.newContext started``)

Both carry ISO 8601 UTC timestamps.  JSON lines may carry ``test_id``/
``test_name`` and/or ``suite_id``/``suite_name`` correlation fields once the
Browser library has received a ``setRFContext`` call from Robot Framework.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GrpcEvent:
    """A JSON log line emitted by the Browser library gRPC server."""

    time: datetime
    seq: int
    level: str
    event_kind: str  # "grpc", "grpc_error", or "" for free-form msg lines
    action: str
    status: str
    error_type: str
    msg: str
    test_id: str | None
    test_name: str | None
    suite_id: str | None
    suite_name: str | None
    raw: str = field(compare=False, repr=False)


@dataclass(frozen=True)
class PwApiEvent:
    """A plain ``pw:api`` line emitted directly by Playwright."""

    time: datetime
    text: str
    raw: str = field(compare=False, repr=False)


PlaywrightLogEvent = GrpcEvent | PwApiEvent
MatchSource = str  # "test_id" | "suite_id" | "time_only" | "anomaly"

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_PW_PREFIX_LEN = len("2026-")  # length of year prefix - used to detect pw:api lines


def _parse_timestamp(ts: str) -> datetime:
    parsed = datetime.fromisoformat(ts)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_json_line(raw: str) -> GrpcEvent | None:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    time_str = obj.get("time")
    if not time_str:
        return None
    return GrpcEvent(
        time=_parse_timestamp(time_str),
        seq=obj.get("seq", 0),
        level=obj.get("level", ""),
        event_kind=obj.get("event_kind", ""),
        action=obj.get("action", ""),
        status=obj.get("status", ""),
        error_type=obj.get("error_type", ""),
        msg=obj.get("msg", ""),
        test_id=obj.get("test_id"),
        test_name=obj.get("test_name"),
        suite_id=obj.get("suite_id"),
        suite_name=obj.get("suite_name"),
        raw=raw,
    )


def _parse_pwapi_line(raw: str) -> PwApiEvent | None:
    # Format: "2026-04-30T18:07:23.734Z pw:api ..."
    space_idx = raw.find(" ")
    if space_idx == -1:
        return None
    ts_str = raw[:space_idx]
    try:
        ts = _parse_timestamp(ts_str)
    except ValueError:
        return None
    text = raw[space_idx + 1 :]
    return PwApiEvent(time=ts, text=text, raw=raw)


def parse_log_file(path: Path) -> list[PlaywrightLogEvent]:
    """Parse a Playwright log file and return all events in file order."""
    logger.info("parse_log_file: reading %s", path)
    events: list[PlaywrightLogEvent] = []
    skipped = 0
    with path.open(encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")
            if not line:
                continue
            if line.startswith("{"):
                event = _parse_json_line(line)
                if event is not None:
                    events.append(event)
                else:
                    skipped += 1
                    logger.debug("parse_log_file: skipped unparseable JSON line: %.120s", line)
            else:
                pw_event = _parse_pwapi_line(line)
                if pw_event is not None:
                    events.append(pw_event)
                else:
                    skipped += 1
                    logger.debug("parse_log_file: skipped unrecognised line: %.120s", line)
    logger.info(
        "parse_log_file: parsed %d event(s), skipped %d line(s) from %s",
        len(events),
        skipped,
        path.name,
    )
    return events


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------


def _parse_window(start_time: str, end_time: str) -> tuple[datetime, datetime]:
    return _parse_timestamp(start_time), _parse_timestamp(end_time)


def _target_suite_ids(
    events: Sequence[PlaywrightLogEvent],
    test_id: str,
    start: datetime,
    end: datetime,
) -> set[str]:
    suite_ids: set[str] = set()
    for event in events:
        if not isinstance(event, GrpcEvent):
            continue
        if event.time < start or event.time > end:
            continue
        if event.test_id != test_id:
            continue
        if event.suite_id:
            suite_ids.add(event.suite_id)
    return suite_ids


def _match_source_for_grpc(
    event: GrpcEvent,
    test_id: str,
    target_suite_ids: set[str],
) -> MatchSource | None:
    if event.test_id:
        if event.test_id != test_id:
            return None
        # test_id matches — check for suite_id conflict
        if event.suite_id and target_suite_ids and event.suite_id not in target_suite_ids:
            return "anomaly"
        return "test_id"
    if event.suite_id and target_suite_ids:
        if event.suite_id in target_suite_ids:
            return "suite_id"
        return None
    return "time_only"


def filter_events_for_test_with_match_info(
    events: Sequence[PlaywrightLogEvent],
    test_id: str,
    start_time: str,
    end_time: str,
) -> list[tuple[PlaywrightLogEvent, MatchSource]]:
    """Return events in test window with correlation source metadata."""
    start, end = _parse_window(start_time, end_time)
    target_suite_ids = _target_suite_ids(events, test_id, start, end)
    result: list[tuple[PlaywrightLogEvent, MatchSource]] = []
    matched_test_id = 0
    matched_suite = 0
    matched_time_only = 0
    for event in events:
        if event.time < start or event.time > end:
            continue
        if isinstance(event, PwApiEvent):
            result.append((event, "time_only"))
            matched_time_only += 1
            continue
        match_source = _match_source_for_grpc(event, test_id, target_suite_ids)
        if match_source is None:
            continue
        if match_source == "test_id":
            matched_test_id += 1
        elif match_source == "suite_id":
            matched_suite += 1
        else:
            matched_time_only += 1
        result.append((event, match_source))
    logger.info(
        (
            "filter_events_for_test: %d/%d event(s) matched for test_id=%s "
            "(%d matched id, %d matched suite, %d time-only)"
        ),
        len(result),
        len(events),
        test_id,
        matched_test_id,
        matched_suite,
        matched_time_only,
    )
    return result


def filter_errors_for_test_with_match_info(
    events: Sequence[PlaywrightLogEvent],
    test_id: str,
    start_time: str,
    end_time: str,
) -> list[tuple[GrpcEvent, MatchSource]]:
    """Return grpc_error events in test window with correlation source metadata."""
    start, end = _parse_window(start_time, end_time)
    target_suite_ids = _target_suite_ids(events, test_id, start, end)
    result: list[tuple[GrpcEvent, MatchSource]] = []
    matched_id = 0
    matched_suite = 0
    no_context = 0
    for event in events:
        if not isinstance(event, GrpcEvent):
            continue
        if event.event_kind != "grpc_error":
            continue
        if event.time < start or event.time > end:
            continue
        match_source = _match_source_for_grpc(event, test_id, target_suite_ids)
        if match_source is None:
            continue
        if match_source == "test_id":
            matched_id += 1
        elif match_source == "suite_id":
            matched_suite += 1
        else:
            no_context += 1
        result.append((event, match_source))
    logger.info(
        (
            "filter_errors_for_test: %d error(s) for test_id=%s "
            "(%d matched id, %d matched suite, %d no-context)"
        ),
        len(result),
        test_id,
        matched_id,
        matched_suite,
        no_context,
    )
    return result


def filter_events_for_test(
    events: Sequence[PlaywrightLogEvent],
    test_id: str,
    start_time: str,
    end_time: str,
) -> list[PlaywrightLogEvent]:
    """Return events that fall within the test's time window.

    For JSON events, also accept those without a ``test_id`` (e.g. ``pw:api``
    lines and correlation-free errors) as long as they are within the window,
    since they may relate to this test.

    JSON events that carry a *different* ``test_id`` are excluded even if
    they fall in the same time range.
    """
    matched = filter_events_for_test_with_match_info(events, test_id, start_time, end_time)
    return [event for event, _ in matched]


def filter_errors_for_test(
    events: Sequence[PlaywrightLogEvent],
    test_id: str,
    start_time: str,
    end_time: str,
) -> list[GrpcEvent]:
    """Return only ``grpc_error`` events within the test's time window.

    Errors that carry a different ``test_id`` are excluded.
    Errors without any ``test_id`` are included (context may not have been set).
    """
    matched = filter_errors_for_test_with_match_info(events, test_id, start_time, end_time)
    return [event for event, _ in matched]
