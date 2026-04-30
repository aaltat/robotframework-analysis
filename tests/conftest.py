from __future__ import annotations

import os

from approvaltests import set_default_reporter
from approvaltests.reporters import GenericDiffReporter
from approvaltests.reporters.generic_diff_reporter_config import GenericDiffReporterConfig

# Use VS Code as the default ApprovalTests diff editor.
set_default_reporter(
    GenericDiffReporter(
        GenericDiffReporterConfig("vscode", "code", ["--wait", "--diff", "%s", "%s"])
    )
)

# Allow agent modules that construct an Agent at import time to load without a
# running Ollama instance.  The base URL is intentionally non-functional; tests
# that need a real model should use TestModel instead.
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434/v1")
