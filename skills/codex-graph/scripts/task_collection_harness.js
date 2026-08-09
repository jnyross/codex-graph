"use strict";

const MAX_OUTPUT_CHARS_PER_ITEM = 20000;
// ChatGPT Desktop rejects read_thread turnLimit above 10 (openai/codex#30058).
const MAX_TURN_LIMIT = 10;
// Consecutive errored wait/read results allowed per handle before collection
// aborts with a named blocker (a clean read resets the count).
const MAX_CONSECUTIVE_TOOL_ERRORS = 3;
// Cap for the last raw read result embedded in a blocked terminal.
const FORENSIC_RESULT_CAP = 2000;

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
  // Token-boundary match so N1 does not substring-hit N10 / N2A.
  const nodeToken = nodeId
    ? new RegExp(`\\b${String(nodeId).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`)
    : null;
  const fieldHit = (s) => s.includes(taggedForm) && (!nodeToken || nodeToken.test(s));
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

/** Recursively yield schema-valid handoffs for nodeId in depth-first order. */
function* iterateHandoffsInValue(value, nodeId, seen = new Set()) {
  if (value == null) return;
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (
      !(trimmed.startsWith("{") || trimmed.startsWith("[")) ||
      seen.has(trimmed)
    ) {
      return;
    }
    seen.add(trimmed);
    try {
      yield* iterateHandoffsInValue(JSON.parse(trimmed), nodeId, seen);
    } catch {
      return;
    }
    return;
  }
  if (typeof value !== "object") return;
  if (isValidTerminalHandoff(value, nodeId)) {
    yield value;
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      yield* iterateHandoffsInValue(item, nodeId, seen);
    }
    return;
  }
  for (const nested of Object.values(value)) {
    yield* iterateHandoffsInValue(nested, nodeId, seen);
  }
}

