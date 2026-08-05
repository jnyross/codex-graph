$ErrorActionPreference = "Stop"

python skills/codex-graph/scripts/validate_skill.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

node --test skills/codex-graph/scripts/task_collection_harness.test.js
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
