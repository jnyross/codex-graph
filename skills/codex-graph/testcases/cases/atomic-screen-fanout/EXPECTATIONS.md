# Expectations — atomic-screen-fanout

## Design (Part 1)

- Task family: research or analysis. Baseline tier: **L2** — the independent
  read-only questions are the per-candidate gate checks. A cardinality trigger
  (`T4-SHARDED-RECOVERY`) may be declared for the 24-wide fan-out but must be
  a named gate, not up-front machinery.
- The graph freezes the candidate pool and gate definitions in `N1` before
  any screener starts. Screeners are atomic: one candidate in, one verdict
  out. The Mermaid may show representative screeners (`S1`–`S3`) with the
  cardinality stated on the contract, matching the skill's minimal-node
  guidance.
- The pool policy (uncertain→PASS, screener failure→PASS with recorded
  reason) is owned by the join node `N3` in orchestration code. No screener
  prompt may instruct a worker to apply pool-level policy, rank survivors, or
  reference synthesis obligations (#12).
- No repository writes anywhere: every node uses a local environment. A
  worktree environment for a read-only screen graph is a #14 regression.

## Script (Part 2)

- Screeners start in one `Promise.allSettled` batch; a rejected start
  preserves its handle (#11 aggregate-failure shape).
- Collection is read-first: read each thread before its first wait and after
  every wait (#13). Item budget never exceeds 20000.
- Verdict handoffs are schema-checked (`name`, `verdict`, `reason`,
  `gate_failed`); malformed verdicts route to the fail-open policy with a
  logged reason — in the kill log, never silently.
- Exactly one terminal result behind a `terminalEmitted` guard, containing
  survivors, the complete kill log, and per-screener status.

## Machine contract

```json
{
  "case_id": "atomic-screen-fanout",
  "task_family": "research or analysis",
  "baseline_tier": "L2",
  "required_node_ids": ["N1", "S1", "S2", "S3", "N3", "T1"],
  "parallel_groups": [["S1", "S2", "S3"]],
  "env": { "local": ["N1", "S1", "S2", "S3", "N3", "T1"], "worktree": [] },
  "collection": {
    "read_first": true,
    "read_after_wait": true,
    "max_output_chars_per_item": 20000
  },
  "terminal_guard": true,
  "required_snippets": ["allSettled", "gate_failed"],
  "forbidden_snippets": [
    "rank the survivors",
    "all screeners must pass"
  ]
}
```
