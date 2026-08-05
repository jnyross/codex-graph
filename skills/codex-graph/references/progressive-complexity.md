# Progressive complexity ladder

Use this ladder as the authority for graph complexity. Tiers are cumulative:
the baseline is the lowest tier that satisfies every already-proven trigger
(equivalently, the highest proven tier). Report every fired trigger, not only
the baseline tier's trigger. Anything unproven is a run-time escalation gate,
not an up-front node.

## Tiers

### L0 direct

- **Adds:** one implementation or synthesis stage, one targeted validator, and
  one terminal outcome.
- **Entry trigger:** the goal has one bounded write or output scope, one
  decision owner, and one targeted check.
- **Evidence:** name the scope, validator, and acceptance check before drawing
  the graph; no independent work item or ambiguity requires delegation.
- **Cost bought:** the lowest coordination, prompt, wait, and failure cost.
- **Baseline shape:** one stage plus one targeted check; no delegation and no
  workers.

### L1 delegated

- **Adds:** one read-only worker, one validator, and at most one repair stage.
- **Entry trigger:** one material discovery or implementation subtask is
  separable from the owner, but parallel independence or multiple write scopes
  is not proven.
- **Evidence:** name the single worker's bounded read scope and the validator's
  distinct acceptance check; show that one owner can consume the handoff.
- **Cost bought:** limited discovery assistance without a fan-out or join.

### L2 bounded discovery

- **Adds:** bounded parallel read-only discovery (at most four workers), one
  writer or integration owner, and one validator.
- **Entry trigger:** two or more genuinely independent read-only questions are
  required, or ambiguity cannot be resolved by one owner reading the named
  context.
- **Evidence:** list each question, its disjoint read scope, and the decision
  that joins them; prove independence rather than using visual parallelism.
- **Cost bought:** faster evidence gathering while preserving one authority for
  writes and integration.

### L3 independent validation

- **Adds:** parallel independent validation or audit lenses joined at one
  root-owned acceptance gate.
- **Entry trigger:** the artifact has two or more acceptance dimensions that
  are genuinely independent after integration.
- **Evidence:** name each lens, its criterion ID, disjoint inputs, and why one
  validator cannot cover the dimensions without conflating decisions.
- **Cost bought:** independent coverage and failure isolation at the acceptance
  boundary.

### L4 sharded recovery

- **Adds:** record-specific repair fan-out, an expansion queue, checkpoints, and
  resume handles.
- **Entry trigger:** declared record cardinality exceeds its declared
  threshold, or a validator returns repair spanning independent lenses or
  record batches.
- **Evidence:** declare the cardinality threshold or machine-readable repair
  result before activation; identify stable record IDs and the checkpoint
  boundary.
- **Cost bought:** bounded recovery and resumability for large or interrupted
  runs without turning repair into a loop.

## Trigger table

| Tier | Observable trigger | Required evidence | Added machinery |
|---|---|---|---|
| L0 | One bounded scope and one targeted check | Named scope and check | Direct stage and validator |
| L1 | One separable worker need | Named worker scope and distinct check | One worker and one validator |
| L2 | At least two independent read-only questions | Disjoint scopes and join decision | Bounded fan-out and one owner |
| L3 | At least two independent acceptance dimensions | Lens criteria and independence proof | Parallel validators and root gate |
| L4 | Cardinality above declared threshold or cross-lens repair | IDs, threshold, or validator decision | Shards, queue, checkpoints, resume |

## Anti-triggers

Do not escalate for visual parallelism, "might be useful later," speculative
lenses, or node-count targets. A larger graph is not better. Do not add workers
because a task feels important, because a topology pattern contains them, or
because future scope is imaginable. Do not promote a tier without observable
goal-specific evidence.

## Design-time and run-time split

At design time, declare the baseline tier, every fired trigger, and its
evidence. Select the lowest tier that satisfies every already-proven trigger.
Defer every unproven trigger to an explicit named run-time gate. Baseline nodes
are always active; higher-tier nodes are conditional and are reported as
skipped when not active. Escalation is default-off.

`P1` is a zero-worker, zero-task inline evaluation of evidence already produced
by the baseline stage. It never delegates or spawns a task. `E1` is a plain
conditional gate. When the design proves that no trigger is deferrable because
the scope is fully bounded and every trigger is resolved, declare
`escalation: none-declared` and omit `P1` and `E1`; document that omission in
the Complexity ladder section. Otherwise declare them as control nodes, but
exclude both from the minimal baseline executable-node count.

Count only baseline executable nodes for minimal-node guidance.
Exclude conditional higher-tier stages, `P1`, and escalation gates from that count.
Declared skipped nodes remain in the graph and metadata even though they do not
inflate the baseline count.

## Executable escalation tests

Declare this threshold set before execution and reuse it as part of the same
acceptance contract; do not choose thresholds after observing results. When a
cardinality threshold is needed, derive it from the already-declared budgets:
the threshold is the number of records one serial owner can validate and
normalize within the declared per-item output budget and handoff budget. Show
the arithmetic in the design; do not use an unexplained round number.

For example, if one normalized record requires 1,500 characters, the per-item
output budget is 20,000 characters, and the handoff budget is 9,000 characters,
the usable capacity is `min(floor(20000 / 1500), floor(9000 / 1500)) = 6`
records. Declare `record_count > 6` as the L4 cardinality trigger before
execution.

Each baseline graph with deferred triggers includes probe node `P1`, which
runs only the cheap guard test for the next tier after the baseline stage. A
valid verdict has this shape:
`{trigger_id, state: "fired"|"not_fired"|"not_evaluated", fired: true|false|null,
evidence, measured, threshold, action}`. `not_evaluated` is distinct from
`fired: false`: tests above the next tier are deferred and reported as
`not_evaluated`. Missing or malformed verdicts fail closed, are reported with
`state: "not_evaluated"` and `action: "none"`, and do not escalate.

