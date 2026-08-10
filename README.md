# codex-graph

A Codex skill that turns a free-form goal into two matched outputs:

1. a human-readable agent workflow with explicit nodes, joins, gates, and one bounded repair stage;
2. a complete paste-ready JavaScript program for Codex Code Mode.

The skill includes field-tested rules for progressive minimal-first complexity, saved-project binding, pending task setup, structured task output, bounded handoffs, resumable checkpoints, audit fan-out, canonical schemas, and single-emission terminal results.

It can also run a bounded self-test: package the generated workflow as a
candidate skill, execute it once in an isolated child thread, collect explicit
acceptance evidence, produce an observed improvement roadmap, and perform at
most one evidence-led repair and re-run.

## Install as a Codex plugin

Add this public repository as a plugin marketplace, then install the plugin:

```bash
codex plugin marketplace add jnyross/codex-graph
codex plugin add codex-graph@codex-graph
```

You can also use the full repository URL in the first command:

```bash
codex plugin marketplace add https://github.com/jnyross/codex-graph.git
```

Restart Codex after installation. Then invoke the skill:

```text
$codex-graph
```

### Manual skill install

If your Codex version does not support plugins, clone the repository and copy
`skills/codex-graph` into your Codex skills directory.

## Validate

```bash
python3 skills/codex-graph/scripts/validate_skill.py
```

The skill bundle also ships a Mermaid graph-coherence linter
(`skills/codex-graph/scripts/graph_coherence.py`) that checks generated or
reference diagrams for orphaned, stranded, or unreachable nodes. Pass the files
to lint, or pipe a diagram in on stdin. It exits 1 on an incoherent diagram and
2 when none of the given files contains a diagram, so a mistyped path is never
reported as a pass:

```bash
python3 skills/codex-graph/scripts/graph_coherence.py skills/codex-graph/references/topology-library.md
python3 skills/codex-graph/scripts/graph_coherence.py < diagram.mmd
```

On macOS and Linux, run the full regression suite (validator, graph-coherence
selfcheck, task-collection suite, resolved testcase conformance, and release
automation tests) with:

```bash
npm ci
./scripts/run_regressions.sh
```

On Windows, run the same regression suite from Codex Desktop's terminal:

```powershell
npm ci
.\scripts\run_windows_regressions.ps1
```

The regression suite uses Node's built-in test runner and the pinned Acorn
parser. It simulates the active task tool and covers cursor forwarding,
cursorless snapshot deduplication, the 20,000-character item limit, delayed
completion, bounded
stall handling, schema-valid terminal handoffs, and pattern-derived collection
scenarios (atomic screen fan-out, staged cardinality, adversarial dual
validation).

### Dynamic-workflow test cases

`skills/codex-graph/testcases/` holds six canonical offline cases. Each case
has one `GOAL.md` and one `contract.json`. An explicit case resolves before
generation; the same immutable binding drives generation and structural
validation. Check one generated metadata, Mermaid, and executable artifact set:

```bash
node skills/codex-graph/testcases/harness/check_workflow.js \
  --case atomic-screen-fanout \
  --metadata /path/to/metadata.json \
  --graph /path/to/graph.mmd \
  --script /path/to/workflow.js
```

See `skills/codex-graph/testcases/README.md` for binding, artifact, role, and
verdict semantics.

## Add regression coverage with new features

Every pull request runs the Windows suite automatically. When a feature
changes root-owned reliability behavior, add a scenario to
`skills/codex-graph/scripts/test_root_workflow.py`. For task collection or
generated workflow structure, add a scenario to
`skills/codex-graph/scripts/task_collection_harness.test.js` or a canonical
structural case under `skills/codex-graph/testcases/cases/` before opening the
pull request.
The pull request template records the Windows command and
requires either a named regression case or an explanation for a documentation-
only change.

## Versioning and releases

The product version is kept in `VERSION` and mirrored in
`.codex-plugin/plugin.json`. Every push to `main` runs the automatic release
workflow. It considers commits since the latest `vX.Y.Z` tag and derives the
highest semantic-version bump: `BREAKING CHANGE` (or `!`) is major, `feat` is
minor, and other commits are patch releases. The workflow updates both version
files and `CHANGELOG.md`, commits them back to `main`, tags the commit, and
creates a GitHub release with generated notes. Release commits are ignored by
the workflow to prevent loops. Use conventional commit subjects such as
`feat: add ...`, `fix: correct ...`, or `feat!: change ...`.

## Repository layout

- `.agents/plugins/marketplace.json` — URL marketplace registration
- `.codex-plugin/plugin.json` — Codex plugin manifest
- `VERSION` — canonical product version used for GitHub releases
- `.github/workflows/release.yml` — automatic versioning and release automation
- `skills/codex-graph/SKILL.md` — main skill instructions
- `skills/codex-graph/agents/openai.yaml` — Codex skill metadata
- `skills/codex-graph/references/` — topology, lifecycle, script, and source guidance
- `skills/codex-graph/references/progressive-complexity.md` — authoritative L0-L4 escalation ladder
- `skills/codex-graph/references/self-testing.md` — candidate packaging, child-thread validation, roadmap capture, and bounded repair
- `skills/codex-graph/scripts/validate_skill.py` — structural and contract checks
- `skills/codex-graph/testcases/` — canonical goals, structural contracts, the resolver, and the offline conformance seam

## Status

Preview release. The bundled validator passes. Use generated workflows in a test workspace before consequential use.

## License

MIT
