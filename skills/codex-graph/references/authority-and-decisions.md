# Authority and Decisions

This module is the sole owner of authority, decisions, review, continuation,
and final workflow outcomes. Consumers link here. They do not restate these
rules.

## Owned terms

- **Authority-bearing workflow** — a workflow with a reachable durable
  mutation, publication, or real-checkout integration.
- **Interactive workflow** — a workflow with a reachable human decision loop.
- **Durable mutation** — an action that changes user, repository, service, or other persistent state outside an isolated worker draft.
- **Authority preflight** — the root-owned record that classifies interactivity, mutation authority, worker confinement, generic triggers, selected topology, and whether generation may continue.
- **Worker confinement** — positive evidence of one worker's environment, read
  scope, write scope, isolation, and available capabilities. It includes proof
  that no available capability can perform a durable mutation.
- **Protected domain** — one of the closed consequence-bearing categories in the protected-domain gate.
- **Decision frontier** — the complete revisioned set of independently answerable human questions that are currently unblocked by other questions.
- **Decision receipt** — the durable normalization of accepted answers for one workflow, plan revision, and queue revision.
- **Dispatch authority** — permission recorded in the current checkpoint for a specific revision to start authority-bearing work.
- **Action attempt** — the non-replayable boundary recorded when an external mutation may have started.
- **Preservation proof** — evidence that completed work remains valid after a revision change.
- **Local repair** — reuse of unaffected pending work across a proved closed invalidation boundary.
- **Remaining-graph replan** — reconstruction of pending work from observed effects when that closed boundary is not proved.
- **Workflow outcome** — the root-owned final state of the current goal and revision, distinct from process, task, review, testcase, or lab verdicts.

## Authority preflight and topology safety

The root records the authority preflight before generic complexity selection or graph generation. It contains:

- the interactivity verdict and its evidence;
- the authority-bearing verdict and its evidence;
- every reachable decision-loop path;
- every reachable mutation identity and its root owner;
- each worker's semantic role, environment, read scope, write scope,
  capabilities, isolation proof, and positive proof that its capabilities
  cannot perform a durable mutation;
- the generic trigger state and selected topology; and
- `allow_generation`, `block`, or runtime-replan state.

Classify safety before complexity. A reachable human decision loop makes L1–L4 not applicable and selects L0 so the parent conversation retains the loop. A non-human failure path alone is not interactive. Generic complexity can add machinery only after this verdict; it cannot override safety.

Every durable mutation stays root-owned. Prior authorization, reversibility, narrow scope, or a single worker does not transfer authority. Workers may read and create isolated drafts only within proved scopes. A worker that discovers a required durable mutation stops before action and returns sanitized evidence to the root.

Delegation requires positive proof for each worker that its available
capabilities cannot perform a durable mutation. Instructions, policy,
confidence, convention, and absence of an observed violation are not proof.
Durable actions must also remain root-owned. Missing, malformed, ambiguous,
stale, or contradicted preflight or confinement evidence selects L0 and blocks.

Runtime discovery invalidates the current preflight:

- If a human decision loop becomes reachable, delegated work stops. Preserve valid evidence and observed effects, then create a new L0 revision before work continues.
- If a worker discovers a required durable mutation, it stops before action.
  The root owns the mutation. L1+ can continue only after a new preflight proves
  that every delegated worker's current capabilities cannot perform durable
  mutation. Otherwise select L0 and block.

## Protected-domain mutation gate

Run gates in this fixed order: transport completeness, item/action classification, exact current authorization, then mutation. Evidence completeness is owned by [Evidence and Acceptance](evidence-and-acceptance.md). Any change to item, action, predicate, target, or scope reruns the gate.

Classify both the item and the proposed action by function, with multiple labels allowed, against this closed list:

1. security and account control;
2. identity and official status;
3. financial assets and obligations;
4. legal rights and obligations;
5. health and medical care;
6. physical safety and emergency;
7. privacy, consent, and data control; and
8. high-impact eligibility and essential services.

A protected or uncertain result on either axis fails closed. Expiry never
removes a protected classification. It can only make authorization stale.
Model confidence cannot clear deterministic markers, plausible protected
meaning, missing content, conflicts, or expiry.

