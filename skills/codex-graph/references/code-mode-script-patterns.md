# Code Mode script patterns

Use this reference for generic Code Mode JavaScript after the graph design and
activated contracts are approved. Authority-bearing execution also requires
[Authority and Decisions](authority-and-decisions.md); mutation evidence and
acceptance require
[Evidence and Acceptance](evidence-and-acceptance.md). Tailor the script to the
goal; do not copy the skeleton unchanged.

## Runtime facts to design around

- Code Mode evaluates raw JavaScript in a fresh V8 isolate as an async module.
- Nested tools are exposed on the global `tools` object.
- `ALL_TOOLS` contains metadata for enabled and deferred nested tools.
- The runtime is not Node.js: there is no direct filesystem, network, imports, or `console`.
- Use top-level `await` and emit model-visible output with `text(...)`.
- Every promise that matters must be awaited; unawaited promises are discarded when the isolate ends.
- A first-line `// @exec: {...}` pragma can set the outer yield interval and output budget.
- If the outer execution yields with a cell ID, the caller must use the public Code Mode wait operation until the cell completes.

## Keep prerequisite artifacts outside the graph

The script should consume stable references to prerequisite artifacts rather
than creating them as worker stages. Keep eval cases, fixtures, benchmark
corpora, rubrics, reference answers, seed datasets, and scoring harnesses in a
separate artifact lifecycle. The work graph may produce outputs and evidence,
or invoke an existing evaluator as a declared acceptance check, but should not
grow nodes for generating the evaluator or aggregating its score. If the user
asks for a new prerequisite artifact, produce and validate it as a separate
deliverable before wiring its reference into the repeatable graph.

## Prefer semantic tool resolution over hard-coded namespaces

Tool namespaces and multi-agent versions can differ. Resolve an operation from actual metadata, confirm it is callable, and fail closed when it is absent. Every resolved `call` must return the exact-envelope pair from `normalizeToolResult` so string tool payloads are parsed once at the boundary (see the next section).

```javascript
function candidatePropertyNames(name) {
  return [...new Set([
    name,
    name.replace(/[.\-/:]+/g, "_"),
    name.replace(/[.\-/:]+/g, "__"),
  ])];
}

function normalizeToolResult(raw) {
  if (typeof raw !== "string") return { value: raw, raw };
  try {
    return { value: JSON.parse(raw.trim()), raw };
  } catch {
    return { value: raw, raw };
  }
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
          call: async (args) =>
            normalizeToolResult(await tools[propertyName](args)),
        };
      }
    }
  }

  for (const propertyName of candidatePropertyNames(operation)) {
    if (typeof tools[propertyName] === "function") {
      return {
        name: propertyName,
        metadata: { name: propertyName, description: "" },
        call: async (args) =>
          normalizeToolResult(await tools[propertyName](args)),
      };
    }
  }

  if (required) throw new Error(`Required Code Mode tool is unavailable: ${operation}`);
  return null;
}
```

Do not rely on this helper alone when the current declaration already provides an exact name and schema. Prefer the exact exposed declaration and use defensive resolution only for namespace portability. If you resolve a tool without `resolveTool`, still wrap its `call` with `normalizeToolResult` the same way.

## Normalize tool results at the call boundary

A resolved tool can return its complete payload as a JSON string. Any key lookup
on that raw string fails silently.

`resolveTool` returns `{ value, raw }` from each `call`. Use the parsed value
for key lookup. Keep the raw value with the boundary result when an activated
contract requires it:

```javascript
const result = await operation.call(args);
const resultId = findString(result.value, ["resultId", "result_id"]);
```

Parse the complete trimmed string once. Do not apply fenced-block or object
fragment extraction to a tool return. Those heuristics can discard parts of a
multi-object response.

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

Use `Promise.allSettled` when partial diagnostics are useful. Inspect every
result and block the scoped stage when a required call fails. Use
`Promise.all` only when one rejection must stop the batch and no partial result
is useful.

When an active tool or observed workload requires a cap, run independent sets
in explicit stages. Join them under one owner. Do not create a worker that
spawns another worker.

## Route visible task lifecycles

When a script creates visible Codex tasks or threads, implement the complete
[Codex task lifecycle](task-lifecycle.md). That module owns project binding,
per-node environments, setup identity, collection, read bounds, resumable
handles, and attempt-level reporting. This generic script module does not
restate those rules.

## Handoffs and joins

Require each worker to return one complete JSON object. Treat it as a routing
index, not the authoritative evidence store. Preserve full evidence in an
approved durable artifact when it exceeds the active transport. Return the
artifact path or identifier and hash.

Build joins from compact manifests or artifact references. Use staged fan-in
only when an observed transport limit requires it. Preserve stable record and
artifact identities. Never slice serialized JSON.

Validate each handoff against one canonical graph-local record shape. Declare
equivalent forms and deterministic adapters before execution. Run adapters
before cardinality and field checks. Reject missing, duplicate, unknown, or
ambiguous references.

A repair worker can use a compact form only when the repair owner normalizes it
before revalidation and formatting. Final formatting rejects missing required
fields instead of guessing a shape or emitting `null`. These adapters do not
define transport completeness or an evidence family. Those rules belong to
[Evidence and Acceptance](evidence-and-acceptance.md).

## Freeze one graph-local work contract

Before workers start, declare the fixed work scope, selection rule, record
fields, validation criteria, and repair boundary. Give the same **contract ID**
and shared field definitions to the stages that consume them. Reject a
validator result that invents a new cutoff or expands the fixed scope. Do not
paste publication or root-gate obligations into mid-graph worker prompts; those
stay with the stages that own them.

