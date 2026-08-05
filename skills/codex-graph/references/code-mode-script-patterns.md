# Code Mode script patterns

Use this reference to turn the approved graph design into complete Codex Code Mode JavaScript. Tailor the script to the goal; do not copy the skeleton unchanged.

## Runtime facts to design around

- Code Mode evaluates raw JavaScript in a fresh V8 isolate as an async module.
- Nested tools are exposed on the global `tools` object.
- `ALL_TOOLS` contains metadata for enabled and deferred nested tools.
- The runtime is not Node.js: there is no direct filesystem, network, imports, or `console`.
- Use top-level `await` and emit model-visible output with `text(...)`.
- Every promise that matters must be awaited; unawaited promises are discarded when the isolate ends.
- A first-line `// @exec: {...}` pragma can set the outer yield interval and output budget.
- If the outer execution yields with a cell ID, the caller must use the public Code Mode wait operation until the cell completes.

## Prefer semantic tool resolution over hard-coded namespaces

Tool namespaces and multi-agent versions can differ. Resolve an operation from actual metadata, confirm it is callable, and fail closed when it is absent.

```javascript
function candidatePropertyNames(name) {
  return [...new Set([
    name,
    name.replace(/[.\-/:]+/g, "_"),
    name.replace(/[.\-/:]+/g, "__"),
  ])];
}

function resolveTool(operation, { required = true } = {}) {
  const exactOrSuffix = ALL_TOOLS.filter(({ name = "", description = "" }) => {
    const normalized = name.toLowerCase();
    const descriptionText = description.toLowerCase();
    return normalized === operation ||
      normalized.endsWith(`__${operation}`) ||
      normalized.endsWith(`_${operation}`) ||
      normalized.endsWith(`.${operation}`) ||
      descriptionText.includes(` ${operation.replaceAll("_", " ")}`);
  });

  for (const metadata of exactOrSuffix) {
    for (const propertyName of candidatePropertyNames(metadata.name)) {
      if (typeof tools[propertyName] === "function") {
        return {
          name: propertyName,
          metadata,
          call: (args) => tools[propertyName](args),
        };
      }
    }
  }

  for (const propertyName of candidatePropertyNames(operation)) {
    if (typeof tools[propertyName] === "function") {
      return {
        name: propertyName,
        metadata: { name: propertyName, description: "" },
        call: (args) => tools[propertyName](args),
      };
    }
  }

  if (required) throw new Error(`Required Code Mode tool is unavailable: ${operation}`);
  return null;
}
```

Do not rely on this helper alone when the current declaration already provides an exact name and schema. Prefer the exact exposed declaration and use defensive resolution only for namespace portability.

## Build arguments from the exposed declaration

Multi-agent versions may accept different spawn fields. Inspect the declaration text before adding optional fields.

```javascript
function spawnArgs(spawnTool, node) {
  const declaration = `${spawnTool.metadata.name}\n${spawnTool.metadata.description}`;
  const args = { message: node.prompt };

  if (/\btask_name\b/.test(declaration)) args.task_name = node.id.toLowerCase();
  if (/\bfork_turns\b/.test(declaration)) args.fork_turns = "none";
  else if (/\bfork_context\b/.test(declaration)) args.fork_context = false;

  return args;
}
```

Do not add `agent_type`, model, or reasoning overrides unless the goal requires them and the current declaration supports the combination. A clear worker prompt is usually safer and more portable.

## Bounded parallel fan-out

Use `Promise.allSettled` when partial diagnostics are useful, but treat any required worker failure as a blocked stage.

```javascript
async function spawnRequiredBatch(nodes, spawnTool) {
  const settled = await Promise.allSettled(
    nodes.map((node) => spawnTool.call(spawnArgs(spawnTool, node)))
  );

  const failures = settled
    .map((result, index) => ({ result, node: nodes[index] }))
    .filter(({ result }) => result.status === "rejected");

  if (failures.length > 0) {
    throw new Error(`Required workers failed to spawn: ${failures.map(({ node }) => node.id).join(", ")}`);
  }

  return settled.map(({ value }, index) => ({
    node: nodes[index],
    spawnResult: value,
    agentId: findAgentId(value),
  }));
}
```

When the active tool or observed workload requires a fan-out cap, run larger
independent sets in explicit sequential stages and join them under one owner.
Do not create a worker that spawns another worker.

## Bind visible tasks to the correct project

When the script creates visible Codex tasks, read `task-lifecycle.md` and use its complete contract. Resolve the exact saved project before task creation. Use its local environment only when every task is read-only. Use isolated project worktrees when any task can write. Use a projectless target only when no saved project applies or the user explicitly requests it.

## Preserve setup handles and terminal handoffs

A task-creation result can contain a ready `threadId` or only a pending `clientThreadId`. Both are successful setup states. Retain the complete result and resolve pending setup with bounded polling before calling wait or read tools. Match the exact project ID and unique run tag. The tag normally appears in `title`, but can appear in `summary` while project setup is loading. Retain `hostId` when present. See `task-lifecycle.md` for the state machine and code pattern.

