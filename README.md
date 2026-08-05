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

On Windows, run the validator and task-collection regression suite from
Codex Desktop's terminal:

```powershell
.\skills\codex-graph\scripts\run_windows_regressions.ps1
```

The regression suite uses only Node's built-in test runner and simulates the
active task tool. It covers cursor forwarding, cursorless snapshot
deduplication, the 20,000-character item limit, delayed completion, bounded
stall handling, and schema-valid terminal handoffs.

## Versioning and releases

The product version is kept in `VERSION` and mirrored in
`.codex-plugin/plugin.json`. Releases use semantic versioning and are published
from matching Git tags:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The release workflow verifies both version files, runs the validator, and
creates the corresponding GitHub release with generated notes. Use
`MAJOR.MINOR.PATCH`: increment the major version for breaking plugin changes,
the minor version for backwards-compatible features, and the patch version for
backwards-compatible fixes.

## Repository layout

- `.agents/plugins/marketplace.json` — URL marketplace registration
- `.codex-plugin/plugin.json` — Codex plugin manifest
- `VERSION` — canonical product version used for GitHub releases
- `.github/workflows/release.yml` — tag verification and release automation
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
