#!/usr/bin/env node
"use strict";

// Offline structural conformance CLI.
//
// node check_workflow.js --case <id> --metadata <metadata.json>
//   --graph <graph.mmd> --script <workflow.js>

const fs = require("node:fs");
const { parseArgs } = require("node:util");
const { checkConformance, listCaseIds } = require("./conformance.js");


try {
  const { values: args } = parseArgs({
    args: process.argv.slice(2),
    options: {
      case: { type: "string" },
      metadata: { type: "string" },
      graph: { type: "string" },
      script: { type: "string" },
    },
    strict: true,
  });
  if (!args.case || !args.metadata || !args.graph || !args.script) {
    throw new Error(
      `usage: check_workflow.js --case <id> --metadata <metadata.json> ` +
        `--graph <graph.mmd> --script <workflow.js>\n` +
        `cases: ${listCaseIds().join(", ")}`,
    );
  }
  const verdict = checkConformance({
    case_id: args.case,
    artifacts: {
      metadata: JSON.parse(fs.readFileSync(args.metadata, "utf8")),
      graph: fs.readFileSync(args.graph, "utf8"),
      executable: fs.readFileSync(args.script, "utf8"),
    },
  });
  process.stdout.write(`${JSON.stringify(verdict, null, 2)}\n`);
  process.exitCode = verdict.ok ? 0 : 1;
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 2;
}
