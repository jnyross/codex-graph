# Dynamic-workflow test-case catalog for codex-graph

This catalog turns real dynamic multi-agent workflow shapes that the user runs
on Grok (Rhai orchestration) and Claude (subagent/team orchestration) into
CodexGraph regression and golden test cases. The goal: exercise the skill
against real user orchestration patterns, not only the Lisbon dogfood graph.

Sources were read for **topology shape** only. Goals in the test cases are
synthetic and anonymized; no personal itinerary or family data is copied.

## 1. Candidate workflow survey

| # | Source | Domain | Phases | Fan-out | Join style | Validation style |
|---|---|---|---|---|---|---|
| W1 | `~/.grok/workflows/destination-discovery.rhai` (v3 coverage audit) | Consumer discovery/research | Seed → Generate → Complete → Screen → Cluster → Research → Factcheck → Synthesize | ~17 atomic generators (8 region + 6 archetype + 1 mode + 2 contrarian); 14 slice critics; 1 screener **per candidate**; 1 POV per cluster; 1 fact-checker per POV | Deterministic pool dedupe in orchestrator; single cluster agent with identity-map fallback | Hard gates only at screen (fail-open PASS on agent failure); adversarial per-POV fact-check; **non-binding** light synthesis (human ranks; league tables forbidden) |
| W2 | `~/.grok/workflows/hotel-resort-discovery.rhai` | Consumer discovery/research | Seed → Generate → Screen → Research → Factcheck → Synthesize | Generate = shortlist × 3 lenses (luxury/apartment/resort); screen/research/factcheck = 1 job per hotel | Orchestrator pool + soft per-parent cap (seeds first) | Atomic hard-gate screen (fail-open); sealed stay packs; adversarial fact-check; non-binding matrix |
| W3 | Session `wf_019f9a98…` (destination-discovery v1) | Consumer discovery | Generate → Complete → Screen → Research → Factcheck → Judge | 4 fixed lenses; screen in batches of 9; POV per survivor; 3 blind judges | Loop-until-dry critic (max rounds + dry threshold); index-aligned result zip | Blind vote panel with distinct priorities → **binding** aggregate |
| W4 | Session `wf_019f9ab7…` (destination-discovery v2 atomic) | Consumer discovery | Seed → Generate → Complete → Screen → Research → Factcheck → Judge | ~17 atomic generators + 14 slice critics; 1 screener per candidate | force_deep bypasses screen; survivor cap keeps priority first | Sealed POVs; adversarial fact-check; 3 blind judges → binding synthesis |
| W5 | Session `wf_019f9aeb…` (destination-discovery v3) | Consumer discovery | as W1 | as W1 | as W1 | as W1 |
| W6 | Session `wf_019f9b53…` (hotel-resort-discovery) | Consumer discovery | as W2 | as W2 | as W2 | as W2 |
| W7 | Session `wf_019fa823…` (agents-md-lean-research, research-first) | Technical research | Research → Counterexamples → Synthesize → Baseline → Compare | 1 panel of 5 fixed source lanes | Schema-gated digests; fail-open drop of empty lanes; fail-closed synth | Sequential adversarial counterexample lane; baseline arm as non-binding A/B control |
| W8 | Session `wf_019fa822…` (agents-md-lean-research, baseline-first twin) | Technical research | Baseline → Research → Counterexamples → Synthesize | same 5 fixed lanes | All-lanes-empty fails closed | Baseline-first A/B; synth embeds comparison |
| W9 | Session `wf_019fa820…` (agents-md-prune-research) | Technical research | Fan-out → Synthesize | 4 fixed source lanes | Single synth agent | Schema-only; fail-open partial result |
| C1 | `~/.claude/agents.md`, `CLAUDE.md` history | Coding orchestration | Plan → fan-out → integrate | Director + isolated atomic subagents (~3–5 concurrent) | Orchestrator-only integration; workers context-sealed | Two-stage: implementer then fresh verifier |
| C2 | `~/.claude/teams/*/config.json` (research + planning teams) | Research/planning | Lead → topic researchers → serial compiler | 4–5 parallel topic workers with file handoffs | One serial report compiler | Compiler-owned reconciliation |
| C3 | `~/.claude/teams/pageindex-integration` + two-mac orchestration backups | Coding | Claim → implement → integrate | Disjoint implement teammates; worktree-isolated parallel implementers | Shared task list; sibling module contracts | Disjoint write scopes; orchestrator merge |
| C4 | `feature-dev` / `code-review` plugin commands | Coding review | Explore → architect → implement → review | 2–3 explorers; 5 review lenses; parallel confidence scorers | Human approval gates between phases | Score threshold (≥80) gate before publication |

## 2. Cross-cutting semantics worth encoding

1. **Atomic screen agents** — exactly one candidate in, one verdict out
   (W1/W2/W4). Verdict schema `{name, verdict, reason, gate_failed}`. Screen
   failure is a *root-owned policy decision* (Grok fails open to PASS); the
   worker never decides pool membership.
2. **Parallel generate by disjoint slice** — one generator per region /
   archetype / lens; slice quota; orchestrator dedupes into a pool with
   deterministic plain-code rules (exact-name match, priority-first upgrade).
