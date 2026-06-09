# App Log File Selection Uses RF Lifecycle Context, Not Timestamps or Heuristics

In pabot runs each parallel worker runs its own test-app server, producing one `test-app-<pid>.log` per worker in the **App Log Directory**. When the orchestrator needs app log evidence for a failing test, it must pick the correct file before the **App Log State Machine** can run.

We select by scanning all files for RF lifecycle signals in priority order (**App Log File Selection**, Rules 0–3):

1. A file containing `start_test id=<test_id>` is the definitive match and ends the search (Rule 0).
2. A file with `start_suite id=<suite_id>` (derived via **RF Hierarchical ID**) but no matching `start_test`, combined with a time-window overlap, is a fallback candidate (Rule 1.5).
3. A file with zero RF lifecycle events but a time-window overlap is also a fallback candidate (Rule 1).
4. A file with `start_test` events that do not match `test_id` is excluded, even if timestamps match (Rule 2).

Rule 0 evicts all fallback candidates. When only fallback candidates exist, Rule 1.5 beats Rule 1 (suite context is a stronger signal than pure time coincidence). Rule 3 applies when no file matches at all.

**Considered and rejected**:

- **Latest-modified file**: ignores RF context entirely; wrong file chosen whenever the failing test ran on any worker other than the last to write.
- **Merge all files by time window**: pabot workers run in parallel so their time windows overlap; merging produces duplicate and unrelated events from other workers' tests.
- **LLM picks the file**: the model would receive filenames or directory listings as prompt text; small models hallucinate path strings, and this is an architectural invariant we uphold across all agents.
- **Time-window match regardless of test_id presence (no Rule 2)**: a file that ran *other* tests has explicit negative evidence — we know our test did not run there. Treating that file's time-window events as relevant would be misleading.
