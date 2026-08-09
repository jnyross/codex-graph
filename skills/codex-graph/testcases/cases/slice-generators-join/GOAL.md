# Goal

Build a broad candidate pool of family-friendly holiday destinations by
generating per slice, then merging into one deduplicated pool.

Slices are fixed input data:

- Six regions (Nordics, Iberia, France, Alps, Adriatic, Britain & Ireland),
  quota 4 candidates each. A region generator proposes candidates in its
  region only.
- Four archetypes (city, lake, coast, countryside estate), quota 3 each. An
  archetype generator proposes candidates of its archetype only, spread
  across countries.

Rules:

- Each generator handles exactly one slice and must not propose outside it.
  Every candidate carries name, region, archetype, and a one-sentence why.
- Merging is deterministic: exact name match after trim/lowercase is a
  duplicate; first occurrence wins; a small seed list supplied with the run
  is loaded first and takes priority. Deduplication happens in orchestration
  code, not by asking another agent to deduplicate.
- One owner produces the final merged pool artifact and a per-slice
  contribution count so I can see which slices were thin.
- If a generator returns malformed output, drop it with a logged reason and
  keep going; do not fail the whole pool for one bad slice.

This is read-only research; no repository files change.
