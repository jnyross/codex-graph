# Gate node contract findings

## Scope and evidence

This finding compares the offline `disjoint-writers-worktree` case contract with the
frozen Lisbon v7 candidate. The case is an offline static gate; it does not execute a
workflow (`skills/codex-graph/testcases/README.md:9-10`, `104-107`). The frozen
candidate was blocked before execution, so no runtime task or terminal result can be
used as evidence (`candidates/frozen-lisbon-v7/CRITIQUE-v7.md:22-44`, frozen lab
commit `508b1ce`).

The key fact is that these are different inputs: the case goal asks for two independent
example generators plus a root index (`skills/codex-graph/testcases/cases/disjoint-writers-worktree/GOAL.md:1-28`),
whereas the frozen prompt asks for Lisbon research, two Lisbon draft writers, and a
Lisbon report (`candidates/frozen-lisbon-v7/PROMPT.txt:1-5`). The v7 bytes were not
generated from the case goal or its node alphabet.

## Where the IDs and snippets come from

The case's fenced JSON in `EXPECTATIONS.md` is the machine contract. It is the source
of the exact required IDs, parallel groups, environment lists, collection assertions,
markers, and literal snippets (`skills/codex-graph/testcases/cases/disjoint-writers-worktree/EXPECTATIONS.md:41-66`):

| Contract item | Case source | Intended assertion |
|---|---|---|
| `N1`, `D1`, `D2`, `W1`, `W2`, `V1`, `G1`, `R1`, `V2`, `T1` | `EXPECTATIONS.md:45-49` | The generated script contains the case's stable node vocabulary. The prose assigns `N1` scope confirmation; `D1`/`D2` local read-only discovery; `W1`/`W2` disjoint worktree writers; `V1` validation; `G1` the gate; `R1` one repair; `V2` revalidation; and `T1` root publication (`EXPECTATIONS.md:14-21`). |
| `[[D1,D2],[W1,W2]]` | `EXPECTATIONS.md:48-50` | The two discovery nodes and two writer nodes are separate settled parallel batches. `Promise.allSettled` is required when groups are present (`README.md:67-68`; `expectations.js:168-189`). |
| `env.local` and `env.worktree` lists | `EXPECTATIONS.md:50-53` | Environment is selected per node: discovery/root/read-only work uses local, writers use isolated worktrees; a global worktree for discovery is the #14 regression (`EXPECTATIONS.md:19-21`; `README.md:69-72`). |
| `read_first`, `read_after_wait`, budget `20000` | `EXPECTATIONS.md:54-58` | Collection must read before the first wait, read again after waits, and keep every literal item budget at or below 20,000 (`README.md:73-89`; `task-lifecycle.md:231-244`). |
| `pending_setup_resolution`, `repairUsed`, `terminalEmitted` | `EXPECTATIONS.md:59-61` | Pending `clientThreadId` setup must have bounded resolution evidence; exactly one repair and one terminal guard must be represented (`README.md:90-97`; `expectations.js:304-341`). |
| `allSettled`; absence of `apply worktree to every node` | `EXPECTATIONS.md:62-65` | Required/forbidden literal tripwires (`expectations.js:344-359`). |

`check_workflow.js` loads the selected case and passes the script text to the static
checker, returning JSON and a non-zero exit on any failed check
(`skills/codex-graph/testcases/harness/check_workflow.js:37-41`). Required node IDs
are checked as verbatim word-boundary text, not as parsed declarations
(`expectations.js:163-166`). Environment checks count only literal
`type: "local"`/`type: "worktree"` (`expectations.js:45-48`, `192-222`), and
collection ordering searches await-adjacent tool/helper call sites
(`expectations.js:224-301`).

The expected topology independently repeats the case alphabet, including a distinct
`G1` gate (`skills/codex-graph/testcases/cases/disjoint-writers-worktree/topology.hint.mmd:1-15`).

## What the skill promises about naming

The generator guidance promises **graph-local identity and parity**, not a universal
case-catalog alphabet:

* Every node gets a stable short ID such as `N1`, `N2A`, or `V1`, plus a concrete
  goal-specific label (`skills/codex-graph/SKILL.md:88-96`).
* Part 1 and Part 2 must agree one-for-one; the script metadata must contain node IDs,
  dependencies, scopes, handoffs, gates, concurrency, and repair allowance
  (`SKILL.md:198-230`).
* The topology library explicitly says to rename every node for the goal while
  preserving those renamed IDs in JavaScript `WORKFLOW` metadata
  (`references/topology-library.md:1-5`). A gate may be a conditional, but it is
  supposed to be explicit and listed in `WORKFLOW.nodes` (`topology-library.md:198-208`).
* The progressive-complexity reference uses `D*`, `G1`, and related names as action
  vocabulary for a tier, not as a mandatory alphabet for every free-form goal
  (`references/progressive-complexity.md:150-170`).

The skill does separately promise per-node environment semantics and lifecycle
behavior: local for read-only work, worktree for repository writers, no global
worktree, and root-owned publication (`SKILL.md:185-196`; `references/code-mode-script-patterns.md:197-215`).
It also promises read-first/read-after-wait collection (`references/task-lifecycle.md:231-244`).
None of those rules says that an unconstrained Lisbon generation must emit the IDs from
`disjoint-writers-worktree/EXPECTATIONS.md`.

## Frozen v7 versus the case

