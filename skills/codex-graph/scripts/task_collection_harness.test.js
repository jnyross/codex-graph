"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const {
  MAX_OUTPUT_CHARS_PER_ITEM,
  FORENSIC_RESULT_CAP,
  collectTask,
  normalizeToolResult,
  aggregateStartFailure,
  canonicalUrlForComparison,
  findHandoffInValue,
  findExactThread,
  preflightWorktreeTarget,
} = require("./task_collection_harness.js");

function sequenceWaiter(snapshots) {
  let index = 0;
  return async (request) => {
    const snapshot = snapshots[Math.min(index++, snapshots.length - 1)];
    assert.equal(request.maxOutputCharsPerItem, MAX_OUTPUT_CHARS_PER_ITEM);
    return snapshot;
  };
}

test("rejects a read budget above the active tool limit", async () => {
  await assert.rejects(
    collectTask({
      nodeId: "W1",
      threadId: "thread-1",
      waitThreads: async () => ({ items: [] }),
      maxOutputCharsPerItem: 100000,
    }),
    /exceeds 20000/,
  );
});

test("forwards an advancing cursor instead of rereading the same page", async () => {
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    waitThreads: sequenceWaiter([
      { afterCursor: "c1", items: [{ id: 1 }] },
      {
        afterCursor: "c2",
        items: [{ id: 2 }],
        terminal: { node_id: "W1", status: "passed" },
      },
    ]),
  });

  assert.deepEqual(result.calls.map(({ afterCursor }) => afterCursor), [
    undefined,
    "c1",
  ]);
  assert.deepEqual(result.collectedItems, [{ id: 1 }, { id: 2 }]);
  assert.equal(result.status, "passed");
  assert.equal(result.terminalEmitted, true);
});

test("does not duplicate identical cursorless snapshots", async () => {
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    maxCollectionRounds: 3,
    maxIdlePolls: 2,
    waitThreads: sequenceWaiter([
      { items: [{ id: 1 }] },
      { items: [{ id: 1 }] },
      { items: [{ id: 1 }] },
      { items: [], terminal: { node_id: "W1", status: "blocked" } },
    ]),
  });

  assert.deepEqual(result.collectedItems, [{ id: 1 }]);
  assert.equal(result.status, "blocked");
});

test("stops a stalled worker with a bounded blocked result", async () => {
  let calls = 0;
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    maxIdlePolls: 3,
    waitThreads: async () => {
      calls += 1;
      return { items: [] };
    },
  });

  assert.equal(result.status, "blocked");
  assert.equal(result.terminalEmitted, false);
  assert.equal(calls, 4);
  assert.equal(result.idlePolls, 3);
});

test("keeps collecting through unchanged polls until delayed completion", async () => {
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    maxCollectionRounds: 2,
    maxIdlePolls: 4,
    waitThreads: sequenceWaiter([
      { items: [] },
      { items: [] },
      {
        items: [{ claim: "five laws" }],
        terminal: { node_id: "W1", status: "passed" },
      },
    ]),
  });

  assert.deepEqual(result.collectedItems, [{ claim: "five laws" }]);
  assert.equal(result.status, "passed");
});

test("ignores malformed terminal handoffs and returns blocked", async () => {
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    maxIdlePolls: 1,
    waitThreads: sequenceWaiter([
      { items: [], terminal: { node_id: "W2", status: "passed" } },
      { items: [], terminal: { node_id: "W1", status: "unknown" } },
    ]),
  });

  assert.equal(result.status, "blocked");
  assert.equal(result.terminal, undefined);
});

test("parses a JSON-string tool result exactly once and keeps the raw payload", () => {
  const raw = JSON.stringify({
    threadId: "019fe5b3-09bd-7020-a3a6-500d2969dce9",
    projectlessOutputDirectory: "/tmp/diag/outputs",
    hostId: "local",
  });

  const normalized = normalizeToolResult(raw);

  assert.equal(normalized.value.threadId, "019fe5b3-09bd-7020-a3a6-500d2969dce9");
  assert.equal(normalized.value.hostId, "local");
  assert.equal(normalized.raw, raw);

  const passthrough = normalizeToolResult({ threadId: "t-1" });
  assert.deepEqual(passthrough.value, { threadId: "t-1" });
});

