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



function buildConformingFixture(binding) {
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
  const workflowStructure = {
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
    ...workflowStructure.nodes.map(({ id, role }) => `  ${id}[${role}]`),
    ...workflowStructure.edges.map(
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
      nodes: workflowStructure.nodes.map(({ prompt, ...node }) => node),
      edges: workflowStructure.edges,
      concurrency: workflowStructure.concurrency,
      gates: workflowStructure.gates,
      repair_edges: workflowStructure.repair_edges,
      terminal_paths: workflowStructure.terminal_paths,
      collection: workflowStructure.collection,
    },
  };
  const artifacts = {
    metadata,
    graph,
    executable: executableSource(workflowStructure),
    workflowStructure,
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
  return criterion;
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

    const verdict = checkConformance({ case_id: caseId, artifacts: buildConformingFixture(binding) });
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

test("contract normalization has a fixed locale-independent digest", () => {
  assert.equal(
    resolveCase({ case_id: "adversarial-dual-validation" }).contract_digest,
    "f807539b74b55ef786e2ac3e0be549032aecccfaeaf09876a68353e0a527fdbd",
  );
});

test("binding failures stop before structural comparison at stable criteria", () => {
  const first = resolveCase({ case_id: "atomic-screen-fanout" });
  const artifacts = buildConformingFixture(first);

  failedCriterion(
    checkConformance({ case_id: "slice-generators-join", artifacts }),
    "binding:case",
  );
  failedCriterion(
    checkConformance({ case_id: first.case_id, goal: "custom goal", artifacts }),
    "binding:custom-goal",
  );
  failedCriterion(checkConformance({ artifacts }), "binding:case");
  failedCriterion(
    checkConformance({ case_id: "not-a-real-case", artifacts }),
    "binding:case",
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
  const base = buildConformingFixture(binding);
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
  const structure = structuredClone(ambiguous.workflowStructure);
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
  const artifacts = buildConformingFixture(binding);
  artifacts.executable += "\nawait unexpectedMutation();";

  failedCriterion(
    checkConformance({ case_id: binding.case_id, artifacts }),
    "binding:artifact-digest",
  );
});
test("only one intended top-level workflow binding receives credit", () => {
  const binding = resolveCase({ case_id: "atomic-screen-fanout" });
  const mutations = [
    ["wrong structure", (source) => source.replace(
      "runWorkflow(workflowStructure)",
      "runWorkflow(otherStructure)",
    )],
    ["unawaited call", (source) => source.replace(
      "await runWorkflow(workflowStructure);",
      "runWorkflow(workflowStructure);",
    )],
    ["dead nested call", (source) => source.replace(
      "await runWorkflow(workflowStructure);",
      "function deadPath() { return runWorkflow(workflowStructure); }",
    )],
    ["shadowed call", (source) =>
      `const runWorkflow = () => {};\n${source}`],
    ["nested declaration", (source) => `{\n${source}\n}`],
    ["unguarded export", (source) => source.replace(
      'if (typeof module !== "undefined") module.exports = workflowStructure;',
      "module.exports = workflowStructure;",
    )],
    ["dead export", (source) => source.replace(
      'if (typeof module !== "undefined") module.exports = workflowStructure;',
      "if (false) module.exports = workflowStructure;",
    )],
    ["extra export", (source) =>
      `${source}\nmodule.exports = workflowStructure;`],
    ["duplicate call", (source) =>
      `${source}\nawait runWorkflow(workflowStructure);`],
  ];

  for (const [name, mutate] of mutations) {
    const artifacts = buildConformingFixture(binding);
    artifacts.executable = mutate(artifacts.executable);
    refreshDigest(artifacts);
    const criterion = failedCriterion(
      checkConformance({ case_id: binding.case_id, artifacts }),
      "structure:parse",
    );
    assert.match(criterion.unmatched_facts[0], /top-level workflow binding/, name);
  }
});
test("both Mermaid outcome label forms preserve terminal facts", () => {
  const binding = resolveCase({ case_id: "nonbinding-synthesis-gate" });
  const pipeLabeled = buildConformingFixture(binding);
  assert.equal(
    checkConformance({ case_id: binding.case_id, artifacts: pipeLabeled }).ok,
    true,
  );

  const inlineLabeled = buildConformingFixture(binding);
  inlineLabeled.graph = inlineLabeled.graph.replace(
    /-->\|([^|]+)\|/g,
    "-- $1 -->",
  );
  refreshDigest(inlineLabeled);
  assert.equal(
    checkConformance({ case_id: binding.case_id, artifacts: inlineLabeled }).ok,
    true,
  );
});



test("structural contradictions and lexical decoys receive no credit", () => {
  const binding = resolveCase({ case_id: "atomic-screen-fanout" });
  const artifacts = buildConformingFixture(binding);
  const structure = structuredClone(artifacts.workflowStructure);
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
    ["kind", (structure) => { structure.nodes[0].kind = "writer"; }],
    ["environment", (structure) => { structure.nodes[0].environment = "worktree"; }],
    ["concurrency", (structure) => { structure.concurrency[0].pop(); }],
    ["gate", (structure) => { structure.gates[0].outcomes = ["pass"]; }],
    ["repair edge", (structure) => { structure.repair_edges.pop(); }],
    ["terminal path", (structure) => { structure.terminal_paths.pop(); }],
  ];
  for (const key of ["concurrency", "gates", "repair_edges", "terminal_paths"]) {
    assert.ok(binding.contract[key].length > 0, `fixture needs ${key}`);
  }
  for (const [name, mutate] of mutations) {
    const artifacts = buildConformingFixture(binding);
    const structure = structuredClone(artifacts.workflowStructure);
    mutate(structure);
    artifacts.executable = executableSource(structure);
    refreshDigest(artifacts);
    const verdict = checkConformance({ case_id: binding.case_id, artifacts });
    assert.equal(verdict.ok, false, `${name} mutation passed`);
    failedCriterion(verdict, "structure:executable");
  }
});



test("malformed structure containers and entries fail at structure shape", () => {
  const binding = resolveCase({ case_id: "nonbinding-synthesis-gate" });
  const cases = [
    ["nodes container", (value) => { value.nodes = {}; }, "structure.nodes must be an array"],
    ["node entry", (value) => { value.nodes[0] = null; }, "structure.nodes[0] must be an object"],
    ["edges container", (value) => { value.edges = null; }, "structure.edges must be an array"],
    ["concurrency container", (value) => { value.concurrency = {}; }, "structure.concurrency must be an array"],
    ["concurrency entry", (value) => { value.concurrency[0] = "not-an-array"; }, "structure.concurrency[0] must be an array"],
    ["gates container", (value) => { value.gates = {}; }, "structure.gates must be an array"],
    ["gate entry", (value) => { value.gates[0] = null; }, "structure.gates[0] must be an object"],
    ["repair container", (value) => { value.repair_edges = {}; }, "structure.repair_edges must be an array"],
    ["repair entry", (value) => { value.repair_edges[0] = null; }, "structure.repair_edges[0] must be an object"],
    ["terminal container", (value) => { value.terminal_paths = {}; }, "structure.terminal_paths must be an array"],
    ["terminal entry", (value) => { value.terminal_paths[0] = null; }, "structure.terminal_paths[0] must be an object"],
    ["collection", (value) => { value.collection = []; }, "structure.collection must be an object"],
  ];

  for (const [name, mutate, fact] of cases) {
    const artifacts = buildConformingFixture(binding);
    const structure = structuredClone(artifacts.workflowStructure);
    mutate(structure);
    artifacts.executable = executableSource(structure);
    refreshDigest(artifacts);
    const criterion = failedCriterion(
      checkConformance({ case_id: binding.case_id, artifacts }),
      "structure:shape",
    );
    assert.deepEqual(criterion.unmatched_facts, [fact], name);
  }
});

test("isomorphism failures report normalized fact-level differences", () => {
  const binding = resolveCase({ case_id: "atomic-screen-fanout" });
  const artifacts = buildConformingFixture(binding);
  const structure = structuredClone(artifacts.workflowStructure);
  structure.nodes[0].environment = "worktree";
  artifacts.executable = executableSource(structure);
  refreshDigest(artifacts);

  const criterion = failedCriterion(
    checkConformance({ case_id: binding.case_id, artifacts }),
    "structure:executable",
  );
  assert.deepEqual(criterion.unmatched_facts, [...criterion.unmatched_facts].sort());
  assert.ok(criterion.unmatched_facts.some((fact) => fact.startsWith("missing node:")));
  assert.ok(criterion.unmatched_facts.some((fact) => fact.startsWith("unexpected node:")));
  assert.ok(criterion.locators.some((locator) => locator.startsWith("contract.")));
  assert.ok(criterion.locators.some((locator) => locator.startsWith("workflow.js:workflowStructure.")));
  assert.doesNotMatch(criterion.unmatched_facts.join("\\n"), /contradicts resolved contract/);
});

test("unknown structure keys and prototype keys fail closed", () => {
  const binding = resolveCase({ case_id: "atomic-screen-fanout" });
  const cases = [
    ["structure key", (artifacts, structure) => { structure.extra = true; }],
    ["node key", (artifacts, structure) => { structure.nodes[0].extra = true; }],
    ["metadata key", (artifacts) => { artifacts.metadata.structure.extra = true; }],
    ["prototype key", (artifacts) => {
      artifacts.executable = artifacts.executable.replace(
        "const workflowStructure = {",
        'const workflowStructure = {"__proto__": {},',
      );
    }],
  ];

  for (const [name, mutate] of cases) {
    const artifacts = buildConformingFixture(binding);
    const structure = structuredClone(artifacts.workflowStructure);
    mutate(artifacts, structure);
    if (!name.includes("metadata") && !name.includes("prototype")) {
      artifacts.executable = executableSource(structure);
    }
    refreshDigest(artifacts);
    const criterion = failedCriterion(
      checkConformance({ case_id: binding.case_id, artifacts }),
      "structure:shape",
    );
    assert.match(criterion.unmatched_facts[0], /unknown|__proto__/, name);
  }
});
test("literal checks inspect only their contracted parsed field", () => {
  const binding = resolveCase({ case_id: "atomic-screen-fanout" });
  const assertion = binding.contract.assertions.find(
    ({ operator }) => operator === "excludes_exact_text",
  );
  assert.ok(assertion);

  const commentOnly = buildConformingFixture(binding);
  commentOnly.executable += `\n// ${assertion.value}`;
  refreshDigest(commentOnly);
  assert.equal(
    checkConformance({ case_id: binding.case_id, artifacts: commentOnly }).ok,
    true,
  );

  const parsedField = buildConformingFixture(binding);
  const structure = structuredClone(parsedField.workflowStructure);
  structure.nodes.find(({ role }) => role === assertion.roles[0]).prompt = assertion.value;
  parsedField.executable = executableSource(structure);
  refreshDigest(parsedField);
  failedCriterion(
    checkConformance({ case_id: binding.case_id, artifacts: parsedField }),
    assertion.id,
  );

  for (const [name, prompt] of [["missing", undefined], ["non-string", 42]]) {
    const artifacts = buildConformingFixture(binding);
    const changed = structuredClone(artifacts.workflowStructure);
    const node = changed.nodes.find(({ role }) => role === assertion.roles[0]);
    if (prompt === undefined) delete node.prompt;
    else node.prompt = prompt;
    artifacts.executable = executableSource(changed);
    refreshDigest(artifacts);
    const criterion = failedCriterion(
      checkConformance({ case_id: binding.case_id, artifacts }),
      assertion.id,
    );
    assert.match(
      criterion.unmatched_facts.join("\n"),
      /must be an own string/,
      name,
    );
  }
});

test("offline verdicts reject proof-category leaks", () => {
  const binding = resolveCase({ case_id: "atomic-screen-fanout" });
  const artifacts = buildConformingFixture(binding);
  artifacts.metadata.proof_scope = "runtime-proof-and-execution-authority";
  refreshDigest(artifacts);

  failedCriterion(
    checkConformance({ case_id: binding.case_id, artifacts }),
    "scope:conformance-only",
  );
  const unknownClaim = buildConformingFixture(binding);
  unknownClaim.metadata.runtime_proof = true;
  refreshDigest(unknownClaim);
  failedCriterion(
    checkConformance({ case_id: binding.case_id, artifacts: unknownClaim }),
    "scope:conformance-only",
  );
});

