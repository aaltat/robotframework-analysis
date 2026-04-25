"""Artifact fetching utilities for CI analysis."""

from robotframework_analysis.artifacts.bundle import ArtifactBundle
from robotframework_analysis.artifacts.fetcher import (
    ArtifactFetchError,
    fetch_artifact_bundle,
    parse_artifact_url,
)

__all__ = [
    "ArtifactBundle",
    "ArtifactFetchError",
    "fetch_artifact_bundle",
    "parse_artifact_url",
]
