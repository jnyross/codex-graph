"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const {
  CASES_ROOT,
  extractExpectations,
  loadCatalog,
  listCaseIds,
  loadCase,
  checkWorkflowText,
} = require("./expectations.js");

// ── Bundle integrity ────────────────────────────────────────────────────────

test("catalog and case directories agree exactly", () => {
  const catalogIds = loadCatalog().cases.map((entry) => entry.id).sort();
  assert.deepEqual(listCaseIds(), catalogIds);
  assert.ok(catalogIds.length >= 5, "shortlist is 5-8 first-class cases");
  assert.ok(catalogIds.length <= 8, "shortlist is 5-8 first-class cases");
});

test("every case bundle is complete and internally consistent", () => {
  for (const id of listCaseIds()) {
    const testCase = loadCase(id);
    assert.equal(testCase.expectations.case_id, id);
    assert.ok(testCase.goal.trim().length > 200, `${id}: GOAL.md too thin`);
    assert.match(
      testCase.hint,
      /^flowchart TD/,
      `${id}: topology hint must be an unfenced flowchart TD`,
    );
    for (const file of ["GOAL.md", "EXPECTATIONS.md", "topology.hint.mmd"]) {
      assert.ok(
        fs.existsSync(path.join(CASES_ROOT, id, file)),
        `${id}: missing ${file}`,
      );
    }
  }
});

test("catalog entries carry the required index fields", () => {
  for (const entry of loadCatalog().cases) {
    for (const field of [
      "id",
      "title",
      "task_family",
      "baseline_tier",
      "source_shape",
      "phases",
      "fanout",
      "join",
      "validation",
      "contracts",
    ]) {
      assert.ok(
        entry[field] !== undefined && entry[field] !== "",
        `${entry.id}: catalog field ${field} missing`,
      );
    }
    assert.match(entry.baseline_tier, /^L[0-4]$/);
  }
});

test("case tier and family match the catalog", () => {
  const byId = new Map(loadCatalog().cases.map((entry) => [entry.id, entry]));
  for (const id of listCaseIds()) {
    const { expectations } = loadCase(id);
    const entry = byId.get(id);
    assert.equal(expectations.baseline_tier, entry.baseline_tier, id);
    assert.equal(expectations.task_family, entry.task_family, id);
  }
});

test("every required node ID appears in the topology hint", () => {
  for (const id of listCaseIds()) {
    const { expectations, hint } = loadCase(id);
    for (const nodeId of expectations.required_node_ids ?? []) {
      assert.match(
        hint,
        new RegExp(`\\b${nodeId}\\b`),
        `${id}: node ${nodeId} missing from topology hint`,
      );
    }
  }
});

// ── Expectations extraction ─────────────────────────────────────────────────

test("extractExpectations rejects missing, multiple, and malformed blocks", () => {
  assert.throws(() => extractExpectations("# no block"), /exactly one/);
  assert.throws(
    () =>
      extractExpectations(
        '```json\n{"case_id":"a"}\n```\n```json\n{"case_id":"b"}\n```',
      ),
    /exactly one/,
  );
  assert.throws(
    () => extractExpectations('```json\n{"no_case": true}\n```'),
    /case_id/,
  );
  assert.throws(
    () => extractExpectations('```json\n{"case_id":"a","typo_key":1}\n```'),
    /unknown expectation key: typo_key/,
  );
});

// ── Static checker ──────────────────────────────────────────────────────────

// Build the smallest script exhibiting every marker a case demands. The case
// bundles are golden data; these fixtures prove each contract is satisfiable
// and that the checker holds the line when a marker is removed.
function buildFixtureScript(expectations) {
  const lines = ["// @exec fixture workflow"];
  const nodeIds = expectations.required_node_ids ?? [];
  lines.push(`const WORKFLOW = { nodes: [${nodeIds.map((id) => `"${id}"`).join(", ")}] };`);
  for (const group of expectations.parallel_groups ?? []) {
    lines.push(`// panel: ${group.join(" ")}`);
  }
  if ((expectations.parallel_groups ?? []).length > 0) {
    lines.push("const settled = await Promise.allSettled(starts);");
  }
  const env = expectations.env ?? {};
  for (const id of env.local ?? []) {
    lines.push(`// ${id} target
const env_${id} = { environment: { type: "local" } };`);
  }
  for (const id of env.worktree ?? []) {
    lines.push(`const env_${id} = { environment: { type: "worktree" } };`);
  }
  if (expectations.pending_setup_resolution) {
    lines.push("const pending = start.clientThreadId ?? null;");
  }
  if (expectations.collection) {
    lines.push("const MAX_OUTPUT_CHARS_PER_ITEM = 20000;");
    lines.push(
      "const first = await readThread({ threadId, maxOutputCharsPerItem: MAX_OUTPUT_CHARS_PER_ITEM });",
    );
    lines.push("const snap = await waitThreads({ threadIds: [threadId] });");
    lines.push(
      "const again = await readThread({ threadId, maxOutputCharsPerItem: MAX_OUTPUT_CHARS_PER_ITEM });",
    );
  }
  if (expectations.single_repair) {
    lines.push("let repairUsed = false;");
  }
  if (expectations.terminal_guard) {
    lines.push("let terminalEmitted = false;");
  }
  for (const snippet of expectations.required_snippets ?? []) {
    lines.push(`// contract marker: ${snippet}`);
  }
  return lines.join("\n");
}

