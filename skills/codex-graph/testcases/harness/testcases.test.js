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

test("slice-generators-join uses canonical N3 integration vocabulary", () => {
  const { expectations, hint } = loadCase("slice-generators-join");
  assert.ok(expectations.required_node_ids.includes("N3"));
  assert.ok(expectations.env.local.includes("N3"));
  assert.equal(expectations.required_node_ids.includes("I1"), false);
  assert.equal(expectations.env.local.includes("I1"), false);
  assert.match(hint, /\bN3\b/);
  assert.doesNotMatch(hint, /\bI1\b/);

  const script = buildFixtureScript(expectations);
  assert.doesNotMatch(script, /\bI1\b/);
  assert.equal(checkWorkflowText(script, expectations).ok, true);
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
    lines.push("const START_RESOLVE_ATTEMPTS = 90;");
    lines.push("const pending = start.clientThreadId ?? null;");
    lines.push("const roster = await listThreads({ limit: 50 });");
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

test("empty contract does not pass vacuously", () => {
  const verdict = checkWorkflowText("anything at all", { case_id: "x" });
  assert.equal(verdict.ok, false);
  assert.deepEqual(verdict.checks, []);
});

test("parameter-list identifier order cannot flip read-first (#13)", () => {
  // frozen-lisbon-v3 shape after a 2-line parameter rename: readThread
  // precedes waitThreads in the signature, but the first await-adjacent
  // call is still the wait. The defect must keep failing.
  const script = [
    "async function collect(handles, readThread, waitThreads) {",
    "  const snap = await waitThreads.call({ targets: [] });",
    "  const out = await readThread.call({ threadId: 't' });",
    "  return out;",
    "}",
  ].join("\n");
  const verdict = checkWorkflowText(script, {
    case_id: "x",
    collection: { read_first: true },
  });
  assert.equal(verdict.ok, false);
  const check = verdict.checks.find((c) => c.id === "collection:read-first");
  assert.equal(check.ok, false);
  assert.match(check.detail, /wait-only/);
});

test("helper-wrapped correct collector is not false-failed on read-first", () => {
  // Shape of a genuinely read-first collector whose wait helper happens to
  // be declared above its read helper and whose tool calls sit inside
  // wrappers: no await-adjacent call sites, so ordering is not judged.
  const script = [
    "async function waitForNode(h) { return waitThreads.call({ targets: [h] }); }",
    "async function readNode(h) { return readThread.call({ threadId: h }); }",
    "async function collect(h) {",
    "  let out = await readNode(h);",
    "  while (!out.done) { await waitForNode(h); out = await readNode(h); }",
    "  return out;",
    "}",
  ].join("\n");
  const verdict = checkWorkflowText(script, {
    case_id: "x",
    collection: { read_first: true, read_after_wait: true },
  });
  assert.equal(verdict.ok, true);
});

test("resolved helper names reject member and identifier-suffix call sites", () => {
  for (const falseReadCall of [
    "await helpers.readFor(h);",
    "await notreadFor(h);",
  ]) {
    const script = [
      "const readFor = (h) => readThread.call({ threadId: h });",
      "async function collect(h) {",
      `  const falseRead = ${falseReadCall}`,
      "  return await waitThreads.call({ targets: [h] });",
      "}",
    ].join("\n");
    const verdict = checkWorkflowText(script, {
      case_id: "x",
      collection: { read_first: true },
    });
    const readFirst = verdict.checks.find(
      (check) => check.id === "collection:read-first",
    );
    assert.equal(readFirst.ok, false, falseReadCall);
    assert.match(readFirst.detail, /wait-only/, falseReadCall);
  }
});

test("mentioning clientThreadId without a resolution loop fails (#14)", () => {
  // The canonical #14 failure stores and tests the identifier but never
  // resolves it against the task list.
  const script = [
    "const handle = { client_thread_id: start.clientThreadId ?? null };",
    "if (!handle.client_thread_id) { throw new Error('no id'); }",
  ].join("\n");
  const verdict = checkWorkflowText(script, {
    case_id: "x",
    pending_setup_resolution: true,
  });
  assert.equal(verdict.ok, false);
  const check = verdict.checks.find((c) => c.id === "setup:pending-resolution");
  assert.equal(check.ok, false);
  assert.match(check.detail, /no resolution-loop evidence/);
});

test("mixed wrapper collector (direct wait, helper reads) passes ordering (#13)", () => {
  // frozen-lisbon-v4 shape: reads go through a resolved helper while the
  // wait is a direct call site. Genuine read -> wait -> read must pass.
  const script = [
    "async function readFor(h) { const r = await readThread.call({ threadId: h }); return r; }",
    "async function collectOne(h) {",
    "  let out = await readFor(h);",
    "  while (!out) {",
    "    const w = await waitThreads.call({ targets: [h] });",
    "    out = await readFor(h);",
    "  }",
    "  return out;",
    "}",
  ].join("\n");
  const verdict = checkWorkflowText(script, {
    case_id: "x",
    collection: { read_first: true, read_after_wait: true },
  });
  assert.equal(verdict.ok, true, JSON.stringify(verdict.checks));
});

test("genuinely wait-first mixed wrapper script still fails read-first (#13)", () => {
  // Same helper shape, but the first call site is the wait and the read
  // helper is declared below it: the defect must keep failing.
  const script = [
    "async function run(h) {",
    "  const w = await waitThreads.call({ targets: [h] });",
    "  const out = await readFor(h);",
    "  return out;",
    "}",
    "async function readFor(h) { const r = await readThread.call({ threadId: h }); return r; }",
  ].join("\n");
  const verdict = checkWorkflowText(script, {
    case_id: "x",
    collection: { read_first: true },
  });
  const check = verdict.checks.find((c) => c.id === "collection:read-first");
  assert.equal(check.ok, false);
  assert.match(check.detail, /wait-only/);
});

test("call-free stub fails when collection is declared", () => {
  // Comment-only stub that satisfies every marker textually but never
  // calls a tool: the ordering carve-out must not green-light it.
  const { expectations } = loadCase("sealed-pov-factcheck");
  const script = [
    "// N1 N2A N2B N2C V1A V1B V1C G1 T1",
    "// Promise.allSettled UNVERIFIABLE",
    '// environment type: "local"',
    "// maxOutputCharsPerItem: 20000",
    "// terminalEmitted",
  ].join("\n");
  const verdict = checkWorkflowText(script, expectations);
  assert.equal(verdict.ok, false);
  const failed = verdict.checks.filter((c) => !c.ok);
  assert.deepEqual(
    failed.map((c) => c.id),
    ["collection:call-sites"],
  );
  assert.match(failed[0].detail, /no tool call sites/);
});