test("does not extract JSON fragments from a non-JSON string tool result", () => {
  const mixed = 'prefix {"threadId":"t-9"} suffix';

  const normalized = normalizeToolResult(mixed);

  assert.equal(normalized.value, mixed);
  assert.equal(normalized.raw, mixed);
});

test("preserves every rejected start handle on aggregate failure", () => {
  const settled = [
    { status: "fulfilled", value: { node_id: "D1" } },
    {
      status: "rejected",
      reason: Object.assign(new Error("no ready threadId"), {
        handle: { node_id: "D2", state: "pending_setup" },
      }),
    },
    {
      status: "rejected",
      reason: Object.assign(new Error("no ready threadId"), {
        handle: { node_id: "D3", state: "pending_setup" },
      }),
    },
    { status: "rejected", reason: new Error("handleless rejection") },
  ];

  const error = aggregateStartFailure("Required feed workers failed to start", settled);

  assert.match(error.message, /failed to start/);
  assert.deepEqual(
    error.handles.map((handle) => handle.node_id),
    ["D2", "D3"],
  );
});

test("normalizes HTML entities before URL comparison", () => {
  const escaped = "https://example.org/story?a=1&amp;b=2";
  const decimal = "https://example.org/story?a=1&#38;b=2";
  const hex = "https://example.org/story?a=1&#x26;b=2";
  const plain = "https://example.org/story?a=1&b=2";

  assert.equal(canonicalUrlForComparison(escaped), plain);
  assert.equal(canonicalUrlForComparison(decimal), plain);
  assert.equal(canonicalUrlForComparison(hex), plain);
  assert.equal(canonicalUrlForComparison(plain), plain);
  assert.equal(canonicalUrlForComparison(null), null);
});


test("findHandoffInValue digs nested turns/items and string JSON", () => {
  const handoff = {
    node_id: "N2A",
    status: "complete",
    candidates: [{ id: "a" }],
  };
  const nested = {
    turns: [
      {
        items: [
          { type: "text", text: "noise" },
          { type: "output", content: JSON.stringify(handoff) },
        ],
      },
    ],
  };
  assert.deepEqual(findHandoffInValue(nested, "N2A").node_id, "N2A");
  assert.equal(findHandoffInValue(nested, "N2A").status, "complete");
});

test("collects handoff when thread is already complete on first read", async () => {
  const handoff = {
    node_id: "N2A",
    status: "complete",
    candidates: [{ id: "N2A-01", name: "Park" }],
  };
  let waits = 0;
  const result = await collectTask({
    nodeId: "N2A",
    threadId: "thread-done",
    waitThreads: async () => {
      waits += 1;
      return { items: [] };
    },
    readThread: async () => ({
      status: "idle",
      turns: [{ items: [{ type: "message", text: JSON.stringify(handoff) }] }],
    }),
  });
  assert.equal(waits, 0, "must not wait when first read already has handoff");
  assert.equal(result.terminalEmitted, true);
  assert.equal(result.status, "passed");
  assert.equal(result.terminal.node_id, "N2A");
  assert.equal(result.terminal.candidates.length, 1);
});

test("finds handoff via post-wait read when wait snapshot stays empty", async () => {
  const handoff = {
    node_id: "W1",
    status: "complete",
    candidates: [],
  };
  let reads = 0;
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    maxCollectionRounds: 3,
    maxIdlePolls: 3,
    waitThreads: async () => ({ items: [], terminal: null }),
    readThread: async () => {
      reads += 1;
      if (reads < 2) return { items: [] };
      return {
        turns: [{ items: [{ content: handoff }] }],
      };
    },
  });
  assert.equal(result.terminalEmitted, true);
  assert.equal(result.terminal.status, "complete");
  assert.ok(reads >= 2);
});

test("unwraps resolveTool envelopes from wait and read", async () => {
  const handoff = { node_id: "W1", status: "complete", candidates: [] };
  const result = await collectTask({
    nodeId: "W1",
    threadId: "t1",
    waitThreads: async () => ({ value: { items: [] }, raw: "{}" }),
    readThread: async () => ({
      value: { turns: [{ items: [{ content: handoff }] }] },
      raw: "{}",
    }),
  });
  assert.equal(result.terminalEmitted, true);
  assert.equal(result.terminal.node_id, "W1");
});


