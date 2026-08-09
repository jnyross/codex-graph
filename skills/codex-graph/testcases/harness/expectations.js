"use strict";

// Offline loader and static checker for the dynamic-workflow test cases.
// It validates case bundles (catalog + GOAL + EXPECTATIONS + topology hint)
// and statically checks a generated Code Mode workflow.js against a case's
// machine contract. Checks are conservative textual tripwires for the
// regression classes observed in lab runs (see testcases/README.md); they
// never execute the script.

const fs = require("node:fs");
const path = require("node:path");

const TESTCASES_ROOT = path.join(__dirname, "..");
const CASES_ROOT = path.join(TESTCASES_ROOT, "cases");
const CATALOG_PATH = path.join(TESTCASES_ROOT, "catalog.json");

const KNOWN_EXPECTATION_KEYS = new Set([
  "case_id",
  "task_family",
  "baseline_tier",
  "required_node_ids",
  "parallel_groups",
  "env",
  "collection",
  "single_repair",
  "terminal_guard",
  "pending_setup_resolution",
  "required_snippets",
  "forbidden_snippets",
]);

// Tool-name tripwires. Generated scripts bind read/wait tools under names
// containing these stems regardless of client namespace.
const READ_TOOL_RE = /read_?[Tt]hread|readTask|read_task/;
const WAIT_TOOL_RE = /wait_?[Tt]hread|waitTask|wait_task/;
const LOCAL_ENV_RE = /type\s*:\s*["']local["']/g;
const WORKTREE_ENV_RE = /type\s*:\s*["']worktree["']/g;
const ITEM_BUDGET_RE =
  /(?:maxOutputCharsPerItem\s*[:=]|MAX_OUTPUT_CHARS_PER_ITEM\s*=)\s*(\d+)/g;

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function extractExpectations(markdown) {
  const blocks = [...markdown.matchAll(/```json\s*\n([\s\S]*?)\n```/g)];
  if (blocks.length !== 1) {
    throw new Error(
      `expected exactly one fenced json block, found ${blocks.length}`,
    );
  }
  const parsed = JSON.parse(blocks[0][1]);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("expectations block must be a JSON object");
  }
  if (typeof parsed.case_id !== "string" || parsed.case_id === "") {
    throw new Error("expectations block requires a non-empty case_id");
  }
  for (const key of Object.keys(parsed)) {
    if (!KNOWN_EXPECTATION_KEYS.has(key)) {
      throw new Error(`unknown expectation key: ${key}`);
    }
  }
  return parsed;
}

function loadCatalog() {
  return JSON.parse(fs.readFileSync(CATALOG_PATH, "utf8"));
}

function listCaseIds() {
  return fs
    .readdirSync(CASES_ROOT, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
}

function loadCase(caseId) {
  const dir = path.join(CASES_ROOT, caseId);
  if (!fs.existsSync(dir)) {
    throw new Error(`unknown case: ${caseId}`);
  }
  const goal = fs.readFileSync(path.join(dir, "GOAL.md"), "utf8");
  const expectationsText = fs.readFileSync(
    path.join(dir, "EXPECTATIONS.md"),
    "utf8",
  );
  const expectations = extractExpectations(expectationsText);
  if (expectations.case_id !== caseId) {
    throw new Error(
      `case_id mismatch: directory ${caseId} vs contract ${expectations.case_id}`,
    );
  }
  const hintPath = path.join(dir, "topology.hint.mmd");
  const hint = fs.readFileSync(hintPath, "utf8");
  return { id: caseId, dir, goal, expectationsText, expectations, hintPath, hint };
}

function checkWorkflowText(scriptText, expectations) {
  if (typeof scriptText !== "string" || scriptText === "") {
    throw new Error("scriptText must be a non-empty string");
  }
  const checks = [];
  const add = (id, ok, detail) => checks.push({ id, ok, detail });

  for (const nodeId of expectations.required_node_ids ?? []) {
    const present = new RegExp(`\\b${escapeRegExp(nodeId)}\\b`).test(scriptText);
    add(`node:${nodeId}`, present, present ? "declared" : "node ID missing");
  }

  const groups = expectations.parallel_groups ?? [];
  if (groups.length > 0) {
    const settled = scriptText.includes("Promise.allSettled");
    add(
      "parallel:allSettled",
      settled,
      settled
        ? "Promise.allSettled present"
        : "parallel groups declared but no Promise.allSettled batch",
    );
    groups.forEach((group, index) => {
      const missing = group.filter(
        (id) => !new RegExp(`\\b${escapeRegExp(id)}\\b`).test(scriptText),
      );
      add(
        `parallel:group${index + 1}`,
        missing.length === 0,
        missing.length === 0
          ? `members present: ${group.join(", ")}`
          : `missing members: ${missing.join(", ")}`,
      );
    });
  }

  const env = expectations.env;
  if (env) {
    const localCount = (scriptText.match(LOCAL_ENV_RE) ?? []).length;
    const worktreeCount = (scriptText.match(WORKTREE_ENV_RE) ?? []).length;
    if ((env.worktree ?? []).length === 0) {
      add(
        "env:no-worktree",
        worktreeCount === 0,
        worktreeCount === 0
          ? "read-only graph creates no worktree environments"
          : `read-only graph creates ${worktreeCount} worktree environment(s)`,
      );
    } else {
      add(
        "env:worktree-writers",
        worktreeCount > 0,
        worktreeCount > 0
          ? "writer nodes use worktree environments"
          : "writers declared but no worktree environment created",
      );
    }
    if ((env.local ?? []).length > 0) {
      add(
        "env:local-nodes",
        localCount > 0,
        localCount > 0
          ? "local environments present"
          : "local nodes declared but no local environment created (global-worktree regression, #14)",
      );
    }
  }

  const collection = expectations.collection;
  if (collection) {
    const firstRead = scriptText.search(READ_TOOL_RE);
    const firstWait = scriptText.search(WAIT_TOOL_RE);
    if (collection.read_first) {
      const ok = firstRead !== -1 && (firstWait === -1 || firstRead < firstWait);
      add(
        "collection:read-first",
        ok,
        ok
          ? "read tool referenced before any wait tool"
          : "no read before the first wait (wait-only collection, #13)",
      );
    }
    if (collection.read_after_wait) {
      let ok = true;
      let detail = "no wait tool referenced; nothing to follow";
      if (firstWait !== -1) {
        const tail = scriptText.slice(firstWait);
        ok = READ_TOOL_RE.test(tail);
        detail = ok
          ? "read tool referenced after the first wait"
          : "no read after the first wait (#13)";
      }
      add("collection:read-after-wait", ok, detail);
    }
    const limit = collection.max_output_chars_per_item;
    if (typeof limit === "number") {
      const budgets = [...scriptText.matchAll(ITEM_BUDGET_RE)].map((m) =>
        Number(m[1]),
      );
      const over = budgets.filter((value) => value > limit);
      const ok = budgets.length > 0 && over.length === 0;
      add(
        "collection:item-budget",
        ok,
        budgets.length === 0
          ? "no maxOutputCharsPerItem declared"
          : over.length === 0
            ? `all ${budgets.length} budget(s) within ${limit}`
            : `budget(s) exceed ${limit}: ${over.join(", ")}`,
      );
    }
  }

  if (expectations.single_repair) {
    const ok = scriptText.includes("repairUsed");
    add(
      "repair:reported",
      ok,
      ok ? "repairUsed marker present" : "repairUsed marker missing",
    );
  }

  if (expectations.terminal_guard) {
    const ok = scriptText.includes("terminalEmitted");
    add(
      "terminal:guard",
      ok,
      ok ? "terminalEmitted guard present" : "terminalEmitted guard missing",
    );
  }

  if (expectations.pending_setup_resolution) {
    const ok = /clientThreadId|client_thread_id/.test(scriptText);
    add(
      "setup:pending-resolution",
      ok,
      ok
        ? "pending clientThreadId handling present"
        : "no pending clientThreadId resolution (#14)",
    );
  }

  for (const snippet of expectations.required_snippets ?? []) {
    const ok = scriptText.includes(snippet);
    add(
      `required:${snippet}`,
      ok,
      ok ? "present" : "required snippet missing",
    );
  }

  for (const snippet of expectations.forbidden_snippets ?? []) {
    const ok = !scriptText.includes(snippet);
    add(
      `forbidden:${snippet}`,
      ok,
      ok ? "absent" : "forbidden snippet present (over-scoped prompt, #12)",
    );
  }

  return {
    ok: checks.every((check) => check.ok),
    case: expectations.case_id,
    checks,
  };
}

module.exports = {
  CASES_ROOT,
  CATALOG_PATH,
  KNOWN_EXPECTATION_KEYS,
  extractExpectations,
  loadCatalog,
  listCaseIds,
  loadCase,
  checkWorkflowText,
};
