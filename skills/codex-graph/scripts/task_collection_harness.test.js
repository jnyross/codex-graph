"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const {
  MAX_OUTPUT_CHARS_PER_ITEM,
  collectTask,
  normalizeToolResult,
  aggregateStartFailure,
  canonicalUrlForComparison,
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
