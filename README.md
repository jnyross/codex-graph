# codex-graph

A Codex skill that turns a free-form goal into two matched outputs:

1. a human-readable agent workflow with explicit nodes, joins, gates, and one bounded repair stage;
2. a complete paste-ready JavaScript program for Codex Code Mode.

The skill includes field-tested rules for saved-project binding, pending task setup, structured task output, bounded handoffs, resumable checkpoints, audit fan-out, canonical schemas, and single-emission terminal results.

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

## Repository layout

- `.agents/plugins/marketplace.json` — URL marketplace registration
- `.codex-plugin/plugin.json` — Codex plugin manifest
- `skills/codex-graph/SKILL.md` — main skill instructions
- `skills/codex-graph/agents/openai.yaml` — Codex skill metadata
- `skills/codex-graph/references/` — topology, lifecycle, script, and source guidance
- `skills/codex-graph/scripts/validate_skill.py` — structural and contract checks

## Status

Preview release. The bundled validator passes. Use generated workflows in a test workspace before consequential use.

## License

MIT
