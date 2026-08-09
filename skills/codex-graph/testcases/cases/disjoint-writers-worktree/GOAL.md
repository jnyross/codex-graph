# Goal

Add two independent example generators to this repository and a top-level
index that links them:

1. `examples/csv-report/` — a small self-contained script that turns a CSV
   of monthly totals into a Markdown table, with its own README and one
   fixture input.
2. `examples/json-summary/` — a small self-contained script that summarizes
   a JSON array of events into counts per type, with its own README and one
   fixture input.
3. `examples/README.md` — an index describing both, written last.

Rules:

- The two example directories are fully independent: different inputs,
  different code, no shared helpers. Build them in parallel, each in its own
  isolated working copy so neither can touch the other's files or my
  uncommitted work.
- Before writing anything, scan the repository conventions in parallel:
  applicable AGENTS/README guidance, and how existing scripts are laid out,
  so the examples match house style.
- Validate each example by actually running it against its fixture and
  checking the output shape.
- The final index at `examples/README.md` must be written by the
  coordinator on the real checkout after both examples are integrated — not
  left stranded inside a disposable working copy.
- Keep the diff minimal; no new dependencies.
