"use strict";

const MAX_OUTPUT_CHARS_PER_ITEM = 20000;

function snapshotFingerprint(snapshot) {
  return JSON.stringify({
    items: snapshot.items ?? [],
    terminal: snapshot.terminal ?? null,
  });
}

function normalizeToolResult(raw) {
  if (typeof raw !== "string") return { value: raw, raw };
  try {
    return { value: JSON.parse(raw.trim()), raw };
  } catch {
    return { value: raw, raw };
  }
}

function aggregateStartFailure(message, settledStarts) {
  const handles = settledStarts
    .filter((entry) => entry.status === "rejected")
    .map((entry) => entry.reason && entry.reason.handle)
    .filter(Boolean);
  return Object.assign(new Error(message), { handles });
}

function canonicalUrlForComparison(url) {
  if (typeof url !== "string") return url;
  return url
    .replace(/&amp;/gi, "&")
    .replace(/&#0*38;/g, "&")
    .replace(/&#x0*26;/gi, "&")
    .trim();
}

function isValidTerminalHandoff(value, nodeId) {
  return (
    value &&
    typeof value === "object" &&
    value.node_id === nodeId &&
    ["passed", "blocked", "failed"].includes(value.status)
  );
}

async function collectTask({
  nodeId,
  threadId,
  waitThreads,
  maxCollectionRounds = 4,
  maxIdlePolls = 4,
  maxOutputCharsPerItem = MAX_OUTPUT_CHARS_PER_ITEM,
  delay = async () => {},
}) {
  if (maxOutputCharsPerItem > MAX_OUTPUT_CHARS_PER_ITEM) {
    throw new RangeError(
      `maxOutputCharsPerItem exceeds ${MAX_OUTPUT_CHARS_PER_ITEM}`,
    );
  }

  let afterCursor;
  let collectionRounds = 0;
  let idlePolls = 0;
  let previousFingerprint;
  let terminal;
  const collectedItems = [];
  const calls = [];

  while (
    collectionRounds < maxCollectionRounds &&
    idlePolls < maxIdlePolls &&
    !terminal
  ) {
    const request = {
      threadIds: [threadId],
      maxOutputCharsPerItem,
    };
    if (afterCursor !== undefined) request.afterCursor = afterCursor;
    calls.push(request);

    const snapshot = await waitThreads(request);
    const nextCursor = snapshot.afterCursor;
    const cursorAdvanced =
      nextCursor !== undefined && nextCursor !== afterCursor;
    const fingerprint = snapshotFingerprint(snapshot);
    const snapshotChanged =
      previousFingerprint === undefined || fingerprint !== previousFingerprint;
    const hasNewData = cursorAdvanced || snapshotChanged;

    if (hasNewData) {
      collectionRounds += 1;
      idlePolls = 0;
      if (Array.isArray(snapshot.items)) collectedItems.push(...snapshot.items);
    } else {
      idlePolls += 1;
      await delay();
    }

    previousFingerprint = fingerprint;
    if (nextCursor !== undefined) afterCursor = nextCursor;

    if (isValidTerminalHandoff(snapshot.terminal, nodeId)) {
      terminal = snapshot.terminal;
    }
  }

  return {
    status: terminal ? terminal.status : "blocked",
    terminal,
    collectedItems,
    afterCursor,
    calls,
    collectionRounds,
    idlePolls,
    terminalEmitted: terminal !== undefined,
  };
}

module.exports = {
  MAX_OUTPUT_CHARS_PER_ITEM,
  collectTask,
  isValidTerminalHandoff,
  normalizeToolResult,
  aggregateStartFailure,
  canonicalUrlForComparison,
};
