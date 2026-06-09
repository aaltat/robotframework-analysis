# App Log Matching Uses Test Name as Fallback When Test ID Diverges Between Worker and Merged Output

In a pabot run, each worker process runs a single `.robot` file in isolation. The RF hierarchical IDs emitted into the **App Log** by a worker are rooted at that worker's local suite tree (e.g. `s1-s1-s1-t45`). After the run, pabot merges all worker outputs into a single `output.xml` where every test is re-rooted under the full project suite tree (e.g. `s1-s2-s3-t45`). These two IDs refer to the same test but are structurally different strings.

The orchestrator looks up the failing test using the merged `test_id` from `output.xml`. Before this ADR, **App Log File Selection** Rule 0 and the **App Log State Machine** both matched exclusively by `id`. This caused two failures:

1. **File Selection (Rule 0 miss → Rule 2 exclusion)**: the correct worker log *contains* `start_test` events, but none match the merged ID. Rule 2 then correctly excluded the file (it has test events for the wrong ID), and Rule 3 returned no file at all.
2. **State Machine (id lookup miss → time-range fallback)**: even if the file had been selected by a fallback rule, `filter_events_for_test` would have fallen through to the **App Log Time-Range Fallback**, losing suite setup/teardown context.

The test `name` field (e.g. `"Get Console Log Test"`) is written by the worker and is identical in both the worker log and the merged `output.xml`. Within a single worker's log, test names are unique because pabot never co-schedules multiple `.robot` files in the same process and RF enforces unique test names within a file.

We extend both layers to fall back to name-based matching when ID matching fails:

- **App Log File Selection Rule 0**: a file with `start_test name=<test_name>` is a definitive match, ranked equal to an ID match. ID is tried first; name is the fallback. A file whose test events match neither ID nor name still triggers Rule 2 exclusion.
- **App Log State Machine**: `filter_events_for_test` (and `filter_http_for_test`) accept an optional `test_name`. If the id-based boundary search yields no result, the name-based search is attempted before the **App Log Time-Range Fallback**. This preserves full suite context inclusion.

`test_name` flows from the RF error group through `delegate.py` → `find_app_log_for_test` + `AppLogAnalystContext` → MCP tool calls → `log_parser.py`.

**Considered and rejected**:

- **Time-range fallback only (no name matching)**: the correct file would be selected via Rule 1.5 (suite-id match) or Rule 1 (time window), and the state machine would fall back to the time window. This works but loses suite setup and teardown context, which is always included under the **Suite Context Inclusion** policy and often contains relevant HTTP activity.
- **Normalise IDs before matching**: attempting to strip the pabot prefix from merged IDs to reconstruct the worker ID is fragile — the mapping between merged and worker IDs is not a simple prefix transformation and varies with how pabot constructs the output tree.
- **Pass the worker test_id through to the orchestrator**: pabot does not expose per-worker IDs in the merged `output.xml`; the orchestrator only ever sees merged IDs.
