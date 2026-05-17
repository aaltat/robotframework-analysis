# Browser CI Failure Analysis

A context for analyzing Robot Framework Browser CI failures by correlating RF failure data with Playwright log evidence.

## Language

**ADR (Architecture Decision Record)**:
A short record of an important, hard-to-reverse architectural decision and why it was made.
_Avoid_: ARD

**Correlation Policy**:
The ordered rule set used to decide whether a log event belongs to a failed test.
_Avoid_: matching logic, filter heuristic

**Match Source**:
The evidence source used for correlation: `test_id`, `suite_id`, `time_only`, or `anomaly`.
_Avoid_: detection mode, confidence tier

**Suite-Constrained Match**:
When test_id is missing and suite_id exists, the suite_id must match the target suite to include the event.
_Avoid_: loose suite fallback

**Time-Only Fallback**:
If both test_id and suite_id are missing, event inclusion is allowed only when the event is inside the failure time window.
_Avoid_: unconditional fallback

**Endpoint-Uniform Policy**:
The same Correlation Policy applies to all Playwright MCP endpoints; endpoint type does not change matching semantics.
_Avoid_: endpoint-specific correlation exceptions

**Mandatory Match Source**:
Every returned Playwright MCP event and error item must include matched_by; the value set is `test_id`, `suite_id`, `time_only`, or `anomaly`; no separate flag field is used for anomalies.
_Avoid_: optional match provenance

**Test ID Uniqueness**:
Each Robot Framework test must have a unique test_id; different tests sharing one test_id is invalid data.
_Avoid_: reused test identifiers

**Suite Membership**:
Multiple tests can belong to the same suite_id; this is expected and normal.
_Avoid_: one-test-per-suite assumption

**Correlation Anomaly**:
If test_id indicates inclusion but suite_id conflicts with the target suite, include the event and mark it as an anomaly.
_Avoid_: silent mismatch

**Strong Suspect Marker**:
A test_id and suite_id conflict anomaly is treated as a strong signal that upstream context propagation may be wrong.
_Avoid_: low-priority anomaly handling

**Independent Field Interpretation**:
In the Playwright log, test_id and suite_id are treated as independent values emitted separately by upstream; we compare what was emitted and never derive one from the other algorithmically. This scoping matters because the app log uses RF's own hierarchical ID convention (see **RF Hierarchical ID**), where reading the suite prefix from a test ID is parsing a known format, not performing structural inference.
_Avoid_: deriving suite_id from test_id prefix in Playwright log correlation

**RF Hierarchical ID**:
Robot Framework's structured identifier convention for suites and tests. A test ID such as `s1-s1-s1-t5` embeds its suite ID (`s1-s1-s1`) as a prefix. The app log parser reads this known format to determine suite membership; this is not algorithmic inference but parsing an RF-defined structure.
_Avoid_: computed suite_id, inferred suite

**App Log**:
The NDJSON file emitted by the Browser library's Node.js test-app server. Each line is a JSON object with a `timestamp` and `event` field. Event types include: `server_start`, `start_suite`, `end_suite`, `start_test`, `end_test`, `http`, `load`, `click`, `hover`.
_Avoid_: test-app log, server log, node log

**App Log State Machine**:
The algorithm for attributing app log events to tests: walk the log in order, tracking the current active test via `start_test` / `end_test` events. Events between a `start_test` and its matching `end_test` belong to that test. Suite setup events (before the first `start_test`) and teardown events (after the last `end_test`) are attributed to the enclosing suite via **RF Hierarchical ID**.
_Avoid_: time-window matching, event filtering

**Suite Context Inclusion**:
Suite setup events (between `start_suite` and the first `start_test`) and teardown events (between the last `end_test` and `end_suite`) are always included in the response for any test in that suite. This is unconditional — no caller opt-in is required.
_Avoid_: optional suite context, setup-only inclusion

**App Log Time-Range Fallback**:
When `test_id` is provided but no matching `start_test` / `end_test` pair is found in the log (e.g. suite startup failure before RF context was injected), the app log tools fall back to returning events within a provided `start_time` / `end_time` window.
_Avoid_: default fallback, unconditional time filtering

**App Log Server Health Metadata**:
Every app log tool response includes `server_started` (bool: whether a `server_start` event was found) and `total_events_in_log` (int: total parsed events). Callers use this to distinguish "server crashed before startup" from "quiet test window". This replaces per-event provenance for the app log (see ADR-0004).
_Avoid_: per-event provenance on app log events, health flag

**OCR-Authoritative Disagreement Policy**:
When OCR text extraction and multimodal image interpretation disagree, OCR is treated as authoritative for diagnosis in this domain.
_Avoid_: treating multimodal interpretation as equal authority for textual evidence

**Fixed OCR Quality Threshold Policy**:
OCR fallback decisions use fixed, deterministic quality thresholds configured in code or settings; adaptive per-project threshold learning is out of scope for the first version.
_Avoid_: drifting thresholds between runs

