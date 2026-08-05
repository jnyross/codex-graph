"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const {
  MAX_OUTPUT_CHARS_PER_ITEM,
  collectTask,
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
