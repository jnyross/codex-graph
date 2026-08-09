# codex-graph dynamic-workflow test cases

Golden test cases derived from real Grok (Rhai) and Claude multi-agent
orchestration shapes. Each case is a synthetic, anonymized goal plus
machine-checkable expectations about the graph and Code Mode script that
`$codex-graph` should produce for it. Provenance and shape analysis:
`docs/dynamic-workflow-testcase-catalog.md` at the repository root.

Nothing here requires a live ChatGPT Desktop run. The harness is offline and
static; live dogfood stays in the separate lab repository.

## Layout

```
testcases/
  catalog.json            machine index of all cases
  cases/<id>/
    GOAL.md               free-form user goal, as $codex-graph would receive it
    EXPECTATIONS.md       prose + one fenced json block of machine expectations
    topology.hint.mmd     expected Mermaid shape (must pass graph_coherence.py)
  harness/
    expectations.js       loader + static workflow.js checker (library)
    check_workflow.js     CLI: check a generated workflow.js against a case
    testcases.test.js     node --test suite for the bundle and the checker
```

## Running

```bash
node --test skills/codex-graph/testcases/harness/testcases.test.js
python3 skills/codex-graph/scripts/graph_coherence.py \
  skills/codex-graph/testcases/cases/*/topology.hint.mmd
```

To check a generated script against a case:

```bash
node skills/codex-graph/testcases/harness/check_workflow.js \
  --case atomic-screen-fanout --script /path/to/workflow.js
```

The checker prints one JSON verdict: `{ok, case, checks:[{id, ok, detail}]}`
and exits non-zero when any check fails.

## What each case proves

| Case | Real-world source shape | Skill contracts exercised |
|---|---|---|
| `atomic-screen-fanout` | Grok destination/hotel screen phase: one atomic verdict agent per candidate, root-owned fail-open policy | #13 read-first collection; #12 node-local screen prompts; per-node local env; bounded collection |
| `slice-generators-join` | Grok atomic generators per region/archetype with one dedupe owner | #11 tool-result normalization; single integration owner; no nested delegation |
| `sealed-pov-factcheck` | Grok sealed decision packs + one adversarial fact-checker per pack | #12 sealed worker scoping; fail-closed evidence; durable artifact + compact handoffs |
| `nonbinding-synthesis-gate` | Grok non-binding light synthesis (human ranks); inverse of Lisbon self-block defect | #12 synthesis never owns publication or self-blocks; #13 |
| `adversarial-dual-validation` | Grok blind vote panels / A-B research arms; Claude review-scorer panels | Fail-closed malformed verdicts; index-arithmetic regroup; one root gate |
| `disjoint-writers-worktree` | Claude disjoint implement teammates in isolated worktrees | #14 per-node environment + pending clientThreadId resolution; disjoint write scopes; root-owned publication |

Contract IDs refer to shipped fixes: #11 `d06ccb9`, #12 `7ea5de3`,
#13 `dce28be`, #14 `1a1828a`.

## Expectation semantics

The fenced `json` block in each `EXPECTATIONS.md` is the machine contract.
Recognized fields (all optional unless noted):

- `case_id` (required) — must match the directory and `catalog.json`.
- `task_family`, `baseline_tier` — documentation, echoed by the checker.
- `required_node_ids` — every ID must appear verbatim in the script.
- `parallel_groups` — arrays of node IDs expected to run in one settled
  batch; when present the script must contain `Promise.allSettled`.
- `env` — `{ "local": [ids], "worktree": [ids] }`. Rules enforced:
  worktree list empty → the script must not create worktree environments;
  both lists non-empty → the script must create both env types (a global
  worktree for one writer is the #14 regression).
- `collection` — `{ "read_first": true, "read_after_wait": true,
  "max_output_chars_per_item": 20000 }`. Declaring `collection` requires at
  least one await-adjacent tool or resolved-helper call site
  (`collection:call-sites`) — a call-free script fails outright. Ordering
  is judged on **await-adjacent call sites**, so parameter lists, bindings,
  and comments cannot flip the verdict. Helper names bound to exactly one
  of the two tools — a function-like binding (`const readFor = … =>`,
  `resolveTool`, `.bind`) or a declared function whose bounded body window
  references the tool — count only when awaited as standalone call targets;
  member/property and identifier-suffix matches do not count. A helper
  touching both tools is ambiguous and votes for neither, so mixed collectors
  (direct wait, wrapped reads) are judged correctly.
  `read_first` fails when the first wait call site precedes any read call
  site; `read_after_wait` requires a read call site after the first wait.
  When no call sites resolve at all, ordering is not judged — the
  call-sites check governs. The item budget caps every literal
  `maxOutputCharsPerItem` in the script.
- `single_repair` — requires a `repairUsed` marker in the script.
- `terminal_guard` — requires a `terminalEmitted` marker.
- `pending_setup_resolution` — requires the `clientThreadId` identifier
  **plus** evidence of a bounded resolution loop in the same script: a
  named attempts constant (`START_RESOLVE_ATTEMPTS`, `RESOLVE_ATTEMPTS`,
  `MAX_SETUP_POLLS`, `resolveBounds`) or a task-list poll
  (`list_threads`/`listThreads`). Merely storing or testing the identifier
  is the canonical #14 failure and does not pass.
- `required_snippets` / `forbidden_snippets` — literal substrings that must
  or must not appear anywhere in the script. Used, for example, to forbid
  publication-rule phrases inside mid-graph worker prompts (#12 is enforced
  as a textual heuristic; the phrases are chosen so a correctly scoped
  script never contains them).

Static checks are deliberately conservative: they catch the regression
classes observed in lab runs (wait-only collection, global worktree,
over-scoped worker prompts, unbounded budgets) without pretending to
execute the script.
