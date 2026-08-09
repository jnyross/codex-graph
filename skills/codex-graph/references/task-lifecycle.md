# Codex task lifecycle

Read this reference whenever a Code Mode graph creates visible Codex tasks or threads. Treat creation, setup, execution, collection, and terminal reporting as separate states.

## 1. Bind the graph to its project

Inspect the active declarations for project listing and task creation.

1. If the goal belongs to a saved Codex project, resolve the exact project path through the project-list tool.
2. Match the exact path. Fail closed on no match or more than one match.
3. Choose the task **environment per node**, not once for the whole graph:
   - Read-only nodes (research, discovery, audit/read lenses) use
     `target: { type: "project", projectId, environment: { type: "local" } }`.
   - Nodes that write repository files use
     `target: { type: "project", projectId, environment: { type: "worktree" } }`
     with disjoint write scopes for concurrent writers.
   - Never apply `worktree` globally because one writer exists. Observed
     Lisbon dogfood v4: research workers created with worktree returned only
     `clientThreadId`, never resolved within a chat-scale bound, and blocked
     before collection while v3's `local` research workers got ready
     `threadId`s immediately.
4. Prefer the root orchestrator (or a single integration owner on `local` /
   the real project checkout) for final user-facing artifacts such as report
   files in the project root. Do not strand publication writes only inside a
   disposable worker worktree.
5. Use a projectless target only when no saved project applies or the user explicitly requests it.

Keep the resolved project ID in the workflow result. Do not use a generated directory as the identity of a saved-project task.

## 2. Treat setup as a state machine

A task-creation call can return:

- a ready `threadId` and optional `hostId`;
- a pending `clientThreadId` while the task is being prepared;
- a real tool error.

