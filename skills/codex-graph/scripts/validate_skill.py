#!/usr/bin/env python3
"""Static validation for the codex-graph skill bundle.

Uses only the Python standard library so the validator does not add a package
requirement to the skill.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import graph_coherence  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
OPENAI_YAML = ROOT / "agents" / "openai.yaml"
REQUIRED_REFERENCES = {
    ROOT / "references" / "topology-library.md",
    ROOT / "references" / "code-mode-script-patterns.md",
    ROOT / "references" / "task-lifecycle.md",
    ROOT / "references" / "reference-seeds.md",
    ROOT / "references" / "progressive-complexity.md",
    ROOT / "references" / "self-testing.md",
}
EXACT_SENTENCE = (
    "Write a code-mode script that implements "
    "this exact workflow and run it…"
)
REQUIRED_OUTPUT_HEADINGS = [
    "# Part 1 — Workflow Design",
    "## Objective",
    "## Known context and assumptions",
    "## Success criteria",
    "## Complexity ladder",
    "## Workflow graph",
    "## Node contracts",
    "## Constraints and guardrails",
    "## Rationale",
    "## References & Links",
    "# Part 2 — Code Mode Script",
    "## Execution instruction",
    "## Runtime and tool bindings",
    "## Script",
    "## How to run",
    "## Direct-subagent fallback",
    "## Expected terminal output",
]


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def parse_scalar(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith('"'):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            fail(f"invalid double-quoted YAML scalar: {exc}")
        if not isinstance(value, str):
            fail("expected a string scalar")
        return value
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1].replace("''", "'")
    return raw


def parse_flat_mapping(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_-]+):\s*(.*)", line)
        if not match:
            fail(f"unsupported frontmatter line: {line!r}")
        key, raw_value = match.groups()
        if key in result:
            fail(f"duplicate frontmatter key: {key}")
        result[key] = parse_scalar(raw_value)
    return result


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, flags=re.DOTALL)
    if not match:
        fail("SKILL.md has no valid YAML frontmatter block")
    return parse_flat_mapping(match.group(1)), match.group(2)


def read_openai_interface(text: str) -> dict[str, str]:
    if not re.search(r"(?m)^interface:\s*$", text):
        fail("agents/openai.yaml must contain an interface mapping")
    result: dict[str, str] = {}
    for key in ("display_name", "short_description", "default_prompt"):
        match = re.search(rf"(?m)^\s{{2}}{key}:\s*(.+?)\s*$", text)
        if not match:
            fail(f"agents/openai.yaml is missing interface.{key}")
        result[key] = parse_scalar(match.group(1))
    return result


def main() -> None:
    if not SKILL.is_file():
        fail("SKILL.md is missing")
    if not OPENAI_YAML.is_file():
        fail("agents/openai.yaml is missing")
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_REFERENCES if not path.is_file()]
    if missing:
        fail(f"missing references: {', '.join(sorted(missing))}")

    text = SKILL.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(text)

    if set(metadata) != {"name", "description"}:
        fail("frontmatter must contain only name and description")
    if metadata["name"] != ROOT.name:
        fail("frontmatter name must match the skill directory")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", metadata["name"]):
        fail("skill name must be lower-case kebab-case")
    if not 1 <= len(metadata["description"]) <= 1024:
        fail("description must be 1–1024 characters")
    if len(text.splitlines()) > 500:
        fail("SKILL.md exceeds 500 lines")
    if text.count(EXACT_SENTENCE) != 1:
        fail("the exact required execution sentence must occur once in SKILL.md")

    positions = []
    for heading in REQUIRED_OUTPUT_HEADINGS:
        position = body.find(f"`{heading}`")
        if position < 0:
            fail(f"missing output-contract heading: {heading}")
        positions.append(position)
    if positions != sorted(positions):
        fail("output-contract headings are not listed in the required order")

    for required_phrase in [
        "complete JavaScript",
        "Do not merely tell a later Codex turn to write the script",
        "Promise.allSettled",
        "ALL_TOOLS",
        "repairUsed",
        "Direct-subagent fallback",
        "clientThreadId",
        "maxOutputCharsPerItem",
        "saved Codex project",
        "expansion queue",
        "staged fan-in",
        "observed run demonstrates a limit",
        "baseline tier",
        "always active at baseline",
        "reported as skipped",
        "not_evaluated",
        "none-declared",
        "four verdict states",
        "fenced JSON verdict block",
        "same trigger set",
        "baseline executable nodes only",
        "escalation gates are excluded",
        "self-testing protocol",
        "isolated child thread",
        "roadmap items",
        "bounded self-test repair",
        "Separate artifact lifecycle from the work graph",
        "stable references to them as",
        "Keep scoring and evaluation harnesses outside the core work graph",
        "repeatable work execution",
        "complete and reachable",
        "Many files \u2260 parallel",
        "graph_coherence.py",
    ]:
        if required_phrase not in text:
            fail(f"missing required behavior: {required_phrase}")

    interface = read_openai_interface(OPENAI_YAML.read_text(encoding="utf-8"))
    if not 25 <= len(interface["short_description"]) <= 64:
        fail("short_description should be 25–64 characters")
    if "$codex-graph" not in interface["default_prompt"]:
        fail("default_prompt must explicitly invoke the skill")

    lifecycle = (ROOT / "references" / "task-lifecycle.md").read_text(encoding="utf-8")
    for required_phrase in [
        "clientThreadId",
        "exact project ID",
        "structured `items`",
        "maxOutputCharsPerItem",
        "expansion_queue",
        "active tool contract",
        "staged fan-in",
        "resumable handles",
        "same-model retry",
        "every still-live handle",
        "requested title in `summary`",
        "terminalEmitted",
        "Resume without duplicate tasks",
        "`not_started`",
        "task-specific deadline",
        "active-tool limit or observed condition",
    ]:
        if required_phrase not in lifecycle:
            fail(f"task lifecycle reference is missing: {required_phrase}")

    self_testing = (ROOT / "references" / "self-testing.md").read_text(encoding="utf-8")
    for required_phrase in [
        "candidate bundle",
        "portable skill_name",
        "installable skill artifact",
        "allow_nested_self_test",
        "one bounded test run",
        "Reject malformed",
        "observed roadmap",
        "One repair and re-run",
        "fresh child thread",
        "still-live handles",
        "evaluation harness outside the work graph",
        "fixed eval cases",
        "Scoring remains in the harness",
    ]:
        if required_phrase not in self_testing:
            fail(f"self-testing reference is missing: {required_phrase}")

    patterns = (ROOT / "references" / "code-mode-script-patterns.md").read_text(encoding="utf-8")
    if "return `${rendered.slice" in patterns:
        fail("code patterns must not slice serialized JSON")
    for required_phrase in [
        "routing index, not the authoritative evidence store",
        "Do not impose a character budget",
        "observed transport limit",
        "staged validation fan-in",
        "Freeze one acceptance and schema contract",
        "canonical record schema",
        "record-specific correction shards",
        "transport forms and their adapters",
        "Keep prerequisite artifacts outside the graph",
        "separate artifact lifecycle",
        "stable references to prerequisite artifacts",
    ]:
        if required_phrase not in patterns:
            fail(f"code patterns are missing verified graph lesson: {required_phrase}")

    topology = (ROOT / "references" / "topology-library.md").read_text(encoding="utf-8")
    for required_phrase in [
        "Artifact boundary",
        "Create and version prerequisite artifacts separately",
        "scoring",
        "not graph nodes",
    ]:
        if required_phrase not in topology:
            fail(f"topology reference is missing artifact boundary rule: {required_phrase}")

    for node_id in ("V1A", "V1B", "V1C", "V1D", "G1"):
        if node_id not in topology:
            fail(f"research audit fan-out is missing node: {node_id}")

    complexity = (
        ROOT / "references" / "progressive-complexity.md"
    ).read_text(encoding="utf-8")
    for required_phrase in [
        "L0 direct",
        "L1 delegated",
        "L2 parallel discovery",
        "L3 independent validation",
        "L4 sharded recovery",
        "Trigger table",
        "Anti-triggers",
        "never demote",
        "no demotion",
        "escalationsUsed",
        "one repair total regardless of tier",
        "T1-WORKER-NEED",
        "T2-DISJOINT-READ-SCOPES",
        "T3-INDEPENDENT-LENSES",
        "T4-SHARDED-RECOVERY",
        "Escalation action mapping",
        "probe node `P1`",
        "verdicts fail closed",
        "not_evaluated",
        "none-declared",
        "state: \"fired\"|\"not_fired\"|\"not_evaluated\"|\"not_applicable\"",
        "exactly one state",
        "not_applicable",
        "fenced JSON verdict block",
        "same trigger set",
    ]:
        if required_phrase not in complexity:
            fail(f"progressive complexity reference is missing: {required_phrase}")

    # Structural coherence of every Mermaid diagram in the bundle.
    # A diagram with an orphan, a dead end, or an unreachable node is not
    # executable as designed, regardless of how the prose describes it.
    for markdown_file in [SKILL, *sorted(REQUIRED_REFERENCES)]:
        problems = graph_coherence.check_text(
            markdown_file.read_text(encoding="utf-8")
        )
        if problems:
            fail(
                f"{markdown_file.relative_to(ROOT)} has incoherent diagram(s): "
                + "; ".join(problems[:6])
            )

    for markdown_file in [SKILL, *sorted(REQUIRED_REFERENCES)]:
        fence_count = sum(
            1 for line in markdown_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("```")
        )
        if fence_count % 2:
            fail(f"unbalanced Markdown fences in {markdown_file.relative_to(ROOT)}")

    print("PASS: skill bundle structure and fixed two-part output contract are valid")


if __name__ == "__main__":
    main()