**Screenshot No-Evidence Policy**:
When OCR quality is below threshold and no multimodal fallback is available, the screenshot analyst returns `no_evidence` with a reason code; no root cause is guessed from low-quality image data.
_Avoid_: speculative diagnosis from unreadable screenshots

**Screenshot Path Provenance**:
The screenshot analyst sub-agent receives screenshot paths directly from the orchestrator (already resolved by the RF results pipeline); it does not re-derive paths via an MCP tool. However, the sub-agent may call `get_failure_detail` to get broader failure context (log messages, keyword tree) that helps interpret what the screenshot shows.
_Avoid_: re-resolving paths that are already verified by the results pipeline

**Screenshot Analysis Granularity**:
The screenshot analyst is invoked once per error group, using the representative test's screenshots; per-test invocation is out of scope.
_Avoid_: per-test screenshot analysis within a group

**Screenshot Skip Policy**:
When the representative test has no screenshot paths, the orchestrator skips the screenshot analyst entirely and records `no_screenshots` as the reason; it does not call the sub-agent with an empty list.
_Avoid_: calling the screenshot analyst with no input

**Screenshot Analyst Output Contract**:
The screenshot analyst returns one JSON object per error group, synthesizing findings across all screenshots for that group; per-screenshot output is out of scope. The agreed shape is: `test_id`, `screenshot_text`, `visible_error`, `failure_area` (one of `auth | navigation | validation | network | dialog | unknown`), `confidence` (`high | medium | low | no_evidence`), `evidence_source` (`ocr | multimodal | none`), and `reason` (reason code when `no_evidence`, e.g. `no_screenshots | screenshot_unreadable`, otherwise null).
_Avoid_: returning one item per screenshot

**Screenshot Confidence Mapping**:
- `high`: OCR text contains a visible error message that semantically matches the RF failure message or a known error keyword (`error`, `failed`, `invalid`, `denied`, `timeout`).
- `medium`: OCR text is present and plausible but does not directly match the RF failure (e.g. a generic dialog is visible).
- `low`: OCR quality passed threshold but extracted text has no clear failure signal; or multimodal was used and found only a weak visual cue.
- `no_evidence`: no screenshots, unreadable image, or OCR below threshold with no multimodal fallback available.
_Avoid_: using `high` confidence when screenshot text does not correlate with the RF failure

## Relationships

- A **Correlation Policy** defines which **Match Source** can be used and in which order.
- A **Suite-Constrained Match** is a branch of the **Correlation Policy**.
- **Time-Only Fallback** is the last-resort branch of the **Correlation Policy**.
- An **Endpoint-Uniform Policy** means all endpoints share one correlation contract.
- **Mandatory Match Source** makes provenance explicit on every returned item.
- **Test ID Uniqueness** means test_id is the strongest identifier when present.
- **Suite Membership** allows many tests to share one suite_id.
- A **Correlation Anomaly** is included evidence plus a diagnostic signal.
- A **Strong Suspect Marker** elevates anomaly visibility for debugging.
- **Independent Field Interpretation** is scoped to the Playwright log; it does not apply to **RF Hierarchical ID** parsing in the app log.
- **RF Hierarchical ID** is used by **App Log State Machine** to determine suite membership for **Suite Context Inclusion**.
- **App Log State Machine** is the primary attribution algorithm; **App Log Time-Range Fallback** activates only when no matching lifecycle pair is found in the log.
- **Suite Context Inclusion** is unconditional — it always applies when **App Log State Machine** is used.
- **App Log Server Health Metadata** gives callers a response-level signal about server startup failures, replacing per-event provenance for the app log (see **Mandatory Match Source** for why this differs from the Playwright approach, and ADR-0004).
- **OCR-Authoritative Disagreement Policy** defines conflict resolution between screenshot evidence extractors.
- **Fixed OCR Quality Threshold Policy** keeps screenshot routing deterministic and testable.
- **Screenshot No-Evidence Policy** prevents false diagnosis from unreadable images.
- **Screenshot Path Provenance** avoids duplicating resolution logic that lives in the results pipeline.
- **Screenshot Analysis Granularity** aligns screenshot analysis with the error group model, not per-test.
- **Screenshot Skip Policy** prevents wasted sub-agent calls when no visual evidence exists.
- **Screenshot Analyst Output Contract** keeps the orchestrator's merge logic consistent across all analyst sub-agents.
- **Screenshot Confidence Mapping** defines when screenshot evidence is strong enough to include in the final report.
- An **ADR (Architecture Decision Record)** records why a **Correlation Policy** was chosen.

## Example dialogue

> **Dev:** "This event has no test_id. Should we still include it for the failed test?"
> **Domain expert:** "Only if suite_id matches; if there is no suite_id either, include it only by time-window fallback."

## Flagged ambiguities

- "ARD" and "ADR" were used interchangeably. Resolved: canonical term is **ADR (Architecture Decision Record)**.
