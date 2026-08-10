"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  OFFLINE_SCOPE,
  calculateArtifactDigest,
  checkConformance,
  listCaseIds,
  resolveCase,
} = require("./conformance.js");
function executableSource(structure, trailer = "") {
  return [
    `const workflowStructure = ${JSON.stringify(structure, null, 2)};`,
    'if (typeof module !== "undefined") module.exports = workflowStructure;',
    "await runWorkflow(workflowStructure);",
    trailer,
  ].join("\n");
}

function executableStructure(source) {
  return JSON.parse(
    source.match(/const workflowStructure = ([\s\S]*?);\nif \(/)[1],
  );
}


function localize(binding) {
  const roleMap = Object.fromEntries(
    binding.contract.role_instances.map(({ role }, index) => [role, `L${index + 1}`]),
  );
  const local = (role) => roleMap[role];
  const prompts = Object.fromEntries(
    binding.contract.role_instances.map(({ role }) => [role, ""]),
  );
  for (const assertion of binding.contract.assertions) {
    if (assertion.operator === "includes_exact_text") {
      for (const role of assertion.roles) prompts[role] += `${assertion.value}\n`;
    }
  }
  const structure = {
    nodes: binding.contract.role_instances.map(({ role, kind }) => ({
      id: local(role),
      role,
      kind,
      environment: binding.contract.environments[role],
      prompt: prompts[role],
    })),
    edges: binding.contract.topology.map(({ from, to, outcome }) => ({
      from: local(from),
      to: local(to),
      ...(outcome === undefined ? {} : { outcome }),
    })),
    concurrency: binding.contract.concurrency.map((group) => group.map(local)),
    gates: binding.contract.gates.map(({ role, outcomes }) => ({
      node: local(role),
      outcomes,
    })),
    repair_edges: binding.contract.repair_edges.map(({ from, to }) => ({
      from: local(from),
      to: local(to),
    })),
    terminal_paths: binding.contract.terminal_paths.map(({ from, to, outcome }) => ({
      from: local(from),
      to: local(to),
      outcome,
    })),
    collection: binding.contract.collection,
  };
  const graph = [
    "flowchart TD",
    ...structure.nodes.map(({ id, role }) => `  ${id}[${role}]`),
    ...structure.edges.map(
      ({ from, to, outcome }) =>
        `  ${from} -->${outcome === undefined ? "" : `|${outcome}|`} ${to}`,
    ),
  ].join("\n");
  const metadata = {
    case_id: binding.case_id,
    schema_version: binding.schema_version,
    canonical_goal_digest: binding.canonical_goal_digest,
    contract_digest: binding.contract_digest,
    proof_scope: OFFLINE_SCOPE,
    role_map: roleMap,
    structure: {
      nodes: structure.nodes.map(({ prompt, ...node }) => node),
      edges: structure.edges,
      concurrency: structure.concurrency,
      gates: structure.gates,
      repair_edges: structure.repair_edges,
      terminal_paths: structure.terminal_paths,
      collection: structure.collection,
    },
  };
  const artifacts = {
    metadata,
    graph,
    executable: executableSource(structure),
  };
  metadata.artifact_digest = calculateArtifactDigest({
    metadata,
    graph,
    executable: artifacts.executable,
  });
  return artifacts;
}

function refreshDigest(artifacts) {
  artifacts.metadata.artifact_digest = calculateArtifactDigest({
    metadata: artifacts.metadata,
    graph: artifacts.graph,
    executable: artifacts.executable,
  });
}

function failedCriterion(verdict, id) {
  assert.equal(verdict.ok, false);
  const criterion = verdict.criteria.find((item) => item.id === id);
  assert.ok(criterion, `missing criterion ${id}: ${JSON.stringify(verdict)}`);
  assert.equal(criterion.ok, false);
  assert.ok(criterion.locators.length > 0);
  assert.ok(criterion.unmatched_facts.length > 0);
}

test("all six cases resolve and conform at one structural seam", () => {
  const ids = listCaseIds();
  assert.deepEqual(ids, [
    "adversarial-dual-validation",
    "atomic-screen-fanout",
    "disjoint-writers-worktree",
    "nonbinding-synthesis-gate",
    "sealed-pov-factcheck",
    "slice-generators-join",
  ]);

  for (const caseId of ids) {
    const binding = resolveCase({ case_id: caseId });
    assert.equal(Object.isFrozen(binding), true);
    assert.equal(Object.isFrozen(binding.contract), true);
    assert.match(binding.canonical_goal_digest, /^[a-f0-9]{64}$/);
    assert.match(binding.contract_digest, /^[a-f0-9]{64}$/);

    const verdict = checkConformance({ case_id: caseId, artifacts: localize(binding) });
    assert.equal(verdict.ok, true, `${caseId}: ${JSON.stringify(verdict.criteria.filter(({ ok }) => !ok))}`);
    assert.equal(verdict.scope, OFFLINE_SCOPE);
    assert.deepEqual(verdict.unmatched_facts, []);
    assert.equal(verdict.identities.case_id, caseId);
    assert.equal(verdict.identities.schema_version, binding.schema_version);
    assert.equal(verdict.identities.contract_digest, binding.contract_digest);
    assert.match(verdict.identities.artifact_digest, /^[a-f0-9]{64}$/);
    assert.ok(verdict.criteria.every(({ id, ok, locators }) => id && ok && locators.length));
  }
});

test("binding failures stop before structural comparison at stable criteria", () => {
  const first = resolveCase({ case_id: "atomic-screen-fanout" });
  const artifacts = localize(first);

  failedCriterion(
    checkConformance({ case_id: "slice-generators-join", artifacts }),
    "binding:case",
  );
  failedCriterion(
    checkConformance({ case_id: first.case_id, goal: "custom goal", artifacts }),
    "binding:custom-goal",
  );

  const changedContractDigest = structuredClone(artifacts);
  changedContractDigest.metadata.contract_digest =
    `${first.contract_digest[0] === "0" ? "1" : "0"}${first.contract_digest.slice(1)}`;
  refreshDigest(changedContractDigest);
  failedCriterion(
    checkConformance({ case_id: first.case_id, artifacts: changedContractDigest }),
    "binding:contract-digest",
  );

  const changedGoalDigest = structuredClone(artifacts);
  changedGoalDigest.metadata.canonical_goal_digest = "0".repeat(64);
  refreshDigest(changedGoalDigest);
  failedCriterion(
    checkConformance({ case_id: first.case_id, artifacts: changedGoalDigest }),
    "binding:goal-digest",
  );
});

test("missing duplicate unknown and ambiguous roles fail cardinality", () => {
  const binding = resolveCase({ case_id: "atomic-screen-fanout" });
  const base = localize(binding);
  const roles = Object.keys(base.metadata.role_map);

  const missing = structuredClone(base);
  delete missing.metadata.role_map[roles[0]];
  refreshDigest(missing);
  failedCriterion(
    checkConformance({ case_id: binding.case_id, artifacts: missing }),
    "roles:cardinality",
  );

  const duplicate = structuredClone(base);
  duplicate.metadata.role_map[roles[1]] = duplicate.metadata.role_map[roles[0]];
  refreshDigest(duplicate);
  failedCriterion(
    checkConformance({ case_id: binding.case_id, artifacts: duplicate }),
    "roles:cardinality",
  );

  const unknown = structuredClone(base);
  unknown.metadata.role_map.intruder = "LX";
  refreshDigest(unknown);
  failedCriterion(
    checkConformance({ case_id: binding.case_id, artifacts: unknown }),
    "roles:cardinality",
  );

  const ambiguous = structuredClone(base);
  const structure = executableStructure(ambiguous.executable);
  structure.nodes.push({ ...structure.nodes[0], id: "LX" });
  ambiguous.executable = executableSource(structure);
  refreshDigest(ambiguous);
  failedCriterion(
    checkConformance({ case_id: binding.case_id, artifacts: ambiguous }),
    "roles:cardinality",
  );
});

test("artifact identity covers executable source outside the structure", () => {
  const binding = resolveCase({ case_id: "atomic-screen-fanout" });
  const artifacts = localize(binding);
  artifacts.executable += "\nawait unexpectedMutation();";

  failedCriterion(
    checkConformance({ case_id: binding.case_id, artifacts }),
    "binding:artifact-digest",
  );
});
test("the executable runs the same exported structure", () => {
  const binding = resolveCase({ case_id: "atomic-screen-fanout" });
  const artifacts = localize(binding);
  artifacts.executable = artifacts.executable.replace(
    "runWorkflow(workflowStructure)",
    "runWorkflow(otherStructure)",
  );
  refreshDigest(artifacts);

  failedCriterion(
    checkConformance({ case_id: binding.case_id, artifacts }),
    "structure:parse",
  );
});


test("structural contradictions and lexical decoys receive no credit", () => {
  const binding = resolveCase({ case_id: "atomic-screen-fanout" });
  const artifacts = localize(binding);
  const structure = executableStructure(artifacts.executable);
  const removed = structure.edges.pop();
  artifacts.executable = executableSource(
    structure,
    `// decoy ${removed.from} --> ${removed.to}`,
  );
  refreshDigest(artifacts);

  failedCriterion(
    checkConformance({ case_id: binding.case_id, artifacts }),
    "structure:executable",
  );
});
test("each structural proof fact rejects one contradictory mutation", () => {
  const binding = resolveCase({ case_id: "nonbinding-synthesis-gate" });
  const mutations = [
    ["role", (structure) => { structure.nodes[0].kind = "writer"; }],
    ["environment", (structure) => { structure.nodes[0].environment = "worktree"; }],
    ["concurrency", (structure) => { structure.concurrency[0].pop(); }],
    ["gate", (structure) => { structure.gates[0].outcomes = ["pass"]; }],
    ["repair edge", (structure) => { structure.repair_edges.pop(); }],
    ["terminal path", (structure) => { structure.terminal_paths.pop(); }],
  ];

  for (const [name, mutate] of mutations) {
    const artifacts = localize(binding);
    const structure = executableStructure(artifacts.executable);
    mutate(structure);
    artifacts.executable = executableSource(structure);
    refreshDigest(artifacts);
    const verdict = checkConformance({ case_id: binding.case_id, artifacts });
    assert.equal(verdict.ok, false, `${name} mutation passed`);
    failedCriterion(verdict, "structure:executable");
  }
});


test("literal checks inspect only their contracted parsed field", () => {
  const binding = resolveCase({ case_id: "atomic-screen-fanout" });
  const assertion = binding.contract.assertions.find(
    ({ operator }) => operator === "excludes_exact_text",
  );
  assert.ok(assertion);

  const commentOnly = localize(binding);
  commentOnly.executable += `\n// ${assertion.value}`;
  refreshDigest(commentOnly);
  assert.equal(
    checkConformance({ case_id: binding.case_id, artifacts: commentOnly }).ok,
    true,
  );

  const parsedField = localize(binding);
  const structure = executableStructure(parsedField.executable);
  structure.nodes.find(({ role }) => role === assertion.roles[0]).prompt = assertion.value;
  parsedField.executable = executableSource(structure);
  refreshDigest(parsedField);
  failedCriterion(
    checkConformance({ case_id: binding.case_id, artifacts: parsedField }),
    assertion.id,
  );
});

test("offline verdicts reject proof-category leaks", () => {
  const binding = resolveCase({ case_id: "atomic-screen-fanout" });
  const artifacts = localize(binding);
  artifacts.metadata.proof_scope = "runtime-proof-and-execution-authority";
  refreshDigest(artifacts);

  failedCriterion(
    checkConformance({ case_id: binding.case_id, artifacts }),
    "scope:conformance-only",
  );
  const unknownClaim = localize(binding);
  unknownClaim.metadata.runtime_proof = true;
  refreshDigest(unknownClaim);
  failedCriterion(
    checkConformance({ case_id: binding.case_id, artifacts: unknownClaim }),
    "scope:conformance-only",
  );
});

