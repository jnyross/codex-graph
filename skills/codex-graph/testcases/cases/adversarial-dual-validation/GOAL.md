# Goal

Review the draft upgrade guide `docs/UPGRADE.md` in this repository before we
publish it, using two genuinely independent validators, and give me a single
accept/revise decision with evidence.

Rules:

- First assemble the review bundle: the draft, the changelog entries it
  claims to cover, and the commands it tells users to run.
- Then two blind validators in parallel, each with its own fixed criteria:
  - Validator A (accuracy): every claim in the guide matches the code and
    changelog; every command exists and its flags are real. It tries to
    refute the guide, not to confirm it.
  - Validator B (completeness and safety): every breaking change in the
    changelog appears in the guide; rollback guidance exists; no step
    destroys user data without a warning.
- Each validator returns machine-readable JSON: pass or revise, the failed
  criteria with IDs, affected sections, and concrete evidence. A validator
  that returns anything else counts as failed — a malformed or missing
  verdict must never count as a pass.
- Neither validator can accept the guide alone; only the coordinator's gate
  combines both verdicts. If the gate requests changes, apply one bounded
  revision to the named sections only, re-run only the validator(s) that
  failed, then stop either way with the evidence.

The validators only read; the one revision is the only write, limited to
`docs/UPGRADE.md`.
