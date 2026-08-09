"use strict";

const MAX_OUTPUT_CHARS_PER_ITEM = 20000;

function snapshotFingerprint(snapshot) {
  return JSON.stringify({
    items: snapshot.items ?? [],
    terminal: snapshot.terminal ?? null,
    status: snapshot.status ?? null,
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

/**
 * Resolve a pending-setup handle from a task-list snapshot.
 * Matches the per-node unique form only: the bracketed exact run tag
 * `[<runTag>]` plus the node id in the same field, against the explicit key
 * list name/title/summary/preview (OSS rows carry name/preview, Desktop rows
 * have shown title/summary). Prefers name/title/summary over preview, never
 * matches an excluded (own/parent or already claimed) thread id, and never
 * falls back to a bare `id` key for matching.
 */
function findExactThread(value, projectId, runTag, nodeId, clientThreadId, excludeThreadIds = []) {
  const excluded = new Set([...excludeThreadIds].filter(Boolean).map(String));
  const taggedForm = `[${runTag}]`; // bracketed exact form only
  const text = (row, key) => (typeof row[key] === "string" ? row[key] : "");
  // Per-node unique form: the bracketed tag AND the node id in one field.
  const fieldHit = (s) => s.includes(taggedForm) && (!nodeId || s.includes(nodeId));
  const rowMatches = (row, allowPreview) => {
    const rowThreadId = row.threadId ?? row.thread_id ?? row.id ?? null;
    if (rowThreadId != null && excluded.has(String(rowThreadId))) return false;
    const listedClient = row.clientThreadId ?? row.client_thread_id ?? null;
    if (
      clientThreadId &&
      listedClient &&
      String(listedClient) === String(clientThreadId)
    ) {
      return true;
    }
    // Explicit key list: OSS rows carry name/preview, Desktop rows have
    // shown title/summary. Never add a bare `id` fallback here.
    const strongHit =
      fieldHit(text(row, "name")) ||
      fieldHit(text(row, "title")) ||
      fieldHit(text(row, "summary"));
    const previewHit = allowPreview && fieldHit(text(row, "preview"));
    if (!strongHit && !previewHit) return false;
    // Projectless handles have no projectId; match the unique run tag alone.
    // When a project is bound, prefer projectId match but do not require it
    // while setup is still loading (projectId may be absent on early rows).
    const projectRequired = projectId != null && projectId !== "";
    const listedProject = row.projectId ?? row.project_id;
    return !projectRequired || listedProject == null || listedProject === projectId;
  };
  const walk = (node, allowPreview) => {
    if (typeof node === "string") {
      try {
        return walk(JSON.parse(node), allowPreview);
      } catch {
        return null;
      }
    }
    if (!node || typeof node !== "object") return null;
    if (!Array.isArray(node) && rowMatches(node, allowPreview)) return node;
    for (const nested of Object.values(node)) {
      const found = walk(nested, allowPreview);
      if (found) return found;
    }
    return null;
  };
  // Pass 1 ignores preview everywhere; pass 2 admits preview-only hits.
  // A parent thread's preview can embed worker titles — preview is a
  // fallback key, never the preferred one.
  return walk(value, false) ?? walk(value, true);
}

/**
 * Gate worktree targets on the project lookup's isGitRepository flag.
 * openai/codex#28204: worktree provisioning on a non-git project root fails
 * silently — no thread row is written and the pending id is never listed.
 * Fails closed unless isGitRepository === true.
 */
function preflightWorktreeTarget({ environmentType, isGitRepository, singleWriter = false }) {
  if (environmentType !== "worktree" || isGitRepository === true) {
    return { action: "proceed" };
  }
  if (singleWriter) {
    return {
      action: "degrade_to_root_write",
      reason:
        "worktree requires a git repository; route the single repository write through the root orchestrator",
    };
  }
  return {
    action: "fail_closed",
    unresolved_risk:
      "worktree target requires isGitRepository === true " +
      "(openai/codex#28204: silent worktree-init failure — no thread row, never listed)",
  };
}

const HANDOFF_STATUSES = new Set([
  "passed",
  "complete",
  "blocked",
  "failed",
]);

function isValidTerminalHandoff(value, nodeId) {
  return (
    value &&
    typeof value === "object" &&
    value.node_id === nodeId &&
    HANDOFF_STATUSES.has(value.status)
  );
}

/** Recursively find a schema-valid handoff for nodeId in any nested structure. */
function findHandoffInValue(value, nodeId, seen = new Set()) {
  if (value == null) return null;
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (
      !(trimmed.startsWith("{") || trimmed.startsWith("[")) ||
      seen.has(trimmed)
    ) {
      return null;
    }
    seen.add(trimmed);
    try {
      return findHandoffInValue(JSON.parse(trimmed), nodeId, seen);
    } catch {
      return null;
    }
  }
  if (typeof value !== "object") return null;
  if (isValidTerminalHandoff(value, nodeId)) return value;
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = findHandoffInValue(item, nodeId, seen);
      if (found) return found;
    }
    return null;
  }
  for (const nested of Object.values(value)) {
    const found = findHandoffInValue(nested, nodeId, seen);
    if (found) return found;
  }
  return null;
}

