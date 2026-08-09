# Expectations — sealed-pov-factcheck

## Design (Part 1)

- Task family: research or analysis. Baseline tier: **L3** — the adversarial
  fact-check lanes are independent acceptance dimensions (claim truth vs pack
  completeness), proven at design time by the goal's explicit refute-lane
  requirement.
- `N1` freezes the acceptance contract: pack schema, the exactly-3
  load-bearing-claims rule, score dimensions, and the UNVERIFIABLE fail-closed
  rule. Representative pack builders (`N2A`–`N2C`) and fact-checkers
  (`V1A`–`V1C`) carry the real cardinality (8) in their contracts.
- Pack builders are sealed: their prompts contain their own destination, the
  pack schema, and node-local obligations only. They must not receive the
  fact-check criteria, root-gate semantics, or comparative-ranking duties
  (#12). Fact-checkers receive one pack's claims and context only.
- `G1` (root gate) owns acceptance. It maps a failed or malformed fact-check
  lane to UNVERIFIABLE-ONLINE for that pack — fail-closed evidence, never a
  confirming vote.
- Full packs go to a durable artifact; joins carry compact cards plus the
  artifact reference. Read-only research: all environments local.

## Script (Part 2)

- Two `Promise.allSettled` panels (builders, then checkers); checker
  cardinality derives from collected builder handoffs, not from the input
  list — a failed pack has no checker but keeps its failure recorded.
- Read-first collection with reads after every wait (#13); item budget at
  most 20000.
- The UNVERIFIABLE-ONLINE mapping for missing/failed checks is orchestration
  code at the gate, visible in the terminal result per pack.
- One terminal result behind a `terminalEmitted` guard: artifact reference,
  compact cards, per-claim outcomes, coverage summary, no ranking.

## Machine contract

```json
{
  "case_id": "sealed-pov-factcheck",
  "task_family": "research or analysis",
  "baseline_tier": "L3",
  "required_node_ids": ["N1", "N2A", "N2B", "N2C", "V1A", "V1B", "V1C", "G1", "T1"],
  "parallel_groups": [["N2A", "N2B", "N2C"], ["V1A", "V1B", "V1C"]],
  "env": {
    "local": ["N1", "N2A", "N2B", "N2C", "V1A", "V1B", "V1C", "G1", "T1"],
    "worktree": []
  },
  "collection": {
    "read_first": true,
    "read_after_wait": true,
    "max_output_chars_per_item": 20000
  },
  "terminal_guard": true,
  "required_snippets": ["allSettled", "UNVERIFIABLE"],
  "forbidden_snippets": [
    "compare against the other destinations",
    "all audit lanes must pass"
  ]
}
```