// ── Dynamic-workflow pattern fixtures ───────────────────────────────────────
// Shapes derived from the same orchestration patterns as testcases/.

test("atomic screen fan-out: verdicts terminal at first read need no waits (#13)", async () => {
  // Grok screen phase: one atomic screener per candidate; workers finish fast
  // and the verdict is nested as string JSON inside turns/items (Lisbon v3).
  const candidates = ["S1", "S2", "S3", "S4", "S5"];
  const results = await Promise.all(
    candidates.map((nodeId) =>
      collectTask({
        nodeId,
        threadId: `screen-${nodeId}`,
        readThread: async () => ({
          turns: [
            {
              items: [
                {
                  type: "text",
                  text: JSON.stringify({
                    node_id: nodeId,
                    status: "complete",
                    verdict: nodeId === "S3" ? "KILL" : "PASS",
                    reason: "hard gate check",
                    gate_failed: nodeId === "S3" ? "heat" : "",
                  }),
                },
              ],
            },
          ],
        }),
        waitThreads: async () => {
          throw new Error("wait must not run when read already has the handoff");
        },
      }),
    ),
  );
  for (const result of results) {
    assert.equal(result.status, "passed");
    assert.deepEqual(result.calls, []);
  }
  assert.deepEqual(
    results.map((result) => result.terminal.verdict),
    ["PASS", "PASS", "KILL", "PASS", "PASS"],
  );
});

test("screen-then-POV: second-stage fan-out follows first-stage verdicts", async () => {
  // Funnel shape: atomic screeners decide the pool; sealed deep-research
  // workers exist only for survivors. A blocked screener is distinguishable
  // from a KILL verdict so the root can apply its own fail-open policy.
  const pool = ["alpha", "beta", "gamma", "delta"];
  const killed = new Set(["beta"]);
  const stalled = new Set(["delta"]);
  const screens = await Promise.all(
    pool.map((name, index) =>
      collectTask({
        nodeId: `S${index + 1}`,
        threadId: `screen-${name}`,
        maxIdlePolls: 1,
        readThread: async () => ({ items: [] }),
        waitThreads: async () =>
          stalled.has(name)
            ? { items: [] }
            : {
                items: [],
                terminal: {
                  node_id: `S${index + 1}`,
                  status: "complete",
                  name,
                  verdict: killed.has(name) ? "KILL" : "PASS",
                },
              },
      }),
    ),
  );

  const survivors = [];
  const killLog = [];
  screens.forEach((result, index) => {
    const name = pool[index];
    if (result.status === "passed" && result.terminal.verdict === "PASS") {
      survivors.push(name);
    } else if (result.status === "passed") {
      killLog.push({ name, reason: "gate failed", stage: "screen" });
    } else {
      // Root-owned fail-open policy: a broken screener keeps the candidate.
      assert.equal(result.status, "blocked");
      assert.equal(result.terminalEmitted, false);
      survivors.push(name);
      killLog.push({ name, reason: "screener blocked; failed open", stage: "screen" });
    }
  });
  assert.deepEqual(survivors, ["alpha", "gamma", "delta"]);
  assert.equal(killLog.length, 2);

  const povs = await Promise.all(
    survivors.map((name, index) =>
      collectTask({
        nodeId: `P${index + 1}`,
        threadId: `pov-${name}`,
        readThread: async () => ({
          terminal: {
            node_id: `P${index + 1}`,
            status: "complete",
            destination: name,
            load_bearing_claims: ["c1", "c2", "c3"],
          },
        }),
        waitThreads: async () => ({ items: [] }),
      }),
    ),
  );
  assert.equal(povs.length, survivors.length);
  assert.ok(povs.every((result) => result.status === "passed"));
  assert.ok(!povs.some((result) => result.terminal.destination === "beta"));
});

