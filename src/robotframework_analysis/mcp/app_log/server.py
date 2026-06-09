"""FastMCP server exposing Browser library test-app log analysis tools."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from robotframework_analysis.mcp.app_log.log_parser import (
    AppLogEvent,
    ClickEvent,
    EndSuiteEvent,
    EndTestEvent,
    HoverEvent,
    HttpEvent,
    LoadEvent,
    ServerStartEvent,
    StartSuiteEvent,
    StartTestEvent,
    UnknownEvent,
    filter_events_for_test,
    filter_http_for_test,
    parse_log_file,
)

name = "rf_analyst_app_log"
logger = logging.getLogger(name)

mcp = FastMCP(name)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


@dataclass
class _LogCache:
    _store: dict[tuple[Path, float], list[AppLogEvent]] = field(default_factory=dict)

    def get(self, log_file: str) -> list[AppLogEvent]:
        path = Path(log_file).resolve()
        if not path.exists():
            msg = f"App log file not found: {path}"
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


def _event_to_dict(event: AppLogEvent) -> dict[str, Any]:  # noqa: C901, PLR0911
    if isinstance(event, ServerStartEvent):
        return {"timestamp": event.timestamp.isoformat(), "event": "server_start", "url": event.url}
    if isinstance(event, HttpEvent):
        d: dict[str, Any] = {
            "timestamp": event.timestamp.isoformat(),
            "event": "http",
            "method": event.method,
            "url": event.url,
            "status": event.status,
            "response_time_ms": event.response_time_ms,
        }
        if event.content_length is not None:
            d["content_length"] = event.content_length
        return d
    if isinstance(event, LoadEvent):
        return {
            "timestamp": event.timestamp.isoformat(),
            "event": "load",
            "url": event.url,
            "title": event.title,
        }
    if isinstance(event, ClickEvent):
        return {
            "timestamp": event.timestamp.isoformat(),
            "event": "click",
            "url": event.url,
            "tag": event.tag,
            "text": event.text,
        }
    if isinstance(event, HoverEvent):
        return {
            "timestamp": event.timestamp.isoformat(),
            "event": "hover",
            "url": event.url,
            "tag": event.tag,
            "text": event.text,
        }
    if isinstance(event, StartSuiteEvent):
        return {
            "timestamp": event.timestamp.isoformat(),
            "event": "start_suite",
            "id": event.id,
            "name": event.name,
        }
    if isinstance(event, EndSuiteEvent):
        return {
            "timestamp": event.timestamp.isoformat(),
            "event": "end_suite",
            "id": event.id,
            "name": event.name,
            "status": event.status,
        }
    if isinstance(event, StartTestEvent):
        return {
            "timestamp": event.timestamp.isoformat(),
            "event": "start_test",
            "id": event.id,
            "name": event.name,
        }
    if isinstance(event, EndTestEvent):
        return {
            "timestamp": event.timestamp.isoformat(),
            "event": "end_test",
            "id": event.id,
            "name": event.name,
            "status": event.status,
        }
    if isinstance(event, UnknownEvent):
        return {"timestamp": event.timestamp.isoformat(), "event": event.event}
    return {}


def _build_response(result: Any) -> dict[str, Any]:
    return {
        "server_started": result.server_started,
        "total_events_in_log": result.total_events_in_log,
        "events": [_event_to_dict(e) for e in result.events],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_optional_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value).astimezone(UTC)


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


@mcp.tool()
def get_app_log_http_for_test(
    log_file: str,
    test_id: str,
    test_name: str = "",
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    """Return HTTP events from the test-app log attributed to *test_id*.

    Use this tool first to detect polling patterns, slow endpoints, or
    unexpected HTTP status codes during the failing test.

    Args:
        log_file: Absolute or cwd-relative path to the test-app NDJSON log.
        test_id: Robot Framework test ID (e.g. ``s1-s1-s1-t5``).
        test_name: Human-readable test name; used as a fallback when the
            worker-assigned ID in the log differs from the merged output.xml ID.
        start_time: ISO 8601 UTC fallback window start (used when neither
            test_id nor test_name is found in lifecycle events).
        end_time: ISO 8601 UTC fallback window end.

    Returns:
        A dict with ``server_started`` (bool), ``total_events_in_log`` (int),
        and ``events`` (list of HTTP event dicts).
    """
    logger.info("get_app_log_http_for_test: log=%s test_id=%s", log_file, test_id)
    all_events = _cache.get(log_file)
    result = filter_http_for_test(
        all_events,
        test_id=test_id,
        test_name=test_name,
        start_time=_parse_optional_time(start_time),
        end_time=_parse_optional_time(end_time),
    )
    return _build_response(result)


@mcp.tool()
def get_app_log_events_for_test(
    log_file: str,
    test_id: str,
    test_name: str = "",
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    """Return all app log events attributed to *test_id*.

    Includes HTTP requests, page loads, click/hover interactions, and RF
    lifecycle events.  Also includes suite setup and teardown context.
    Call this after ``get_app_log_http_for_test`` when you need fuller context.

    Args:
        log_file: Absolute or cwd-relative path to the test-app NDJSON log.
        test_id: Robot Framework test ID (e.g. ``s1-s1-s1-t5``).
        test_name: Human-readable test name; used as a fallback when the
            worker-assigned ID in the log differs from the merged output.xml ID.
        start_time: ISO 8601 UTC fallback window start.
        end_time: ISO 8601 UTC fallback window end.

    Returns:
        A dict with ``server_started`` (bool), ``total_events_in_log`` (int),
        and ``events`` (list of event dicts).
    """
    logger.info("get_app_log_events_for_test: log=%s test_id=%s", log_file, test_id)
    all_events = _cache.get(log_file)
    result = filter_events_for_test(
        all_events,
        test_id=test_id,
        test_name=test_name,
        start_time=_parse_optional_time(start_time),
        end_time=_parse_optional_time(end_time),
    )
    return _build_response(result)
