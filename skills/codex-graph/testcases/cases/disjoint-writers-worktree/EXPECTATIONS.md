# Expectations — disjoint-writers-worktree

This case pins the shipped #14 contract: environments are chosen per node,
never globally. Observed Lisbon dogfood v4: research workers created with a
global worktree environment returned only `clientThreadId`, never resolved
within chat-scale bounds, and blocked the run before collection.

## Design (Part 1)

- Task family: feature or refactor. Baseline tier: **L2** — two independent
  read-only discovery questions (conventions, script layout) plus two
  demonstrably disjoint write scopes (`examples/csv-report/` vs
  `examples/json-summary/`).
- `N1` confirms scope; `D1`/`D2` are read-only discovery on **local**
  environments; `W1`/`W2` are the parallel writers on **worktree**
  environments with explicitly disjoint directory scopes; `V1` validates
  both examples; `G1` gates; `T1` is the root-owned publication of
  `examples/README.md` on the real checkout.
- Never a global worktree: discovery nodes on worktree environments is the
  #14 regression this case exists to catch. Conversely the writers must not
  run on local where they could collide with uncommitted work.
- Publication is not stranded in a worker worktree: the index write belongs
  to the root/integration owner.

## Script (Part 2)

- Discovery panel and writer panel are separate `Promise.allSettled`
  batches; writer prompts name their single allowed directory and forbid
  touching the sibling's scope or repo root.
- Pending setup resolution (#14): a start that returns only
  `clientThreadId` is polled against the task list with named bounds —
  chat-scale for local nodes, provisioning-scale for worktree nodes — and
  correlated by `clientThreadId` when the list exposes it. Never fail a
  start closed while its pending setup can still resolve; never create a
  replacement task while the original can still resolve.
- Read-first collection with reads after every wait (#13); item budget at
  most 20000.
- One terminal result behind a `terminalEmitted` guard listing changed
  paths per writer and validation evidence.

## Machine contract

```json
{
  "case_id": "disjoint-writers-worktree",
  "task_family": "feature or refactor",
  "baseline_tier": "L2",
  "required_node_ids": ["N1", "D1", "D2", "W1", "W2", "V1", "G1", "T1"],
  "parallel_groups": [["D1", "D2"], ["W1", "W2"]],
  "env": {
    "local": ["N1", "D1", "D2", "V1", "G1", "T1"],
    "worktree": ["W1", "W2"]
  },
  "collection": {
    "read_first": true,
    "read_after_wait": true,
    "max_output_chars_per_item": 20000
  },
  "pending_setup_resolution": true,
  "terminal_guard": true,
  "required_snippets": ["allSettled"],
  "forbidden_snippets": [
    "apply worktree to every node"
  ]
}
```
