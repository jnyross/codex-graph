# Expectations — slice-generators-join

## Design (Part 1)

- Task family: research or analysis. Baseline tier: **L2** — the disjoint
  read-only questions are the slice generators; independence is proven by the
  slice definitions themselves.
- `N1` freezes slices, quotas, and the seed list. Representative generators
  (`N2A`–`N2C`) fan out; cardinality (6 regions + 4 archetypes) lives in the
  node contract, not as 10 drawn boxes.
- `I1` is the single integration owner: it applies the deterministic
  exact-name dedupe and seed priority **in plain orchestration code**, and it
  is the only node that can shape the final pool. No generator prompt asks
  the worker to deduplicate the pool, enforce global coverage, or evaluate
  other slices (#12).
- Read-only graph: all nodes use a local environment.

## Script (Part 2)

- Every tool result is normalized at the call boundary — the whole trimmed
  string parsed exactly once (`JSON.parse`), no fragment-extraction
  heuristics, raw payload preserved (#11).
- Generator starts use `Promise.allSettled`; rejected starts preserve their
  handles in the aggregate error (#11).
- Malformed generator handoffs are dropped with a logged reason and reported
  in the terminal result; they must not abort the merge.
- Collection is read-first with reads after every wait (#13); item budget at
  most 20000.
- One terminal result behind a `terminalEmitted` guard with the merged pool,
  per-slice contribution counts, and dropped-slice reasons.

## Machine contract

```json
{
  "case_id": "slice-generators-join",
  "task_family": "research or analysis",
  "baseline_tier": "L2",
  "required_node_ids": ["N1", "N2A", "N2B", "N2C", "I1", "T1"],
  "parallel_groups": [["N2A", "N2B", "N2C"]],
  "env": { "local": ["N1", "N2A", "N2B", "N2C", "I1", "T1"], "worktree": [] },
  "collection": {
    "read_first": true,
    "read_after_wait": true,
    "max_output_chars_per_item": 20000
  },
  "terminal_guard": true,
  "required_snippets": ["allSettled", "JSON.parse"],
  "forbidden_snippets": [
    "deduplicate the pool",
    "enforce global coverage"
  ]
}
```
