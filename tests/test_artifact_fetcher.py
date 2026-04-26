from __future__ import annotations

import asyncio
import io
import zipfile
from typing import TYPE_CHECKING

import httpx
import pytest

from robotframework_analysis.artifacts.fetcher import (
    ArtifactFetchError,
    fetch_artifact_bundle,
    parse_artifact_url,
)

if TYPE_CHECKING:
    from pathlib import Path


def _run(coro: object) -> object:
    return asyncio.run(coro)  # type: ignore[arg-type]


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_parse_artifact_url_valid() -> None:
    url = "https://github.com/MarketSquare/robotframework-browser/actions/runs/24936397462/artifacts/6641439436"
    assert parse_artifact_url(url) == (
        "MarketSquare",
        "robotframework-browser",
        24936397462,
        6641439436,
    )


def test_parse_artifact_url_invalid_path() -> None:
    with pytest.raises(ArtifactFetchError, match="Artifact URL path"):
        parse_artifact_url("https://github.com/org/repo/actions/jobs/123")


def test_parse_artifact_url_invalid_host() -> None:
    with pytest.raises(ArtifactFetchError, match="Artifact URL must be"):
        parse_artifact_url("https://example.com/org/repo/actions/runs/1/artifacts/2")


def test_parse_artifact_url_non_integer_ids() -> None:
    with pytest.raises(ArtifactFetchError, match="must be integers"):
        parse_artifact_url("https://github.com/org/repo/actions/runs/not-a-number/artifacts/two")


def test_fetch_artifact_bundle_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(ArtifactFetchError, match="GitHub token is required"):
        _run(fetch_artifact_bundle("https://github.com/org/repo/actions/runs/1/artifacts/2"))


def test_fetch_artifact_bundle_follows_redirect_and_extracts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    artifact_url = "https://github.com/org/repo/actions/runs/10/artifacts/20"
    zip_payload = _zip_bytes(
        {
            "results/output.xml": "<robot></robot>",
            "results/playwright-log-1.txt": "2026-01-01T00:00:00.000Z pw:api => click",
            "results/app.log": "INFO service started",
            "results/screenshot.png": "png-data",
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/org/repo/actions/artifacts/20":
            return httpx.Response(
                200,
                json={
                    "name": "artifact-name",
                    "archive_download_url": "https://api.github.com/artifact/archive/20",
                },
            )
        if request.url.path == "/artifact/archive/20":
            return httpx.Response(
                302,
                headers={"Location": "https://objects.githubusercontent.com/archive/20.zip"},
            )
        if request.url.host == "objects.githubusercontent.com":
            return httpx.Response(200, content=zip_payload)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    async def run_test() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            bundle = await fetch_artifact_bundle(artifact_url, client=client)

        assert bundle.run_id == 10
        assert bundle.job_id == 20
        assert bundle.artifact_filename == "artifact-name"
        assert bundle.output_xml.name == "output.xml"
        assert bundle.playwright_log_dir is not None
        assert bundle.playwright_log_dir.name == "results"
        assert [path.name for path in bundle.app_logs] == ["app.log"]
        assert [path.name for path in bundle.screenshots] == ["screenshot.png"]

    _run(run_test())


def test_fetch_artifact_bundle_retries_transient_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    artifact_url = "https://github.com/org/repo/actions/runs/10/artifacts/20"
    zip_payload = _zip_bytes({"output.xml": "<robot></robot>"})
    call_count = {"archive": 0}
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/org/repo/actions/artifacts/20":
            return httpx.Response(
                200,
                json={
                    "name": "artifact-name",
                    "archive_download_url": "https://api.github.com/artifact/archive/20",
                },
            )
        if request.url.path == "/artifact/archive/20":
            call_count["archive"] += 1
            if call_count["archive"] < 3:
                return httpx.Response(503)
            return httpx.Response(200, content=zip_payload)
        return httpx.Response(404)

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    transport = httpx.MockTransport(handler)

    async def run_test() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            bundle = await fetch_artifact_bundle(
                artifact_url,
                client=client,
                sleep_func=fake_sleep,
                retry_delays=(0.5, 1.0, 10.0),
            )

        assert bundle.output_xml.name == "output.xml"

    _run(run_test())

    assert sleeps == [0.5, 1.0]
    assert sum(sleeps) <= 5.0


def test_fetch_artifact_bundle_requires_single_output_xml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    artifact_url = "https://github.com/org/repo/actions/runs/10/artifacts/20"
    zip_payload = _zip_bytes({"not-output.txt": "x"})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/org/repo/actions/artifacts/20":
            return httpx.Response(
                200,
                json={
                    "name": "artifact-name",
                    "archive_download_url": "https://api.github.com/artifact/archive/20",
                },
            )
        if request.url.path == "/artifact/archive/20":
            return httpx.Response(200, content=zip_payload)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    async def run_test() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ArtifactFetchError, match=r"Expected exactly one output\.xml"):
                await fetch_artifact_bundle(artifact_url, client=client)

    _run(run_test())


def test_fetch_artifact_bundle_uses_given_extract_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    artifact_url = "https://github.com/org/repo/actions/runs/10/artifacts/20"
    zip_payload = _zip_bytes({"output.xml": "<robot></robot>"})
    destination = tmp_path / "artifact-destination"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/org/repo/actions/artifacts/20":
            return httpx.Response(
                200,
                json={
                    "name": "artifact-name",
                    "archive_download_url": "https://api.github.com/artifact/archive/20",
                },
            )
        if request.url.path == "/artifact/archive/20":
            return httpx.Response(200, content=zip_payload)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    async def run_test() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            bundle = await fetch_artifact_bundle(
                artifact_url,
                client=client,
                extract_dir=destination,
            )

        assert bundle.temp_dir == destination.resolve()
        assert (destination / "output.xml").exists()

    _run(run_test())


def test_fetch_artifact_bundle_ignores_pabot_results_output_xml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    artifact_url = "https://github.com/org/repo/actions/runs/10/artifacts/20"
    zip_payload = _zip_bytes(
        {
            "output.xml": "<robot></robot>",
            "pabot_results/0/output.xml": "<robot>ignore</robot>",
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/org/repo/actions/artifacts/20":
            return httpx.Response(
                200,
                json={
                    "name": "artifact-name",
                    "archive_download_url": "https://api.github.com/artifact/archive/20",
                },
            )
        if request.url.path == "/artifact/archive/20":
            return httpx.Response(200, content=zip_payload)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    async def run_test() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            bundle = await fetch_artifact_bundle(artifact_url, client=client)

        assert bundle.output_xml.parts[-1] == "output.xml"
        assert "pabot_results" not in bundle.output_xml.parts

    _run(run_test())


def test_fetch_artifact_bundle_rejects_invalid_metadata_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    transport = httpx.MockTransport(handler)

    async def run_test() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ArtifactFetchError, match="was not valid JSON"):
                await fetch_artifact_bundle(
                    "https://github.com/org/repo/actions/runs/10/artifacts/20",
                    client=client,
                )

    _run(run_test())


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        ({"archive_download_url": "https://api.github.com/artifact/archive/20"}, "artifact name"),
        ({"name": "artifact-name"}, "archive_download_url"),
    ],
)
def test_fetch_artifact_bundle_rejects_incomplete_metadata(
    monkeypatch: pytest.MonkeyPatch,
    metadata: dict[str, str],
    message: str,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=metadata)

    transport = httpx.MockTransport(handler)

    async def run_test() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ArtifactFetchError, match=message):
                await fetch_artifact_bundle(
                    "https://github.com/org/repo/actions/runs/10/artifacts/20",
                    client=client,
                )

    _run(run_test())


