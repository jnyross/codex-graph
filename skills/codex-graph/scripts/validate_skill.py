#!/usr/bin/env python3
"""Top-level structural acceptance for a codex-graph skill bundle."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import graph_coherence  # noqa: E402

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
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
REQUIRED_OWNER_HEADINGS = {
    "references/authority-and-decisions.md": [
        "# Authority and Decisions",
        "## Owned terms",
        "## Authority preflight and topology safety",
        "## Protected-domain mutation gate",
        "## Frozen design review gate",
        "## Decision frontier and answer receipt",
        "## Checkpoint, cutover, and continuation",
        "## Workflow states and outcomes",
    ],
    "references/evidence-and-acceptance.md": [
        "# Evidence and Acceptance",
        "## Owned terms",
        "## Acceptance-capable action path",
        "## Transport proof and completion witnesses",
        "## Monotonic evidence repair",
        "## Target-level evidence chain",
        "## Canonical reconciliation and zero-mutation proof",
        "## Universal acceptance manifest",
        "## Evidence-family field matrix",
        "## Family outcomes",
        "## Terminal derivation and proof scope",
    ],
}
REQUIRED_REFERENCES = {
    "references/topology-library.md",
    "references/code-mode-script-patterns.md",
    "references/task-lifecycle.md",
    "references/reference-seeds.md",
    "references/progressive-complexity.md",
    "references/self-testing.md",
    *REQUIRED_OWNER_HEADINGS,
}


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
    if raw.startswith("'"):
        if len(raw) < 2 or not raw.endswith("'"):
            fail("unterminated single-quoted YAML scalar")
        inner = raw[1:-1]
        if not re.fullmatch(r"(?:[^']|'')*", inner):
            fail(f"invalid single-quoted YAML scalar: {raw!r}")
        return inner.replace("''", "'")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _./$:+-]*", raw):
        fail(f"unsupported YAML scalar: {raw!r}")
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
    lines = [
        line
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not lines or lines[0] != "interface:":
        fail("agents/openai.yaml must start with an interface mapping")

    result: dict[str, str] = {}
    for line in lines[1:]:
        match = re.fullmatch(r"  ([A-Za-z0-9_-]+):\s*(.+)", line)
        if not match:
            fail(f"malformed agents/openai.yaml line: {line!r}")
        key, raw_value = match.groups()
        if key in result:
            fail(f"duplicate agents/openai.yaml interface key: {key}")
        result[key] = parse_scalar(raw_value)

    expected = {"display_name", "short_description", "default_prompt"}
    if set(result) != expected:
        missing = sorted(expected - set(result))
        extra = sorted(set(result) - expected)
        fail(
            "agents/openai.yaml interface keys differ: "
            f"missing={missing}, extra={extra}"
        )
    return result


def require_headings(path: Path, headings: list[str]) -> None:
    present = set(path.read_text(encoding="utf-8").splitlines())
    for heading in headings:
        if heading not in present:
            fail(f"{path.name} is missing required heading: {heading}")


def validate_machine_data(root: Path, markdown_files: list[Path]) -> None:
    for path in sorted(root.rglob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            fail(f"malformed machine data in {path.relative_to(root)}: {exc}")

    fenced_json = re.compile(r"(?ms)^```json\s*\n(.*?)^```\s*$")
    for path in markdown_files:
        for index, block in enumerate(fenced_json.findall(path.read_text(encoding="utf-8")), 1):
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                fail(
                    f"malformed fenced JSON {index} in "
                    f"{path.relative_to(root)}: {exc}"
                )


def validate_relative_links(root: Path, markdown_files: list[Path]) -> None:
    link_pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
    for path in markdown_files:
        text = re.sub(
            r"(?ms)^[ \t]*```[^\n]*\n.*?^[ \t]*```[ \t]*$",
            "",
            path.read_text(encoding="utf-8"),
        )
        for raw_target in link_pattern.findall(text):
            target = raw_target.strip()
            if (
                not target
                or target.startswith(("#", "/", "http://", "https://", "mailto:"))
            ):
                continue
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            target = unquote(target.split("#", 1)[0])
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                fail(f"{path.relative_to(root)} links outside the bundle: {raw_target}")
            if not resolved.exists():
                fail(
                    f"broken relative link in {path.relative_to(root)}: "
                    f"{raw_target}"
                )


def validate_markdown_and_graphs(root: Path, markdown_files: list[Path]) -> None:
    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        fence_count = sum(
            1 for line in text.splitlines() if re.match(r"^\s*```", line)
        )
        if fence_count % 2:
            fail(f"unbalanced Markdown fences in {path.relative_to(root)}")

    graph_files = [*markdown_files, *sorted(root.rglob("*.mmd"))]
    for path in graph_files:
        problems = graph_coherence.check_text(path.read_text(encoding="utf-8"))
        if problems:
            fail(
                f"{path.relative_to(root)} has incoherent diagram(s): "
                + "; ".join(problems[:6])
            )


def validate(root: Path) -> None:
    root = root.resolve()
    skill = root / "SKILL.md"
    openai_yaml = root / "agents" / "openai.yaml"
    if not skill.is_file():
        fail("SKILL.md is missing")
    if not openai_yaml.is_file():
        fail("agents/openai.yaml is missing")

    missing = sorted(path for path in REQUIRED_REFERENCES if not (root / path).is_file())
    if missing:
        fail(f"missing references: {', '.join(missing)}")

    text = skill.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(text)
    if set(metadata) != {"name", "description"}:
        fail("frontmatter must contain only name and description")
    if metadata["name"] != root.name:
        fail("frontmatter name must match the skill directory")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", metadata["name"]):
        fail("skill name must be lower-case kebab-case")
    if not 1 <= len(metadata["description"]) <= 1024:
        fail("description must be 1–1024 characters")
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

    for relative_path, headings in REQUIRED_OWNER_HEADINGS.items():
        require_headings(root / relative_path, headings)

    interface = read_openai_interface(openai_yaml.read_text(encoding="utf-8"))
    if not 25 <= len(interface["short_description"]) <= 64:
        fail("short_description should be 25–64 characters")
    if "$codex-graph" not in interface["default_prompt"]:
        fail("default_prompt must explicitly invoke the skill")

    markdown_files = sorted(root.rglob("*.md"))
    validate_machine_data(root, markdown_files)
    validate_relative_links(root, markdown_files)
    validate_markdown_and_graphs(root, markdown_files)


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        fail("usage: validate_skill.py [skill-root]")
    validate(Path(args[0]) if args else DEFAULT_ROOT)
    print("PASS: skill bundle structural acceptance is valid")


if __name__ == "__main__":
    main()
