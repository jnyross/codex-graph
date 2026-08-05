# Topology library

Use these patterns as starting points for Part 1 and as the execution skeleton for Part 2. Rename every node, tailor every contract, and preserve the same node IDs in the JavaScript `WORKFLOW` metadata. Do not force parallelism onto a trivial task.

Select the lowest progressive-complexity tier whose trigger is already proven.
The small-change pattern is the explicit L0 baseline. Each pattern notes which
stages are escalation-gated rather than baseline.

## Artifact boundary

The topology describes repeatable work execution, not the lifecycle of every
input or evaluation asset. Create and version prerequisite artifacts separately,
then pass stable references into the graph. This includes eval cases, fixtures,
benchmark data, rubrics, reference answers, seed datasets, and scoring
harnesses. A graph can consume an existing evaluator or emit evidence for an
external scorer, but artifact creation and post-run scoring are not graph nodes
unless they are explicitly the repeatable work being requested.

## Selection guide

| Task family | Safe parallel work | Serialized authority | Typical gate | Script shape |
|---|---|---|---|---|
| Small change | Usually none; optionally location and test scans | Edit and acceptance | Targeted test or static check | One worker, validator, conditional repair |
| Feature or refactor | Architecture, contract, test, and dependency scans | Plan, overlapping writes, integration | Tests plus diff review | Parallel reconnaissance, one writer, parallel validation |
| Debugging or investigation | Reproduction, trace, history, competing hypotheses | Root-cause decision and fix | Original reproduction plus regression test | Parallel evidence workers, one fixer, two checks |
| Research or analysis | Official sources, community evidence, counterevidence | Claim reconciliation and synthesis | Claim/citation audit | Parallel collectors, one synthesizer, one verifier |
| Audit or review | Correctness, security/privacy, tests, provenance | Deduplication and severity | Evidence verification | Parallel lenses, one reconciler, one verifier |
| Migration or rollout | Inventory, compatibility, tests, rollback analysis | Sequencing and integration | Compatibility and rollback checks | Parallel inventory, one staged implementer, two checks |
| Mixed | Bounded decomposition and independent branches | Cross-branch synthesis | Goal-specific | One decomposition stage, bounded branch batches, one join |

## Pattern: small change

Use when the change is narrow and extra workers would add coordination cost.

```mermaid
flowchart TD
    N1[Inspect named area and applicable instructions] --> N2[Make the smallest change]
    N2 --> V1[Run targeted validation]
    V1 -->|pass| T1[Return evidence-backed result]
    V1 -->|repair required| R1[Apply one minimal repair]
    R1 --> V2[Re-run targeted validation]
    V2 -->|pass| T1
    V2 -->|fail| X1[Stop with evidence]
```

**Script mapping:** run `N1` and `N2` in one implementation-owner prompt when their separation adds no value; keep their IDs in the workflow metadata. Parse `V1` as machine-readable JSON. Use one conditional `if` for `R1` and `V2`.
**Tier:** L0 baseline; `R1` and `V2` are conditional repair stages, not baseline.

## Pattern: feature or refactor

Parallelize reconnaissance. Keep integration under one owner. Split implementation only for disjoint write scopes.

```mermaid
flowchart TD
    N1[Confirm goal scope and repository rules] --> N2A[Map architecture and call paths]
    N1 --> N2B[Map contracts and compatibility constraints]
    N1 --> N2C[Map tests and acceptance evidence]
    N2A --> N3[Synthesize minimal implementation plan]
    N2B --> N3
    N2C --> N3
    N3 --> N4[Implement and integrate under one owner]
    N4 --> V1A[Run targeted tests]
    N4 --> V1B[Review diff correctness and regression risk]
    V1A --> G1{Validation gate}
    V1B --> G1
    G1 -->|pass| T1[Return evidence-backed result]
    G1 -->|repair required| R1[Apply one smallest repair]
    R1 --> V2[Revalidate affected checks]
    V2 -->|pass| T1
    V2 -->|fail| X1[Stop with evidence]
```

**Script mapping:** spawn `N2A–N2C` concurrently after `N1`; wait for all required handoffs; give them to one `N3/N4` integration owner. Run `V1A` and `V1B` concurrently only because they are read-only after integration. Join both into one gate decision.
**Tier:** L2 baseline for bounded discovery; `V1A`, `V1B`, and `G1` are L3
escalation-gated validation stages.

## Pattern: debugging or investigation

Collect independent evidence before selecting a hypothesis.

```mermaid
flowchart TD
    N1[Define symptom and success condition] --> N2A[Reproduce and capture failure]
    N1 --> N2B[Trace code and state transitions]
    N1 --> N2C[Inspect history docs and recent changes]
    N2A --> N3[Rank hypotheses against evidence]
    N2B --> N3
    N2C --> N3
    N3 --> N4[Implement minimal root-cause fix]
    N4 --> V1A[Re-run original reproduction]
    N4 --> V1B[Run targeted regression tests]
    V1A --> G1{Validation gate}
    V1B --> G1
    G1 -->|pass| T1[Return evidence-backed result]
    G1 -->|repair required| R1[Apply one evidence-led repair]
    R1 --> V2[Repeat reproduction and affected tests]
    V2 -->|pass| T1
    V2 -->|fail| X1[Stop with evidence]
```

**Script mapping:** parallel workers may propose hypotheses but cannot choose the root cause. `N3` is the sole evidence-reconciliation agent. `N4` is the sole writer unless the goal proves disjoint scopes.
**Tier:** L2 when competing evidence is proven; parallel evidence workers and
the extra validation lane are escalation-gated.

## Pattern: research or analysis

