"""FastMCP server exposing Playwright log analysis tools."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from fastmcp import FastMCP
from pydantic import BaseModel

from robotframework_analysis.mcp.playwright.log_parser import (
    GrpcEvent,
    PlaywrightLogEvent,
    PwApiEvent,
    filter_errors_for_test_with_match_info,
    filter_events_for_test_with_match_info,
    parse_log_file,
)

name = "rf_analyst_playwright_log"
logger = logging.getLogger(name)

mcp = FastMCP(name)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class PlaywrightEventItem(BaseModel):
    time: str
    type: str  # "grpc" | "pwapi"
    seq: int | None = None
    level: str | None = None
    event_kind: str | None = None
    action: str | None = None
    status: str | None = None
    test_id: str | None = None
    suite_id: str | None = None
    msg: str | None = None
    text: str | None = None  # pw:api line text
    matched_by: str  # "test_id" | "suite_id" | "time_only" | "anomaly"


class PlaywrightErrorItem(BaseModel):
    time: str
    seq: int
    error_type: str
    action: str
    msg: str
    test_id: str | None = None
    matched_by: str  # "test_id" | "suite_id" | "time_only" | "anomaly"


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


@dataclass
class _LogCache:
    _store: dict[tuple[Path, float], list[PlaywrightLogEvent]] = field(default_factory=dict)

    def get(self, log_file: str) -> list[PlaywrightLogEvent]:
        path = Path(log_file).resolve()
        if not path.exists():
            msg = f"Playwright log file not found: {path}"
            raise FileNotFoundError(msg)
        mtime = path.stat().st_mtime
        key = (path, mtime)
        if key not in self._store:
            self._store.clear()
            self._store[key] = parse_log_file(path)
        return self._store[key]


_cache = _LogCache()


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _serialise_event(
    event: PlaywrightLogEvent,
    matched_by: str,
) -> PlaywrightEventItem:
    if isinstance(event, GrpcEvent):
        return PlaywrightEventItem(
            time=event.time.isoformat(),
            type="grpc",
            seq=event.seq,
            level=event.level,
            event_kind=event.event_kind,
            action=event.action,
            status=event.status,
            test_id=event.test_id,
            suite_id=event.suite_id,
            msg=event.msg or None,
            matched_by=matched_by,
        )
    if not isinstance(event, PwApiEvent):  # pragma: no cover
        msg = f"Unexpected event type: {type(event)}"
        raise TypeError(msg)
    return PlaywrightEventItem(
        time=event.time.isoformat(),
        type="pwapi",
        text=event.text,
        matched_by=matched_by,
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def get_playwright_events_for_test(
    log_file: str,
    test_id: str,
    start_time: str,
    end_time: str,
) -> list[PlaywrightEventItem]:
    """Return all Playwright log events for a given test time window.

    Includes both Browser-library JSON events and raw ``pw:api`` lines.
    Events from a *different* test_id that fall in the same time window are
    excluded; events with no test_id are included (they may belong to this test).

    Args:
        log_file: Absolute or cwd-relative path to the playwright-log-*.txt file.
        test_id: Robot Framework test ID (e.g. ``s1-s1-s1-t3``), from output.xml.
        start_time: ISO 8601 UTC start of the test (from output.xml ``starttime``).
        end_time: ISO 8601 UTC end of the test (from output.xml ``endtime``).
    """
    logger.info(
        "get_playwright_events_for_test: test_id=%s window=[%s, %s]",
        test_id,
        start_time,
        end_time,
    )
    all_events = _cache.get(log_file)
    filtered = filter_events_for_test_with_match_info(all_events, test_id, start_time, end_time)
    logger.info("get_playwright_events_for_test: returning %d event(s)", len(filtered))
    return [_serialise_event(event, matched_by) for event, matched_by in filtered]


@mcp.tool()
def get_playwright_errors_for_test(
    log_file: str,
    test_id: str,
    start_time: str,
    end_time: str,
) -> list[PlaywrightErrorItem]:
    """Return only error events for a given test time window.

    Returns ``grpc_error`` events — each has ``error_type``, ``action``, and
    the full error message.  Useful when you want a concise view of what
    went wrong without the surrounding noise.

    Args:
        log_file: Absolute or cwd-relative path to the playwright-log-*.txt file.
        test_id: Robot Framework test ID (e.g. ``s1-s1-s1-t3``), from output.xml.
        start_time: ISO 8601 UTC start of the test (from output.xml ``starttime``).
        end_time: ISO 8601 UTC end of the test (from output.xml ``endtime``).
    """
    logger.info(
        "get_playwright_errors_for_test: test_id=%s window=[%s, %s]",
        test_id,
        start_time,
        end_time,
    )
    all_events = _cache.get(log_file)
    errors = filter_errors_for_test_with_match_info(all_events, test_id, start_time, end_time)
    logger.info("get_playwright_errors_for_test: returning %d error(s)", len(errors))
    return [
        PlaywrightErrorItem(
            time=e.time.isoformat(),
            seq=e.seq,
            error_type=e.error_type,
            action=e.action,
            msg=e.msg,
            test_id=e.test_id,
            matched_by=matched_by,
        )
        for e, matched_by in errors
    ]


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    mcp.run()


if __name__ == "__main__":
    main()
