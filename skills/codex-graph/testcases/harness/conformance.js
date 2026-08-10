"use strict";

const acorn = require("acorn");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const CASES_ROOT = path.join(__dirname, "..", "cases");
const OFFLINE_SCOPE = "offline-structural-conformance-only";
const CONTRACT_KEYS = new Set([
  "assertions",
  "canonical_goal_digest",
  "case_id",
  "collection",
  "concurrency",
  "environments",
  "gates",
  "repair_edges",
  "role_instances",
  "schema_version",
  "terminal_paths",
  "topology",
]);
const METADATA_KEYS = new Set([
  "artifact_digest",
  "canonical_goal_digest",
  "case_id",
  "contract_digest",
  "proof_scope",
  "role_map",
  "schema_version",
  "structure",
]);
const ROLE_KINDS = new Set([
  "contract",
  "discovery",
  "gate",
  "integration",
  "repair",
  "terminal",
  "validator",
  "writer",
]);
const COLLECTION_KEYS = new Set([
  "max_output_chars_per_item",
  "parse_result",
  "pending_setup_resolution",
  "read_after_wait",
  "read_first",
]);

class ConformanceError extends Error {
  constructor(criterion, fact) {
    super(fact);
    this.criterion = criterion;
    this.fact = fact;
  }
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function sortedObject(value) {
  if (Array.isArray(value)) return value.map(sortedObject);
  if (!isObject(value)) return value;
  return Object.fromEntries(
    Object.keys(value)
      .sort()
      .map((key) => [key, sortedObject(value[key])]),
  );
}

function stableStringify(value) {
  return JSON.stringify(sortedObject(value));
}

function sortObjects(items) {
  return [...items].sort((left, right) =>
    stableStringify(left).localeCompare(stableStringify(right)),
  );
}

function digest(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function normalizeGoal(goal) {
  return `${goal.replace(/\r\n?/g, "\n").trimEnd()}\n`;
}

function deepFreeze(value) {
  Object.freeze(value);
  for (const child of Object.values(value)) {
    if (child && typeof child === "object" && !Object.isFrozen(child)) deepFreeze(child);
  }
  return value;
}

function fail(criterion, fact) {
  throw new ConformanceError(criterion, fact);
}

function exactKeys(value, allowed, criterion, label) {
  if (!isObject(value)) fail(criterion, `${label} must be an object`);
  const unknown = Object.keys(value).filter((key) => !allowed.has(key));
  if (unknown.length) fail(criterion, `${label} has unknown facts: ${unknown.join(", ")}`);
}

function normalizeEdge(edge, roles, label) {
  exactKeys(edge, new Set(["from", "outcome", "to"]), "contract:shape", label);
  if (!roles.has(edge.from) || !roles.has(edge.to)) {
    fail("contract:roles", `${label} references an unknown role`);
  }
  if (edge.from === edge.to) fail("contract:topology", `${label} is a self edge`);
  if (edge.outcome !== undefined && (typeof edge.outcome !== "string" || !edge.outcome)) {
    fail("contract:topology", `${label} has an invalid outcome`);
  }
  return {
    from: edge.from,
    to: edge.to,
    ...(edge.outcome === undefined ? {} : { outcome: edge.outcome }),
  };
}

function normalizedContract(raw, directoryCaseId, goalDigest) {
  exactKeys(raw, CONTRACT_KEYS, "contract:shape", "contract");
  for (const key of CONTRACT_KEYS) {
    if (!(key in raw)) fail("contract:shape", `contract is missing ${key}`);
  }
  if (raw.case_id !== directoryCaseId) {
    fail("binding:case", `directory ${directoryCaseId} contradicts contract ${raw.case_id}`);
  }
  if (typeof raw.schema_version !== "string" || !raw.schema_version) {
    fail("binding:schema", "schema_version must be a non-empty string");
  }
  if (raw.canonical_goal_digest !== goalDigest) {
    fail("binding:goal-digest", "contract canonical_goal_digest does not match GOAL.md");
  }
  if (!Array.isArray(raw.role_instances) || raw.role_instances.length === 0) {
    fail("contract:roles", "role_instances must be non-empty");
  }

  const roleInstances = raw.role_instances.map((entry, index) => {
    exactKeys(entry, new Set(["kind", "role"]), "contract:roles", `role_instances[${index}]`);
    if (typeof entry.role !== "string" || !entry.role) {
      fail("contract:roles", `role_instances[${index}] has no role`);
    }
    if (!ROLE_KINDS.has(entry.kind)) {
      fail("contract:roles", `role ${entry.role} has unknown kind ${entry.kind}`);
    }
    return { role: entry.role, kind: entry.kind };
  });
  const roles = new Set(roleInstances.map(({ role }) => role));
  if (roles.size !== roleInstances.length) fail("contract:roles", "duplicate semantic role");
  const kindByRole = Object.fromEntries(roleInstances.map(({ role, kind }) => [role, kind]));

  exactKeys(raw.environments, roles, "contract:roles", "environments");
  if (Object.keys(raw.environments).length !== roles.size) {
    fail("contract:roles", "every semantic role needs one environment");
  }
  for (const [role, environment] of Object.entries(raw.environments)) {
    if (!roles.has(role) || !["local", "worktree"].includes(environment)) {
      fail("contract:roles", `invalid environment for ${role}`);
    }
  }

  if (!Array.isArray(raw.topology) || raw.topology.length === 0) {
    fail("contract:topology", "topology must be non-empty");
  }
  const topology = raw.topology.map((edge, index) =>
    normalizeEdge(edge, roles, `topology[${index}]`),
  );
  const edgeKeys = topology.map(stableStringify);
  if (new Set(edgeKeys).size !== edgeKeys.length) fail("contract:topology", "duplicate topology edge");

  if (!Array.isArray(raw.concurrency)) fail("contract:concurrency", "concurrency must be an array");
  const concurrency = raw.concurrency.map((group, index) => {
    if (!Array.isArray(group) || group.length < 2) {
      fail("contract:concurrency", `concurrency[${index}] needs at least two roles`);
    }
    if (new Set(group).size !== group.length || group.some((role) => !roles.has(role))) {
      fail("contract:concurrency", `concurrency[${index}] has duplicate or unknown roles`);
    }
    return [...group].sort();
  });

  if (!Array.isArray(raw.gates)) fail("contract:gates", "gates must be an array");
  const gates = raw.gates.map((gate, index) => {
    exactKeys(gate, new Set(["outcomes", "role"]), "contract:gates", `gates[${index}]`);
    if (kindByRole[gate.role] !== "gate") fail("contract:gates", `${gate.role} is not a gate role`);
    if (!Array.isArray(gate.outcomes) || gate.outcomes.length === 0 || new Set(gate.outcomes).size !== gate.outcomes.length) {
      fail("contract:gates", `${gate.role} has invalid outcomes`);
    }
    return { role: gate.role, outcomes: [...gate.outcomes].sort() };
  });
  for (const gate of gates) {
    const routedOutcomes = topology
      .filter((edge) => edge.from === gate.role && edge.outcome !== undefined)
      .map(({ outcome }) => outcome)
      .sort();
    if (stableStringify(routedOutcomes) !== stableStringify(gate.outcomes)) {
      fail("contract:gates", `${gate.role} outcomes contradict its topology routes`);
    }
  }

  const repairEdges = raw.repair_edges.map((edge, index) =>
    normalizeEdge(edge, roles, `repair_edges[${index}]`),
  );
  for (const edge of repairEdges) {
    if (!topology.some((candidate) => candidate.from === edge.from && candidate.to === edge.to)) {
      fail("contract:repair-edges", `repair edge ${edge.from}->${edge.to} is absent from topology`);
    }
  }

  const terminalPaths = raw.terminal_paths.map((edge, index) =>
    normalizeEdge(edge, roles, `terminal_paths[${index}]`),
  );
  for (const edge of terminalPaths) {
    if (kindByRole[edge.to] !== "terminal" || !topology.some((candidate) => stableStringify(candidate) === stableStringify(edge))) {
      fail("contract:terminal-paths", `terminal path ${edge.from}->${edge.to} contradicts topology`);
    }
  }

  exactKeys(raw.collection, COLLECTION_KEYS, "contract:collection", "collection");
  if (raw.collection.read_first !== true || raw.collection.read_after_wait !== true) {
    fail("contract:collection", "collection must be read-first and read after wait");
  }
  if (!Number.isInteger(raw.collection.max_output_chars_per_item) || raw.collection.max_output_chars_per_item <= 0) {
    fail("contract:collection", "collection item budget must be a positive integer");
  }

  if (!Array.isArray(raw.assertions)) fail("contract:assertions", "assertions must be an array");
  const assertions = raw.assertions.map((assertion, index) => {
    exactKeys(
      assertion,
      new Set(["field", "id", "operator", "roles", "value"]),
      "contract:assertions",
      `assertions[${index}]`,
    );
    if (typeof assertion.id !== "string" || !assertion.id || assertion.field !== "prompt") {
      fail("contract:assertions", `assertions[${index}] has invalid identity or field`);
    }
    if (!["includes_exact_text", "excludes_exact_text"].includes(assertion.operator)) {
      fail("contract:assertions", `${assertion.id} has unknown operator`);
    }
    if (!Array.isArray(assertion.roles) || assertion.roles.length === 0 || new Set(assertion.roles).size !== assertion.roles.length || assertion.roles.some((role) => !roles.has(role))) {
      fail("contract:assertions", `${assertion.id} has duplicate or unknown roles`);
    }
    if (typeof assertion.value !== "string" || !assertion.value) {
      fail("contract:assertions", `${assertion.id} has no exact text`);
    }
    return { ...assertion, roles: [...assertion.roles].sort() };
  });
  if (new Set(assertions.map(({ id }) => id)).size !== assertions.length) {
    fail("contract:assertions", "duplicate assertion identity");
  }

  return {
    case_id: raw.case_id,
    schema_version: raw.schema_version,
    canonical_goal_digest: raw.canonical_goal_digest,
    role_instances: sortObjects(roleInstances),
    topology: sortObjects(topology),
    environments: sortedObject(raw.environments),
    concurrency: sortObjects(concurrency),
    gates: sortObjects(gates),
    repair_edges: sortObjects(repairEdges),
    terminal_paths: sortObjects(terminalPaths),
    collection: sortedObject(raw.collection),
    assertions: sortObjects(assertions),
  };
}

function listCaseIds() {
  const ids = fs
    .readdirSync(CASES_ROOT, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  const normalizedIds = ids.map((id) => id.toLowerCase());
  if (new Set(normalizedIds).size !== normalizedIds.length) {
    fail("binding:case", "case directories contain ambiguous identities");
  }
  return ids;
}

function resolveCase(options) {
  if (!isObject(options) || typeof options.case_id !== "string" || !options.case_id) {
    fail("binding:case", "an explicit case_id is required");
  }
  if (Object.prototype.hasOwnProperty.call(options, "goal")) {
    fail("binding:custom-goal", "a selected testcase cannot be combined with a custom goal");
  }
  const ids = listCaseIds();
  if (!ids.includes(options.case_id)) fail("binding:case", `unknown case_id: ${options.case_id}`);
  const caseDir = path.join(CASES_ROOT, options.case_id);
  const canonicalGoal = normalizeGoal(fs.readFileSync(path.join(caseDir, "GOAL.md"), "utf8"));
  const canonicalGoalDigest = digest(canonicalGoal);
  const rawContract = JSON.parse(fs.readFileSync(path.join(caseDir, "contract.json"), "utf8"));
  const contract = normalizedContract(rawContract, options.case_id, canonicalGoalDigest);
  const binding = {
    case_id: contract.case_id,
    schema_version: contract.schema_version,
    canonical_goal: canonicalGoal,
    canonical_goal_digest: canonicalGoalDigest,
    contract_digest: digest(stableStringify(contract)),
    contract,
  };
  return deepFreeze(binding);
}

function parseGraph(graph) {
  if (typeof graph !== "string" || !graph.trim()) {
    throw new Error("graph must be non-empty Mermaid text");
  }
  const parser = path.join(__dirname, "..", "..", "scripts", "graph_coherence.py");
  const result = spawnSync("python3", [parser, "--parse-stdin-json"], {
    input: graph,
    encoding: "utf8",
    maxBuffer: 1024 * 1024,
  });
  if (result.status !== 0) {
    throw new Error(result.stderr.trim() || "Mermaid parsing failed");
  }
  const parsed = JSON.parse(result.stdout);
  return { nodes: [...parsed.nodes].sort(), edges: sortObjects(parsed.edges) };
}

function astValue(node) {
  if (node?.type === "Literal" && !node.regex && !node.bigint) return node.value;
  if (
    node?.type === "UnaryExpression" &&
    node.operator === "-" &&
    node.argument.type === "Literal" &&
    typeof node.argument.value === "number"
  ) {
    return -node.argument.value;
  }
  if (node?.type === "ArrayExpression" && node.elements.every(Boolean)) {
    return node.elements.map(astValue);
  }
  if (node?.type === "ObjectExpression") {
    const value = {};
    for (const property of node.properties) {
      if (
        property.type !== "Property" ||
        property.kind !== "init" ||
        property.computed ||
        property.method ||
        property.shorthand
      ) {
        throw new Error("workflowStructure must contain only plain data properties");
      }
      const key =
        property.key.type === "Identifier" ? property.key.name : property.key.value;
      if (
        typeof key !== "string" ||
        Object.prototype.hasOwnProperty.call(value, key)
      ) {
        throw new Error("workflowStructure has an invalid or duplicate property");
      }
      value[key] = astValue(property.value);
    }
    return value;
  }
  throw new Error(`workflowStructure contains unsupported ${node?.type ?? "syntax"}`);
}

function walk(node, visit) {
  if (!node || typeof node !== "object") return;
  visit(node);
  for (const [key, child] of Object.entries(node)) {
    if (key === "start" || key === "end" || key === "loc") continue;
    if (Array.isArray(child)) child.forEach((item) => walk(item, visit));
    else if (child && typeof child.type === "string") walk(child, visit);
  }
}

function parseExecutable(source) {
  if (typeof source !== "string" || !source.trim()) {
    throw new Error("executable must be non-empty JavaScript");
  }
  const program = acorn.parse(source, {
    ecmaVersion: "latest",
    sourceType: "script",
    allowAwaitOutsideFunction: true,
    allowReturnOutsideFunction: true,
  });
  const declarations = [];
  let exportsStructure = 0;
  let workflowRuns = 0;
  let boundWorkflowRuns = 0;
  walk(program, (node) => {
    if (
      node.type === "VariableDeclarator" &&
      node.id.type === "Identifier" &&
      node.id.name === "workflowStructure"
    ) {
      declarations.push(node.init);
    }
    if (
      node.type === "AssignmentExpression" &&
      node.operator === "=" &&
      node.left.type === "MemberExpression" &&
      !node.left.computed &&
      node.left.object.type === "Identifier" &&
      node.left.object.name === "module" &&
      node.left.property.type === "Identifier" &&
      node.left.property.name === "exports" &&
      node.right.type === "Identifier" &&
      node.right.name === "workflowStructure"
    ) {
      exportsStructure += 1;
    }
    if (
      node.type === "CallExpression" &&
      node.callee.type === "Identifier" &&
      node.callee.name === "runWorkflow"
    ) {
      workflowRuns += 1;
      if (
        node.arguments.length === 1 &&
        node.arguments[0].type === "Identifier" &&
        node.arguments[0].name === "workflowStructure"
      ) {
        boundWorkflowRuns += 1;
      }
    }
  });
  if (
    declarations.length !== 1 ||
    exportsStructure !== 1 ||
    workflowRuns !== 1 ||
    boundWorkflowRuns !== 1
  ) {
    throw new Error(
      "workflow.js must declare, export, and run exactly one workflowStructure",
    );
  }
  return astValue(declarations[0]);
}

function metadataForDigest(metadata) {
  const copy = structuredClone(metadata);
  delete copy.artifact_digest;
  return copy;
}

function calculateArtifactDigest({ metadata, graph, executable }) {
  return digest(
    stableStringify({
      metadata: metadataForDigest(metadata),
      graph,
      executable,
    }),
  );
}

function criterion(id, ok, locators, unmatchedFacts = []) {
  return { id, ok, locators, unmatched_facts: unmatchedFacts };
}

function verdict(binding, criteria, identities = {}) {
  const unmatchedFacts = criteria.flatMap(({ unmatched_facts: facts }) => facts);
  return {
    ok: criteria.length > 0 && criteria.every(({ ok }) => ok),
    scope: OFFLINE_SCOPE,
    identities: {
      case_id: identities.case_id ?? binding?.case_id ?? null,
      schema_version: identities.schema_version ?? binding?.schema_version ?? null,
      contract_digest: identities.contract_digest ?? binding?.contract_digest ?? null,
      artifact_digest: identities.artifact_digest ?? null,
    },
    criteria,
    unmatched_facts: unmatchedFacts,
  };
}

function failureVerdict(error, caseId = null) {
  const id = error instanceof ConformanceError ? error.criterion : "binding:contract";
  const fact = error instanceof ConformanceError ? error.fact : error.message;
  return verdict(null, [criterion(id, false, ["resolver"], [fact])], { case_id: caseId });
}

function normalizeStructure(structure, includePrompts) {
  if (!isObject(structure)) throw new Error("structure must be an object");
  const nodes = structure.nodes.map((node) => ({
    id: node.id,
    role: node.role,
    kind: node.kind,
    environment: node.environment,
    ...(includePrompts ? { prompt: node.prompt } : {}),
  }));
  return {
    nodes: sortObjects(nodes),
    edges: sortObjects(structure.edges),
    concurrency: sortObjects(structure.concurrency.map((group) => [...group].sort())),
    gates: sortObjects(structure.gates.map((gate) => ({ node: gate.node, outcomes: [...gate.outcomes].sort() }))),
    repair_edges: sortObjects(structure.repair_edges),
    terminal_paths: sortObjects(structure.terminal_paths),
    collection: sortedObject(structure.collection),
  };
}

function expectedStructure(binding, roleMap) {
  const local = (role) => roleMap[role];
  return normalizeStructure({
    nodes: binding.contract.role_instances.map(({ role, kind }) => ({
      id: local(role),
      role,
      kind,
      environment: binding.contract.environments[role],
    })),
    edges: binding.contract.topology.map(({ from, to, outcome }) => ({
      from: local(from),
      to: local(to),
      ...(outcome === undefined ? {} : { outcome }),
    })),
    concurrency: binding.contract.concurrency.map((group) => group.map(local)),
    gates: binding.contract.gates.map(({ role, outcomes }) => ({ node: local(role), outcomes })),
    repair_edges: binding.contract.repair_edges.map(({ from, to }) => ({ from: local(from), to: local(to) })),
    terminal_paths: binding.contract.terminal_paths.map(({ from, to, outcome }) => ({ from: local(from), to: local(to), outcome })),
    collection: binding.contract.collection,
  }, false);
}

function checkConformance({ case_id: caseId, goal, artifacts }) {
  let binding;
  try {
    binding = resolveCase(
      goal === undefined ? { case_id: caseId } : { case_id: caseId, goal },
    );
  } catch (error) {
    return failureVerdict(error, caseId);
  }
  if (!isObject(artifacts) || !isObject(artifacts.metadata)) {
    return failureVerdict(new ConformanceError("binding:metadata", "artifact metadata is required"), caseId);
  }
  const metadata = artifacts.metadata;
  const identities = {
    case_id: metadata.case_id,
    schema_version: metadata.schema_version,
    contract_digest: metadata.contract_digest,
    artifact_digest: metadata.artifact_digest,
  };
  const bindingCriteria = [
    criterion("binding:case", metadata.case_id === binding.case_id, ["metadata.case_id"], metadata.case_id === binding.case_id ? [] : [`expected ${binding.case_id}, got ${metadata.case_id}`]),
    criterion("binding:schema", metadata.schema_version === binding.schema_version, ["metadata.schema_version"], metadata.schema_version === binding.schema_version ? [] : [`expected ${binding.schema_version}, got ${metadata.schema_version}`]),
    criterion("binding:goal-digest", metadata.canonical_goal_digest === binding.canonical_goal_digest, ["metadata.canonical_goal_digest"], metadata.canonical_goal_digest === binding.canonical_goal_digest ? [] : ["canonical goal digest mismatch"]),
    criterion("binding:contract-digest", metadata.contract_digest === binding.contract_digest, ["metadata.contract_digest"], metadata.contract_digest === binding.contract_digest ? [] : ["resolved contract digest mismatch"]),
  ];
  if (bindingCriteria.some(({ ok }) => !ok)) return verdict(binding, bindingCriteria, identities);

  let graph;
  let executable;
  try {
    graph = parseGraph(artifacts.graph);
    executable = parseExecutable(artifacts.executable);
  } catch (error) {
    return verdict(binding, [criterion("structure:parse", false, ["artifact-set"], [error.message])], identities);
  }

  const calculatedArtifactDigest = calculateArtifactDigest({
    metadata,
    graph: artifacts.graph,
    executable: artifacts.executable,
  });
  const criteria = [
    ...bindingCriteria,
    criterion("binding:artifact-digest", metadata.artifact_digest === calculatedArtifactDigest, ["metadata.artifact_digest"], metadata.artifact_digest === calculatedArtifactDigest ? [] : ["generated artifact digest mismatch"]),
  ];
  if (criteria.some(({ ok }) => !ok)) return verdict(binding, criteria, identities);

  const expectedRoles = binding.contract.role_instances.map(({ role }) => role).sort();
  const roleMap = metadata.role_map;
  const roleFacts = [];
  if (!isObject(roleMap)) {
    roleFacts.push("metadata.role_map must be an object");
  } else {
    const mappedRoles = Object.keys(roleMap).sort();
    if (stableStringify(mappedRoles) !== stableStringify(expectedRoles)) roleFacts.push("role_map roles differ from the resolved contract");
    const localIds = Object.values(roleMap);
    if (localIds.some((id) => typeof id !== "string" || !id) || new Set(localIds).size !== localIds.length) roleFacts.push("role_map must map one-to-one to non-empty graph-local identities");
  }
  if (isObject(roleMap) && Array.isArray(executable.nodes)) {
    const executableRoles = executable.nodes.map(({ role }) => role).sort();
    const executableIds = executable.nodes.map(({ id }) => id);
    if (stableStringify(executableRoles) !== stableStringify(expectedRoles)) roleFacts.push("parsed executable roles are missing, unknown, or ambiguous");
    if (new Set(executableIds).size !== executableIds.length) roleFacts.push("parsed executable has duplicate graph-local identities");
    for (const node of executable.nodes) {
      if (roleMap[node.role] !== node.id) roleFacts.push(`parsed executable mapping contradicts ${node.role}`);
    }
  } else {
    roleFacts.push("parsed executable has no node declarations");
  }
  criteria.push(criterion("roles:cardinality", roleFacts.length === 0, ["metadata.role_map", "workflow.js:workflowStructure.nodes"], roleFacts));
  if (roleFacts.length) return verdict(binding, criteria, identities);

  const expected = expectedStructure(binding, roleMap);
  let metadataStructure;
  let executableStructure;
  try {
    metadataStructure = normalizeStructure(metadata.structure, false);
    executableStructure = normalizeStructure(executable, false);
  } catch (error) {
    return verdict(binding, [...criteria, criterion("structure:shape", false, ["metadata.structure", "workflow.js:workflowStructure"], [error.message])], identities);
  }
  const metadataOk = stableStringify(metadataStructure) === stableStringify(expected);
  const executableOk = stableStringify(executableStructure) === stableStringify(expected);
  const expectedGraph = {
    nodes: Object.values(roleMap).sort(),
    edges: expected.edges,
  };
  const graphOk = stableStringify(graph) === stableStringify(expectedGraph);
  criteria.push(
    criterion("structure:metadata", metadataOk, ["metadata.structure"], metadataOk ? [] : ["metadata structure contradicts resolved contract"]),
    criterion("structure:graph", graphOk, ["graph.mmd"], graphOk ? [] : ["Mermaid graph contradicts resolved contract"]),
    criterion("structure:executable", executableOk, ["workflow.js:workflowStructure"], executableOk ? [] : ["parsed executable contradicts resolved contract"]),
  );

  const nodeByRole = Object.fromEntries(executable.nodes.map((node) => [node.role, node]));
  for (const assertion of binding.contract.assertions) {
    const failures = [];
    for (const role of assertion.roles) {
      const field = nodeByRole[role]?.[assertion.field];
      const includes = typeof field === "string" && field.includes(assertion.value);
      if (assertion.operator === "includes_exact_text" ? !includes : includes) {
        failures.push(`${role}.${assertion.field} ${assertion.operator} failed`);
      }
    }
    criteria.push(
      criterion(
        assertion.id,
        failures.length === 0,
        assertion.roles.map((role) => `workflow.js:workflowStructure.nodes[role=${role}].${assertion.field}`),
        failures,
      ),
    );
  }

  const unknownMetadata = Object.keys(metadata).filter(
    (key) => !METADATA_KEYS.has(key),
  );
  const scopeOk =
    metadata.proof_scope === OFFLINE_SCOPE && unknownMetadata.length === 0;
  const scopeFacts = [];
  if (metadata.proof_scope !== OFFLINE_SCOPE) {
    scopeFacts.push("offline conformance claims runtime proof or execution authority");
  }
  if (unknownMetadata.length) {
    scopeFacts.push(`unknown metadata facts: ${unknownMetadata.join(", ")}`);
  }
  criteria.push(
    criterion(
      "scope:conformance-only",
      scopeOk,
      ["metadata.proof_scope", "metadata"],
      scopeFacts,
    ),
  );
  return verdict(binding, criteria, identities);
}

module.exports = {
  CASES_ROOT,
  ConformanceError,
  OFFLINE_SCOPE,
  calculateArtifactDigest,
  checkConformance,
  listCaseIds,
  resolveCase,
};