test("adversarial dual validators: malformed lane fails closed at the join", async () => {
  // Blind dual-validator panel: one lane returns a valid verdict, the other
  // returns wrong-node and malformed-status handoffs. The malformed lane must
  // end blocked, and the join must not count it as confirmation.
  const lanes = await Promise.all([
    collectTask({
      nodeId: "V1A",
      threadId: "lane-a",
      readThread: async () => ({
        terminal: {
          node_id: "V1A",
          status: "complete",
          pass: true,
          evidence: "independently reproduced every claim",
        },
      }),
      waitThreads: async () => ({ items: [] }),
    }),
    collectTask({
      nodeId: "V1B",
      threadId: "lane-b",
      maxIdlePolls: 1,
      readThread: async () => ({ items: [] }),
      waitThreads: sequenceWaiter([
        { items: [], terminal: { node_id: "OTHER", status: "complete" } },
        { items: [], terminal: { node_id: "V1B", status: "approved-ish" } },
      ]),
    }),
  ]);

  assert.equal(lanes[0].status, "passed");
  assert.equal(lanes[1].status, "blocked");
  assert.equal(lanes[1].terminal, undefined);
  const confirmed = lanes.every(
    (lane) => lane.status === "passed" && lane.terminal?.pass === true,
  );
  assert.equal(confirmed, false);
});

test("resolves a ready thread listed under OSS name/preview keys", () => {
  const runTag = "lisbon-family-1786287437517-N2A";
  const snapshot = {
    threads: [
      { id: "t-other", name: "[other-tag-N9Z] unrelated", preview: "noise" },
      {
        id: "t-worker",
        name: `[${runTag}] Research transport`,
        preview: "You are node N2A.",
        cwd: "/repo",
        status: "ready",
      },
    ],
  };
  const record = findExactThread(snapshot, "proj-1", runTag, "N2A", null);
  assert.equal(record.id, "t-worker");
});

test("still correlates a pending handle by clientThreadId", () => {
  const snapshot = {
    threads: [{ id: "t-9", clientThreadId: "client-new-thread:abc" }],
  };
  const record = findExactThread(
    snapshot,
    "proj-1",
    "tag-N1",
    "N1",
    "client-new-thread:abc",
  );
  assert.equal(record.id, "t-9");
});

test("resolves via preview only as a second-pass fallback", () => {
  const runTag = "lisbon-family-1786287437517-N2B";
  const snapshot = {
    threads: [
      { id: "t-worker", preview: `[${runTag}] Research beaches`, status: "ready" },
    ],
  };
  const record = findExactThread(snapshot, null, runTag, "N2B", null);
  assert.equal(record.id, "t-worker");
});

test("requires the bracketed exact run-tag form", () => {
  const runTag = "lisbon-family-1786287437517-N2D";
  const snapshot = {
    threads: [{ id: "t-1", title: `retry ${runTag} later`, status: "ready" }],
  };
  assert.equal(findExactThread(snapshot, null, runTag, "N2D", null), null);
});

test("rejects a run-tag hit that only lives in the parent thread preview", () => {
  const runTag = "lisbon-family-1786287437517-N2C";
  const parentRow = {
    id: "t-parent",
    name: "Orchestrate Lisbon graph",
    preview: `Start worker [${runTag}] Research food now`,
  };
  const workerRow = { id: "t-worker", name: `[${runTag}] Research food` };
  const record = findExactThread(
    { threads: [parentRow, workerRow] },
    null,
    runTag,
    "N2C",
    null,
    ["t-parent"],
  );
  assert.equal(record.id, "t-worker");
  assert.equal(
    findExactThread({ threads: [parentRow] }, null, runTag, "N2C", null, [
      "t-parent",
    ]),
    null,
  );
});

test("two concurrent pending workers resolve to their own threads", () => {
  const sharedTag = "lisbon-v5-1786290000000";
  const snapshot = {
    threads: [
      { id: "t-b", name: `[${sharedTag}] N2B beaches` },
      { id: "t-a", name: `[${sharedTag}] N2A transport` },
    ],
  };
  const claimed = new Set();
  const recordA = findExactThread(snapshot, null, sharedTag, "N2A", null, claimed);
  assert.equal(recordA.id, "t-a", "shared-tag hit must not cross-bind to N2B's thread");
  claimed.add(recordA.id);
  const recordB = findExactThread(snapshot, null, sharedTag, "N2B", null, claimed);
  assert.equal(recordB.id, "t-b");
  claimed.add(recordB.id);
  // A claimed thread id is never resolved twice.
  assert.equal(findExactThread(snapshot, null, sharedTag, "N2A", null, claimed), null);
});