A protected mutation requires a current human decision. The decision binds to
the exact mutation, one queue revision, and a named item or finite named batch.
Silence, ambiguity, stale answers, broad preferences, blanket rules, and scope
mismatch grant no authority.

A mixed batch can partition only under three conditions:

- item records are complete;
- execution is item-level; and
- no data, ordering, or state coupling crosses the partition.

The security-gate record contains:

- item and batch identities;
- exact action and target state;
- transport-proof reference;
- both classifications and every protected category considered;
- deterministic markers, uncertainty, and expiry;
- evidence locators;
- authorization reference and scope;
- partition sets; and
- `allow` or `block`.

## Frozen design review gate

Every authority-bearing design passes all three layers against the exact design digest:

1. a structured generator self-check;
2. a separate read-only independent review of that exact frozen revision; and
3. a static protocol and disposition gate.

Independence requires a separate context with no design-writing or mutation authority. A different model family is preferred but not required. Missing, timed-out, malformed, stale, or wrong-digest review is missing acceptance evidence and blocks. It cannot be waived.

Use the existing acceptance and validator path. Add one self-check result and
one independent-review envelope keyed by the design digest. The envelope
contains:

- review identity and design digest;
- verdict;
- reviewer-independence facts;
- findings;
- repair count; and
- evidence locators.

The review verdict is exactly `pass`, `repair`, or `block`. `pass` has no
unresolved must-fix finding. `repair` permits the one automatic repair. `block`
covers missing review evidence or a must-fix that cannot proceed.

Each finding contains a stable identity, `must-fix` or `advisory` class, and
cited criterion. It also contains affected nodes, sanitized evidence,
rationale, clearance condition, and waiver policy. An unspecified waiver policy
fails closed. Advisory findings remain visible but do not block.

A must-fix disposition is exactly one of:

- `repaired`, followed by independent clearance on the new revision;
- `human-authorized-deviation`, bound to the exact waivable finding, design revision, governing waiver permission, and decision receipt; or
- `unresolved`, which blocks accepted, executable, and dogfood-ready labels.

The generator gets at most one automatic repair. After repair, rerun the full
self-check, independent review, and static gate. The static gate verifies the
current digest, envelope shape, finding identities, permitted verdicts and
dispositions, clearance evidence, and the one-repair maximum. It rejects every
other verdict value. It does not make semantic judgments.

The root checkpoint binds the used repair allowance to the revision and digest
that returned `repair_required`. Later pass and block results preserve that
repair origin so resume and correction remain possible. Only a new
`repair_required` result may establish the origin. Malformed or unknown
checkpoint state blocks and cannot restore an unused repair allowance.

An unresolved must-fix produces a structured blocked diagnostic artifact. It
also produces a precise parent question bound to the finding and revision.
Offer retry, design change, deviation only when the finding is waivable, or
termination. The question cannot waive independent review. If no answer can
create a safe path, return the final blocked outcome instead.

## Decision frontier and answer receipt

Only a typed `human_decision_required` blocker renders a decision frontier. Other blockers use their own recovery or final-report path and never become human questions.

The root renders the complete current frontier inline in the parent
conversation. It assigns stable identities from one global decision-ID
sequence and preserves internal source bindings. It groups related items and
deduplicates equivalent questions. It reports material recommendation conflicts
in sanitized terms. It defers questions that depend on unanswered questions.

Each visible decision item contains its identity, queue revision, question, choices, recommendation with rationale or a no-safe-recommendation statement, no-answer effect, and affected mutation identities. Recommendations and silence authorize nothing.

Answer normalization accepts decision identities, choice numbers, concise unambiguous language, valid partial answers, and revision-scoped batch acceptance. “Take all recommendations” applies only to visible recommendations in the named revision. Explicit answers override batch choices. Return accepted mappings, pending mappings, rejected stale or ambiguous mappings, and whether scope changed.

Checkpoint valid partial answers. Reject stale, conflicting, ambiguous, superseded, or unmappable answers while retaining settled work. An identical duplicate answer for the current revision is a recorded no-op. Independent work continues only when all of its decision prerequisites are settled.

