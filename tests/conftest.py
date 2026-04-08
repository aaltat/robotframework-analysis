from __future__ import annotations

from approvaltests import set_default_reporter
from approvaltests.reporters import GenericDiffReporter
from approvaltests.reporters.generic_diff_reporter_config import GenericDiffReporterConfig

# Use VS Code as the default ApprovalTests diff editor.
set_default_reporter(
    GenericDiffReporter(
        GenericDiffReporterConfig("vscode", "code", ["--wait", "--diff", "%s", "%s"])
    )
)