test("node id match requires a token boundary (N1 vs N10, N2 vs N2A)", () => {
  const sharedTag = "lisbon-v5-1786290000001";
  const snapshot = {
    threads: [
      { id: "t-10", name: `[${sharedTag}] N10 transport` },
      { id: "t-2a", name: `[${sharedTag}] N2A beaches` },
      { id: "t-1", name: `[${sharedTag}] N1 scope` },
      { id: "t-2", name: `[${sharedTag}] N2 inventory` },
    ],
  };
  assert.equal(findExactThread(snapshot, null, sharedTag, "N1", null).id, "t-1");
  assert.equal(findExactThread(snapshot, null, sharedTag, "N10", null).id, "t-10");
  assert.equal(findExactThread(snapshot, null, sharedTag, "N2", null).id, "t-2");
  assert.equal(findExactThread(snapshot, null, sharedTag, "N2A", null).id, "t-2a");
});

test("worktree preflight degrades a git-less single writer to a root write", () => {
  const decision = preflightWorktreeTarget({
    environmentType: "worktree",
    isGitRepository: false,
    singleWriter: true,
  });
  assert.equal(decision.action, "degrade_to_root_write");
});

test("worktree preflight fails closed with a named unresolved risk", () => {
  const decision = preflightWorktreeTarget({
    environmentType: "worktree",
    isGitRepository: undefined,
  });
  assert.equal(decision.action, "fail_closed");
  assert.match(decision.unresolved_risk, /isGitRepository === true/);
  assert.match(decision.unresolved_risk, /28204/);
});

test("worktree preflight passes git repositories and local targets", () => {
  assert.equal(
    preflightWorktreeTarget({ environmentType: "worktree", isGitRepository: true })
      .action,
    "proceed",
  );
  assert.equal(
    preflightWorktreeTarget({ environmentType: "local", isGitRepository: false })
      .action,
    "proceed",
  );
});

test("repair recollect rejects the stale pre-repair handoff and accepts the post-repair handoff", async () => {
  const stale = {
    node_id: "W1",
    status: "complete",
    candidates: [{ id: "pre-repair" }],
  };
  const freshCorrected = {
    node_id: "W1",
    status: "passed",
    candidates: [{ id: "post-repair" }],
    corrected_at: "2026-08-09T10:00:00Z",
  };
  let reads = 0;
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    repairMarker: "corrected_at",
    maxCollectionRounds: 3,
    maxIdlePolls: 3,
    waitThreads: async () => ({ turns: [stale, freshCorrected] }),
    readThread: async () => {
      reads += 1;
      return { turns: [{ items: [{ content: stale }] }] };
    },
  });
  assert.equal(reads, 1, "stale first read must not terminate collection");
  assert.equal(result.status, "passed");
  assert.deepEqual(result.terminal, freshCorrected);
  assert.notDeepEqual(result.terminal, stale);
  assert.equal(result.invalidSightings.length, 1);
  assert.match(
    result.invalidSightings[0].errors[0],
    /missing post-repair marker "corrected_at"/,
  );
});

test("finds the marker-carrying corrected handoff in a clipped turn window", async () => {
  // Scenario B: the read tool clipped a 13-turn history to the last 2 turns.
  // Any absolute turn index recorded before the repair send is meaningless
  // against this window; marker correlation must still find the handoff.
  const corrected = {
    node_id: "W1",
    status: "complete",
    candidates: [{ id: "fixed" }],
    corrected_at: "2026-08-09T21:30:00Z",
  };
  const clippedWindow = {
    turns: [
      { items: [{ content: "acknowledging repair request" }] },
      { items: [{ content: corrected }] },
    ],
  };
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    repairMarker: "corrected_at",
    waitThreads: async () => ({}),
    readThread: async () => clippedWindow,
  });
  assert.equal(result.status, "passed");
  assert.deepEqual(result.terminal, corrected);
});

