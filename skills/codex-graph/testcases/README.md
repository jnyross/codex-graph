# codex-graph testcase conformance

These six offline cases bind generation to one canonical goal and one immutable structural contract. A testcase pass proves only offline conformance. It does not prove runtime behavior, external facts, transport completeness, post-state, or permission to execute.

## Binding

A prompt author must select an exact `case_id` before generation. Call `resolveCase({ case_id })` from `harness/conformance.js`. The resolver loads `GOAL.md` and `contract.json` together, validates and normalizes the contract, checks the canonical-goal digest, calculates the contract digest, and returns one deeply frozen binding.

Do not combine a selected case with a custom goal. Missing, unknown, ambiguous, duplicate, contradictory, or digest-mismatched facts fail closed. The resolver never selects a nearby case.

Generation and validation must use the same resolved binding. Generated metadata must echo:

- `case_id`;
- `schema_version`;
- `canonical_goal_digest`;
- `contract_digest`;
- `artifact_digest`;
- `proof_scope: "offline-structural-conformance-only"`;
- a one-to-one `role_map` from contract roles to graph-local node identities; and
- the generated structural declarations.

The generated Mermaid graph and executable must use the mapped graph-local identities. The executable must export the same structure for offline parsing, for example:

```js
const workflowStructure = {
  nodes: [],
  edges: [],
  concurrency: [],
  gates: [],
  repair_edges: [],
  terminal_paths: [],
  collection: {},
};

if (typeof module !== "undefined") module.exports = workflowStructure;
await runWorkflow(workflowStructure);
```

The executable must pass that same object to its single `runWorkflow` entry. The guarded export is inert in Code Mode and gives the offline matcher one parsed executable field. It is not a second declaration of the contract.

## Contract ownership

- The skill owns semantic-role meanings and reliability invariants.
- `harness/conformance.js` owns contract field and matcher semantics.
- Each case owns its required role instances, topology, environments, concurrency, gates, repair edges, terminal paths, and exact-text assertions.
- Each generated artifact set owns its graph-local node identities and role mapping.

Semantic role kinds are:

- `contract`: freezes case scope and machine facts;
- `discovery`: gathers one bounded read-only input;
- `writer`: changes one declared isolated scope;
- `validator`: checks one declared criterion;
- `integration`: combines handoffs under one owner;
- `gate`: routes using declared outcomes;
- `repair`: applies the one declared bounded repair;
- `terminal`: ends one declared path.

Role instance names are case-local semantic identities. Generated node IDs are artifact-local. Neither is a universal node alphabet.

## Layout

```text
testcases/
  cases/<id>/
    GOAL.md          canonical goal
    contract.json    canonical normalized-contract source
  harness/
    conformance.js   resolver, digest calculation, and structural matcher
    check_workflow.js
    testcases.test.js
```

There is no catalog authority, topology hint, expectation document, lexical matcher, or compatibility loader. Case discovery reads the case directories. There is no standalone JSON Schema because the resolver is the only schema consumer.

## Conformance

The matcher parses `workflow.js` once with Acorn without evaluating it, uses the bundle's shared Mermaid parser, and compares the contract, metadata, graph, and executable after role normalization. The artifact digest covers the complete generated metadata, graph source, and executable source. Literal assertions inspect only the named parsed field where exact text is the contract. Comments and unrelated identifiers receive no credit.

A verdict contains case, schema, contract, and artifact identities; stable criterion IDs; structural locators; unmatched facts; pass/fail state; and the explicit offline-only scope.

Run the focused seam:

```bash
npm ci
node --test skills/codex-graph/testcases/harness/testcases.test.js
```

Check one generated artifact set:

```bash
node skills/codex-graph/testcases/harness/check_workflow.js \
  --case atomic-screen-fanout \
  --metadata /path/to/metadata.json \
  --graph /path/to/graph.mmd \
  --script /path/to/workflow.js
```
