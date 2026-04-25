from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class ArtifactBundle:
    source_url: str
    run_id: int
    job_id: int
    artifact_filename: str
    output_xml: Path
    screenshots: list[Path]
    playwright_log_dir: Path | None
    app_logs: list[Path]
    temp_dir: Path
