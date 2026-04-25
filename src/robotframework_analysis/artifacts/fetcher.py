from __future__ import annotations

import asyncio
import io
import os
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx

from robotframework_analysis.artifacts.bundle import ArtifactBundle

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

_RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_DEFAULT_RETRY_DELAYS = (0.5, 1.0, 1.5, 2.0)
_MAX_RETRY_DELAY_SECONDS = 5.0
_URL_MIN_SEGMENTS = 7
_STATUS_OK_MAX = 399
_STATUS_NOT_FOUND = 404


class ArtifactFetchError(RuntimeError):
    """Raised when an artifact cannot be fetched or parsed."""


@dataclass(frozen=True)
class _ArtifactUrlParts:
    owner: str
    repo: str
    run_id: int
    job_id: int


def parse_artifact_url(artifact_url: str) -> tuple[str, str, int, int]:
    """Parse a GitHub artifact URL and return owner, repo, run_id and trailing id."""
    parts = _parse_artifact_url(artifact_url)
    return (parts.owner, parts.repo, parts.run_id, parts.job_id)


def _parse_artifact_url(artifact_url: str) -> _ArtifactUrlParts:
    parsed = urlparse(artifact_url)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        msg = (
            "Artifact URL must be an https://github.com URL like "
            "https://github.com/<owner>/<repo>/actions/runs/<run_id>/artifacts/<id>"
        )
        raise ArtifactFetchError(msg)

    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < _URL_MIN_SEGMENTS:
        msg = "Artifact URL path is incomplete."
        raise ArtifactFetchError(msg)

    owner, repo, actions, runs, run_id_raw, artifacts, job_id_raw = segments[:7]
    if actions != "actions" or runs != "runs" or artifacts != "artifacts":
        msg = "Artifact URL path must be /<owner>/<repo>/actions/runs/<run_id>/artifacts/<id>."
        raise ArtifactFetchError(msg)

    try:
        run_id = int(run_id_raw)
        job_id = int(job_id_raw)
    except ValueError as exc:
        msg = "run_id and artifact id must be integers in the artifact URL."
        raise ArtifactFetchError(msg) from exc

    return _ArtifactUrlParts(owner=owner, repo=repo, run_id=run_id, job_id=job_id)


async def fetch_artifact_bundle(  # noqa: PLR0913
    artifact_url: str,
    *,
    extract_dir: Path | None = None,
    token: str | None = None,
    token_env_var: str = "GITHUB_TOKEN",  # noqa: S107
    client: httpx.AsyncClient | None = None,
    retry_delays: Sequence[float] = _DEFAULT_RETRY_DELAYS,
    sleep_func: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> ArtifactBundle:
    """Download and extract a GitHub Actions artifact from a direct artifact URL."""
    url_parts = _parse_artifact_url(artifact_url)
    api_token = token or os.getenv(token_env_var)
    if not api_token:
        msg = f"GitHub token is required. Set {token_env_var}."
        raise ArtifactFetchError(msg)

    bounded_delays = _bounded_delays(retry_delays, _MAX_RETRY_DELAY_SECONDS)

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Accept": "application/vnd.github+json",
    }

    own_client = client is None
    http_client = client or httpx.AsyncClient(timeout=10.0)

    metadata_url = f"https://api.github.com/repos/{url_parts.owner}/{url_parts.repo}/actions/artifacts/{url_parts.job_id}"

    try:
        metadata_response = await _request_with_retry(
            http_client,
            method="GET",
            url=metadata_url,
            headers=headers,
            retry_delays=bounded_delays,
            sleep_func=sleep_func,
            follow_redirects=False,
        )
        try:
            metadata = metadata_response.json()
        except ValueError as exc:
            msg = "GitHub artifact metadata response was not valid JSON."
            raise ArtifactFetchError(msg) from exc

        artifact_filename = metadata.get("name")
        archive_download_url = metadata.get("archive_download_url")
        if not isinstance(artifact_filename, str) or not artifact_filename:
            msg = "GitHub artifact metadata did not include a valid artifact name."
            raise ArtifactFetchError(msg)
        if not isinstance(archive_download_url, str) or not archive_download_url:
            msg = "GitHub artifact metadata did not include archive_download_url."
            raise ArtifactFetchError(msg)

        archive_response = await _request_with_retry(
            http_client,
            method="GET",
            url=archive_download_url,
            headers=headers,
            retry_delays=bounded_delays,
            sleep_func=sleep_func,
            follow_redirects=True,
        )

        destination_dir = _resolve_extract_dir(extract_dir)
        _extract_archive_safely(archive_response.content, destination_dir)
        output_xml = _discover_single_output_xml(destination_dir)
        screenshots = _discover_screenshots(destination_dir)
        playwright_log_dir = _discover_playwright_log_dir(destination_dir)
        app_logs = _discover_app_logs(destination_dir)

        return ArtifactBundle(
            source_url=artifact_url,
            run_id=url_parts.run_id,
            job_id=url_parts.job_id,
            artifact_filename=artifact_filename,
            output_xml=output_xml,
            screenshots=screenshots,
            playwright_log_dir=playwright_log_dir,
            app_logs=app_logs,
            temp_dir=destination_dir,
        )
    finally:
        if own_client:
            await http_client.aclose()