The frozen graph uses `N0`, `N1A`/`N1B`/`N1C`, `J1`, `W1`, `W2`, `I1`, `N2`, `V1`,
`R1`, `V2`, `T1`, and `X1` (`candidates/frozen-lisbon-v7/graph.mmd:1-37`). Its
`WORKFLOW.nodes` metadata uses the same Lisbon names except that the safe-stop `X1`
is represented by the blocked terminal path rather than listed as a node
(`candidates/frozen-lisbon-v7/workflow.js:25-40`). It has no declared `D1`, `D2`, or
`G1`.

The frozen positive result is reproducible and says `ok: false`
(`candidates/frozen-lisbon-v7/check-workflow-positive.json:1-4`):

| Failed check | Result | Classification | Evidence and explanation |
|---|---:|---|---|
| `node:D1` | false | **Naming mismatch / missing case binding** | The case requires `D1` (`EXPECTATIONS.md:48`), while v7 declares `N1A`/`N1B`/`N1C` research nodes (`graph.mmd:3-5`; `workflow.js:25-30`, `285-289`). Raw failure: `check-workflow-positive.json:10-14`. |
| `node:D2` | false | **Naming mismatch / missing case binding** | Same contract mismatch; raw failure: `check-workflow-positive.json:15-19`. |
| `node:G1` | false | **Naming mismatch / missing case binding** | The case requires a distinct `G1` validation gate (`EXPECTATIONS.md:14-18`, `topology.hint.mmd:8-15`). v7 has a `V1` validator whose decision branches directly to repair (`workflow.js:335-338`), so the case's literal gate ID is absent. Raw failure: `check-workflow-positive.json:35-39`. This is not proof that v7's Lisbon validation had no decision; it is proof that the case's gate label was never bound into generation. |
| `parallel:group1` | false | **Naming mismatch (derived)** | The checker only tests that `D1` and `D2` occur in the script (`expectations.js:178-188`). v7 does have a concurrent research batch (`workflow.js:285-297`), but its members are `N1A`/`N1B`/`N1C`, not the case's `D1`/`D2`. Raw failure: `check-workflow-positive.json:60-64`. |
| `env:worktree-writers` | false | **Static shape/recognition mismatch, not a confirmed runtime behavior gap** | The checker requires a literal `type: "worktree"` (`expectations.js:45-46`, `205-211`). v7 stores `environment: "worktree"` in writer specs and constructs `{ type: environment }`, then passes `{ type: node.environment }` per node (`workflow.js:156-165`, `302-306`). Thus the generated bytes contain no literal `type: "worktree"`, explaining the false check, but the runtime construction is per-node worktree as the skill requires. Raw failure: `check-workflow-positive.json:70-74`. |
| `env:local-nodes` | false | **Static shape/recognition mismatch, not a confirmed runtime behavior gap** | The checker requires a literal `type: "local"` (`expectations.js:45`, `213-220`). v7 uses local node-spec values and the same dynamic constructor (`workflow.js:27-29`, `156-165`, `285-289`). The frozen code therefore lacks the literal shape the harness recognizes while preserving the intended local environment behavior. Raw failure: `check-workflow-positive.json:75-79`. |
| `collection:read-after-wait` | false | **Harness recognition gap, not a confirmed behavior gap** | The actual collector performs `await read()` before the loop, then `await waitThreads.call(...)`, then `await read()` after every wait (`workflow.js:208-229`, especially `219-227`). The checker resolves only same-line function-like bindings or declared `function` helpers (`expectations.js:54-84`); v7's multiline arrow helper has no same-line tool stem (`workflow.js:211-218`), so `await read()` is not recognized after the wait. Raw failure: `check-workflow-positive.json:90-94`. |

There are no other failed checks in the frozen positive result. `Promise.allSettled`,
W1/W2, repair, terminal guard, bounded pending resolution, item budget, the required
`allSettled` snippet, and the forbidden phrase all pass (`check-workflow-positive.json:55-59`,
`65-69`, `95-123`). The apparent `node:N1` pass is also only lexical evidence: the
actual metadata has `N1A`/`N1B`/`N1C`, while the token `"N1"` occurs in prefix filters
(`workflow.js:335`, `350`); this illustrates why the gate is a conservative textual
tripwire rather than declaration-aware validation.

## Verdict

**Primary verdict: missing binding between skill guidance and harness cases.**

This is not primarily a generator defect: for the actual Lisbon prompt, v7 chose
stable, goal-specific IDs and implemented the skill's per-node local/worktree and
collection behavior. It is not primarily a case defect: the synthetic
`disjoint-writers-worktree` goal, topology hint, and machine contract consistently pin
`D1`/`D2`/`G1` and the associated assertions. The generation request never supplied
that case contract, and the offline gate was then run against the unrelated Lisbon
workflow.

The secondary defect is **harness-shape sensitivity**: dynamic but behaviorally
conforming environment construction and a nested read helper are not recognized by
literal/static heuristics. Therefore, among the seven failed checks, four are naming
mismatches (three missing IDs plus the derived discovery-group check), and three are
static shape/recognition mismatches. **No failed check establishes a real runtime
behavioral gap in the frozen bytes**, and the frozen candidate must still be treated as
red because the static case contract was not satisfied and execution was correctly
blocked.

A reliable future gate needs one explicit binding before generation: either generate
from the selected case's `GOAL.md`/`EXPECTATIONS.md` and preserve its IDs, or select a
case whose contract matches the generated goal. Separately, the harness can reduce
false negatives by recognizing dynamic environment constructors and multiline helper
bindings, or generation can emit the literal forms the current checker recognizes.
