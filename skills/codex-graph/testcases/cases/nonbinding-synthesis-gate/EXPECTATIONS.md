# Expectations — nonbinding-synthesis-gate

This case is the direct inverse of the observed Lisbon dogfood defect
(shipped fix #12): a synthesis worker that received the full acceptance
contract demanded audit-lane results that only exist after synthesis,
self-blocked with zero candidates, and failed the run while every upstream
handoff was complete.

## Design (Part 1)

- Task family: research or analysis. Baseline tier: **L3** — two declared
  post-synthesis audit dimensions (provenance fields, topic coverage) with
  distinct criteria.
- `N1` freezes the contract. `N2A`–`N2C` are the three topic collectors.
  `N3` is the synthesizer; `V1A`/`V1B` are the audit lenses; `G1` is the
  root acceptance gate; `R1`/`V2` form the single unrolled repair path.
- The `N3` prompt is node-local (#12): it carries the merge schema, the
  non-binding language rules, and an explicit scoping statement that its
  only obligation is the N3 output schema — audits and acceptance belong to
  later nodes. It must **not** contain the audit-lane requirements, the
  publication rule, or root-gate semantics.
- `G1` alone accepts or routes to the one repair. A missing or malformed
  audit verdict fails closed at `G1` (safe stop with evidence), never by a
  worker refusing to hand off.

## Script (Part 2)

- Collectors in one `Promise.allSettled` panel; audits in a second panel
  strictly after `N3` returns its draft.
- Read-first collection with reads after every wait (#13); item budget at
  most 20000.
- Exactly one repair (`repairUsed` reported), one terminal result behind a
  `terminalEmitted` guard.

## Machine contract

```json
{
  "case_id": "nonbinding-synthesis-gate",
  "task_family": "research or analysis",
  "baseline_tier": "L3",
  "required_node_ids": ["N1", "N2A", "N2B", "N2C", "N3", "V1A", "V1B", "G1", "R1", "V2", "T1"],
  "parallel_groups": [["N2A", "N2B", "N2C"], ["V1A", "V1B"]],
  "env": {
    "local": ["N1", "N2A", "N2B", "N2C", "N3", "V1A", "V1B", "G1", "T1"],
    "worktree": []
  },
  "collection": {
    "read_first": true,
    "read_after_wait": true,
    "max_output_chars_per_item": 20000
  },
  "single_repair": true,
  "terminal_guard": true,
  "required_snippets": ["allSettled", "only obligation", "non-binding"],
  "forbidden_snippets": [
    "must pass all audit lanes",
    "wait for the audit results before returning",
    "declare the overall workflow complete"
  ]
}
```
