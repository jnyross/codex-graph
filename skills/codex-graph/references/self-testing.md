# Bounded workflow self-testing

Use this reference when the user asks the skill to test, package, monitor, or
improve a generated workflow. It owns the bounded candidate self-test only.
Self-testing validates the generated artifact; it does not execute the user's
underlying goal, grant authority, prove external state, or determine the final
workflow outcome. Authority-bearing candidates also use
[Authority and Decisions](authority-and-decisions.md) and
[Evidence and Acceptance](evidence-and-acceptance.md).

## 1. Keep the evaluation harness outside the work graph

Self-testing is an evaluation harness around a candidate work graph, not a
reason to add packaging, eval generation, or scoring nodes to that graph.
Create and version the candidate bundle, fixed eval cases, rubric, and expected
evidence as separate artifacts. The child receives stable references to those
inputs; it exercises the candidate graph and returns outputs and evidence.
Scoring remains in the harness, while the candidate graph remains focused on
repeatable work execution.

## 2. Freeze the candidate contract

Before starting a child thread, record a candidate bundle with:

- a stable `candidate_id` and content hash when the active tools can provide one;
- a portable skill_name and bundle root containing `SKILL.md`, the generated
  workflow, and only the references or metadata required to invoke it;
- the complete skill instructions and workflow script, not a truncated excerpt;
- the fixed test goal, acceptance criteria, expected artifacts, and explicit
  non-goals;
- the child isolation mode, project ID, worktree policy, and run tag;
- `allow_nested_self_test: false` and `repair_budget: 1`.

The candidate is an installable skill artifact under test. Prefer the active
file or artifact tool's native bundle/package operation and verify that the
returned bundle contains the declared root files before starting the child.
Do not let the child silently replace
the candidate with a newly designed workflow. If packaging or artifact storage
is unavailable, use the exact bundle in the child prompt and report that
non-portable fallback; do not claim it was installed or invokable elsewhere.

## 3. Use one bounded test run

The self-test graph is:

```text
T0 Freeze and package candidate
  -> T1 Start isolated child thread
  -> T2 Wait and collect structured result
  -> G2{Explicit acceptance pass?}
       | yes -> F1 Report pass and roadmap
       | no  -> R2 Root-cause repair
                 -> T3 Re-run the repaired candidate once
                 -> G3{Revalidation pass?}
                      | yes -> F1
                      | no  -> F2 Report failed evidence and roadmap
```

`T1` and `T2` follow the complete task lifecycle in `task-lifecycle.md`.
Preserve `threadId`, `clientThreadId`, `hostId`, project ID, title, run tag,
state, exact start result, wait observations, and every live handle. A wait
timeout is not a failure; collect fresh state until the declared tool-specific
deadline or polling maximum is reached.

The child prompt must include the candidate bundle, fixed test goal, acceptance
contract, allowed scope, worktree requirement for writes, no nested delegation,
no nested self-testing, and a required terminal JSON handoff. The handoff must
include:

```json
{
  "candidate_id": "string",
  "skill_name": "string",
  "bundle_files": ["SKILL.md", "workflow.js"],
  "status": "passed | blocked | failed",
  "acceptance": {"decision": "pass | fail", "criteria": []},
  "evidence": [{"kind": "test | artifact | observation", "value": "string"}],
  "changed_files": [],
  "issues": [{"root_cause": "string", "evidence": "string", "priority": "string"}]
}
```

Reject malformed, missing, or prose-only handoffs. `status: passed` without
acceptance evidence is not a pass. `blocked` remains blocked unless the
missing access or approval is explicitly resolved; do not repair around it.

## 4. Build the observed roadmap

The roadmap is produced after collection from actual child evidence. Each item
has an ID, observed symptom, root-cause hypothesis, supporting evidence,
priority, and proposed next action. Separate confirmed root cause from
hypothesis. Include successful observations when they reveal a useful
regression test or reusable guardrail. Keep the roadmap outside the candidate
acceptance contract so it cannot expand the current test scope.

## 5. One repair and re-run

If `G2` fails for a fixable candidate defect, `R2` performs one smallest
evidence-led repair. The parent owns the repair; the child never edits the
candidate or its own test instructions. Revalidate the same fixed goal and
criteria with the repaired candidate in a fresh child thread and a new run tag.
Do not create a second repair branch, retry indefinitely, substitute a different
model, or broaden the acceptance scope.

The repair is not appropriate for missing credentials, unavailable tools,
approval-gated actions, or an ambiguous test contract. Return `blocked` with the
live handle and exact unblock condition. If `T3` fails, return `failed` with
both runs, the root-cause evidence, the repair diff or rationale, and the
roadmap. A later invocation may consume that roadmap as a new, explicitly
scoped test goal.

## 6. Terminal result requirements

When active, the parent terminal object includes:

- `self_test.status`: `passed`, `blocked`, or `failed`, scoped only to this
  candidate self-test;
- `candidate_id`, bundle identity, and fixed test contract;
- child run handles and terminal verdicts for the initial and repair runs;
- observed evidence and validation decision;
- `roadmap`: observed issues and improvements only;
- `repair_used`: one boolean covering the self-test repair;
- all still-live handles and the exact next action.

Never claim the workflow is self-improving merely because a roadmap was
generated. Improvement requires an observed defect, an evidence-led repair, and
an explicit re-run result.
