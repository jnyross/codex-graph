#!/usr/bin/env node
"use strict";

// CLI: statically check a generated Code Mode workflow.js against one
// test case's machine contract.
//
//   node check_workflow.js --case <case-id> --script <path/to/workflow.js>
//
// Prints one JSON verdict {ok, case, checks:[{id, ok, detail}]} and exits
// non-zero when any check fails.

const fs = require("node:fs");
const { listCaseIds, loadCase, checkWorkflowText } = require("./expectations.js");

function parseArgs(argv) {
  const args = { case: undefined, script: undefined };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--case") args.case = argv[++i];
    else if (argv[i] === "--script") args.script = argv[++i];
    else {
      process.stderr.write(`unknown argument: ${argv[i]}\n`);
      process.exit(2);
    }
  }
  return args;
}

const args = parseArgs(process.argv.slice(2));
if (!args.case || !args.script) {
  process.stderr.write(
    `usage: check_workflow.js --case <id> --script <workflow.js>\n` +
      `cases: ${listCaseIds().join(", ")}\n`,
  );
  process.exit(2);
}

const testCase = loadCase(args.case);
const scriptText = fs.readFileSync(args.script, "utf8");
const verdict = checkWorkflowText(scriptText, testCase.expectations);
process.stdout.write(`${JSON.stringify(verdict, null, 2)}\n`);
process.exit(verdict.ok ? 0 : 1);