@pytest.mark.parametrize(
    ("status_code", "message"),
    [
        (401, "rejected credentials"),
        (404, "no longer available"),
        (418, "status 418"),
    ],
)
def test_fetch_artifact_bundle_surfaces_non_retriable_http_errors(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    message: str,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code)

    transport = httpx.MockTransport(handler)

    async def run_test() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ArtifactFetchError, match=message):
                await fetch_artifact_bundle(
                    "https://github.com/org/repo/actions/runs/10/artifacts/20",
                    client=client,
                )

    _run(run_test())


def test_fetch_artifact_bundle_fails_after_connection_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    transport = httpx.MockTransport(handler)

    async def run_test() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ArtifactFetchError, match="failed after retries"):
                await fetch_artifact_bundle(
                    "https://github.com/org/repo/actions/runs/10/artifacts/20",
                    client=client,
                    sleep_func=fake_sleep,
                    retry_delays=(0.1, 0.2),
                )

    _run(run_test())

    assert sleeps == [0.1, 0.2]


def test_fetch_artifact_bundle_rejects_invalid_zip_archive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/org/repo/actions/artifacts/20":
            return httpx.Response(
                200,
                json={
                    "name": "artifact-name",
                    "archive_download_url": "https://api.github.com/artifact/archive/20",
                },
            )
        if request.url.path == "/artifact/archive/20":
            return httpx.Response(200, content=b"not-a-zip")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    async def run_test() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ArtifactFetchError, match="not a valid zip archive"):
                await fetch_artifact_bundle(
                    "https://github.com/org/repo/actions/runs/10/artifacts/20",
                    client=client,
                )

    _run(run_test())


def test_fetch_artifact_bundle_rejects_unsafe_zip_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    zip_payload = _zip_bytes({"../escape/output.xml": "<robot></robot>"})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/org/repo/actions/artifacts/20":
            return httpx.Response(
                200,
                json={
                    "name": "artifact-name",
                    "archive_download_url": "https://api.github.com/artifact/archive/20",
                },
            )
        if request.url.path == "/artifact/archive/20":
            return httpx.Response(200, content=zip_payload)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    async def run_test() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ArtifactFetchError, match="Unsafe zip entry"):
                await fetch_artifact_bundle(
                    "https://github.com/org/repo/actions/runs/10/artifacts/20",
                    client=client,
                )

    _run(run_test())
