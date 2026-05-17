# robotframework-analysis

A local CLI tool for investigating [robotframework-browser](https://github.com/MarketSquare/robotframework-browser) CI failures. Point it at an `output.xml` (and optionally a Playwright log) and it runs a pipeline of specialist LLM agents that identify failure patterns, correlate browser-level evidence, and print a Markdown report.

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — package manager and virtual-env runner
- [Ollama](https://ollama.com/) running locally with `gemma4:e4b` pulled:
  ```
  ollama pull gemma4:e4b
  ```
- (Optional) `GITHUB_TOKEN` env var for the `download` subcommand

---

## Installation

```bash
uv sync
```

This installs the `rfanalysis` CLI into the project's virtual environment.

---

## Usage

### Analyze a local artifact

```bash
uv run rfanalysis analyze output/output.xml
```

With a Playwright log for browser-level evidence:

```bash
uv run rfanalysis analyze output/output.xml \
    --playwright-log output/playwright-log.txt
```

Paths are resolved to absolute before any agent runs — relative paths work from any working directory.

### Download a GitHub Actions artifact

```bash
GITHUB_TOKEN=<token> uv run rfanalysis download \
    "https://github.com/<owner>/<repo>/actions/runs/<run_id>/artifacts/<artifact_id>"
```

Prints artifact metadata and the path of the extracted `output.xml`.

---

## How it works

```
rfanalysis analyze output.xml [--playwright-log ...]
    │
    ├─ RF Results Analyst      always — parses output.xml, groups failures by error pattern
    ├─ Playwright Log Analyst  if --playwright-log given — correlates browser errors per test
    ├─ App Log Analyst         if --app-log given — correlates HTTP events per test
    └─ Screenshot Analyst      if screenshots present in output.xml — OCR + visual analysis
    │
    └─► synthesized Markdown report → stdout
```

File paths are **never passed through the LLM**. They are injected via pydantic-ai `deps_type` at each agent boundary, eliminating path hallucination from small models. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design.

---

## Development

```bash
uv run invoke lint                                        # ruff format + ruff check + mypy
uv run pytest tests/ --ignore=tests/test_ocr.py -q      # unit tests (OCR needs tesseract)
```

Tests use `pytest` with [approvaltests](https://github.com/approvals/ApprovalTests.Python) for agent output snapshots. Approved files live next to the test files as `*.approved.txt` / `*.approved.json`.