Before revised dispatch becomes active, write one decision receipt with workflow, plan, and queue revisions, normalized choices, and explicit overrides. Then report the mapping concisely and automatically resume the same checkpointed workflow; do not require a separate continue command. A replacement machine handle does not change workflow identity. New or expanded authority returns as a new decision item.

## Checkpoint, cutover, and continuation

The durable checkpoint contains:

- workflow identity;
- goal and acceptance contract;
- plan and queue revisions;
- decision receipt;
- completed work and evidence;
- frozen-design review state and whether its automatic repair was used;
- every action attempt and canonical target;
- pending and invalidated work;
- dependency closure;
- dispatch authority;
- preservation entries;
- reconciliation state;
- queue state; and
- optional live handles.

A live handle is only an optimization. Resume requires matching workflow and revisions, valid dispatch authority, proved preserved dependency closure, and no uncheckpointed action attempt. Otherwise start a replacement attempt from the checkpoint without changing workflow identity.

A scope-changing answer uses one atomic cutover:

1. validate revisions and normalize the answer;
2. write the receipt;
3. revoke affected old-revision dispatch authority; and
4. commit the revised checkpoint.

After the receipt, only non-mutating repair, replan, reconciliation, and
preservation checks may run. This restriction continues until the full current
frontier is recomputed. New, changed, conflicting, ambiguous, or expanded-scope
decisions create a new queue revision before further mutation.

Authority-bearing execution resumes automatically only when the frontier is
empty and every authority and evidence gate passes. If no human answer can
create a safe path, return the applicable final outcome. Do not ask a useless
question.

Use existing dependency and provenance facts for invalidation. Local repair is
legal only when these facts prove a closed affected subgraph:

- unchanged inputs and assumptions;
- unchanged authority and target scope;
- unchanged predicate, ordering, and atomicity;
- unchanged topology and review binding; and
- unchanged acceptance contract.

Shared changes, cross-boundary effects, missing provenance, or unproved closure
require a remaining-graph replan from observed current state.

A preservation entry retains:

- immutable locators and digests;
- inputs;
- target identities and versions;
- decisions and authority;
- predicate and transport witness;
- downstream uses;
- freshness rule; and
- revalidation result.

Historical transport completeness does not prove current eligibility. A target
version mismatch forces a new complete read. Then repeat inspection,
classification, and frontier computation.

Every recorded action attempt is a non-replayable effect boundary. Missing action evidence requires reconciliation and remains indeterminate; it never authorizes replay. Retry, undo, compensation, or correction is a new mutation with a new identity, current evidence, and current authorization. Late scope narrowing does not make a valid completed effect retroactively unauthorized.

A late old-revision mutation is a process violation and requires
reconciliation. A known effect is `failed`. An unresolved possible effect is
`indeterminate`.

## Workflow states and outcomes

`continue` and `human_decision_required` are non-final workflow states. Final workflow outcomes are only:

- `accepted` — every current-goal target has root-owned evidence-backed acceptance;
- `cancelled` — the human explicitly stops the workflow;
- `blocked` — a pre-action gate cannot be satisfied safely;
- `failed` — authoritative contradiction, rejection, duplicate or out-of-scope effect, known process violation, or no safe corrective path prevents the current goal; and
- `indeterminate` — an action may have occurred but its effect cannot be resolved.

For mixed results, `failed` takes precedence over `indeterminate`, which takes precedence over `blocked`; `accepted` requires all current-goal targets to be accepted. Recompute acceptance against a revised goal even when a scope change leaves no pending work. Only an explicit human stop is `cancelled`.

Task, attempt, review, testcase, process, and lab verdicts stay scoped to their
interfaces. A normal process exit can be reported as a process fact while the
workflow remains open. Generated artifacts, valid JSON, worker claims,
receipts, review artifacts, and static passes do not establish workflow
success. Only `accepted` permits success wording. Acceptance evidence and
target-level terminal derivation belong to
[Evidence and Acceptance](evidence-and-acceptance.md).
