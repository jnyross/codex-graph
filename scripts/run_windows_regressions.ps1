$ErrorActionPreference = "Stop"

npm ci
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python skills/codex-graph/scripts/validate_skill.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python skills/codex-graph/scripts/test_validate_skill.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }


python skills/codex-graph/scripts/test_root_workflow.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python skills/codex-graph/scripts/graph_coherence.py --selfcheck
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

node --test skills/codex-graph/scripts/task_collection_harness.test.js
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

node --test skills/codex-graph/testcases/harness/testcases.test.js
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python scripts/test_auto_release.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
