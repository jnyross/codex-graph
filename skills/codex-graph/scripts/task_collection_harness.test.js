"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const {
  MAX_OUTPUT_CHARS_PER_ITEM,
  collectTask,
  normalizeToolResult,
  aggregateStartFailure,
  canonicalUrlForComparison,
  findHandoffInValue,
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
// Shapes derived from real Grok/Claude orchestration patterns; see
// docs/dynamic-workflow-testcase-catalog.md and testcases/.

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