test("repair mode keeps fallback surfaces and filters by marker, not position", async () => {
  const stale = {
    node_id: "W1",
    status: "complete",
    candidates: [{ id: "pre-repair" }],
  };
  const corrected = {
    node_id: "W1",
    status: "complete",
    candidates: [{ id: "post-repair" }],
    corrected_at: "2026-08-09T21:31:00Z",
  };
  // Stale handoff sits on the first-searched surface (terminal); the
  // corrected one is only reachable through the items fallback. Repair mode
  // must skip the stale sighting and continue across surfaces.
  const snapshot = { terminal: stale, items: [corrected] };
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    repairMarker: "corrected_at",
    waitThreads: async () => ({}),
    readThread: async () => snapshot,
  });
  assert.equal(result.status, "passed");
  assert.deepEqual(result.terminal, corrected);
  assert.equal(result.invalidSightings.length, 1);
  assert.match(
    result.invalidSightings[0].errors[0],
    /missing post-repair marker/,
  );
});

test("skips a structurally invalid complete sighting and collects a later valid handoff", async () => {
  const invalidHandoff = {
    node_id: "W1",
    status: "complete",
    candidates: [{ id: "broken" }],
  };
  const validHandoff = {
    node_id: "W1",
    status: "complete",
    candidates: [{ id: "ok" }],
  };
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    maxCollectionRounds: 3,
    maxIdlePolls: 3,
    waitThreads: sequenceWaiter([
      { turns: [invalidHandoff], afterCursor: 1 },
      { turns: [validHandoff], afterCursor: 2 },
    ]),
    validateHandoff: (handoff) =>
      handoff === invalidHandoff ? ["missing field"] : [],
  });
  assert.equal(result.status, "passed");
  assert.deepEqual(result.terminal, validHandoff);
  assert.equal(result.invalidSightings.length, 1);
  assert.deepEqual(result.invalidSightings[0].errors, ["missing field"]);
  assert.deepEqual(result.invalidSightings[0].handoff, invalidHandoff);
});

test("skips an invalid complete sighting and accepts a later valid handoff in the same snapshot", async () => {
  const invalidHandoff = {
    node_id: "W1",
    status: "complete",
    candidates: [{ id: "broken" }],
  };
  const validHandoff = {
    node_id: "W1",
    status: "complete",
    candidates: [{ id: "ok" }],
  };
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    maxCollectionRounds: 2,
    maxIdlePolls: 2,
    waitThreads: async () => ({
      turns: [invalidHandoff, validHandoff],
      afterCursor: 1,
    }),
    validateHandoff: (handoff) =>
      handoff === invalidHandoff ? ["missing field"] : [],
  });
  assert.equal(result.status, "passed");
  assert.deepEqual(result.terminal, validHandoff);
  assert.equal(result.invalidSightings.length, 1);
  assert.deepEqual(result.invalidSightings[0].handoff, invalidHandoff);
});

test("accepts an explicit failed worker handoff even when schema validation would reject it", async () => {
  const failedHandoff = {
    node_id: "W1",
    status: "failed",
    candidates: [],
  };
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    waitThreads: async () => ({ turns: [failedHandoff] }),
    validateHandoff: () => ["missing field"],
  });
  assert.equal(result.status, "failed");
  assert.deepEqual(result.terminal, failedHandoff);
  assert.equal(result.terminalEmitted, true);
  assert.deepEqual(result.invalidSightings, []);
});

// ── Collection read bounds + error-envelope fail-fast (Lisbon v5/v3) ────────
// ChatGPT Desktop rejects read_thread turnLimit > 10 (openai/codex#30058).
// The rejection is a BARE STRING tool result, not an error object. Lisbon v5
// generated turnLimit:20, treated the string as "no handoff yet", and burned
// three 35-minute collection windows while three complete 18KB handoffs sat
// unread (v3 blocked the same way). Forensic replays live in the lab repo:
// results/v5-pull/forensic-read-n2a-limit20.json and -limit100.json.

const DESKTOP_TURN_LIMIT_REJECTION =
  "read_thread received invalid arguments: turnLimit: Too big: expected number to be <=10.";

test("rejects a turn window above the Desktop cap", async () => {
  await assert.rejects(
    collectTask({
      nodeId: "W1",
      threadId: "thread-1",
      waitThreads: async () => ({ items: [] }),
      turnLimit: 20,
    }),
    /turnLimit exceeds 10/,
  );
});

