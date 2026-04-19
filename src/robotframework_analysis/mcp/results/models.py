from __future__ import annotations

from pydantic import BaseModel


class FailedTestRef(BaseModel):
    suite_name: str
    test_name: str
    source_path: str
    error_prefix: str
    short_error: str


class ErrorGroup(BaseModel):
    group_id: int
    error_prefix: str
    representative_error: str
    tests: list[FailedTestRef]


class RunTotals(BaseModel):
    total: int
    passed: int
    failed: int
    skipped: int


class TestRunSummary(BaseModel):
    suite_name: str
    start_time: str
    end_time: str
    totals: RunTotals
    error_groups: list[ErrorGroup]


class FailureDetail(BaseModel):
    suite_name: str
    test_name: str
    message: str
    log_messages: list[str]
    keyword_leaf: list[str]
    test_source: str
    last_user_keyword_source: str | None
    failing_library: str | None
    screenshot_paths: list[str] = []