3. **Sealed decision packs** — per-item deep research worker that "knows
   nothing about other candidates"; fixed handoff schema with exactly N
   load-bearing claims + sources; full dossiers go to a durable artifact, not
   into the join payload (W1 explicitly caps synth input to compact cards).
4. **Adversarial fact-check lanes** — one refuting checker per pack; outcomes
   `CONFIRMED | CONTRADICTED | UNVERIFIABLE-ONLINE`; a failed checker is
   recorded as UNVERIFIABLE, never as confirmation (fail-closed evidence).
5. **Non-binding synthesis** — human ranks; synthesis is forbidden from
   declaring winners; acceptance authority stays at the root gate. This is the
   exact inverse of the Lisbon v1 defect (#12) where a synthesis worker
   self-blocked on downstream audit obligations.
6. **Blind vote panels** — N judges with distinct priorities in one flat
   panel, regrouped by index arithmetic; binding aggregate happens in one
   serial owner (W3/W4).
7. **Loop-until-dry critics** — bounded rounds + dry threshold (W3). In
   CodexGraph this must stay a *bounded, declared* stage — never an open cycle.
8. **Per-node environment** — all Grok discovery work is effectively
   "local" (read-only web research); Claude implement teams use worktree
   isolation only for writers (C3). Matches skill contract #14.

## 3. Mapping to CodexGraph tiers and contracts

Contract IDs refer to shipped fixes: **#11** normalize string tool results +
preserve start-failure handles; **#12** node-local worker prompt scoping;
**#13** read-first collection (read before first wait, read after every
wait); **#14** per-node environment + pending `clientThreadId` resolution.

| Case id | Derived from | Task family | Baseline tier | Topology template | Must-hit contracts |
|---|---|---|---|---|---|
| `atomic-screen-fanout` | W1/W2/W4 screen phase | Research or analysis | L2 (+T4 gate on cardinality) | Parallel collectors → root-owned pool policy | #13 read-first; #12 node-local gate prompts; root-owned fail-open policy; env local everywhere |
| `slice-generators-join` | W1/W4 generate + complete | Research or analysis | L2 | Disjoint-slice fan-out → one integration owner | #11 result normalization; single owner dedupe; no nested delegation; env local |
| `sealed-pov-factcheck` | W1/W2 research + factcheck | Research or analysis | L3 | Sealed per-item workers → adversarial per-item validators → root gate | #12 sealed prompts; fail-closed evidence (UNVERIFIABLE ≠ confirmed); durable artifact + compact handoffs |
| `nonbinding-synthesis-gate` | W1/W5 light synthesis; Lisbon #12 defect | Research or analysis | L3 | Collectors → non-binding synthesizer → root acceptance gate | #12 (synthesis must not self-block or own publication); #13 |
| `adversarial-dual-validation` | W3/W4 blind judges; W7/W8 A/B arms; C4 scorers | Audit or review | L3 | Flat items×votes panel, index-arithmetic regroup, one root gate | Fail-closed malformed verdicts; #13; one binding aggregate owner |
| `disjoint-writers-worktree` | C3 disjoint implementers; C1 director/worker | Feature or refactor | L2 (+L3 validation) | Local read-only discovery → two disjoint worktree writers → root publishes | #14 per-node env + pending setup resolution; disjoint write scopes; root-owned publication |

Deliberately not first-class (covered implicitly or too thin):

- W3 loop-until-dry critic — an open-ended loop is anti-pattern in CodexGraph;
  its bounded form is covered by the one-repair invariant tests.
- W9 minimal 2-phase research — subsumed by `slice-generators-join`.
- C4 human approval gates — approval boundaries are a terminal/safe-stop
  concern already covered by SKILL.md baseline constraints.
- W1 cluster join with identity fallback — folded into
  `slice-generators-join` expectations (single join owner, deterministic
  fallback).

## 4. Prioritized shortlist

1. `atomic-screen-fanout` — highest-volume real pattern (24–100+ atomic
   verdict agents); stresses collection budgets and read-first (#13).
2. `sealed-pov-factcheck` — sealed worker scoping (#12) + adversarial
   evidence gating; the core "decision pack" handoff schema.
3. `nonbinding-synthesis-gate` — direct regression for the shipped Lisbon
   defect class (#12): root gate owns acceptance, worker never self-blocks.
4. `disjoint-writers-worktree` — direct regression for #14: env per node,
   never global worktree, provisioning-scale pending-setup bounds.
5. `adversarial-dual-validation` — L3 dual/blind validators with fail-closed
   malformed verdicts.
6. `slice-generators-join` — disjoint-slice fan-out with one integration
   owner and #11 result normalization.

Each case ships as `skills/codex-graph/testcases/cases/<id>/` with `GOAL.md`
(the free-form goal `$codex-graph` would receive), `EXPECTATIONS.md` (prose +
one fenced machine-readable JSON block), and `topology.hint.mmd` (expected
shape; must pass `graph_coherence.py`). `testcases/harness/` validates the
bundle offline and can statically check a generated `workflow.js` against a
case's expectations. No live ChatGPT Desktop run is required for CI green;
lab dogfood (mac-vm-harness) remains separate.
