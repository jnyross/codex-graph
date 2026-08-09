# Changelog

All notable product releases are documented here.

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