Use source diversity and independent audit lenses. Keep synthesis distinct from collection and root acceptance.

```mermaid
flowchart TD
    N1[Define questions claims and evidence standard] --> N2A[Collect official primary sources]
    N1 --> N2B[Collect community implementations and operating evidence]
    N1 --> N2C[Collect data counterevidence and dissenting views]
    N2A --> N3[Verify provenance dates and claim support]
    N2B --> N3
    N2C --> N3
    N3 --> N4[Synthesize answer with calibrated confidence]
    N4 --> V1A[Audit sources dates and status]
    N4 --> V1B[Audit claim-to-evidence support]
    N4 --> V1C[Audit coverage duplicates and omissions]
    N4 --> V1D[Challenge false certainty and counterevidence]
    V1A --> G1{Root acceptance gate}
    V1B --> G1
    V1C --> G1
    V1D --> G1
    G1 -->|pass| T1[Produce final artifact]
    G1 -->|one revision required| R1[Revise named claims once]
    R1 --> V2[Re-run affected audit lenses and global invariants]
    V2 -->|pass| T1
    V2 -->|fail| X1[Stop with explicit gaps]
```

**Script mapping:** `N1` freezes one acceptance contract, including the pilot size, selection rule, required evidence fields, audit thresholds, publication rule, and repair boundary. Source collectors return concise claim/evidence indexes, preserve full acceptance evidence in a durable artifact, and put deferred candidates in an expansion queue. `N3/N4` receives bounded handoffs and owns reconciliation into one canonical record schema. Run `V1A-V1D` concurrently because they are read-only and independent; each returns strict JSON with affected claim IDs and declared criterion IDs. Only `G1` can accept the artifact or set the single repair scope. If many records fail, `R1` may use bounded record-specific correction shards, but one serial owner must normalize and integrate them once before `V2`.
**Tier:** L2 for source discovery, L3 for independent audit lenses, and L4
for the expansion queue, record-specific repair shards, checkpoints, and
resume. The collectors, audit lanes, `G1`, and L4 repair machinery are
escalation-gated unless their triggers are proven at design time.

## Pattern: audit or review

Use independent lenses, then deduplicate and verify before assigning severity.

```mermaid
flowchart TD
    N1[Confirm scope authority and review standard] --> N2A[Review correctness and failure modes]
    N1 --> N2B[Review security privacy and side effects]
    N1 --> N2C[Review tests coverage and operability]
    N1 --> N2D[Review provenance docs and stale assumptions]
    N2A --> N3[Deduplicate and reconcile findings]
    N2B --> N3
    N2C --> N3
    N2D --> N3
    N3 --> N4[Verify each material finding against evidence]
    N4 --> V1[Prioritize findings and minimal fixes]
    V1 -->|evidence sufficient| T1[Return final review]
    V1 -->|one verification gap| R1[Resolve highest-impact gap once]
    R1 --> V2[Recheck affected finding]
    V2 -->|resolved| T1
    V2 -->|unresolved| X1[Report uncertainty without overclaiming]
```

**Script mapping:** fan out `N2A–N2D` with a maximum of four workers. Only `N3` can deduplicate or assign canonical finding IDs. Treat the repair path as evidence repair, not permission to modify the reviewed system unless requested.
**Tier:** L3 when independent review lenses are proven; `N2A–N2D` and the join
are escalation-gated. The baseline is one review owner and one validator.

## Pattern: migration or rollout

Front-load compatibility and rollback analysis. Keep implementation staged.

```mermaid
flowchart TD
    N1[Define target state and no-go boundaries] --> N2A[Inventory current usage and dependencies]
    N1 --> N2B[Check compatibility and breaking changes]
    N1 --> N2C[Map tests rollout and rollback evidence]
    N2A --> N3[Choose smallest staged migration plan]
    N2B --> N3
    N2C --> N3
    N3 --> N4[Implement first safe stage]
    N4 --> V1A[Run compatibility and regression tests]
    N4 --> V1B[Review rollback and operational readiness]
    V1A --> G1{Validation gate}
    V1B --> G1
    G1 -->|pass| T1[Report result and next-stage boundary]
    G1 -->|repair required| R1[Apply one minimal repair]
    R1 --> V2[Revalidate failed checks]
    V2 -->|pass| T1
    V2 -->|fail| X1[Stop and preserve rollback path]
```

**Script mapping:** `N4` implements only the first safe stage. The graph must not silently continue to later rollout stages. Approval-gated deployment remains a terminal boundary, not a worker action.
**Tier:** L2 for independent inventory and compatibility discovery; additional
validation is escalation-gated.

## Mixed-task adaptation

For a mixed goal, add a short decomposition stage that produces a finite list of branches and proves their independence. Execute branches with the active tool's supported concurrency; if a measured limit appears, use staged fan-in. Join them under one synthesis owner. Do not allow branches to spawn their own agents.

## General adaptation rules

- Add a current-documentation branch to coding work when an API or version may have changed.
- Add a security/privacy lens only when the goal touches trust boundaries, credentials, personal data, permissions, or untrusted input.
- Add a performance branch only when the goal has a measurable performance requirement.
- Do not split tightly coupled implementation merely to create visual parallelism.
- Prefer a fresh validator that receives acceptance criteria, the diff or artifact, and raw evidence rather than the implementer's narrative alone.
- Keep terminal states explicit: passed, blocked, failed, or unresolved with evidence.
- Keep graph labels readable; put detailed prompts and handoff schemas in node contracts and the JavaScript, not inside Mermaid boxes.
- When a graph node is represented by a gate rather than a worker, encode it as an explicit function or conditional in the script and list it in `WORKFLOW.nodes`.