test("bare-string read rejection aborts with a named blocker instead of burning the window", async () => {
  let waits = 0;
  const result = await collectTask({
    nodeId: "N2A",
    threadId: "thread-n2a",
    maxCollectionRounds: 8,
    maxIdlePolls: 8,
    waitThreads: async () => {
      waits += 1;
      return { afterCursor: `c${waits}`, items: [{ id: waits }] };
    },
    readThread: async () => DESKTOP_TURN_LIMIT_REJECTION,
  });

  assert.equal(result.status, "blocked");
  assert.equal(result.terminalEmitted, false);
  assert.match(result.blocker, /aborted after 3 consecutive tool errors/);
  assert.ok(
    result.blocker.includes(DESKTOP_TURN_LIMIT_REJECTION),
    "blocker embeds the verbatim tool error",
  );
  assert.equal(result.reads.length, 3, "bounded allowance: initial read + two loop reads");
  assert.equal(result.calls.length, 2, "window is not burned to exhaustion");
  assert.ok(
    result.lastReadResult.includes("turnLimit: Too big"),
    "forensic floor keeps the last raw read",
  );
});

test("error-envelope object reads do not count as snapshots", async () => {
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    maxCollectionRounds: 6,
    maxIdlePolls: 6,
    waitThreads: async () => ({ items: [] }),
    readThread: async () => ({
      isError: true,
      message: "read_thread failed: transient backend error",
    }),
  });

  assert.equal(result.status, "blocked");
  assert.match(result.blocker, /consecutive tool errors/);
  assert.match(result.blocker, /transient backend error/);
});

test("a transient read error clears when a clean read follows within the allowance", async () => {
  const handoff = { node_id: "W1", status: "complete", candidates: [] };
  let reads = 0;
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    maxCollectionRounds: 6,
    maxIdlePolls: 6,
    waitThreads: sequenceWaiter([
      { afterCursor: "c1", items: [] },
      { afterCursor: "c2", items: [] },
      { afterCursor: "c3", items: [] },
    ]),
    readThread: async () => {
      reads += 1;
      if (reads <= 2) return DESKTOP_TURN_LIMIT_REJECTION;
      return { turns: [{ items: [{ content: handoff }] }] };
    },
  });

  assert.equal(result.status, "passed");
  assert.equal(result.terminal.node_id, "W1");
  assert.equal(result.blocker, undefined);
});

test("handoff is on the newest page of a LAST-N windowed read (no pagination needed)", async () => {
  // codex-rs thread/turns/list returns the NEWEST turns first
  // (SortDirection::Desc, reverse + truncate in thread_processor.rs; its
  // tests assert limit 2 descending returns ["third", "second"]). A worker's
  // final handoff is therefore on page 0 of a fresh bounded read even when
  // the thread history is deeper than the window.
  const handoff = {
    node_id: "N2A",
    status: "complete",
    candidates: [{ id: "N2A-01" }],
  };
  const fullHistory = Array.from({ length: 32 }, (_, i) => ({
    items: [{ type: "message", text: `turn ${i + 1}` }],
  }));
  fullHistory.push({
    items: [{ type: "message", text: JSON.stringify(handoff) }],
  });
  const newestFirstWindow = fullHistory.slice(-10).reverse();
  const result = await collectTask({
    nodeId: "N2A",
    threadId: "thread-n2a",
    turnLimit: 10,
    waitThreads: async () => {
      throw new Error("wait must not run when the newest page already has the handoff");
    },
    readThread: async (request) => {
      assert.ok(request.turnLimit <= 10, "read request stays within the Desktop cap");
      return { turns: newestFirstWindow };
    },
  });

  assert.equal(result.status, "passed");
  assert.equal(result.terminal.node_id, "N2A");
  assert.equal(result.reads.length, 1, "newest page suffices; no cursor paging");
  assert.deepEqual(result.calls, []);
  assert.equal(result.reads[0].turnLimit, 10);
});

