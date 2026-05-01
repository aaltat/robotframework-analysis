"""Tests for the Playwright log parser."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from robotframework_analysis.mcp.playwright.log_parser import (
    GrpcEvent,
    PwApiEvent,
    filter_errors_for_test,
    filter_events_for_test,
    parse_log_file,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "playwright-log-slice.txt"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event_to_dict(event: object) -> dict[str, object]:
    if isinstance(event, GrpcEvent):
        return {
            "type": "grpc",
            "seq": event.seq,
            "time": event.time.isoformat(),
            "level": event.level,
            "event_kind": event.event_kind,
            "action": event.action,
            "status": event.status,
            "error_type": event.error_type,
            "test_id": event.test_id,
            "suite_id": event.suite_id,
            "msg": event.msg[:120] if event.msg else "",
        }
    if isinstance(event, PwApiEvent):
        return {
            "type": "pwapi",
            "time": event.time.isoformat(),
            "text": event.text,
        }
    raise TypeError(f"Unknown event type: {type(event)}")


# ---------------------------------------------------------------------------
# parse_log_file
# ---------------------------------------------------------------------------


def test_parse_returns_all_lines() -> None:
    events = parse_log_file(_FIXTURE)
    assert len(events) == 18


def test_parse_json_grpc_event() -> None:
    events = parse_log_file(_FIXTURE)
    # seq 117 is the first line - getBrowserCatalog without test context
    first = events[0]
    assert isinstance(first, GrpcEvent)
    assert first.seq == 117
    assert first.event_kind == "grpc"
    assert first.action == "getBrowserCatalog"
    assert first.status == "started"
    assert first.test_id is None
    assert first.suite_id is None


def test_parse_pwapi_event() -> None:
    events = parse_log_file(_FIXTURE)
    # Second line is a pw:api line
    second = events[1]
    assert isinstance(second, PwApiEvent)
    assert second.time == datetime(2026, 4, 30, 18, 7, 24, 144000, tzinfo=UTC)
    assert "page.title" in second.text


def test_parse_grpc_event_with_test_id() -> None:
    events = parse_log_file(_FIXTURE)
    grpc_with_test = [e for e in events if isinstance(e, GrpcEvent) and e.test_id == "s1-s1-s1-t3"]
    assert len(grpc_with_test) >= 4
    first_with_test = grpc_with_test[0]
    assert first_with_test.test_name == "Test.02 Content Keywords.Pdf.Save PDF With Invalid Margin"


def test_parse_grpc_error_event() -> None:
    events = parse_log_file(_FIXTURE)
    errors = [e for e in events if isinstance(e, GrpcEvent) and e.event_kind == "grpc_error"]
    assert len(errors) == 2

    pdf_error = next(e for e in errors if e.test_id == "s1-s1-s1-t3")
    assert pdf_error.error_type == "Error"
    assert "page.pdf: Failed to parse parameter value" in pdf_error.msg

    no_ctx_error = next(e for e in errors if e.test_id is None)
    assert no_ctx_error.error_type == "TimeoutError"
    assert "locator.click" in no_ctx_error.msg


def test_parse_timestamps_are_utc() -> None:
    events = parse_log_file(_FIXTURE)
    for event in events:
        assert event.time.tzinfo == UTC


# ---------------------------------------------------------------------------
# filter_events_for_test
# ---------------------------------------------------------------------------


def test_filter_events_includes_test_events() -> None:
    events = parse_log_file(_FIXTURE)
    filtered = filter_events_for_test(
        events,
        test_id="s1-s1-s1-t3",
        start_time="2026-04-30T18:07:24.149Z",
        end_time="2026-04-30T18:07:24.200Z",
    )
    test_ids = {e.test_id for e in filtered if isinstance(e, GrpcEvent) and e.test_id}
    assert test_ids == {"s1-s1-s1-t3"}


def test_filter_events_excludes_other_test_id() -> None:
    events = parse_log_file(_FIXTURE)
    # The click failure (seq 251-252) at 18:07:25.053Z is outside the window → excluded
    filtered = filter_events_for_test(
        events,
        test_id="s1-s1-s1-t3",
        start_time="2026-04-30T18:07:24.149Z",
        end_time="2026-04-30T18:07:24.200Z",
    )
    seqs = {e.seq for e in filtered if isinstance(e, GrpcEvent)}
    assert 251 not in seqs
    assert 252 not in seqs


def test_filter_events_includes_pwapi_in_window() -> None:
    events = parse_log_file(_FIXTURE)
    filtered = filter_events_for_test(
        events,
        test_id="s1-s1-s1-t3",
        start_time="2026-04-30T18:07:24.149Z",
        end_time="2026-04-30T18:07:24.200Z",
    )
    pwapi = [e for e in filtered if isinstance(e, PwApiEvent)]
    assert len(pwapi) >= 2  # page.pdf started + failed + element visible


def test_filter_events_excludes_before_window() -> None:
    events = parse_log_file(_FIXTURE)
    filtered = filter_events_for_test(
        events,
        test_id="s1-s1-s1-t3",
        start_time="2026-04-30T18:07:24.149Z",
        end_time="2026-04-30T18:07:24.200Z",
    )
    # seq 117 and 118 are before the window
    seqs = {e.seq for e in filtered if isinstance(e, GrpcEvent)}
    assert 117 not in seqs
    assert 118 not in seqs


# ---------------------------------------------------------------------------
# filter_errors_for_test
# ---------------------------------------------------------------------------


def test_filter_errors_returns_only_grpc_errors() -> None:
    events = parse_log_file(_FIXTURE)
    errors = filter_errors_for_test(
        events,
        test_id="s1-s1-s1-t3",
        start_time="2026-04-30T18:07:24.149Z",
        end_time="2026-04-30T18:07:24.200Z",
    )
    assert all(isinstance(e, GrpcEvent) and e.event_kind == "grpc_error" for e in errors)
    assert len(errors) == 1
    assert errors[0].error_type == "Error"
    assert errors[0].test_id == "s1-s1-s1-t3"


def test_filter_errors_excludes_no_context_error_outside_window() -> None:
    events = parse_log_file(_FIXTURE)
    # Window for t3 does not include the click error at 18:07:25.053Z
    errors = filter_errors_for_test(
        events,
        test_id="s1-s1-s1-t3",
        start_time="2026-04-30T18:07:24.149Z",
        end_time="2026-04-30T18:07:24.200Z",
    )
    seqs = {e.seq for e in errors}
    assert 252 not in seqs


def test_filter_errors_includes_no_context_error_in_window() -> None:
    events = parse_log_file(_FIXTURE)
    # Widen the window to include the no-context click error (seq 252)
    errors = filter_errors_for_test(
        events,
        test_id="s1-s1-s1-t3",
        start_time="2026-04-30T18:07:24.149Z",
        end_time="2026-04-30T18:07:25.100Z",
    )
    seqs = {e.seq for e in errors}
    assert 252 in seqs
    assert 127 in seqs


def test_filter_errors_accepts_naive_window_timestamps() -> None:
    events = parse_log_file(_FIXTURE)
    # Real RF data may provide naive timestamps (no timezone suffix).
    errors = filter_errors_for_test(
        events,
        test_id="s1-s1-s1-t3",
        start_time="2026-04-30T18:07:24.149",
        end_time="2026-04-30T18:07:24.200",
    )
    assert len(errors) == 1
    assert errors[0].seq == 127


def test_filter_errors_prefers_same_suite_when_test_id_missing() -> None:
    t = datetime(2026, 5, 1, 11, 1, 10, tzinfo=UTC)
    events = [
        GrpcEvent(
            time=t,
            seq=1,
            level="debug",
            event_kind="grpc",
            action="setRFContext",
            status="succeeded",
            error_type="",
            msg="",
            test_id="s1-s1-s1-t3",
            test_name="Test A",
            suite_id="s1-s1-s1",
            suite_name="Suite A",
            raw="{}",
        ),
        GrpcEvent(
            time=t,
            seq=2,
            level="error",
            event_kind="grpc_error",
            action="click",
            status="failed",
            error_type="TimeoutError",
            msg="suite-matched",
            test_id=None,
            test_name=None,
            suite_id="s1-s1-s1",
            suite_name="Suite A",
            raw="{}",
        ),
        GrpcEvent(
            time=t,
            seq=3,
            level="error",
            event_kind="grpc_error",
            action="click",
            status="failed",
            error_type="TimeoutError",
            msg="suite-mismatch",
            test_id=None,
            test_name=None,
            suite_id="s1-s1-other",
            suite_name="Suite B",
            raw="{}",
        ),
    ]

    errors = filter_errors_for_test(
        events,
        test_id="s1-s1-s1-t3",
        start_time="2026-05-01T11:01:09.500Z",
        end_time="2026-05-01T11:01:10.500Z",
    )

    seqs = {e.seq for e in errors}
    assert 2 in seqs
    assert 3 not in seqs
