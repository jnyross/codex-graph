# Evidence and Acceptance

This module is the sole owner of reliability rules for complete reads, mutation-bound evidence, target reconciliation, acceptance manifests, and evidence-family adapters. Consumers link here; they do not restate these rules.

## Owned terms

- **Fixed mutation predicate** — the exact selection or classification rule that determines which declared targets may receive one mutation.
- **Transport-complete read** — a read whose active capability contract positively proves that all data required by the fixed mutation predicate was returned.
- **Transport proof** — the root-owned record that binds a mutation and its
  targets to required fields, read scopes, and completion witnesses. It also
  records signals, recovery, and a `complete` or `blocked` verdict.
- **Canonical target identity** — the authoritative identity used to join authorization, inspection, intent, action, post-observation, and outcome for one target.
- **Target evidence chain** — the linked root-owned pre-inspection, eligibility and intent, authoritative receipt, independent post-state, ordering, and outcome for one canonical target.
- **Canonical reconciliation** — exact set comparison by canonical target identity across every action and outcome stage.
- **Acceptance manifest** — the single versioned representation of workflow-level target evidence, reconciliation, retention, and final terminal.
- **Evidence repair** — non-mutating, monotonic work that closes evidence gaps without repeating or compensating for an action.
- **Evidence family** — one of the five leaf transition forms or the composite wrapper that determines required identity and state facts.

## Acceptance-capable action path

Before any mutation, prove that the selected tool path can produce:

1. canonical target identity;
2. transport-complete pre-state for the fixed mutation predicate;
3. authoritative action evidence; and
4. an independent root-owned system-of-record post-state.

Receipt-only, aggregate-only, opaque, non-canonical, and non-post-readable paths block before action. Discovery-only tools may still support read-only exploration, but they cannot authorize mutation.

Bind one transport proof to each mutation identity. Declare canonical targets, aggregate scope, relevant versions or states, and every field used for selection or classification before the read. Metadata predicates require complete metadata; content predicates require complete content. A human may choose a different predicate, but cannot declare partial evidence complete.

## Transport proof and completion witnesses

The transport-proof record contains:

- mutation identity, canonical targets, aggregate scope, and fixed predicate;
- required fields and active transport capability;
- read and artifact locators;
- requested and returned scopes;
- counts, pages, cursors, ranges, and authoritative terminal witnesses;
- relevant target versions;
- every truncation, partial, and error signal;
- recovery attempts and their progress;
- the no-progress stop, failed scope, bounded last raw read, completed evidence, live handles, and exact unblock condition when incomplete; and
- a final `complete` or `blocked` verdict.

Completion is capability-specific and positive:

- **Cursor or page reads** reach the authoritative terminal cursor or page witness.
- **Bounded lists** match an authoritative total or the active contract's documented short-page terminal.
- **Single objects** prove the complete object boundary. Use a complete-content
  marker, authoritative length, full-object checksum, or equivalent witness
  from the active contract. Also require all predicate fields and the relevant
  version.
- **Blobs or range reads** prove authoritative length and digest, or gap-free
  coverage of the required byte ranges.
- **Opaque or display-only output** has no mutation-capable completion verdict.

Warning absence, plausible output, a visible subset, a worker boolean, a
generic approval, or naked `complete: true` is not a completion witness. No
universal batch size, retry count, page size, or freshness period exists. Use
the active capability contract and mutation predicate.

A localized incompleteness signal blocks only its identified item or range. A
generic signal invalidates the complete call and every dependent aggregate. An
incomplete target does not block a different mutation with independent complete
evidence. It still blocks an aggregate claim that needs the full set.

## Monotonic evidence repair

Evidence repair can use exact identities, smaller pages, disjoint partitions,
one-object reads, contiguous ranges, or a predeclared authoritative source. It
can normalize and reconcile evidence. It never mutates durable state.

Every recovery step must add coverage or reduce the unresolved scope. Never
repeat an identical incomplete request. Stop at the first no-progress result or
active bound.

If no complete route remains, retain:

- the failed scope;
- all signals and attempts;
- the last raw read under a named forensic cap;
- completed evidence;
- live handles; and
- the exact unblock condition.

Ask a human only when one named answer can create a complete path. Evidence is
not waivable.

A transport-complete historical read proves past completeness only. A stale
read cannot prove current eligibility. A target-version mismatch requires a new
complete read, reinspection, reclassification, and decision-frontier
recomputation before mutation.

After an action attempt, missing evidence triggers reconciliation, not replay.
Evidence repair cannot retry, undo, compensate, or correct a mutation. Each of
those is a new mutation with a new identity, current evidence, and current
authorization under [Authority and Decisions](authority-and-decisions.md).

## Target-level evidence chain

Build one evidence chain per canonical target under one identity:

1. root-owned complete pre-inspection;
2. eligibility and exact intent bound to the mutation identity;
3. authoritative action receipt or result;
4. root-owned independent system-of-record post-observation;
5. contract-backed ordering proof; and
6. target outcome.

Worker post-state statements are claim carriers, not acceptance evidence. Sampling and aggregates may supplement target chains but never replace them.

Ordering prefers an authoritative version, revision, generation, or service sequence. A timestamp is valid only when the active tool contract gives it linearization meaning. Generic wall-clock order is not proof.

