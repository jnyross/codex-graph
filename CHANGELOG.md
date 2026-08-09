# Changelog

All notable product releases are documented here.

## Unreleased

- fix: choose task environment per node (local for read-only, worktree only for writers) and strengthen pending `clientThreadId` resolution (Lisbon dogfood v4)
- feat: dynamic-workflow golden test cases under `skills/codex-graph/testcases/` — six case bundles derived from real Grok Rhai and Claude multi-agent orchestration shapes (atomic screen fan-out, slice generators, sealed POV + adversarial fact-check, non-binding synthesis, dual validation, disjoint worktree writers), an offline expectations checker (`harness/`), pattern-derived collection tests, and catalog research in `docs/dynamic-workflow-testcase-catalog.md`; both regression runners now execute the new suite and lint the topology hints

## [0.5.0] - 2026-08-09

- feat: dynamic-workflow golden test cases from real orchestration shapes (#16)

## [0.4.5] - 2026-08-09

- fix: per-node environment + pending clientThreadId resolution (#14)

## [0.4.4] - 2026-08-09

- fix: collect handoffs when workers finish before wait sees them (#13)

## [0.4.3] - 2026-08-09

- fix: scope mid-graph worker prompts to node-local obligations (#12)

## [0.4.2] - 2026-08-09

- fix: normalize string tool results and preserve start-failure handles (#11)

## [0.4.1] - 2026-08-09

- Add POSIX regression runner mirroring the Windows suite (#10)

## [0.4.0] - 2026-08-08

- Roll back partial parses and drop the contradictory PASS line
- Report files that contain no diagram instead of passing them
- Allow an indented closing mermaid fence
- Normalize newlines inside extract_blocks
- Continue unfenced bodies past blank lines when statements follow
- Normalize CRLF, allow specials in inline labels, keep blank-line groups
- Support o--o/x--x links and bound unfenced diagram bodies
- Parse pipe edge labels and inline class shorthand
- Report unparsed statements and unreadable files instead of failing silently
- Anchor unfenced diagram headers and report shapeless nodes accurately
- Make statement splitting label-aware and track referenced subgraph members
- Keep self-loops and wire subgraph container edges to members
- Preserve link direction and lint every required reference
- Fix inline edge labels and directionless flowchart headers
- Harden Mermaid coherence parser and lint CLI contract
- feat: add Mermaid graph-coherence linter and graph shape rules

## [0.3.0] - 2026-08-05

- fix: preserve unicode in plugin metadata
- fix: tighten automatic release handling
- feat: automate releases from main
- Document 0.2.0 self-testing release
- Add bounded workflow self-testing

## [0.2.0] - 2026-08-05

- Added bounded workflow self-testing with portable candidate-skill packaging,
  isolated child-thread validation, observed improvement roadmaps, and one
  evidence-led repair and re-run.

## [0.1.0] - 2026-08-05

- Initial versioned release of Codex Graph.