test("each case's machine contract is satisfiable by a conforming script", () => {
  for (const id of listCaseIds()) {
    const { expectations } = loadCase(id);
    const verdict = checkWorkflowText(buildFixtureScript(expectations), expectations);
    const failed = verdict.checks.filter((check) => !check.ok);
    assert.deepEqual(failed, [], `${id}: ${JSON.stringify(failed)}`);
  }
});

test("global worktree environment fails the per-node env rule (#14)", () => {
  const { expectations } = loadCase("disjoint-writers-worktree");
  const script = buildFixtureScript(expectations).replaceAll(
    'type: "local"',
    'type: "worktree"',
  );
  const verdict = checkWorkflowText(script, expectations);
  assert.equal(verdict.ok, false);
  const check = verdict.checks.find((c) => c.id === "env:local-nodes");
  assert.equal(check.ok, false);
  assert.match(check.detail, /global-worktree/);
});

test("a worktree environment in a read-only graph fails (#14)", () => {
  const { expectations } = loadCase("atomic-screen-fanout");
  const script =
    buildFixtureScript(expectations) +
    '\nconst rogue = { environment: { type: "worktree" } };';
  const verdict = checkWorkflowText(script, expectations);
  assert.equal(verdict.checks.find((c) => c.id === "env:no-worktree").ok, false);
});

test("wait-only collection fails the read-first rule (#13)", () => {
  const { expectations } = loadCase("atomic-screen-fanout");
  const script = buildFixtureScript(expectations)
    .split("\n")
    .filter((line) => !line.includes("const first = await readThread"))
    .join("\n");
  const verdict = checkWorkflowText(script, expectations);
  assert.equal(
    verdict.checks.find((c) => c.id === "collection:read-first").ok,
    false,
  );
});

test("missing read after wait fails (#13)", () => {
  const { expectations } = loadCase("sealed-pov-factcheck");
  const script = buildFixtureScript(expectations)
    .split("\n")
    .filter((line) => !line.includes("const again = await readThread"))
    .join("\n");
  const verdict = checkWorkflowText(script, expectations);
  assert.equal(
    verdict.checks.find((c) => c.id === "collection:read-after-wait").ok,
    false,
  );
});

test("an oversized item budget fails the declared tool limit", () => {
  const { expectations } = loadCase("slice-generators-join");
  const script = buildFixtureScript(expectations).replace(
    "MAX_OUTPUT_CHARS_PER_ITEM = 20000",
    "MAX_OUTPUT_CHARS_PER_ITEM = 60000",
  );
  const verdict = checkWorkflowText(script, expectations);
  assert.equal(
    verdict.checks.find((c) => c.id === "collection:item-budget").ok,
    false,
  );
});

test("a missing terminal guard fails", () => {
  const { expectations } = loadCase("adversarial-dual-validation");
  const script = buildFixtureScript(expectations).replace(
    "let terminalEmitted = false;",
    "",
  );
  const verdict = checkWorkflowText(script, expectations);
  assert.equal(verdict.checks.find((c) => c.id === "terminal:guard").ok, false);
});

test("an over-scoped worker prompt phrase fails (#12)", () => {
  const { expectations } = loadCase("nonbinding-synthesis-gate");
  const script =
    buildFixtureScript(expectations) +
    '\nconst prompt = "The draft must pass all audit lanes before you return.";';
  const verdict = checkWorkflowText(script, expectations);
  const check = verdict.checks.find(
    (c) => c.id === "forbidden:must pass all audit lanes",
  );
  assert.equal(check.ok, false);
  assert.match(check.detail, /#12/);
});

test("missing pending clientThreadId handling fails (#14)", () => {
  const { expectations } = loadCase("disjoint-writers-worktree");
  const script = buildFixtureScript(expectations).replace(
    "const pending = start.clientThreadId ?? null;",
    "",
  );
  const verdict = checkWorkflowText(script, expectations);
  assert.equal(
    verdict.checks.find((c) => c.id === "setup:pending-resolution").ok,
    false,
  );
});