For authority-bearing execution, this work contract does not replace the
authority, decision, transport-proof, target-chain, or manifest contracts in
the two reliability owners. Link those owners from the responsible root stages.


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

Dry-run the acceptance validator against a minimal conforming draft before executing; a validator with no reachable pass verdict is a generation defect. Never reuse a batch-level validator on subset payloads; each criterion validates the payload shape it receives. Observed: Lisbon dogfood v5 — the root gate rewrapped each selected candidate as a one-candidate handoff and revalidated it with the batch-level worker validator that requires at least five candidates, so every run failed regardless of input.

When a validator compares URLs or other link fields across artifacts, decode
HTML entities before comparing so markup-escaping differences do not consume
the single repair allowance. RSS and HTML sources routinely deliver `&amp;`,
`&#38;`, or `&#x26;` where the canonical URL holds `&`; these are the same
link, not a provenance defect. Compare canonical forms:

```javascript
function canonicalUrlForComparison(url) {
  if (typeof url !== "string") return url;
  return url
    .replace(/&amp;/gi, "&")
    .replace(/&#0*38;/g, "&")
    .replace(/&#x0*26;/gi, "&")
    .trim();
}
```

Reserve the repair stage for substantive defects; instruct validators to apply
this normalization in their prompts when link fidelity is an acceptance
criterion.

## Exactly one repair, unrolled

Do not use a retry loop. Keep the branch visible.

Select repair targets from the validator verdict's `affected_ids` mapped to node
IDs. Never derive them from a criterion-prefix pattern. When repair uses visible
tasks, follow the corrected-handoff and collection rules in
[Codex task lifecycle](task-lifecycle.md).

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

1. Overall objective and success criteria **as context only** — not as obligations the worker must enforce for the whole graph.
2. The node ID, purpose, and dependencies.
3. Allowed read/write scope.
4. Inputs or upstream handoffs.
5. Required work and explicit non-goals for **this node only**.
6. No nested delegation.
7. Required structured handoff schema for **this node only**.
8. A statement that the worker cannot declare the whole workflow complete.

### Scope worker prompts to node-local obligations

A mid-graph worker is a fresh Codex thread with **no DAG awareness**. If its
prompt embeds the full acceptance contract (publication rule, audit-lane
requirements, root-gate semantics, or later-node schemas), it will apply those
downstream conditions to itself and self-block even when its own inputs are
ready. Observed in the Lisbon family day-trip dogfood: synthesis received the
full publication/audit contract, demanded audit-lane results that only exist
**after** synthesis, returned `status: "blocked"` with zero candidates, and
caused the root to fail closed while three research workers had already
produced complete handoffs.

**Rule:** give each mid-graph worker only its **node-scoped obligations** and
handoff schema. Publication rules, multi-lane audit requirements, root-gate
acceptance, and repair authority stay with the root orchestrator (and with
nodes that own those steps). The fixed **contract ID** and shared field
definitions may appear for vocabulary, but the worker must not be told that
**publication** or **later audit lanes** are its success criteria.

When building `node.prompt` (or equivalent spawn message), include an explicit
scoping sentence, for example:

> Your only obligation is the N3 output schema and the work listed for this
> node. Publication, audit verdicts, and whole-workflow acceptance are owned
> by later nodes and the root gate — do not require them here.

Research and discovery workers: rank and evidence within their topic only.
Synthesis/join workers: produce the canonical draft or join handoff from
upstream complete handoffs; do not wait for audits that run after them.
Audit workers: judge the draft they receive against declared criteria only.
Root/gate/formatter: own publication and terminal write.

### Anti-pattern (contract over-scoping)

- Pasting the full acceptance contract, including publication rule and
  audit-lane requirements, into every worker prompt.
- Telling a synthesis node that "all audit lanes must pass" before it may
  return a draft.
- Letting a worker return `status: "blocked"` solely because a **later**
  graph stage has not run yet.

For a sole writer, add instructions to preserve uncommitted work, inspect applicable `AGENTS.md`, keep the diff small, and report exact changed paths and observed validation.

## Final process output

Build one compact process-terminal object, then emit it once through `text(...)`.
Include executed nodes, artifacts, scoped validation, sources, deviations,
blockers, repair use, and outputs from each activated module.

For authority-bearing work, carry the distinct state or outcome from
[Authority and Decisions](authority-and-decisions.md). Never promote this
process terminal into workflow success. Avoid raw tool dumps when a concise
handoff or artifact reference is sufficient.

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
- Slicing JSON to fit a prompt instead of using a compact handoff contract and expansion queue.
- Treating the compact handoff as the only evidence store and losing source locators or required fields.
- Letting an audit invent a cutoff, sample size, or scope that conflicts with the declared pilot.
- Asking one repair worker to fix every record and evidence dimension without record-specific correction shards and one canonical-schema integration.
- Passing a repair transport shape directly to a formatter that expects a different record schema.
- Applying a strict shape guard before a declared deterministic transport adapter.
- Calling `exit()` inside a catchable orchestration block and emitting a second terminal result from `catch`.
- Using one broad validator when record batches or audit lenses can be checked independently.
- Emitting only a success message without evidence.
- Adding an orchestration framework or repository dependency for a temporary workflow.
- Embedding the full publication rule or later-node audit requirements in a mid-graph worker prompt so the worker self-blocks before those stages run.