def _bounded_delays(delays: Sequence[float], limit_seconds: float) -> tuple[float, ...]:
    bounded: list[float] = []
    total = 0.0
    for delay in delays:
        if delay <= 0:
            continue
        if total + delay > limit_seconds:
            break
        bounded.append(delay)
        total += delay
    return tuple(bounded)


def _resolve_extract_dir(extract_dir: Path | None) -> Path:
    if extract_dir is None:
        return Path(tempfile.mkdtemp(prefix="rfanalysis-artifact-"))
    extract_dir.mkdir(parents=True, exist_ok=True)
    return extract_dir.resolve()


async def _request_with_retry(  # noqa: PLR0913
    client: httpx.AsyncClient,
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    retry_delays: Sequence[float],
    sleep_func: Callable[[float], Awaitable[None]],
    follow_redirects: bool,
) -> httpx.Response:
    attempt = 0
    while True:
        attempt += 1
        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                follow_redirects=follow_redirects,
            )
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
            if attempt > len(retry_delays):
                msg = f"Request to {url} failed after retries."
                raise ArtifactFetchError(msg) from exc
            await sleep_func(retry_delays[attempt - 1])
            continue

        status = response.status_code
        if status <= _STATUS_OK_MAX:
            return response

        if status in _RETRIABLE_STATUS_CODES:
            if attempt > len(retry_delays):
                msg = f"Request to {url} failed with status {status} after retries."
                raise ArtifactFetchError(msg)
            await sleep_func(retry_delays[attempt - 1])
            continue

        if status in {401, 403}:
            msg = "GitHub rejected credentials for artifact download."
            raise ArtifactFetchError(msg)
        if status == _STATUS_NOT_FOUND:
            msg = "Artifact not found or no longer available."
            raise ArtifactFetchError(msg)

        msg = f"GitHub request failed with status {status}."
        raise ArtifactFetchError(msg)


def _extract_archive_safely(archive_bytes: bytes, destination: Path) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            _safe_extract(archive, destination)
    except zipfile.BadZipFile as exc:
        msg = "Downloaded artifact is not a valid zip archive."
        raise ArtifactFetchError(msg) from exc


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    destination_resolved = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if destination_resolved not in target.parents and target != destination_resolved:
            msg = f"Unsafe zip entry detected: {member.filename}"
            raise ArtifactFetchError(msg)
    archive.extractall(destination)


def _discover_single_output_xml(temp_dir: Path) -> Path:
    output_candidates = sorted(
        path for path in temp_dir.rglob("output.xml") if "pabot_results" not in path.parts
    )
    if len(output_candidates) != 1:
        msg = (
            "Expected exactly one output.xml in the artifact bundle, "
            f"found {len(output_candidates)}."
        )
        raise ArtifactFetchError(msg)
    return output_candidates[0]


def _discover_screenshots(temp_dir: Path) -> list[Path]:
    screenshot_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    screenshots = [
        path
        for path in temp_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in screenshot_exts
    ]
    return sorted(screenshots)


def _discover_playwright_log_dir(temp_dir: Path) -> Path | None:
    logs = sorted(temp_dir.rglob("playwright-log-*.txt"))
    if not logs:
        return None
    return logs[0].parent


def _discover_app_logs(temp_dir: Path) -> list[Path]:
    app_logs: list[Path] = []
    for path in temp_dir.rglob("*.log"):
        if path.name.startswith("playwright-log-"):
            continue
        app_logs.append(path)
    return sorted(app_logs)
