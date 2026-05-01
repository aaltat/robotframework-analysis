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
test_id and suite_id are treated as independent values emitted separately by upstream; we compare what was emitted and never derive one from the other algorithmically.
_Avoid_: deriving suite_id from test_id prefix

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
- **Independent Field Interpretation** means we compare emitted values; structural derivation is out of scope.
- An **ADR (Architecture Decision Record)** records why a **Correlation Policy** was chosen.

## Example dialogue

> **Dev:** "This event has no test_id. Should we still include it for the failed test?"
> **Domain expert:** "Only if suite_id matches; if there is no suite_id either, include it only by time-window fallback."

## Flagged ambiguities

- "ARD" and "ADR" were used interchangeably. Resolved: canonical term is **ADR (Architecture Decision Record)**.
