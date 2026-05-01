# Playwright Event Correlation Policy

Playwright log events carry optional `test_id` and `suite_id` fields that were added upstream at different points in time, so not every event carries both. We need a deterministic rule for deciding whether an event belongs to a given Robot Framework test failure.

We decided on a priority order: **test_id match first, suite_id match second, time-window fallback last**. If `test_id` is present and matches the target test, the event is included as `test_id`. If `test_id` is absent but `suite_id` is present and matches the inferred target suites, the event is included as `suite_id`. If both are absent, the event is included only when it falls inside the failure time window, as `time_only`. If `test_id` is present but `suite_id` conflicts with the target suite, the event is included but marked `anomaly` — a strong signal that upstream context propagation may be wrong.

The same policy applies uniformly to every Playwright MCP endpoint; endpoint type does not change matching semantics. We rejected per-endpoint variations because they would make caller behaviour unpredictable and make the policy impossible to reason about as a unit.

`test_id` and `suite_id` are treated as independent values emitted separately by upstream. We never derive one from the other algorithmically (e.g. by stripping the `-tN` suffix from `test_id`) because that would couple us to an undocumented format convention that could change silently.
