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
const STRUCTURE_KEYS = new Set([
  "collection",
  "concurrency",
  "edges",
  "gates",
  "nodes",
  "repair_edges",
  "terminal_paths",
]);
const NODE_KEYS = new Set(["environment", "id", "kind", "role"]);
const EXECUTABLE_NODE_KEYS = new Set([...NODE_KEYS, "prompt"]);
const EDGE_KEYS = new Set(["from", "outcome", "to"]);
const REPAIR_EDGE_KEYS = new Set(["from", "to"]);
const GATE_KEYS = new Set(["node", "outcomes"]);

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
      .sort(codeUnitCompare)
      .map((key) => [key, sortedObject(value[key])]),
  );
}

function stableStringify(value) {
  return JSON.stringify(sortedObject(value));
}

function codeUnitCompare(left, right) {
  return left < right ? -1 : left > right ? 1 : 0;
}

function sortObjects(items) {
  return [...items].sort((left, right) =>
    codeUnitCompare(stableStringify(left), stableStringify(right)),
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
    if (!Object.hasOwn(raw, key)) fail("contract:shape", `contract is missing ${key}`);
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
    return [...group].sort(codeUnitCompare);
  });

  if (!Array.isArray(raw.gates)) fail("contract:gates", "gates must be an array");
  const gates = raw.gates.map((gate, index) => {
    exactKeys(gate, new Set(["outcomes", "role"]), "contract:gates", `gates[${index}]`);
    if (kindByRole[gate.role] !== "gate") fail("contract:gates", `${gate.role} is not a gate role`);
    if (!Array.isArray(gate.outcomes) || gate.outcomes.length === 0 || new Set(gate.outcomes).size !== gate.outcomes.length) {
      fail("contract:gates", `${gate.role} has invalid outcomes`);
    }
    return { role: gate.role, outcomes: [...gate.outcomes].sort(codeUnitCompare) };
  });
  for (const gate of gates) {
    const routedOutcomes = topology
      .filter((edge) => edge.from === gate.role && edge.outcome !== undefined)
      .map(({ outcome }) => outcome)
      .sort(codeUnitCompare);
    if (stableStringify(routedOutcomes) !== stableStringify(gate.outcomes)) {
      fail("contract:gates", `${gate.role} outcomes contradict its topology routes`);
    }
  }

  if (!Array.isArray(raw.repair_edges)) {
    fail("contract:repair-edges", "repair_edges must be an array");
  }
  const repairEdges = raw.repair_edges.map((edge, index) =>
    normalizeEdge(edge, roles, `repair_edges[${index}]`),
  );
  for (const edge of repairEdges) {
    if (!topology.some((candidate) => candidate.from === edge.from && candidate.to === edge.to)) {
      fail("contract:repair-edges", `repair edge ${edge.from}->${edge.to} is absent from topology`);
    }
  }

  if (!Array.isArray(raw.terminal_paths)) {
    fail("contract:terminal-paths", "terminal_paths must be an array");
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
    return { ...assertion, roles: [...assertion.roles].sort(codeUnitCompare) };
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
    .sort(codeUnitCompare);
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
  const commands = process.platform === "win32"
    ? [["py", ["-3", parser, "--parse-stdin-json"]], ["python", [parser, "--parse-stdin-json"]]]
    : [["python3", [parser, "--parse-stdin-json"]], ["python", [parser, "--parse-stdin-json"]]];
  let unavailable;
  for (const [command, args] of commands) {
    const result = spawnSync(command, args, {
      input: graph,
      encoding: "utf8",
      maxBuffer: 1024 * 1024,
      timeout: 30_000,
    });
    if (result.error?.code === "ENOENT") {
      unavailable = result.error;
      continue;
    }
    if (result.error) throw result.error;
    if (result.signal) {
      throw new Error(`Mermaid parser terminated by signal ${result.signal}`);
    }
    if (result.status === null) {
      throw new Error("Mermaid parser terminated without an exit status");
    }
    if (result.status !== 0) {
      throw new Error(result.stderr?.trim() || "Mermaid parsing failed");
    }
    const parsed = JSON.parse(result.stdout);
    return {
      nodes: [...parsed.nodes].sort(codeUnitCompare),
      edges: sortObjects(parsed.edges),
    };
  }
  throw unavailable ?? new Error("Python is required for Mermaid parsing");
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
    const value = Object.create(null);
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
        Object.hasOwn(value, key)
      ) {
        throw new Error("workflowStructure has an invalid or duplicate property");
      }
      if (key === "__proto__" || key === "constructor" || key === "prototype") {
        fail("structure:shape", `workflowStructure has unknown key: ${key}`);
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

function patternHasName(pattern, name) {
  if (!pattern) return false;
  if (pattern.type === "Identifier") return pattern.name === name;
  if (pattern.type === "RestElement") return patternHasName(pattern.argument, name);
  if (pattern.type === "AssignmentPattern") return patternHasName(pattern.left, name);
  if (pattern.type === "ArrayPattern") {
    return pattern.elements.some((element) => patternHasName(element, name));
  }
  if (pattern.type === "ObjectPattern") {
    return pattern.properties.some((property) =>
      property.type === "RestElement"
        ? patternHasName(property.argument, name)
        : patternHasName(property.value, name));
  }
  return false;
}

function targetHasName(target, name) {
  if (target?.type === "MemberExpression") {
    return targetHasName(target.object, name);
  }
  if (target?.type === "ChainExpression") {
    return targetHasName(target.expression, name);
  }
  return patternHasName(target, name);
}

function targetsRuntimeBinding(target) {
  return ["runWorkflow", "module"].some((name) => targetHasName(target, name));
}

function assignmentToExport(node) {
  return (
    node?.type === "ExpressionStatement" &&
    node.expression.type === "AssignmentExpression" &&
    node.expression.operator === "=" &&
    node.expression.left.type === "MemberExpression" &&
    !node.expression.left.computed &&
    node.expression.left.object.type === "Identifier" &&
    node.expression.left.object.name === "module" &&
    node.expression.left.property.type === "Identifier" &&
    node.expression.left.property.name === "exports" &&
    node.expression.right.type === "Identifier" &&
    node.expression.right.name === "workflowStructure"
  );
}

function guardedExport(statement) {
  if (statement.type !== "IfStatement" || statement.alternate) return false;
  const test = statement.test;
  const moduleGuard =
    test.type === "BinaryExpression" &&
    ["!=", "!=="].includes(test.operator) &&
    test.left.type === "UnaryExpression" &&
    test.left.operator === "typeof" &&
    test.left.argument.type === "Identifier" &&
    test.left.argument.name === "module" &&
    test.right.type === "Literal" &&
    test.right.value === "undefined";
  if (!moduleGuard) return false;
  const consequent = statement.consequent.type === "BlockStatement"
    ? statement.consequent.body
    : [statement.consequent];
  return consequent.length === 1 && assignmentToExport(consequent[0]);
}

function awaitedWorkflowRun(statement) {
  const expression = statement.type === "ExpressionStatement"
    ? statement.expression
    : null;
  const call = expression?.type === "AwaitExpression" ? expression.argument : null;
  return (
    call?.type === "CallExpression" &&
    call.callee.type === "Identifier" &&
    call.callee.name === "runWorkflow" &&
    call.arguments.length === 1 &&
    call.arguments[0].type === "Identifier" &&
    call.arguments[0].name === "workflowStructure"
  );
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
  const declarations = program.body.filter((statement) =>
    statement.type === "VariableDeclaration" &&
    statement.kind === "const" &&
    statement.declarations.length === 1 &&
    statement.declarations[0].id.type === "Identifier" &&
    statement.declarations[0].id.name === "workflowStructure");
  const guardedExports = program.body.filter(guardedExport);
  const guardedConsequent = guardedExports[0]?.consequent;
  const allowedExportAssignment = guardedExports.length === 1
    ? (guardedConsequent.type === "BlockStatement"
      ? guardedConsequent.body[0]
      : guardedConsequent).expression
    : null;
  let structureBindings = 0;
  let shadowedRuntimeBinding = false;
  let workflowRuns = 0;
  let workflowExports = 0;
  walk(program, (node) => {
    let patterns = [];
    if (node.type === "VariableDeclarator") patterns = [node.id];
    else if (["FunctionDeclaration", "FunctionExpression"].includes(node.type)) {
      patterns = [node.id, ...node.params];
    } else if (node.type === "ArrowFunctionExpression") {
      patterns = node.params;
    } else if (node.type === "ClassDeclaration" || node.type === "ClassExpression") {
      patterns = [node.id];
    } else if (node.type === "CatchClause") {
      patterns = [node.param];
    }
    if (patterns.some((pattern) => patternHasName(pattern, "workflowStructure"))) {
      structureBindings += 1;
    }
    if (patterns.some((pattern) =>
      patternHasName(pattern, "runWorkflow") || patternHasName(pattern, "module"))) {
      shadowedRuntimeBinding = true;
    }
    if (
      (node.type === "AssignmentExpression" &&
        node !== allowedExportAssignment &&
        targetsRuntimeBinding(node.left)) ||
      (node.type === "UpdateExpression" && targetsRuntimeBinding(node.argument))
    ) {
      shadowedRuntimeBinding = true;
    }
    if (assignmentToExport(node)) workflowExports += 1;
    if (
      node.type === "CallExpression" &&
      node.callee.type === "Identifier" &&
      node.callee.name === "runWorkflow"
    ) {
      workflowRuns += 1;
    }
  });

  if (
    declarations.length !== 1 ||
    structureBindings !== 1 ||
    shadowedRuntimeBinding ||
    guardedExports.length !== 1 ||
    workflowExports !== 1 ||
    program.body.filter(awaitedWorkflowRun).length !== 1 ||
    workflowRuns !== 1
  ) {
    throw new Error(
      "workflow.js requires one unshadowed top-level workflow binding, guarded export, and awaited run",
    );
  }
  return astValue(declarations[0].declarations[0].init);
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

function requireObject(value, label) {
  if (!isObject(value)) throw new Error(`${label} must be an object`);
}

function requireArray(value, label) {
  if (!Array.isArray(value)) throw new Error(`${label} must be an array`);
}

function requireKeys(value, allowed, required, label) {
  requireObject(value, label);
  const unknown = Object.keys(value)
    .filter((key) => !allowed.has(key))
    .sort(codeUnitCompare);
  if (unknown.length) throw new Error(`${label} has unknown keys: ${unknown.join(", ")}`);
  for (const key of required) {
    if (!Object.hasOwn(value, key)) throw new Error(`${label} is missing ${key}`);
  }
}

function requireString(value, label) {
  if (typeof value !== "string" || !value) {
    throw new Error(`${label} must be a non-empty string`);
  }
}

function normalizeStructure(structure, includePrompts = false) {
  requireKeys(structure, STRUCTURE_KEYS, STRUCTURE_KEYS, "structure");
  requireArray(structure.nodes, "structure.nodes");
  const nodes = structure.nodes.map((node, index) => {
    const label = `structure.nodes[${index}]`;
    requireKeys(
      node,
      includePrompts ? EXECUTABLE_NODE_KEYS : NODE_KEYS,
      NODE_KEYS,
      label,
    );
    for (const key of NODE_KEYS) requireString(node[key], `${label}.${key}`);
    return {
      id: node.id,
      role: node.role,
      kind: node.kind,
      environment: node.environment,
    };
  });

  requireArray(structure.edges, "structure.edges");
  const edges = structure.edges.map((edge, index) => {
    const label = `structure.edges[${index}]`;
    requireKeys(edge, EDGE_KEYS, new Set(["from", "to"]), label);
    requireString(edge.from, `${label}.from`);
    requireString(edge.to, `${label}.to`);
    if (Object.hasOwn(edge, "outcome")) requireString(edge.outcome, `${label}.outcome`);
    return { from: edge.from, to: edge.to, ...(Object.hasOwn(edge, "outcome") ? { outcome: edge.outcome } : {}) };
  });

  requireArray(structure.concurrency, "structure.concurrency");
  const concurrency = structure.concurrency.map((group, index) => {
    requireArray(group, `structure.concurrency[${index}]`);
    group.forEach((role, roleIndex) =>
      requireString(role, `structure.concurrency[${index}][${roleIndex}]`));
    return [...group].sort(codeUnitCompare);
  });

  requireArray(structure.gates, "structure.gates");
  const gates = structure.gates.map((gate, index) => {
    const label = `structure.gates[${index}]`;
    requireKeys(gate, GATE_KEYS, GATE_KEYS, label);
    requireString(gate.node, `${label}.node`);
    requireArray(gate.outcomes, `${label}.outcomes`);
    gate.outcomes.forEach((outcome, outcomeIndex) =>
      requireString(outcome, `${label}.outcomes[${outcomeIndex}]`));
    return { node: gate.node, outcomes: [...gate.outcomes].sort(codeUnitCompare) };
  });

  const normalizeEdges = (value, key, allowed) => {
    requireArray(value, `structure.${key}`);
    return value.map((edge, index) => {
      const label = `structure.${key}[${index}]`;
      requireKeys(edge, allowed, REPAIR_EDGE_KEYS, label);
      requireString(edge.from, `${label}.from`);
      requireString(edge.to, `${label}.to`);
      if (Object.hasOwn(edge, "outcome")) requireString(edge.outcome, `${label}.outcome`);
      return { from: edge.from, to: edge.to, ...(Object.hasOwn(edge, "outcome") ? { outcome: edge.outcome } : {}) };
    });
  };

  const repairEdges = normalizeEdges(
    structure.repair_edges,
    "repair_edges",
    REPAIR_EDGE_KEYS,
  );
  const terminalPaths = normalizeEdges(
    structure.terminal_paths,
    "terminal_paths",
    EDGE_KEYS,
  );
  requireKeys(structure.collection, COLLECTION_KEYS, new Set(), "structure.collection");
  return {
    nodes: sortObjects(nodes),
    edges: sortObjects(edges),
    concurrency: sortObjects(concurrency),
    gates: sortObjects(gates),
    repair_edges: sortObjects(repairEdges),
    terminal_paths: sortObjects(terminalPaths),
    collection: sortedObject(structure.collection),
  };
}

function factRecords(structure, root) {
  const records = [];
  const add = (kind, value, locator) =>
    records.push({ key: `${kind}:${stableStringify(value)}`, locator });
  structure.nodes.forEach((value) =>
    add("node", value, `${root}.nodes[role=${value.role}]`));
  structure.edges.forEach((value) =>
    add("edge", value, `${root}.edges[${value.from}->${value.to}]`));
  structure.concurrency.forEach((value) =>
    add("concurrency", value, `${root}.concurrency[${value.join(",")}]`));
  structure.gates.forEach((value) =>
    add("gate", value, `${root}.gates[node=${value.node}]`));
  structure.repair_edges.forEach((value) =>
    add("repair_edge", value, `${root}.repair_edges[${value.from}->${value.to}]`));
  structure.terminal_paths.forEach((value) =>
    add("terminal_path", value, `${root}.terminal_paths[${value.from}->${value.to}]`));
  for (const [key, value] of Object.entries(structure.collection)) {
    add("collection", { key, value }, `${root}.collection.${key}`);
  }
  return records;
}

function graphFactRecords(graph, root) {
  return [
    ...graph.nodes.map((node) => ({
      key: `node:${stableStringify(node)}`,
      locator: `${root}.nodes[id=${node}]`,
    })),
    ...graph.edges.map((edge) => ({
      key: `edge:${stableStringify(edge)}`,
      locator: `${root}.edges[${edge.from}->${edge.to}]`,
    })),
  ];
}

function compareFacts(expectedRecords, actualRecords) {
  const grouped = (records) => {
    const groups = new Map();
    for (const record of records) {
      if (!groups.has(record.key)) groups.set(record.key, []);
      groups.get(record.key).push(record.locator);
    }
    return groups;
  };
  const expected = grouped(expectedRecords);
  const actual = grouped(actualRecords);
  const facts = [];
  const locators = new Set();
  const keys = new Set([...expected.keys(), ...actual.keys()]);
  for (const key of [...keys].sort(codeUnitCompare)) {
    const wanted = expected.get(key) ?? [];
    const found = actual.get(key) ?? [];
    for (let index = found.length; index < wanted.length; index += 1) {
      facts.push(`missing ${key}`);
      locators.add(wanted[index]);
    }
    for (let index = wanted.length; index < found.length; index += 1) {
      facts.push(`unexpected ${key}`);
      locators.add(found[index]);
    }
  }
  return {
    ok: facts.length === 0,
    facts,
    locators: [...locators].sort(codeUnitCompare),
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
    const id = error instanceof ConformanceError ? error.criterion : "structure:parse";
    const locator = id === "structure:shape"
      ? "workflow.js:workflowStructure"
      : "artifact-set";
    return verdict(binding, [criterion(id, false, [locator], [error.message])], identities);
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

  let metadataStructure;
  let executableStructure;
  try {
    metadataStructure = normalizeStructure(metadata.structure);
    executableStructure = normalizeStructure(executable, true);
  } catch (error) {
    return verdict(
      binding,
      [...criteria, criterion(
        "structure:shape",
        false,
        ["metadata.structure", "workflow.js:workflowStructure"],
        [error.message],
      )],
      identities,
    );
  }

  const expectedRoles = binding.contract.role_instances
    .map(({ role }) => role)
    .sort(codeUnitCompare);
  const roleMap = metadata.role_map;
  const roleFacts = [];
  if (!isObject(roleMap)) {
    roleFacts.push("metadata.role_map must be an object");
  } else {
    const mappedRoles = Object.keys(roleMap).sort(codeUnitCompare);
    if (stableStringify(mappedRoles) !== stableStringify(expectedRoles)) roleFacts.push("role_map roles differ from the resolved contract");
    const localIds = Object.values(roleMap);
    if (localIds.some((id) => typeof id !== "string" || !id) || new Set(localIds).size !== localIds.length) roleFacts.push("role_map must map one-to-one to non-empty graph-local identities");
  }
  if (isObject(roleMap)) {
    const executableRoles = executableStructure.nodes
      .map(({ role }) => role)
      .sort(codeUnitCompare);
    const executableIds = executableStructure.nodes.map(({ id }) => id);
    if (stableStringify(executableRoles) !== stableStringify(expectedRoles)) roleFacts.push("parsed executable roles are missing, unknown, or ambiguous");
    if (new Set(executableIds).size !== executableIds.length) roleFacts.push("parsed executable has duplicate graph-local identities");
    for (const node of executableStructure.nodes) {
      if (roleMap[node.role] !== node.id) roleFacts.push(`parsed executable mapping contradicts ${node.role}`);
    }
  }
  criteria.push(criterion(
    "roles:cardinality",
    roleFacts.length === 0,
    ["metadata.role_map", "workflow.js:workflowStructure.nodes"],
    roleFacts,
  ));
  if (roleFacts.length) return verdict(binding, criteria, identities);

  const expected = expectedStructure(binding, roleMap);
  const expectedFacts = factRecords(expected, "contract");
  const metadataComparison = compareFacts(
    expectedFacts,
    factRecords(metadataStructure, "metadata.structure"),
  );
  const executableComparison = compareFacts(
    expectedFacts,
    factRecords(executableStructure, "workflow.js:workflowStructure"),
  );
  const expectedGraph = {
    nodes: Object.values(roleMap).sort(codeUnitCompare),
    edges: expected.edges,
  };
  const graphComparison = compareFacts(
    graphFactRecords(expectedGraph, "contract"),
    graphFactRecords(graph, "graph.mmd"),
  );
  criteria.push(
    criterion(
      "structure:metadata",
      metadataComparison.ok,
      metadataComparison.locators.length ? metadataComparison.locators : ["metadata.structure"],
      metadataComparison.facts,
    ),
    criterion(
      "structure:graph",
      graphComparison.ok,
      graphComparison.locators.length ? graphComparison.locators : ["graph.mmd"],
      graphComparison.facts,
    ),
    criterion(
      "structure:executable",
      executableComparison.ok,
      executableComparison.locators.length ? executableComparison.locators : ["workflow.js:workflowStructure"],
      executableComparison.facts,
    ),
  );

  const nodeByRole = Object.fromEntries(executable.nodes.map((node) => [node.role, node]));
  for (const assertion of binding.contract.assertions) {
    const failures = [];
    for (const role of assertion.roles) {
      const node = nodeByRole[role];
      if (!Object.hasOwn(node, assertion.field) || typeof node[assertion.field] !== "string") {
        failures.push(`${role}.${assertion.field} must be an own string`);
        continue;
      }
      const includes = node[assertion.field].includes(assertion.value);
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

  const unknownMetadata = Object.keys(metadata)
    .filter((key) => !METADATA_KEYS.has(key))
    .sort(codeUnitCompare);
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
