# matched_by Is Mandatory on Every Playwright MCP Response Item

Every `PlaywrightEventItem` and `PlaywrightErrorItem` returned by a Playwright MCP tool must include a `matched_by` field carrying the evidence source used for correlation. The allowed values are `test_id`, `suite_id`, `time_only`, and `anomaly`.

We made this mandatory rather than optional because optional provenance hides how reliable a result is. A caller who cannot tell whether an event was matched by test_id or by a time-window fallback cannot make informed decisions about how much weight to give it. Treating `matched_by` as `str | None` was rejected; `None` would be meaningless — if an event is in the response, it was matched by something.

No separate boolean flag is used for anomaly events. Overloading `matched_by = "test_id"` on anomalous events would hide the conflict from callers who only read `matched_by`. The `"anomaly"` value communicates both the inclusion decision and the diagnostic signal in one field.

Legacy compatibility paths that omit `matched_by` are out of scope.
