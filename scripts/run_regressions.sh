#!/bin/sh
# POSIX mirror of run_windows_regressions.ps1 for macOS and Linux.
set -eu

python3 skills/codex-graph/scripts/validate_skill.py
python3 skills/codex-graph/scripts/graph_coherence.py --selfcheck
node --test skills/codex-graph/scripts/task_collection_harness.test.js
node --test skills/codex-graph/testcases/harness/testcases.test.js
python3 skills/codex-graph/scripts/graph_coherence.py skills/codex-graph/testcases/cases/*/topology.hint.mmd
python3 scripts/test_auto_release.py
