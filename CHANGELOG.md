# Changelog

All notable product releases are documented here.

## [0.6.3] - 2026-08-14

- WF-05: enforce transport and security admission (#54)

## [0.6.2] - 2026-08-10

- WF-04: Gate designs on exact-revision review (#53)

## [0.6.1] - 2026-08-10

- fix: make Windows regression script runnable in isolated environments (#55)

## [0.6.0] - 2026-08-10

- feat: install reliability contract owners (#52)

## [0.5.8] - 2026-08-10

- feat: replace all six lexical testcase bundles with explicit canonical-goal bindings, normalized structural contracts, one resolver and role-normalized offline conformance verdict (#42)

- WF-02: replace lexical testcases with structural conformance (#51)

## [0.5.7] - 2026-08-10

- WF-03: enforce authority-safe root admission (#50)

## [0.5.6] - 2026-08-09

- fix: require configured await-call helper names to be standalone targets instead of member/property or identifier-suffix matches, and align the slice-generators testcase with the canonical `N3` integration-node vocabulary

- Fix automatic release changelog promotion (#23)

## [0.5.5] - 2026-08-09

- fix: collection read bounds + error-envelope fail-fast — task reads omit `turnLimit` or bound it at 10 (ChatGPT Desktop rejects larger reads; openai/codex#30058) and return the newest turns first so the latest handoff is on the first page ("a clipped window is not proof of absence"); bare-string and error-envelope tool results are classified as tool errors, never as empty snapshots, with a bounded 3-consecutive-error abort embedding the verbatim error in a named blocker; blocked collections embed the last raw read result truncated to a named cap (Lisbon v5+v3 dogfood forensics) (#21)

## [0.5.4] - 2026-08-09

- fix: validator satisfiability + repair correlation contracts — dry-run acceptance validators for a reachable pass verdict, never reuse batch-level validators on subset payloads, target repair from verdict affected IDs, accept only post-repair handoffs on recollect, skip invalid handoff sightings, preserve executed_nodes in blocked and failed terminals (Lisbon dogfood v5) (#18)

## [0.5.3] - 2026-08-09

- fix: matcher name/preview keys, bracketed per-node tag guard with claimed-id exclusion, worktree git preflight (#17)

## [0.5.2] - 2026-08-09

- fix: expectations checker resolves read/wait helper names as call sites so mixed wrapper collectors (direct wait, helper-bound reads) are judged correctly instead of false-failing `read-after-wait`, and declaring `collection` now requires at least one resolved call site so a call-free stub can no longer pass via the ordering carve-out (#20)

## [0.5.1] - 2026-08-09

- docs: cross-link dynamic-workflow test cases into the README (#19)

## [0.5.0] - 2026-08-09

- feat: dynamic-workflow golden test cases under `skills/codex-graph/testcases/` — six case bundles derived from real Grok Rhai and Claude multi-agent orchestration shapes (atomic screen fan-out, slice generators, sealed POV + adversarial fact-check, non-binding synthesis, dual validation, disjoint worktree writers), an offline expectations checker, pattern-derived collection tests, and source-shape research; both regression runners execute the suite (#16)

## [0.4.5] - 2026-08-09

- fix: choose task environment per node (local for read-only, worktree only for writers) and strengthen pending `clientThreadId` resolution (Lisbon dogfood v4) (#14)

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