function unwrapToolSnapshot(raw) {
  // resolveTool returns { value, raw }. Prefer the inner value; avoid treating
  // the envelope itself as the wait/read snapshot.
  if (
    raw &&
    typeof raw === "object" &&
    !Array.isArray(raw) &&
    Object.prototype.hasOwnProperty.call(raw, "value") &&
    Object.prototype.hasOwnProperty.call(raw, "raw")
  ) {
    return unwrapToolSnapshot(raw.value);
  }
  const normalized = normalizeToolResult(raw);
  return normalized.value;
}

async function collectTask({
  nodeId,
  threadId,
  waitThreads,
  readThread,
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
  let previousReadFingerprint;
  let terminal;
  const collectedItems = [];
  const seenItemKeys = new Set();
  const calls = [];
  const reads = [];

  async function ingestSnapshot(snapshot, source, options = {}) {
    if (!snapshot || typeof snapshot !== "object") return;
    const { collectItems = true } = options;
    const handoff =
      findHandoffInValue(snapshot.terminal, nodeId) ||
      findHandoffInValue(snapshot.items, nodeId) ||
      findHandoffInValue(snapshot.turns, nodeId) ||
      findHandoffInValue(snapshot, nodeId);
    if (handoff) terminal = handoff;
    if (collectItems && Array.isArray(snapshot.items)) {
      for (const item of snapshot.items) {
        let key;
        try {
          key = JSON.stringify(item);
        } catch {
          key = String(item);
        }
        if (seenItemKeys.has(key)) continue;
        seenItemKeys.add(key);
        collectedItems.push(item);
      }
    }
    if (source === "wait" || source === "read") {
      /* count handled by caller for budget */
    }
  }

  // Always read once before waiting: the worker may already be terminal.
  // Lab: Lisbon v3 workers completed in ~161s with valid handoffs; wait-only
  // collection saw idle polls for 30 minutes and never accepted them.
  if (typeof readThread === "function") {
    const readRequest = {
      threadId,
      maxOutputCharsPerItem,
      includeOutputs: true,
    };
    reads.push(readRequest);
    const rawRead = await readThread(readRequest);
    const readSnapshot = unwrapToolSnapshot(rawRead);
    await ingestSnapshot(readSnapshot, "read");
    previousReadFingerprint = snapshotFingerprint(readSnapshot || {});
    if (
      readSnapshot &&
      typeof readSnapshot === "object" &&
      readSnapshot.afterCursor !== undefined
    ) {
      afterCursor = readSnapshot.afterCursor;
    }
    if (terminal) {
      return {
        status: terminal.status === "complete" ? "passed" : terminal.status,
        terminal,
        collectedItems,
        afterCursor,
        calls,
        reads,
        collectionRounds,
        idlePolls,
        terminalEmitted: true,
      };
    }
  }

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

    const rawWait = await waitThreads(request);
    const snapshot = unwrapToolSnapshot(rawWait);
    const nextCursor = snapshot && snapshot.afterCursor;
    const cursorAdvanced =
      nextCursor !== undefined && nextCursor !== afterCursor;
    const fingerprint = snapshotFingerprint(snapshot || {});
    const snapshotChanged =
      previousFingerprint === undefined || fingerprint !== previousFingerprint;
    const hasNewData = cursorAdvanced || snapshotChanged;

    if (hasNewData) {
      collectionRounds += 1;
      idlePolls = 0;
      await ingestSnapshot(snapshot, "wait");
    } else {
      idlePolls += 1;
      await delay();
    }

    // Explicit read after every wait: wait snapshots may omit items when the
    // thread finished between polls; read_thread is the SoT for handoffs.
    let readCursor;
    if (typeof readThread === "function" && !terminal) {
      const readRequest = {
        threadId,
        maxOutputCharsPerItem,
        includeOutputs: true,
      };
      if (afterCursor !== undefined) readRequest.afterCursor = afterCursor;
      reads.push(readRequest);
      const rawRead = await readThread(readRequest);
      const readSnapshot = unwrapToolSnapshot(rawRead);
      readCursor =
        readSnapshot && typeof readSnapshot === "object"
          ? readSnapshot.afterCursor
          : undefined;
      const readFingerprint = snapshotFingerprint(readSnapshot || {});
      const collectItems =
        previousReadFingerprint === undefined ||
        readFingerprint !== previousReadFingerprint;
      const before = terminal;
      await ingestSnapshot(readSnapshot, "read", { collectItems });
      previousReadFingerprint = readFingerprint;
      if (!before && terminal) {
        // Found via read even if wait looked idle — not an idle burn.
        idlePolls = 0;
      }
    }

    previousFingerprint = fingerprint;
    // Prefer wait progress; only take read's cursor when it advances past the
    // request cursor. Read often echoes the request afterCursor when there is
    // no further page, which must not rewind a newer wait cursor.
    const requestCursor = request.afterCursor;
    if (nextCursor !== undefined) afterCursor = nextCursor;
    if (readCursor !== undefined && readCursor !== requestCursor) {
      afterCursor = readCursor;
    }
  }

  const status = terminal
    ? terminal.status === "complete"
      ? "passed"
      : terminal.status
    : "blocked";

  return {
    status,
    terminal,
    collectedItems,
    afterCursor,
    calls,
    reads,
    collectionRounds,
    idlePolls,
    terminalEmitted: terminal !== undefined,
  };
}

module.exports = {
  MAX_OUTPUT_CHARS_PER_ITEM,
  collectTask,
  isValidTerminalHandoff,
  findHandoffInValue,
  findExactThread,
  preflightWorktreeTarget,
  normalizeToolResult,
  aggregateStartFailure,
  canonicalUrlForComparison,
};
