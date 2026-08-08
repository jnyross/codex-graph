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
to lint, or pipe a diagram in on stdin:

```bash
python3 skills/codex-graph/scripts/graph_coherence.py skills/codex-graph/SKILL.md
python3 skills/codex-graph/scripts/graph_coherence.py < diagram.mmd
```

On Windows, run the validator, graph-coherence linter, and task-collection
regression suite from Codex Desktop's terminal:

```powershell
.\scripts\run_windows_regressions.ps1
```

The regression suite uses only Node's built-in test runner and simulates the
active task tool. It covers cursor forwarding, cursorless snapshot
deduplication, the 20,000-character item limit, delayed completion, bounded
stall handling, and schema-valid terminal handoffs.

## Add regression coverage with new features

Every pull request runs the Windows suite automatically. When a feature
changes orchestration behavior, add a scenario to
`skills/codex-graph/scripts/task_collection_harness.test.js` before opening
the pull request. The pull request template records the Windows command and
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

## Status

Preview release. The bundled validator passes. Use generated workflows in a test workspace before consequential use.

## License

MIT
