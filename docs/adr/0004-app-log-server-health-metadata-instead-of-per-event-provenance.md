# App Log Tools Use Response-Level Server Health Metadata Instead of Per-Event Provenance

ADR-0002 mandates a `matched_by` field on every Playwright MCP response item to expose how reliably each event was correlated. The app log MCP tools deliberately do not follow this pattern.

The app log's correlation is structurally unambiguous: Robot Framework emits explicit `start_test` / `end_test` lifecycle events in the same file, so an event either falls between those boundaries for the target test or it does not. There is no equivalent to Playwright's `time_only` or `anomaly` sources — no event can be "weakly" attributed to a test.

The one genuine ambiguity is not about individual events but about the log itself: if the server never started or crashed on startup, the log will be nearly empty and events will be absent rather than misattributed. A per-event `matched_by` field on an empty list communicates nothing useful. Instead, every response envelope includes `server_started` (bool) and `total_events_in_log` (int), giving the caller exactly the signal it needs to diagnose startup failures.

**Considered and rejected**: adding `matched_by` values like `test_id`, `time_range`, and `suite_context` parallel to ADR-0002. Rejected because every event in a given response shares one attribution method — all events are either state-machine-attributed or time-range-fallback-attributed — making per-event tagging redundant noise rather than useful signal.