At the JavaScript level the entire result may arrive as a JSON **string**
(observed for `codex_app__create_thread` on ChatGPT Desktop for macOS). A key
lookup applied to the raw string silently returns nothing and wrongly converts
every successful start into a start failure. Normalize every tool result at
the call boundary with the exact-envelope parser from
`code-mode-script-patterns.md` ("Normalize tool results at the call
boundary"): parse the whole trimmed string exactly once, never apply fragment
extraction heuristics to a tool return, use the parsed value for key lookup,
and keep the raw payload in the handle's `start_result`.

A pending setup handle is success in progress. Preserve it. Use a unique run tag and task title for every node. Store this handle shape:

```javascript
{
  node_id,
  thread_id,
  client_thread_id,
  host_id,
  project_id,
  environment: { type: "local" | "worktree" },
  run_tag,
  title,
  state: "pending_setup | active | complete | failed",
  start_result,
}
```

If `threadId` is absent and `clientThreadId` is present, resolving the pending
setup is **required**, not optional: poll the task list with a named maximum and
short delay. This applies to projectless targets too — match the unique run tag
(and the exact project ID when one exists). Never fail a start closed while its
pending setup can still resolve within the named bound, and never create a
replacement task while the original setup can still resolve. Prefer `title`;
while a project task is loading, Codex can temporarily put the
requested title in `summary`. Accept it only when it contains the same exact unique run
tag. When a project is bound, prefer an exact `projectId` match, but while
setup is still loading allow the same unique run tag in `title`/`summary`
even if `projectId` is not yet present on the list row (Lisbon v4: list
matching that *required* projectId during worktree setup never resolved).
When the list or create payload exposes `clientThreadId` (or equivalent), also
correlate the pending handle by that ID. Copy the ready thread and host IDs into
the existing handle.

Use a **chat-scale** bound for local/projectless starts (for example 30×1s or
60×2s). Use a **provisioning-scale** bound when the node uses a worktree
environment (worktree creation alone can exceed two minutes). Name both
constants in the script.

```javascript
// Chat-scale default for local / projectless. Raise for worktree nodes.
const isWorktree = handle.environment?.type === "worktree";
const START_RESOLVE_ATTEMPTS = isWorktree ? 90 : 30;
const START_RESOLVE_DELAY_MS = isWorktree ? 2000 : 1000;

function findExactThread(value, projectId, runTag, clientThreadId) {
  if (typeof value === "string") {
    try {
      return findExactThread(JSON.parse(value), projectId, runTag, clientThreadId);
    } catch {
      return null;
    }
  }
  if (!value || typeof value !== "object") return null;
  const listedClient =
    value.clientThreadId ?? value.client_thread_id ?? null;
  if (
    clientThreadId &&
    listedClient &&
    String(listedClient) === String(clientThreadId)
  ) {
    return value;
  }
  // Projectless handles have no projectId; match the unique run tag alone.
  // When a project is bound, prefer projectId match but do not require it
  // while setup is still loading (projectId may be absent on early list rows).
  const title = typeof value.title === "string" ? value.title : "";
  const summary = typeof value.summary === "string" ? value.summary : "";
  const tagHit = title.includes(runTag) || summary.includes(runTag);
  if (tagHit) {
    const projectRequired = projectId != null && projectId !== "";
    const listedProject = value.projectId ?? value.project_id;
    if (!projectRequired || listedProject == null || listedProject === projectId) {
      return value;
    }
  }
  for (const nested of Object.values(value)) {
    const found = findExactThread(nested, projectId, runTag, clientThreadId);
    if (found) return found;
  }
  return null;
}

for (let attempt = 1; !handle.thread_id && attempt <= START_RESOLVE_ATTEMPTS; attempt += 1) {
  const snapshot = await listThreads({ limit: 50 });
  const record = findExactThread(
    snapshot,
    handle.project_id,
    handle.run_tag,
    handle.client_thread_id,
  );
  if (record) {
    handle.thread_id = findString(record, ["threadId", "thread_id", "id"]);
    handle.host_id = findString(record, ["hostId", "host_id"]);
    handle.state = handle.thread_id ? "active" : "pending_setup";
  }
  if (!handle.thread_id && attempt < START_RESOLVE_ATTEMPTS) {
    await new Promise((resolve) => setTimeout(resolve, START_RESOLVE_DELAY_MS));
  }
}
```

Adapt field names and arguments to the active declarations. Keep the bounded state transition.

## 3. Wait and read separately

Use the wait tool to pause until progress, completion, attention, or a
tool-supported timeout. Then read the task. A timeout is not proof of failure.
If the active wait implementation can return immediately or run indefinitely,
add a task-specific deadline or polling strategy based on that observed
behavior; do not copy a universal timeout or attempt count.

For each collection round:

1. **Read first, then wait.** On the first collection for a handle, call the
   task-read tool **before** the first wait. The worker may already be idle
   with a complete handoff; wait-only loops can sit on empty snapshots for the
   entire budget (observed: Lisbon dogfood v3 — workers finished in ~161s with
   valid JSON, root reported `rounds=1, idle=15` over 30 minutes and blocked).
2. Call the wait tool with the ready `threadId` and `hostId` when required.
3. **Read again after every wait.** Do not treat the wait payload as the only
   source of items or handoffs. Wait may return no new cursor while
   `read_thread` already has the terminal turn.
4. Use at most `20000` for `maxOutputCharsPerItem` on the current task-read
   declaration unless the active declaration explicitly allows more.
5. Pass the returned pagination cursor (for example, `afterCursor`) into the
   next read or wait call when the tool exposes one. A repeated snapshot with
   no new cursor is not a new collection round and must not consume the
   collection budget — **unless** a concurrent read finds a new handoff.
6. Detect an explicit failed or interrupted terminal turn.
7. Recursively inspect `turns` and their structured `items` (and string JSON
   inside text fields) for the required JSON handoff. Accept status values
   `complete`, `passed`, `blocked`, or `failed` when they match the node
   schema.
8. Accept the handoff only when its `node_id`, status, and task-specific schema match.
9. Continue while the task is active or the handoff is not terminal. Stop only
   at an active-tool failure, explicit terminal failure, a collected terminal
   handoff, or a task-specific deadline introduced for an observed operational
   need. Do **not** stop solely because wait snapshots look idle if you have not
   performed a recent full read.

Do not assume output is one text field. Do not treat an unchanged wait snapshot as failure.

Use a cursor-aware bounded collector rather than repeating the same read.
When `waitThreads` comes from `resolveTool`, every call returns
`{ value, raw }` — read fields from the parsed `value`, not the envelope:

```javascript
const MAX_OUTPUT_CHARS_PER_ITEM = 20000;
const MAX_IDLE_POLLS = 4;
let afterCursor;
let collectionRounds = 0;
let idlePolls = 0;
let previousSnapshotFingerprint;
let handoff;

function snapshotFingerprint(snapshot) {
  return JSON.stringify({
    items: snapshot.items ?? [],
    terminal: snapshot.terminal ?? null,
  });
}

// Read first: worker may already be complete.
{
  const firstRead = await readThread.call({
    threadId: handle.thread_id,
    ...(handle.host_id ? { hostId: handle.host_id } : {}),
    includeOutputs: true,
    maxOutputCharsPerItem: MAX_OUTPUT_CHARS_PER_ITEM,
  });
  handoff = findHandoffInValue(firstRead.value, handle.node_id);
}

while (
  !handoff &&
  collectionRounds < MAX_COLLECTION_ROUNDS &&
  idlePolls < MAX_IDLE_POLLS
) {
  const waitResult = await waitThreads.call({
    threadIds: [handle.thread_id],
    afterCursor,
    maxOutputCharsPerItem: MAX_OUTPUT_CHARS_PER_ITEM,
  });
  const snapshot = waitResult.value;
  const nextCursor = snapshot.afterCursor;
  const cursorAdvanced =
    nextCursor !== undefined && nextCursor !== afterCursor;
  const hasNewData =
    cursorAdvanced ||
    (previousSnapshotFingerprint === undefined ||
      snapshotFingerprint(snapshot) !== previousSnapshotFingerprint);
  if (hasNewData) {
    collectionRounds += 1;
    idlePolls = 0;
  } else {
    idlePolls += 1;
  }
  previousSnapshotFingerprint = snapshotFingerprint(snapshot);
  if (nextCursor !== undefined) afterCursor = nextCursor;

  // Read after every wait — wait items alone are not sufficient.
  const readResult = await readThread.call({
    threadId: handle.thread_id,
    ...(handle.host_id ? { hostId: handle.host_id } : {}),
    includeOutputs: true,
    maxOutputCharsPerItem: MAX_OUTPUT_CHARS_PER_ITEM,
    ...(afterCursor !== undefined ? { afterCursor } : {}),
  });
  handoff = findHandoffInValue(readResult.value, handle.node_id);
  if (!handoff && !hasNewData) {
    await new Promise((resolve) => setTimeout(resolve, COLLECTION_DELAY_MS));
  }
}
```

Adapt the argument names to the active declaration, but preserve both
properties: carry the cursor forward, deduplicate unchanged snapshots, and
stay within the declared item limit and an explicit no-progress bound.

## 4. Make handoffs fit before execution

Require one JSON object with decisive evidence only. Do not set a character budget until the active tool declares one or an observed run proves it is needed.

Treat that object as a compact routing index. It must not become the only copy of evidence needed for acceptance. Give records stable IDs and preserve complete source URLs, roles, dates, locators, and required fields in an approved durable artifact. Return its path or identifier and hash. Do not substitute unexplained source aliases for required evidence.

Use these overflow routes:

- `artifact.expansion_queue` for deferred candidates;
- `unresolved_questions` for open issues;
- an approved durable artifact with a returned path, identifier, and hash when evidence must stay complete.

Integration inputs must be complete JSON. Concatenate upstream handoffs when they fit the active tool contract. If an observed payload limit is reached, pass a compact join manifest or artifact references and use staged fan-in only for the affected portion. If a handoff or join is too large, report the actual size and preserve resumable handles. Never slice serialized JSON.

Validate every handoff against one canonical schema. If a worker uses a compact transport shape, normalize it deterministically before the next node. Final formatting must consume only canonical validated records and must fail closed on missing required fields rather than emitting `null` values.

Run declared transport adapters before shape and cardinality guards. An adapter must be deterministic, resolve every referenced stable ID exactly once, preserve the complete canonical record table, and reject missing, duplicate, or unknown IDs. Do not infer an adapter for an undeclared shape during execution.

Read tools can impose a per-item limit even when the outer Code Mode result
budget is larger. Use the active declaration; do not invent a smaller
application-level budget.

## 5. Report exact failures and live state

Use `Promise.allSettled` for required parallel starts and collections. Report each rejected node with its exact reason. A generic list of node IDs is not enough.

When several required starts fail together, build the aggregate error with
`Object.assign(new Error(...), { handles })`, carrying every rejected node's
handle, and spread `error.handles` into the blocked result's live-handle list.
A rejected start whose task was already created is still a live handle;
dropping it orphans a running task and reports `live_handles: []` while work
continues unobserved.

On any blocked terminal result, include:

- node ID;
- pending and ready task IDs;
- project ID and host ID;
- title and state;
- exact start, wait, read, parse, capacity, or schema error;
- every still-live handle;
- every **completed upstream handoff** already collected (compact schema-valid
  objects), not only handles. Handles alone force re-reading threads to recover
  research that finished before the block; preserve the handoffs in the
  terminal so a later resume or critique can use them without duplicate work.

If a fixed model is at capacity, keep the model policy. Permit one clean same-model retry only when the graph declares that operational retry. Give it a new run tag. Otherwise stop with the capacity error. Operational setup or capacity retries do not consume the artifact-repair allowance, but they must be explicit and bounded.

## 6. Resume without duplicate tasks

For an L4 long graph, accept an explicit checkpoint with three node states:

- `complete`: reuse its compact, schema-valid handoff;
- `active`: validate its live handle and continue collection;
- `not_started`: create it normally only after its dependencies pass.

Validate each active handle before use:

- node ID belongs to the current workflow;
- project ID and host ID match the current resolved target;
- model and reasoning policy match the node contract;
- a ready task ID exists;
- the task title or summary contains the expected unique run tag.

Add the validated handle to the live-handle registry and collect it. Do not call the create tool for that active node. Reject a stale, ambiguous, or policy-mismatched handle with its exact reason. Do not require or fabricate handles for not-started nodes.

If an observed operational limit requires stopping while a task is still active,
build a checkpoint containing:

- the run tag and resolved project ID;
- completed node IDs and their compact handoffs;
- active node IDs and full live handles;
- not-started node IDs;
- executed and skipped stages;
- the active-tool limit or observed condition that caused the stop.

Return the checkpoint with the blocked result. A later run resumes active nodes, reuses completed handoffs, and starts future nodes normally. It does not repeat completed work.

## 7. Emit one terminal result

Build terminal data through normal return values. Use one `terminalEmitted` guard and one final `text(...)` call. Do not call `exit()` inside the main `try` block. In some orchestration layouts, the exit signal can enter `catch` and produce a second terminal object.

Keep terminal states explicit:

- `passed`: acceptance evidence exists;
- `blocked`: progress needs access, capacity, valid transport, or user authority;
- `failed`: the single artifact repair and revalidation did not pass.

Every path must return one of these objects to the single emitter.

## 8. Verify the lifecycle path

Before returning a generated graph script, check these cases against the active tool schemas:

- task creation returns a ready `threadId`;
- task creation returns only `clientThreadId` and later resolves;
- task creation returns the whole result as a JSON string and the script
  normalizes it before key lookup;
- an aggregate start failure preserves each rejected node's handle in the
  blocked result;
- a projectless pending setup resolves from a list response by unique run tag
  alone, reuses the existing handle, and does not create a replacement task;
- the pending task carries its unique run tag in `summary` before `title` is ready;
- a wait call times out while the task remains active;
- a wait call returns immediately and the fallback delay protects the wall-clock budget;
- the final JSON is nested in structured `items`;
- a worker already complete at first collection still yields a handoff via an initial read;
- an empty wait snapshot still yields a handoff via a paired read_thread;
- the read request stays within the item limit;
- an oversized handoff uses an expansion queue or durable artifact;
- a blocked result preserves every live handle and exact node error;
- saved-project tasks remain associated with the exact project ID.
- a valid resume handle is collected without a duplicate task;
- a collection-window stop preserves completed, active, and not-started node state;
- a resumed graph starts later not-started nodes without demanding handles;
- every control path reaches one terminal emitter exactly once.

The lifecycle design is complete only when every case has a defined terminal or continuation path.