/** Recursively find a schema-valid handoff for nodeId in any nested structure. */
function findHandoffInValue(value, nodeId, seen = new Set()) {
  for (const handoff of iterateHandoffsInValue(value, nodeId, seen)) {
    return handoff;
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

/**
 * Classify a wait/read tool result that is not a usable snapshot.
 * Returns the error text, or null when the value is a real snapshot.
 * Observed on ChatGPT Desktop (Lisbon v5 forensics): a rejected read returns
 * the BARE STRING "read_thread received invalid arguments: turnLimit: Too
 * big: expected number to be <=10." — not a thrown error, not an error
 * object. Treating it as "no handoff yet" burned three 35-minute collection
 * windows while three complete handoffs sat unread.
 */
function toolErrorText(value) {
  if (typeof value === "string") return value;
  if (value == null) return "empty tool result";
  if (typeof value !== "object") return String(value);
  if (
    value.turns !== undefined ||
    value.items !== undefined ||
    value.terminal !== undefined
  ) {
    // Prefer the payload: a snapshot carrying real turns/items/terminal is a
    // snapshot even when a non-fatal error field rides along.
    return null;
  }
  if (
    value.isError === true ||
    value.is_error === true ||
    value.error != null
  ) {
    if (typeof value.error === "string") return value.error;
    if (typeof value.message === "string") return value.message;
    try {
      return JSON.stringify(value.error ?? value);
    } catch {
      return String(value.error ?? value);
    }
  }
  if (typeof value.message === "string") {
    return value.message;
  }
  return null;
}

/** Truncate a raw tool result for the blocked-terminal forensic floor. */
function truncateForensic(raw) {
  if (raw === undefined) return undefined;
  let text;
  if (typeof raw === "string") {
    text = raw;
  } else {
    try {
      text = JSON.stringify(raw);
    } catch {
      text = String(raw);
    }
  }
  if (typeof text !== "string") text = String(text);
  return text.length > FORENSIC_RESULT_CAP
    ? `${text.slice(0, FORENSIC_RESULT_CAP)} … [truncated ${text.length - FORENSIC_RESULT_CAP} chars]`
    : text;
}

async function collectTask({
  nodeId,
  threadId,
  waitThreads,
  readThread,
  turnLimit,
  maxCollectionRounds = 4,
  maxIdlePolls = 4,
  maxOutputCharsPerItem = MAX_OUTPUT_CHARS_PER_ITEM,
  delay = async () => {},
  repairMarker,
  startCursor,
  validateHandoff,
}) {
  if (maxOutputCharsPerItem > MAX_OUTPUT_CHARS_PER_ITEM) {
    throw new RangeError(
      `maxOutputCharsPerItem exceeds ${MAX_OUTPUT_CHARS_PER_ITEM}`,
    );
  }
  if (turnLimit !== undefined && turnLimit > MAX_TURN_LIMIT) {
    throw new RangeError(
      `turnLimit exceeds ${MAX_TURN_LIMIT} (ChatGPT Desktop rejects larger reads; openai/codex#30058)`,
    );
  }

  // startCursor seeds cursor provenance: a cursor recorded before the repair
  // send makes cursor-respecting read tools return only post-repair content.
  let afterCursor = startCursor;
  let collectionRounds = 0;
  let idlePolls = 0;
  let consecutiveToolErrors = 0;
  let lastReadResult;
  let previousFingerprint;
  let previousReadFingerprint;
  let terminal;
  const collectedItems = [];
  const seenItemKeys = new Set();
  const invalidSightings = [];
  const seenHandoffKeys = new Set();
  const calls = [];
  const reads = [];

  function recordSighting(errors, handoff) {
    const key = JSON.stringify(handoff);
    if (!seenHandoffKeys.has(key)) {
      seenHandoffKeys.add(key);
      invalidSightings.push({ errors, handoff });
    }
  }

  function acceptHandoff(handoff) {
    const isSuccessStatus =
      handoff.status === "complete" || handoff.status === "passed";
    if (
      isSuccessStatus &&
      repairMarker !== undefined &&
      !handoff[repairMarker]
    ) {
      // Post-repair correlation is by explicit marker (plus cursor
      // provenance), never by array index into a returned turn list: reads
      // may return a clipped window, so an index is meaningless and a short
      // window is not proof of absence. A marker-less complete handoff is
      // the stale pre-repair artifact — skip it and keep collecting.
      recordSighting(
        [`missing post-repair marker "${repairMarker}"`],
        handoff,
      );
      return false;
    }
    if (isSuccessStatus && typeof validateHandoff === "function") {
      const errors = validateHandoff(handoff);
      if (Array.isArray(errors) && errors.length > 0) {
        // Structurally invalid sighting, not a terminal: skip and keep
        // collecting (including later handoffs in this same snapshot).
        // Explicit blocked/failed status always terminates.
        recordSighting(errors, handoff);
        return false;
      }
    }
    terminal = handoff;
    return true;
  }

  function ingestHandoffsFrom(root) {
    for (const handoff of iterateHandoffsInValue(root, nodeId)) {
      if (acceptHandoff(handoff)) return true;
    }
    return false;
  }

  function blockedResult(blockerText) {
    return {
      status: "blocked",
      terminal,
      collectedItems,
      afterCursor,
      calls,
      reads,
      collectionRounds,
      idlePolls,
      terminalEmitted: false,
      blocker: blockerText,
      lastReadResult,
      invalidSightings,
    };
  }

  function abortBlocker(errorText) {
    return `${nodeId}: collection aborted after ${MAX_CONSECUTIVE_TOOL_ERRORS} consecutive tool errors; last tool result: ${errorText}`;
  }

  async function ingestSnapshot(snapshot, source, options = {}) {
    if (!snapshot || typeof snapshot !== "object") return;
    const { collectItems = true } = options;
    // All fallback surfaces stay searched in repair mode; post-repair
    // provenance is a content FILTER (repairMarker in acceptHandoff), not a
    // restriction of the search surface.
    ingestHandoffsFrom(snapshot.terminal) ||
      ingestHandoffsFrom(snapshot.items) ||
      ingestHandoffsFrom(snapshot.turns) ||
      ingestHandoffsFrom(snapshot);
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
      ...(afterCursor !== undefined ? { afterCursor } : {}),
    };
    if (turnLimit !== undefined) readRequest.turnLimit = turnLimit;
    reads.push(readRequest);
    const rawRead = await readThread(readRequest);
    lastReadResult = truncateForensic(rawRead);
    const readSnapshot = unwrapToolSnapshot(rawRead);
    const readError = toolErrorText(readSnapshot);
    if (readError !== null) {
      // A bare-string or error-envelope result is a tool error, not an empty
      // snapshot; it must not pass as "no handoff yet" (Lisbon v5).
      consecutiveToolErrors += 1;
      if (consecutiveToolErrors >= MAX_CONSECUTIVE_TOOL_ERRORS) {
        return blockedResult(abortBlocker(readError));
      }
    } else {
      consecutiveToolErrors = 0;
      await ingestSnapshot(readSnapshot, "read");
      previousReadFingerprint = snapshotFingerprint(readSnapshot || {});
      if (readSnapshot.afterCursor !== undefined) {
        afterCursor = readSnapshot.afterCursor;
      }
    }
    if (terminal) {
      return {
        status: terminal.status === "complete" ? "passed" : terminal.status,
        terminal,
        collectedItems,
        invalidSightings,
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
    const waitError = toolErrorText(snapshot);
    if (waitError !== null) {
      // An errored wait is not a snapshot: no fingerprint, no round credit.
      consecutiveToolErrors += 1;
      if (consecutiveToolErrors >= MAX_CONSECUTIVE_TOOL_ERRORS) {
        return blockedResult(abortBlocker(waitError));
      }
      idlePolls += 1;
      await delay();
      continue;
    }
    if (typeof readThread !== "function") {
      // Wait is the only stream; a clean wait resets the allowance.
      consecutiveToolErrors = 0;
    }
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
      if (turnLimit !== undefined) readRequest.turnLimit = turnLimit;
      reads.push(readRequest);
      const rawRead = await readThread(readRequest);
      lastReadResult = truncateForensic(rawRead);
      const readSnapshot = unwrapToolSnapshot(rawRead);
      const readError = toolErrorText(readSnapshot);
      if (readError !== null) {
        // An errored read is not an empty snapshot; never burn the window
        // on it. Abort after the bounded allowance instead of spinning.
        consecutiveToolErrors += 1;
        if (consecutiveToolErrors >= MAX_CONSECUTIVE_TOOL_ERRORS) {
          return blockedResult(abortBlocker(readError));
        }
      } else {
        consecutiveToolErrors = 0;
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

  if (!terminal) {
    // Forensic floor: a window expiry embeds the last raw read result so the
    // next silent failure is diagnosable from the blocked terminal alone.
    return blockedResult(
      `${nodeId}: collection window expired without terminal JSON`,
    );
  }

  const status = terminal.status === "complete" ? "passed" : terminal.status;

  return {
    status,
    terminal,
    collectedItems,
    invalidSightings,
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
  MAX_TURN_LIMIT,
  MAX_CONSECUTIVE_TOOL_ERRORS,
  FORENSIC_RESULT_CAP,
  collectTask,
  isValidTerminalHandoff,
  findHandoffInValue,
  findExactThread,
  preflightWorktreeTarget,
  normalizeToolResult,
  toolErrorText,
  truncateForensic,
  aggregateStartFailure,
  canonicalUrlForComparison,
};
