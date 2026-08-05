# codex-graph

A Codex skill that turns a free-form goal into two matched outputs:

1. a human-readable agent workflow with explicit nodes, joins, gates, and one bounded repair stage;
2. a complete paste-ready JavaScript program for Codex Code Mode.

The skill includes field-tested rules for saved-project binding, pending task setup, structured task output, bounded handoffs, resumable checkpoints, audit fan-out, canonical schemas, and single-emission terminal results.

## Install

Clone this repository into your Codex skills directory:

```bash
git clone https://github.com/jnyross/codex-graph.git ~/.codex/skills/codex-graph
```

Then invoke it in Codex:

```text
$codex-graph
```

## Validate

```bash
python3 scripts/validate_skill.py
```

## Repository layout

- `SKILL.md` — main skill instructions
- `agents/openai.yaml` — Codex skill metadata
- `references/` — topology, lifecycle, script, and source guidance
- `scripts/validate_skill.py` — structural and contract checks

## Status

Preview release. The bundled validator passes. Use generated workflows in a test workspace before consequential use.

## License

MIT
