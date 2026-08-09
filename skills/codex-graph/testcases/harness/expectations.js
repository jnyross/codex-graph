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

// Await-adjacent tool call sites. Generated scripts bind read/wait tools
// under names containing these stems regardless of client namespace; the
// `await` prefix restricts matching to call sites so that parameter lists,
// bindings, and comments cannot influence ordering verdicts. Helper names
// bound to a tool (const readFor = ... readThread ..., or a function whose
// nearby body references the tool) are resolved as call sites too, so mixed
// collectors that reach one tool through a wrapper are judged correctly.
const READ_STEM_RE = /read_?[Tt]hread|read_?[Tt]ask/;
const WAIT_STEM_RE = /wait_?[Tt]hread|wait_?[Tt]ask/;
const READ_STEM_SOURCE = "read_?[Tt]hread[\\w$]*|read_?[Tt]ask[\\w$]*";
const WAIT_STEM_SOURCE = "wait_?[Tt]hread[\\w$]*|wait_?[Tt]ask[\\w$]*";
// Bounded window for judging a function helper's body without an AST.
const FN_HELPER_WINDOW = 500;
const LOCAL_ENV_RE = /type\s*:\s*["']local["']/g;
const WORKTREE_ENV_RE = /type\s*:\s*["']worktree["']/g;
const ITEM_BUDGET_RE =
  /(?:maxOutputCharsPerItem\s*[:=]|MAX_OUTPUT_CHARS_PER_ITEM\s*=)\s*(\d+)/g;

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function collectHelperNames(scriptText, stemRe) {
  const names = new Set();
  // Single-line bindings: judge only the declaration's own line so that a
  // neighbouring declaration cannot bleed its tool name into this one, and
  // require a function-like right-hand side (arrow, function keyword, tool
  // binding, or bind) — `const readResult = await readThread.call(...)`
  // stores a result and is not a callable helper.
  for (const m of scriptText.matchAll(
    /(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=([^\n]*)/g,
  )) {
    if (
      stemRe.test(m[2]) &&
      /=>|\bfunction\b|resolveTool|\.bind\s*\(/.test(m[2])
    ) {
      names.add(m[1]);
    }
  }
  // Function helpers: judge a bounded body window, cut at the next
  // top-level declaration so a small helper cannot inherit its
  // neighbour's tool references.
  for (const m of scriptText.matchAll(
    /(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(/g,
  )) {
    let window = scriptText.slice(m.index, m.index + FN_HELPER_WINDOW);
    const nextDecl = window
      .slice(1)
      .search(/\n(?:async\s+function\s|function\s|const\s|let\s|var\s)/);
    if (nextDecl !== -1) window = window.slice(0, nextDecl + 1);
    if (stemRe.test(window)) names.add(m[1]);
  }
  return names;
}

function buildAwaitCallRe(stemSource, helperNames) {
  const parts = [
    stemSource,
    ...[...helperNames].map((name) => `${escapeRegExp(name)}\\b`),
  ];
  return new RegExp(`await\\s+[\\w.$]*(?:${parts.join("|")})`);
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
    // Ordering is judged on await-adjacent call sites: parameter lists,
    // bindings, and comments mention tool names without `await`, so
    // declaration order cannot flip the verdict (observed: a 2-line
    // parameter rename flipped the frozen-lisbon-v3 verdict under
    // first-mention matching). Helper names bound to exactly one of the two
    // tools count as call sites for that tool; a helper touching both (a
    // whole collection loop) is ambiguous and votes for neither. A contract
    // that declares collection expectations requires at least one resolved
    // call site — a call-free script must not sail through the ordering
    // carve-out (observed: a comment-only stub passed every check).
    const readHelpers = collectHelperNames(scriptText, READ_STEM_RE);
    const waitHelpers = collectHelperNames(scriptText, WAIT_STEM_RE);
    const unambiguousRead = [...readHelpers].filter(
      (name) => !waitHelpers.has(name),
    );
    const unambiguousWait = [...waitHelpers].filter(
      (name) => !readHelpers.has(name),
    );
    const readCallRe = buildAwaitCallRe(READ_STEM_SOURCE, unambiguousRead);
    const waitCallRe = buildAwaitCallRe(WAIT_STEM_SOURCE, unambiguousWait);
    const firstRead = scriptText.search(readCallRe);
    const firstWait = scriptText.search(waitCallRe);
    const hasCallSites = firstRead !== -1 || firstWait !== -1;
    add(
      "collection:call-sites",
      hasCallSites,
      hasCallSites
        ? "await-adjacent tool or resolved helper call sites present"
        : "collection declared but no tool call sites",
    );
    if (collection.read_first) {
      let ok;
      let detail;
      if (firstWait === -1 && firstRead === -1) {
        ok = true;
        detail =
          "no resolved call sites; ordering not judged (call-site check governs)";
      } else if (firstWait === -1) {
        ok = true;
        detail = "read call present and no direct or resolved wait call";
      } else {
        ok = firstRead !== -1 && firstRead < firstWait;
        detail = ok
          ? "read call site precedes the first wait call site"
          : "first wait call site precedes any read call site (wait-only collection, #13)";
      }
      add("collection:read-first", ok, detail);
    }
    if (collection.read_after_wait) {
      let ok = true;
      let detail = "no wait call site; nothing to follow";
      if (firstWait !== -1) {
        ok = readCallRe.test(scriptText.slice(firstWait));
        detail = ok
          ? "read call site after the first wait"
          : "no read call site after the first wait (#13)";
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
    const mentions = /clientThreadId|client_thread_id/.test(scriptText);
    // The identifier alone is not resolution: the canonical #14 failure
    // stores and tests clientThreadId without ever resolving it. Require
    // evidence of a bounded resolution loop — a named attempts constant or a
    // task-list poll — in the same script.
    const resolves =
      /START_RESOLVE_ATTEMPTS|RESOLVE_ATTEMPTS|MAX_SETUP_POLLS|resolveBounds/.test(
        scriptText,
      ) || /list_?[Tt]hreads|list_?[Tt]asks/.test(scriptText);
    const ok = mentions && resolves;
    add(
      "setup:pending-resolution",
      ok,
      ok
        ? "pending clientThreadId handling with bounded resolution evidence"
        : mentions
          ? "clientThreadId mentioned but no resolution-loop evidence (bounded-attempts marker or task-list call) (#14)"
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
    // An empty contract must not green-light arbitrary input: at least one
    // check has to have run for an ok verdict.
    ok: checks.length > 0 && checks.every((check) => check.ok),
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
