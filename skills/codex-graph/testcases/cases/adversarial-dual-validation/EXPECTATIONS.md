# Expectations — adversarial-dual-validation

## Design (Part 1)

- Task family: audit or review. Baseline tier: **L3** — two independent
  acceptance dimensions (accuracy vs completeness/safety) with distinct
  criterion IDs, declared in the goal itself.
- `N1` freezes the criteria and the review bundle scope; `N2` assembles the
  bundle; `V1A`/`V1B` are the blind validators; `G1` is the root gate;
  `R1`/`V2` form the single unrolled repair; `T1`/`X1` terminals.
- Verdicts fail closed: a malformed, missing, or failed validator result is
  a `revise`-blocking outcome at `G1`, never a pass. No validator prompt
  gives that worker authority over the other lane or over publication (#12).
- The one revision (`R1`) is the only write. If the graph runs in a saved
  project, `R1` is the only node that may need a writable environment;
  validators and bundle assembly stay read-only on local (#14). A design
  that keeps `R1` as a root-owned local edit is also conforming, so the
  machine contract below pins only the read-only lanes.
- Re-validation re-runs only the failed lane(s) plus any changed global
  invariant — not the whole panel unconditionally.

## Script (Part 2)

- The validator panel is one `Promise.allSettled` batch; results are
  regrouped deterministically by index, not by parsing labels out of prose.
- Verdict JSON is schema-checked (`pass`/`revise`, criterion IDs, evidence);
  anything else routes to fail-closed handling at `G1`.
- Read-first collection with reads after every wait (#13); item budget at
  most 20000.
- Exactly one repair with `repairUsed` reported; one terminal result behind
  a `terminalEmitted` guard preserving both verdicts and the action taken.

## Machine contract

```json
{
  "case_id": "adversarial-dual-validation",
  "task_family": "audit or review",
  "baseline_tier": "L3",
  "required_node_ids": ["N1", "N2", "V1A", "V1B", "G1", "R1", "V2", "T1"],
  "parallel_groups": [["V1A", "V1B"]],
  "env": { "local": ["N1", "N2", "V1A", "V1B", "G1", "T1"], "worktree": [] },
  "collection": {
    "read_first": true,
    "read_after_wait": true,
    "max_output_chars_per_item": 20000
  },
  "single_repair": true,
  "terminal_guard": true,
  "required_snippets": ["allSettled", "revise"],
  "forbidden_snippets": [
    "you may approve the guide on your own",
    "treat a missing verdict as a pass"
  ]
}
```