test("window expiry embeds the last raw read result (forensic floor)", async () => {
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    maxIdlePolls: 2,
    waitThreads: async () => ({ items: [] }),
    readThread: async () => ({ items: [], status: "active" }),
  });

  assert.equal(result.status, "blocked");
  assert.equal(result.terminalEmitted, false);
  assert.match(result.blocker, /collection window expired without terminal JSON/);
  assert.ok(
    result.lastReadResult.includes('"status":"active"'),
    "blocked terminal keeps the last raw read",
  );
});

test("forensic floor truncates the raw read to the named cap", async () => {
  const oversized = "x".repeat(FORENSIC_RESULT_CAP * 3);
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    maxCollectionRounds: 6,
    maxIdlePolls: 6,
    waitThreads: async () => ({ items: [] }),
    readThread: async () => oversized, // bare string: also a tool error
  });

  assert.equal(result.status, "blocked");
  assert.match(result.blocker, /consecutive tool errors/);
  assert.ok(result.lastReadResult.length < oversized.length);
  assert.ok(result.lastReadResult.startsWith("x".repeat(64)));
  assert.match(result.lastReadResult, /truncated \d+ chars/);
});

test("skill docs bound the turn window and carry the clipped-window anchor", () => {
  const root = path.join(__dirname, "..");
  const anchor = "a clipped window is not proof of absence";
  const surfaces = [
    path.join(root, "SKILL.md"),
    path.join(root, "references", "task-lifecycle.md"),
    path.join(root, "references", "code-mode-script-patterns.md"),
  ];
  for (const file of surfaces) {
    const text = fs.readFileSync(file, "utf8");
    assert.ok(
      text.includes(anchor),
      `${path.basename(file)} is missing the anchor phrase`,
    );
  }
  // No sample anywhere in the skill bundle may request more than 10 turns.
  const markdownFiles = [
    path.join(root, "SKILL.md"),
    ...fs
      .readdirSync(path.join(root, "references"))
      .filter((name) => name.endsWith(".md"))
      .map((name) => path.join(root, "references", name)),
  ];
  for (const file of markdownFiles) {
    const text = fs.readFileSync(file, "utf8");
    for (const match of text.matchAll(/turnLimit\s*[:=]\s*(\d+)/g)) {
      assert.ok(
        Number(match[1]) <= 10,
        `${path.basename(file)} requests turnLimit ${match[1]} > 10`,
      );
    }
  }
});

test("a blocked abort carries blocker, lastReadResult, and invalidSightings together (#18 composition)", async () => {
  // Union invariant: #18's blocked path reports invalidSightings; #21's
  // reports blocker + lastReadResult. One blocked exit must carry all three.
  const stale = { node_id: "W1", status: "complete", candidates: [] };
  let waits = 0;
  let reads = 0;
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    maxCollectionRounds: 8,
    maxIdlePolls: 8,
    validateHandoff: () => ["fewer than 5 candidates"],
    waitThreads: async () => {
      waits += 1;
      return { afterCursor: `c${waits}`, items: [] };
    },
    readThread: async () => {
      reads += 1;
      if (reads === 1) {
        return { turns: [{ items: [{ content: stale }] }] };
      }
      return DESKTOP_TURN_LIMIT_REJECTION;
    },
  });

  assert.equal(result.status, "blocked");
  assert.equal(result.terminalEmitted, false);
  assert.match(result.blocker, /aborted after 3 consecutive tool errors/);
  assert.ok(result.lastReadResult.includes("turnLimit: Too big"));
  assert.equal(result.invalidSightings.length, 1);
  assert.deepEqual(result.invalidSightings[0].errors, [
    "fewer than 5 candidates",
  ]);
});

test("a non-fatal error field beside real turns is a snapshot, not a tool error", async () => {
  // Prefer the payload: {error, turns:[…handoff…]} must be collected, not
  // classified as a tool error and discarded (PR #21 review finding 1).
  const handoff = { node_id: "W1", status: "complete", candidates: [] };
  const result = await collectTask({
    nodeId: "W1",
    threadId: "thread-1",
    waitThreads: async () => ({ items: [] }),
    readThread: async () => ({
      error: "one turn failed to render",
      turns: [{ items: [{ content: handoff }] }],
    }),
  });

  assert.equal(result.status, "passed");
  assert.equal(result.terminal.node_id, "W1");
  assert.equal(result.blocker, undefined);
});
