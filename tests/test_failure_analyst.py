from __future__ import annotations

import asyncio
from pathlib import Path

from approvaltests import settings, verify
from approvaltests.core.options import Options
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from robot import run as robot_run  # type: ignore[attr-defined]

from robotframework_analysis.agent.failure_analyst import _SYSTEM_PROMPT

_CANNED_ANALYSIS = """\
## Test Run Analysis

**6 failures** across **5 error groups**.

### Error Group 1 — ValueError (Database)
- Root cause: database connection timeout to `host.example.com:5432`
- Tests affected: Database Error One, Database Error Two
- Fix: check DB credentials and network connectivity in CI environment

### Error Group 2 — TypeError (Login)
- Root cause: `None` passed where a `str` is expected in `process_user_data()`
- Tests affected: Login Timeout
- Fix: validate user data before calling the function

### Error Group 3 — Assertion (HTTP)
- Root cause: server returned 403 instead of 200
- Tests affected: Printed Failure
- Fix: ensure the test user has the required role

### Error Group 4 — Setup failure
- Root cause: test setup keyword raised an error before the test body ran
- Tests affected: Setup Failure Case
- Fix: investigate the setup keyword

### Error Group 5 — Teardown failure
- Root cause: test teardown failed to clean up resources
- Tests affected: Teardown Failure Case
- Fix: make the teardown keyword idempotent
"""


def _run_fixture(fixture_name: str, tmp_path: Path) -> str:
    suite_file = Path(__file__).parent / "fixtures" / fixture_name
    output_xml = tmp_path / "output.xml"
    robot_run(str(suite_file), output=str(output_xml), log="NONE", report="NONE", loglevel="TRACE")
    return str(output_xml)


def test_system_prompt_mentions_get_test_run_summary() -> None:
    assert "get_test_run_summary" in _SYSTEM_PROMPT


def test_system_prompt_mentions_get_failure_detail() -> None:
    assert "get_failure_detail" in _SYSTEM_PROMPT


def test_system_prompt_mentions_root_cause() -> None:
    assert "root cause" in _SYSTEM_PROMPT.lower()


def test_analyze_failures_approval(tmp_path: Path) -> None:
    settings().allow_multiple_verify_calls_for_this_method()
    output_xml = _run_fixture("error_groups_suite.robot", tmp_path)

    test_agent: Agent[None, str] = Agent(
        model=TestModel(call_tools=[], custom_output_text=_CANNED_ANALYSIS),
        system_prompt=_SYSTEM_PROMPT,
    )
    output = asyncio.run(
        test_agent.run(f"Analyze the Robot Framework test results in: {output_xml}")
    )

    verify(output.output, options=Options().for_file.with_extension(".txt"))


def test_analyze_failures_returns_string_with_test_model(tmp_path: Path) -> None:
    output_xml = _run_fixture("summary_suite.robot", tmp_path)

    test_agent: Agent[None, str] = Agent(
        model=TestModel(call_tools=[], custom_output_text="ok"),
        system_prompt=_SYSTEM_PROMPT,
    )
    result = asyncio.run(
        test_agent.run(f"Analyze the Robot Framework test results in: {output_xml}")
    )

    assert isinstance(result.output, str)
    assert result.output == "ok"
