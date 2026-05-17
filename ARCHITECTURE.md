# Architecture: Browser CI Failure Analyst

## Overview

A local CLI tool for investigating [robotframework-browser](https://github.com/MarketSquare/robotframework-browser) CI failures. Given a GitHub Actions artifact URL the tool downloads it; given a local `output.xml` it runs specialist agents against it and prints a Markdown report.

---

## CLI Entry Point

Installed as `rfanalysis` via `[project.scripts]` in `pyproject.toml`. Two subcommands:

```
rfanalysis download <github_artifact_url>   # download & inspect an artifact
rfanalysis analyze  <output_xml> [--playwright-log <path>]  # run the analysis agents
```

`download` fetches the artifact from GitHub and prints its contents.
`analyze` resolves all paths to absolute, builds a `DelegateContext`, and runs the orchestrator agent synchronously.

---

## Key Design Principle: Deps Injection

Small LLMs (e.g. `gemma4`) reliably hallucinate file paths when those paths appear in free-form prompt text — they construct plausible-looking paths from context clues (test IDs, timestamps) rather than passing through the literal string given to them.

**File paths never travel through the LLM.** They are injected at each agent boundary via pydantic-ai `deps_type`:

| Context class | Holder | Fields |
|---|---|---|
| `DelegateContext` | `delegate.py` | `output_xml`, `playwright_log`, `app_log` |
| `PlaywrightAnalystContext` | `playwright_log_analyst.py` | `log_file` |
| `AppLogAnalystContext` | `app_log_analyst.py` | `log_file` |

The CLI builds a `DelegateContext` and passes it as `deps=` to `delegate_agent.run_sync()`. The delegate's tools read paths from `ctx.deps` and, when spawning sub-agents, pass a typed context as `deps=` to each sub-agent's `agent.run()`. The LLM prompt contains no file paths at any level.

---

## Layers

### Layer 1 — Artifact Fetcher *(plain async utility, no agent)*

`artifacts/fetcher.py` parses the artifact URL (`/actions/runs/{run_id}/artifacts/{id}`) → GitHub REST API:
- `/repos/{owner}/{repo}/actions/artifacts/{id}` to resolve metadata and `archive_download_url`
- Download archive zip (follow redirects) and extract into a temp directory

Returns an `ArtifactBundle` (`artifacts/bundle.py`):

```python
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
    temp_dir: Path              # caller is responsible for cleanup
```

---

### Layer 2 — Orchestrator Agent *(delegate.py)*

`delegate_agent` is a `pydantic-ai` `Agent[DelegateContext, str]`. The `DelegateContext` deps hold all file paths — they never appear in any prompt. The agent's system prompt tells it to call specialist tools in a fixed order and synthesize their outputs.

Registered tools (all `async`, read paths from `ctx.deps`):

| Tool | What it does |
|---|---|
| `analyze_failures` | Runs the RF Results Analyst via its MCP server |
| `analyze_playwright_failures` | For each error group: runs the Playwright Log Analyst |
| `analyze_app_log_failures` | For each error group: runs the App Log Analyst |
| `analyze_screenshot_failures` | For each error group with screenshots: runs OCR + Screenshot Analyst |

`analyze_playwright_failures` and `analyze_app_log_failures` return `"[]"` immediately (no LLM call) when the corresponding path is absent from `ctx.deps`.

---

### Layer 3 — Specialist Agents

| Agent | File | `deps_type` | Model |
|---|---|---|---|
| **RF Results Analyst** | `agent/failure_analyst.py` | none — `output_xml` in prompt | `ollama:gemma4:e4b` |
| **Playwright Log Analyst** | `agent/playwright_log_analyst.py` | `PlaywrightAnalystContext` | `ollama:gemma4:e4b` |
| **App Log Analyst** | `agent/app_log_analyst.py` | `AppLogAnalystContext` | `ollama:gemma4:e4b` |
| **Screenshot Analyst** | `agent/screenshot_analyst.py` | none — uses OCR text | `ollama:gemma4:e4b` |

The Playwright and App Log analysts are built by factory functions (`build_playwright_analyst_agent`, `build_app_log_analyst_agent`). Each call creates a fresh `Agent` instance with pydantic-ai tools that call the underlying MCP server functions directly (bypassing `FastMCPToolset` so the LLM never needs to supply a `log_file` argument).

OCR text extraction (`agent/ocr.py`) runs outside the LLM — extracted text is embedded in the screenshot analyst's prompt.

---

### Layer 4 — Output

The orchestrator agent's final output is a Markdown report printed to stdout. There is no separate report generator layer at this time.

---

## MCP Servers

MCP servers live under `mcp/` and are used as plain Python modules by the specialist agents (the tools call the server functions directly). They also expose a `FastMCP` instance that can be run as a standalone MCP server if needed.

### RF Results MCP (`mcp/results/server.py`)

| Tool | Args | Returns |
|---|---|---|
| `get_test_run_summary` | `output_xml` | `TestRunSummary` with error groups and `test_id`s |
| `get_failure_detail` | `output_xml`, `suite_name`, `test_name` | `FailureDetail` with log messages and keyword tree |
| `get_screenshot_paths` | `output_xml` | list of absolute screenshot paths |

Results are cached by `(path, mtime)` — re-parsed only when the file changes.

### Playwright Log MCP (`mcp/playwright/server.py`)

Handles two co-existing line formats in `playwright-log-*.txt` files:

| Format | Example |
|---|---|
| JSON (pino) | `{"level":30,"time":"2026-04-23T11:27:02.773Z","seq":1,...,"msg":"..."}` |
| Plain text | `2026-04-23T11:27:03.290Z pw:api => browserType.launch started` |

| Tool | Args | Returns |
|---|---|---|
| `get_playwright_errors_for_test` | `log_file`, `test_id`, `start_time`, `end_time` | list of `PlaywrightErrorItem` |
| `get_playwright_events_for_test` | `log_file`, `test_id`, `start_time`, `end_time` | list of `PlaywrightEventItem` |

Events are matched to a test by `test_id` in the JSON payload; fallback: time-window overlap.

### App Log MCP (`mcp/app_log/server.py`)

Handles Browser library test-app NDJSON log files. Events include HTTP requests, page loads, clicks, and RF lifecycle markers (`start_test`, `end_test`).

| Tool | Args | Returns |
|---|---|---|
| `get_app_log_http_for_test` | `log_file`, `test_id`, `start_time?`, `end_time?` | dict with `server_started`, `events` (HTTP only) |
| `get_app_log_events_for_test` | `log_file`, `test_id`, `start_time?`, `end_time?` | dict with `server_started`, `events` (all types) |

---

## Complete Data Flow

```
rfanalysis analyze output.xml [--playwright-log playwright-log.txt]
        │
        ▼ (cli.py: resolve paths → DelegateContext)
        │
        ▼
[Orchestrator — delegate_agent]
  deps: DelegateContext(output_xml, playwright_log, app_log)
        │
        ├─► analyze_failures
        │     └─ RF Results Analyst (failure_analyst.py)
        │          └─ MCP: get_test_run_summary(output_xml)
        │               → error_groups JSON (test_id, start_time, end_time, screenshots)
        │
        ├─► analyze_playwright_failures   (skipped if playwright_log is None)
        │     for each error group:
        │       └─ Playwright Log Analyst
        │            deps: PlaywrightAnalystContext(log_file)
        │            └─ get_playwright_errors_for_test(log_file, test_id, ...)
        │
        ├─► analyze_app_log_failures      (skipped if app_log is None)
        │     for each error group:
        │       └─ App Log Analyst
        │            deps: AppLogAnalystContext(log_file)
        │            └─ get_app_log_http_for_test(log_file, test_id, ...)
        │
        └─► analyze_screenshot_failures   (skipped if no screenshots)
              for each group with screenshots:
                └─ OCR → Screenshot Analyst
        │
        ▼
  synthesized Markdown report → stdout
```

---

## File Layout

```
src/robotframework_analysis/
  cli.py                            ← entry point: rfanalysis download / analyze
  artifacts/
    bundle.py                       ← ArtifactBundle dataclass
    fetcher.py                      ← GitHub API download + zip extract
  agent/
    delegate.py                     ← orchestrator agent + DelegateContext
    failure_analyst.py              ← RF Results Analyst
    playwright_log_analyst.py       ← Playwright Log Analyst + PlaywrightAnalystContext
    app_log_analyst.py              ← App Log Analyst + AppLogAnalystContext
    screenshot_analyst.py           ← Screenshot Analyst
    ocr.py                          ← OCR text extraction (pytesseract)
  mcp/
    results/
      server.py                     ← FastMCP: get_test_run_summary, get_failure_detail
      models.py                     ← TestRunSummary, FailureDetail pydantic models
      results_analysis.py           ← output.xml parser
    playwright/
      server.py                     ← FastMCP: get_playwright_errors/events_for_test
      log_parser.py                 ← playwright-log-*.txt parser
    app_log/
      server.py                     ← FastMCP: get_app_log_http/events_for_test
      log_parser.py                 ← NDJSON app log parser
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `pydantic-ai` | Agent framework + deps injection |
| `fastmcp` | MCP server (also called as plain Python functions) |
| `httpx` | GitHub API calls |
| `python-dotenv` | `.env` token loading |
| `robotframework` | `output.xml` parsing via RF's result model |
| `pytesseract` | OCR text extraction from screenshots |

Model access: Ollama running on `localhost:11434` (or overridden via `OLLAMA_BASE_URL`).