| Test ID | Cheap probe and measured value | Declared threshold | Fired verdict and action |
|---|---|---|---|
| `T1-WORKER-NEED` | Read the unresolved-ambiguity list and count separable items | `separable_items >= 1` | Add L1 worker `W1` and validator `V1` |
| `T2-DISJOINT-READ-SCOPES` | Count independent read-only questions and compare their scopes | `independent_questions >= 2` and `max_workers <= 4` | Add L2 discovery `D1-D4`, then owner `I1` |
| `T3-INDEPENDENT-LENSES` | Count acceptance lenses with distinct criterion IDs and inputs | `independent_lenses >= 2` | Add L3 validators `V1A-V1D` and root gate `G1` |
| `T4-SHARDED-RECOVERY` | Measure record cardinality and inspect repair verdict span | `record_count > declared_threshold` or `repair_lenses >= 2` | Add L4 shards `R1-R4`, expansion queue `Q1`, checkpoint `C1`, resume `H1` |

Each result must include the measured value and threshold, not just a prose
claim. A fired test promotes to its declared next tier and action exactly; there
is no improvised stage selection. Evaluate only the next tier's guard test,
promote at most once per probe evaluation, and cap total promotions at 2. Tests
above the next tier are reported as `not_evaluated`, not as `fired: false`.

## Escalation action mapping

| Fired trigger | Added stages and IDs | Added scope | Does not change |
|---|---|---|---|
| `T1-WORKER-NEED` | `E1`, `W1`, `V1` | `W1` read-only discovery; `V1` validation | One owner, four-worker cap, one repair |
| `T2-DISJOINT-READ-SCOPES` | `E2`, `D1-D4`, `I1` | Disjoint read-only discovery; `I1` owns writes | One integration owner, no nested delegation |
| `T3-INDEPENDENT-LENSES` | `E3`, `V1A-V1D`, `G1` | Read-only validation lenses and root acceptance | Repair allowance stays one; cap stays four |
| `T4-SHARDED-RECOVERY` | `E4`, `R1-R4`, `Q1`, `C1`, `H1` | Record-specific repair and resumability | No demotion; no extra repair; no new scope |

The script must record the action taken or `none` for every verdict, including
`not_evaluated` and malformed verdicts. A promotion never demotes: no demotion
is permitted, and one repair total remains invariant at every tier.

## Code Mode escalation pattern

Use this bounded skeleton when a deferred trigger may become true during
execution:

```javascript
const BASELINE_TIER = "L0";
const TIER_TRIGGERS = {
  L1: "one separable worker need observed",
  L2: "two independent read-only questions observed",
  L3: "independent acceptance lenses proven",
  L4: "declared cardinality threshold or cross-lens repair observed",
};
const TIER_TESTS = {
  L1: "T1-WORKER-NEED",
  L2: "T2-DISJOINT-READ-SCOPES",
  L3: "T3-INDEPENDENT-LENSES",
  L4: "T4-SHARDED-RECOVERY",
};
const TIER_ACTIONS = {
  L1: "add E1, W1, V1",
  L2: "add E2, D1-D4, I1",
  L3: "add E3, V1A-V1D, G1",
  L4: "add E4, R1-R4, Q1, C1, H1",
};
const ESCALATION_CAP = 2;
let currentTier = BASELINE_TIER;
let escalationsUsed = 0;
const skippedTiers = [];
const triggerVerdicts = [];

function recordNotEvaluated(observation, afterTier) {
  for (const tier of Object.keys(TIER_TESTS)) {
    if (Number(tier.slice(1)) > afterTier) {
      triggerVerdicts.push({
        trigger_id: TIER_TESTS[tier],
        state: "not_evaluated",
        fired: null,
        evidence: "deferred above the next tier",
        measured: null,
        threshold: observation.thresholdFor(TIER_TESTS[tier]),
        action: "none",
      });
      skippedTiers.push(tier);
    }
  }
}

function maybeEscalate(observation) {
  const nextTier = `L${Number(currentTier.slice(1)) + 1}`;
  const triggerId = TIER_TESTS[nextTier];
  if (!triggerId || escalationsUsed >= ESCALATION_CAP) {
    recordNotEvaluated(observation, Number(currentTier.slice(1)));
    return false;
  }
  const raw = observation.verdictFor(triggerId);
  const valid = raw && typeof raw.fired === "boolean";
  const verdict = valid
    ? {
        ...raw,
        trigger_id: triggerId,
        state: raw.fired ? "fired" : "not_fired",
        action: raw.fired ? TIER_ACTIONS[nextTier] : "none",
      }
    : {
        trigger_id: triggerId,
        state: "not_evaluated",
        fired: false,
        evidence: "malformed or missing verdicts fail closed",
        measured: null,
        threshold: observation.thresholdFor(triggerId),
        action: "none",
      };
  triggerVerdicts.push(verdict);
  if (!valid || !verdict.fired) {
    skippedTiers.push(nextTier);
    recordNotEvaluated(observation, Number(nextTier.slice(1)));
    return false;
  }
  currentTier = nextTier;
  escalationsUsed += 1;
  recordNotEvaluated(observation, Number(currentTier.slice(1)));
  return true;
}
```

Keep `escalationsUsed` bounded by an escalation cap of 2. Promote only; never
demote; this is the no-demotion rule.
Apply one repair total regardless of tier. Report the tier reached, every
trigger with its evidence, escalations used versus cap, and skipped tiers or
nodes. A skipped tier is not an omitted node.