Proved aliases require authoritative one-to-one mapping to the canonical identity. Ambiguous aliases block before action. Join every chain and set only by canonical identity.

## Canonical reconciliation and zero-mutation proof

Compare these explicit sets exactly:

- authorized;
- inspected;
- intended;
- attempted;
- receipt-resolved;
- post-verified;
- accepted;
- failed;
- unknown;
- skipped;
- unauthorized; and
- duplicate.

Outcome sets are explicit and disjoint. Derive displayed counts from the sets; count agreement never substitutes for identity agreement. A mismatch cannot be accepted.

A zero-mutation outcome is accepted only after either a transport-complete empty-set proof or evidenced exclusion of every transport-completely inspected candidate. Point reads, uncertain discovery, incomplete lists, sampling, and aggregate totals do not prove a set-wide negative.

## Universal acceptance manifest

Use one versioned acceptance manifest with a `family` discriminator. Do not create an interface per family, adapter registry, plugin system, or separate evidence store.

The manifest contains:

- workflow and revision identity;
- root actor;
- adapter identity and version plus tool-contract digest;
- authorization scope;
- evidence references;
- target entries;
- reconciliation sets and counts derived from them;
- evidence-repair record;
- privacy-minimized retention policy; and
- final terminal.

Every target entry contains:

- canonical identity and proved aliases;
- eligibility;
- exact intent and mutation identity;
- pre-state reference;
- authoritative receipt reference;
- independent post-state reference;
- ordering witness; and
- outcome.

Retain only privacy-minimized evidence:

- durable opaque identities;
- generic state facts;
- counts;
- versions or observation times;
- evidence locators and useful digests;
- completeness status and reconciliation;
- repair attempts;
- outcomes; and
- terminal reason.

Retain raw content only when the active tool contract and authorized boundary
require it.

## Evidence-family field matrix

The universal chain applies to all families. Classify each target by its
authoritative post-state witness, not by product name. Each target uses exactly
one leaf family. The matrix adds the authoritative facts for each form.

| Family | Authoritative identity | Pre-state | Action evidence | Post-state and ordering | Completeness rule |
|---|---|---|---|---|---|
| `record_state` | Service resource identity | Exact relevant fields and version | Receipt bound to resource and mutation | Independent resource read with later version or service sequence | Required predicate fields complete before and after |
| `relationship_set` | Canonical subject, closed relation, canonical object | Exact edge-membership state | Receipt bound to that edge mutation | Independent edge-membership read with authoritative ordering | Both endpoint identities and relation are unambiguous |
| `create_append` | Root client mutation key or preallocated identity, mapped one-to-one to service identity | Collision and eligibility state for the key or allocation | Authoritative create/append result | Result lookup by key or identity with authoritative ordering | Path supports authoritative result lookup; unresolved possible creation is not replayed |
| `delete_erase` | Existing canonical resource identity | Complete existence and deletion-eligibility state | Authoritative delete result | Deletion generation, tombstone, audit record, or authenticated strong-negative witness | Naked not-found is not deletion proof |
| `blob_content` | Stable object identity | Generation, length, digest, and required range coverage | Receipt bound to object generation and mutation | New generation, length, digest, and complete required ranges | No byte gap before or after |
| `operation_composite` | Operation identity plus finite terminal leaf-effect manifest | Declared finite target set and leaf pre-states | Authoritative operation result | Complete leaf-family chains for every effect | Aggregate-only operation blocks before mutation |

The five leaf families and composite wrapper remain semantically distinct even though they share one manifest. Do not collapse family requirements or accept aggregate proof.

## Family outcomes

Apply the common timing rule to each family:

- Pre-action ambiguity, missing canonical identity, incomplete transport, or missing capability is `blocked`.
- After action, missing or unlinked receipt, identity, or post-state that leaves possible effects unresolved is `indeterminate`.
- Authoritative rejection, contradiction, duplicate, unauthorized or out-of-scope effect, or known process violation is `failed`.
- A target is `accepted` only when its complete chain agrees with exact intent.

Specific consequences follow:

- `record_state` and `relationship_set`: incomplete post-read is indeterminate; complete contradiction or unauthorized edge is failed.
- `create_append`: no authoritative result lookup blocks before action; possibly committed creation with unresolved identity is indeterminate; authoritative rejection is failed.
- `delete_erase`: missing post-witness is indeterminate; a complete read proving the target remains is failed.
- `blob_content`: a pre-action byte gap blocks; incomplete post-ranges are indeterminate; complete digest contradiction is failed.
- `operation_composite`: every finite effect must resolve through a leaf family; aggregate counts never establish acceptance.

## Terminal derivation and proof scope

The root derives the final terminal from canonical target sets; it does not trust a worker or receipt total. Pre-action evidence failure is `blocked`. Unresolved possible effects after action are `indeterminate`. Authoritative contradiction, rejection, duplicate, out-of-scope effect, or known process violation is `failed`. Only all-target acceptance yields `accepted`.

The complete workflow outcome vocabulary and precedence belong to
[Authority and Decisions](authority-and-decisions.md). Valid JSON, process
exit, generated artifacts, worker claims, receipts, aggregate counts, review
artifacts, and static passes do not prove accepted external state. They also do
not grant execution authority.