Do not reduce a task handle to one convenience ID while setup or execution is live. A blocked terminal report must include each node ID, ready or pending ID, project ID, host ID, title, state, and the exact start or collection error.

## Read structured task output

Task reads return structured turns and `items`; they are not guaranteed to expose one flat text field. Recursively inspect the structured result and validate the required JSON handoff against the node ID and schema. Request the tool's supported output size rather than assuming a universal item limit.

A wait timeout is not by itself a task failure. Use the active tool's wait semantics; if it can return immediately or run indefinitely, add a named deadline and polling strategy based on the observed behavior.

Accept explicit checkpoints and resume handles for long graphs. Validate active handles by node ID, project ID, host ID, model policy, and ready task ID, then collect the existing task. Reuse compact handoffs for completed nodes. Create `not_started` nodes normally after their dependencies pass; do not require a handle for a future stage. A resume path must not duplicate completed or active work.

When an observed collection limit or active-tool deadline stops a task while it
is still active, return a resumable checkpoint. Preserve completed handoffs,
active handles, not-started node IDs, and the exact stop condition used. Do not
repeat completed research in the next run.

## Handoffs and joins

Require each worker to return one complete JSON object. Do not impose a character budget unless the active tool declares one or a run demonstrates that one is needed. Keep decisive evidence in the handoff; use an approved durable artifact when the evidence is too large for the actual transport.

The compact JSON is a routing index, not the authoritative evidence store. For evidence-heavy work, give each record a stable ID and preserve complete URLs, source roles, dates, locators, and extracts in the durable artifact. Return the artifact identifier and hash with the compact record index. Do not compress required evidence into unexplained aliases such as `S1`.

```javascript
function boundedJson(value, maxChars) {
  const rendered = JSON.stringify(value, null, 2);
  if (maxChars !== undefined && rendered.length > maxChars) {
    throw new Error(`Complete handoff exceeds ${maxChars} characters`);
  }
  return rendered;
}
```

If a measured transport limit appears, declare it in the workflow contract and apply it to the smallest affected boundary. `boundedJson(workerHandoff, observedLimit)` may validate one worker result, but do not apply that limit to an aggregate join unless the tool explicitly imposes it.

Build joins from references rather than embedding every handoff:

```javascript
function joinManifest(handoffs) {
  return handoffs.map(({ nodeId, status, recordIds, artifact }) => ({
    nodeId,
    status,
    recordIds,
    artifactId: artifact?.id,
    artifactHash: artifact?.hash,
  }));
}
```

If an aggregate join exceeds an observed transport limit, create staged validation fan-in: compact manifest entries or artifact references, then bounded shards only where needed, followed by one serial root gate. Preserve exact node and artifact handles. Never slice serialized JSON.

## Freeze one acceptance and schema contract

Before workers start, declare the fixed scope or pilot size, selection rule, required record fields, audit thresholds, publication rule, and repair boundary. Give the same contract ID and values to discovery, integration, every audit lens, the root gate, repair, revalidation, and final formatting. Reject an audit result that invents a new cutoff or expands the fixed pilot.

Define one canonical record schema and validate it at every boundary. A repair worker can use a compact transport form only when the repair owner deterministically normalizes it back to the canonical schema before revalidation and formatting. Never let the formatter guess between object and array shapes or silently emit `null` fields.

Declare any accepted equivalent transport forms and their adapters before execution. For example, a shard can be either a two-record array or an object with exactly two `record_ids` that resolve uniquely against the canonical record table. Normalize first, then enforce cardinality and required fields. Reject undeclared or ambiguous shapes; do not reject a complete declared shape before its adapter runs.

## Machine-readable validation gate

Tell the validator to return JSON only. Parse it strictly enough to fail closed on malformed output.

```javascript
function collectStrings(value, output = []) {
  if (typeof value === "string") output.push(value);
  else if (Array.isArray(value)) for (const item of value) collectStrings(item, output);
  else if (value && typeof value === "object") {
    for (const item of Object.values(value)) collectStrings(item, output);
  }
  return output;
}

function parseValidatorDecision(waitResult) {
  for (const candidate of collectStrings(waitResult).reverse()) {
    const trimmed = candidate.trim();
    const variants = [trimmed];
    const fenced = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/i);
    if (fenced) variants.push(fenced[1].trim());
    const objectLike = trimmed.match(/\{[\s\S]*\}/);
    if (objectLike) variants.push(objectLike[0]);

    for (const variant of variants) {
      try {
        const parsed = JSON.parse(variant);
        if (["pass", "repair"].includes(parsed?.decision)) return parsed;
      } catch {}
    }
  }
  throw new Error("Validator did not return a valid pass-or-repair JSON decision");
}
```

The validator schema should include at least:

```json
{
  "decision": "pass | repair",
  "failed_criteria": [],
  "affected_ids": [],
  "evidence": [],
  "repair_instructions": [],
  "unresolved_risks": []
}
```

When L3 is active and an artifact has independent audit dimensions or record
batches, run those validators in parallel. The root orchestrator then
deduplicates their failed criteria and affected IDs at one serial gate.
Revalidation runs only the affected lanes and any global check invalidated by
the repair.

Each validator must cite a declared acceptance criterion. It cannot require a larger sample or new coverage domain after the run starts. The root gate rejects repair instructions that contradict the fixed scope or cannot be completed within the one declared repair stage.

## Exactly one repair, unrolled

Do not use a retry loop. Keep the branch visible.

If L4 is active and many records need corrections, keep one logical repair
branch but split its internal work into bounded record-specific correction
shards. Join those shards at one serial repair owner, validate and normalize
every record to the canonical schema, and produce one repaired artifact. This is
still one repair stage; failed revalidation stops the graph.

```javascript
async function applySingleRepair(initialDecision, initialArtifact, initialValidation) {
  if (initialDecision.decision !== "repair") {
    return {
      passed: true,
      repairUsed: false,
      artifact: initialArtifact,
      validation: initialValidation,
    };
  }

  const repairResult = await runSingleRepair(initialDecision, initialArtifact);
  const revalidationResult = await runRevalidation(repairResult);
  const revalidationDecision = parseValidatorDecision(revalidationResult);

  if (revalidationDecision.decision !== "pass") {
    return {
      passed: false,
      repairUsed: true,
      artifact: repairResult,
      validation: revalidationDecision,
      reason: "Revalidation failed after the single allowed repair",
    };
  }

  return {
    passed: true,
    repairUsed: true,
    artifact: repairResult,
    validation: revalidationDecision,
  };
}
```

There is no second repair branch. The caller converts this result into one terminal object and sends it through the single emitter.

## Worker prompt contract

Each node prompt should include:

1. Overall objective and success criteria.
2. The node ID, purpose, and dependencies.
3. Allowed read/write scope.
4. Inputs or upstream handoffs.
5. Required work and explicit non-goals.
6. No nested delegation.
7. Required structured handoff schema.
8. A statement that the worker cannot declare the whole workflow complete.

For a sole writer, add instructions to preserve uncommitted work, inspect applicable `AGENTS.md`, keep the diff small, and report exact changed paths and observed validation.

## Final output

Build one compact terminal object, then emit it once through `text(...)`. Include status, executed nodes, artifacts, validation, sources used, deviations, blockers, repair use, and live handles. Avoid dumping every raw tool object when a concise handoff or artifact reference is sufficient.

```javascript
let terminalEmitted = false;

function emitTerminal(payload) {
  if (terminalEmitted) throw new Error("Terminal result was already emitted");
  terminalEmitted = true;
  text(JSON.stringify(payload, null, 2));
}

let terminalResult;
try {
  terminalResult = await runWorkflow();
} catch (error) {
  terminalResult = blockedResult(error);
}
emitTerminal(terminalResult);
```

Do not call `exit()` inside the `try` block. Keep early-stop decisions as returned terminal objects so the catch path cannot emit a second result.

## Anti-patterns

- A Mermaid graph whose node IDs do not appear in the script.
- A code fence containing prose or pseudocode rather than executable JavaScript.
- Hard-coded tool names that are absent from the current declarations.
- Calling a nested tool without awaiting it.
- Parallel writes to overlapping files.
- A worker that spawns more workers.
- `while`, recursive retry, or an unbounded polling loop around repair or validation.
- Parsing validator prose heuristically when strict JSON was requested.
- Treating a pending `clientThreadId` as a failed task start.
- Resolving task identity from a generated directory when an exact saved project ID exists.
- Treating one wait timeout as terminal failure without reading fresh task state.
- Using only an attempt count when the wait tool can return immediately.
- Requesting more than the task-read item limit or ignoring structured `items`.
- Slicing JSON to fit a prompt instead of using a compact handoff contract and expansion queue.
- Treating the compact handoff as the only evidence store and losing source locators or required fields.
- Letting an audit invent a cutoff, sample size, or scope that conflicts with the declared pilot.
- Asking one repair worker to fix every record and evidence dimension without record-specific correction shards and one canonical-schema integration.
- Passing a repair transport shape directly to a formatter that expects a different record schema.
- Applying a strict shape guard before a declared deterministic transport adapter.
- Discarding task, agent, or command handles while work may still be running.
- Creating a replacement task when a valid resume handle exists.
- Requiring resume handles for later nodes that are still `not_started`.
- Discarding completed handoffs when one active task exceeds the collection window.
- Calling `exit()` inside a catchable orchestration block and emitting a second terminal result from `catch`.
- Using one broad validator when record batches or audit lenses can be checked independently.
- Emitting only a success message without evidence.
- Adding an orchestration framework or repository dependency for a temporary workflow.
