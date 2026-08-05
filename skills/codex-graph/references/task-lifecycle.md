# Codex task lifecycle

Read this reference whenever a Code Mode graph creates visible Codex tasks or threads. Treat creation, setup, execution, collection, and terminal reporting as separate states.

## 1. Bind the graph to its project

Inspect the active declarations for project listing and task creation.

1. If the goal belongs to a saved Codex project, resolve the exact project path through the project-list tool.
2. Match the exact path. Fail closed on no match or more than one match.
3. Use `target: { type: "project", projectId, environment: { type: "local" } }` only when every node is strictly read-only.
4. Use the saved project with a worktree environment when any node can write. Give concurrent writers disjoint scopes.
5. Use a projectless target only when no saved project applies or the user explicitly requests it.

Keep the resolved project ID in the workflow result. Do not use a generated directory as the identity of a saved-project task.

## 2. Treat setup as a state machine

A task-creation call can return:

- a ready `threadId` and optional `hostId`;
- a pending `clientThreadId` while the task is being prepared;
- a real tool error.

A pending setup handle is success in progress. Preserve it. Use a unique run tag and task title for every node. Store this handle shape:

```javascript
{
  node_id,
  thread_id,
  client_thread_id,
  host_id,
  project_id,
  run_tag,
  title,
  state: "pending_setup | active | complete | failed",
  start_result,
}
```

If `threadId` is absent and `clientThreadId` is present, poll the task list with a named maximum and short delay. Match the exact project ID and unique run tag. Prefer `title`; while a project task is loading, Codex can temporarily put the requested title in `summary`. Accept `summary` only when it contains the same exact unique run tag and the project ID also matches. Copy the ready thread and host IDs into the existing handle. Do not create a replacement task while the original setup can still resolve.

```javascript
const START_RESOLVE_ATTEMPTS = 30;
const START_RESOLVE_DELAY_MS = 1000;

function findExactThread(value, projectId, runTag) {
  if (typeof value === "string") {
    try {
      return findExactThread(JSON.parse(value), projectId, runTag);
    } catch {
      return null;
    }
  }
  if (!value || typeof value !== "object") return null;
  const sameProject = value.projectId === projectId;
  const title = typeof value.title === "string" ? value.title : "";
  const summary = typeof value.summary === "string" ? value.summary : "";
  if (sameProject && (title.includes(runTag) || summary.includes(runTag))) return value;
  for (const nested of Object.values(value)) {
    const found = findExactThread(nested, projectId, runTag);
    if (found) return found;
  }
  return null;
}

for (let attempt = 1; !handle.thread_id && attempt <= START_RESOLVE_ATTEMPTS; attempt += 1) {
  const snapshot = await listThreads({ limit: 50 });
  const record = findExactThread(snapshot, handle.project_id, handle.run_tag);
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

Use the wait tool to pause until progress, completion, attention, or a bounded timeout. Then read the task. A timeout is not proof of failure.

Use named limits:

```javascript
const WAIT_TIMEOUT_MS = 120000;
const COMPLETION_WAIT_ATTEMPTS = 15;
const COMPLETION_DEADLINE_MS = 30 * 60 * 1000;
const MIN_ACTIVE_POLL_DELAY_MS = 10000;
const MAX_READ_ITEM_CHARS = 20000;
```

Set `const collectionStartedAt = Date.now()` before the loop. Each loop is permitted only while both conditions remain true:

- the attempt count is within `COMPLETION_WAIT_ATTEMPTS`;
- `Date.now() - collectionStartedAt < COMPLETION_DEADLINE_MS`.

After the wait and read calls, measure actual elapsed time for that check. If the task is still active and the wait returned sooner than `MIN_ACTIVE_POLL_DELAY_MS`, sleep for the remaining minimum delay, capped by the wall-clock deadline. This prevents an early-returning wait implementation from consuming a 30-minute budget in seconds.

For each attempt:

1. Call the wait tool with the ready `threadId` and `hostId` when required.
2. Read the newest task turn with `maxOutputCharsPerItem` no greater than 20,000, or a lower declared cap.
3. Detect an explicit failed or interrupted terminal turn.
4. Recursively inspect `turns` and their structured `items` for the required JSON handoff.
5. Accept the handoff only when its `node_id`, status, and task-specific schema match.
6. Continue within the declared attempt budget when the task is active or the handoff is not terminal.

Do not assume output is one text field. Do not treat an unchanged wait snapshot as failure.

## 4. Make handoffs fit before execution

Set a hard worker-output contract, normally 8,000-9,000 characters. Require one JSON object with decisive evidence only.

Treat that object as a compact routing index. It must not become the only copy of evidence needed for acceptance. Give records stable IDs and preserve complete source URLs, roles, dates, locators, and required fields in an approved durable artifact. Return its path or identifier and hash. Do not substitute unexplained source aliases for required evidence.

Use these overflow routes:

- `artifact.expansion_queue` for deferred candidates;
- `unresolved_questions` for open issues;
- an approved durable artifact with a returned path, identifier, and hash when evidence must stay complete.

Integration inputs must be complete JSON. If a handoff is too large, fail with the actual size and node ID. Never slice serialized JSON.

Validate every handoff against one canonical schema. If a worker uses a compact transport shape, normalize it deterministically before the next node. Final formatting must consume only canonical validated records and must fail closed on missing required fields rather than emitting `null` values.

Run declared transport adapters before shape and cardinality guards. An adapter must be deterministic, resolve every referenced stable ID exactly once, preserve the complete canonical record table, and reject missing, duplicate, or unknown IDs. Do not infer an adapter for an undeclared shape during execution.

Read tools can impose a per-item limit even when the outer Code Mode result budget is larger. Set both budgets explicitly and design to the smaller boundary.

## 5. Report exact failures and live state

Use `Promise.allSettled` for required parallel starts and collections. Report each rejected node with its exact reason. A generic list of node IDs is not enough.

On any blocked terminal result, include:

- node ID;
- pending and ready task IDs;
- project ID and host ID;
- title and state;
- exact start, wait, read, parse, capacity, or schema error;
- every still-live handle.

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

If the collection-attempt budget expires while a task is still active, build a checkpoint containing:

- the run tag and resolved project ID;
- completed node IDs and their compact handoffs;
- active node IDs and full live handles;
- not-started node IDs;
- executed and skipped stages;
- the wait timeout and attempt count already used.

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
- the pending task carries its unique run tag in `summary` before `title` is ready;
- a wait call times out while the task remains active;
- a wait call returns immediately and the fallback delay protects the wall-clock budget;
- the final JSON is nested in structured `items`;
- the read request stays within the item limit;
- an oversized handoff uses an expansion queue or durable artifact;
- a blocked result preserves every live handle and exact node error;
- saved-project tasks remain associated with the exact project ID.
- a valid resume handle is collected without a duplicate task;
- a collection-window stop preserves completed, active, and not-started node state;
- a resumed graph starts later not-started nodes without demanding handles;
- every control path reaches one terminal emitter exactly once.

The lifecycle design is complete only when every case has a defined terminal or continuation path.
