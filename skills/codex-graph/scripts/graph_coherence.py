#!/usr/bin/env python3
"""Objective Mermaid graph-coherence linter for the codex-graph skill.

A generated workflow graph is only executable if it is structurally coherent:
every node is defined, none is orphaned, every non-terminal can reach a
terminal, and every node is reachable from some start. This is a pure-stdlib
parser + checker for `flowchart TD` / `LR` blocks. It does not classify the
graph into a task family — it verifies structural executability only, so it
stays orthogonal to the progressive-complexity tier model.

Exit codes:
  0  all checked diagrams are coherent (or --selfcheck passed)
  1  any diagram has an incoherence (or --selfcheck found a bug)

Usage:
  python3 graph_coherence.py <file.md ...>     # lint every Mermaid diagram
  python3 graph_coherence.py --selfcheck       # run built-in unit tests
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# A[L], A(L), A{L} -> id, label
_NODE_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*)\s*([\[\(\{])\s*([^\]\)\}]*?)\s*([\]\)\}])")
# A --> B, A[L] --> B[L], and their |edge label| variants (edge labels discarded)
_EDGE_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9_]*)(?:\s*[\[\(\{][^\]\)\}]*[\]\)\}])?\s*-->"
    r"(?:\|[^\n]*?\|)?\s*([A-Za-z][A-Za-z0-9_]*)(?:\s*[\[\(\{][^\]\)\}]*[\]\)\}])?"
)
_BLOCK_RE = re.compile(r"(?:```mermaid\s*\n)?flowchart\s+(TD|LR)\s*\n(.*?)(?:\n```|\Z)", re.DOTALL)


class Graph:
    def __init__(self, nodes: List[str], labels: Dict[str, str], edges: List[Tuple[str, str]]):
        self.nodes = nodes
        self.labels = labels
        self.edges = edges
        self.outdeg = {n: 0 for n in nodes}
        self.indeg = {n: 0 for n in nodes}
        self.children: Dict[str, List[str]] = {n: [] for n in nodes}
        self.parents: Dict[str, List[str]] = {n: [] for n in nodes}
        for a, b in edges:
            if a in self.outdeg:
                self.outdeg[a] += 1
            if b in self.indeg:
                self.indeg[b] += 1
            if a in self.children and b in self.parents:
                self.children[a].append(b)
                self.parents[b].append(a)

    def terminals(self) -> List[str]:
        return [n for n in self.nodes if self.outdeg[n] == 0]

    def roots(self) -> List[str]:
        return [n for n in self.nodes if self.indeg[n] == 0]


def parse_flowchart(body: str) -> Graph:
    nodes: List[str] = []
    labels: Dict[str, str] = {}
    for nm in _NODE_RE.finditer(body):
        nid, _, label, _ = nm.groups()
        if nid not in nodes:
            nodes.append(nid)
        labels[nid] = label.strip()
    edges: List[Tuple[str, str]] = []
    for em in _EDGE_RE.finditer(body):
        a, b = em.groups()
        if a != b:
            edges.append((a, b))
    return Graph(nodes, labels, edges)


def check_graph(g: Graph) -> List[str]:
    """Return coherence violations for one parsed graph (empty = coherent)."""
    violations: List[str] = []
    if not g.nodes:
        return ["empty diagram: no nodes parsed"]
    defined = set(g.nodes)

    # 1. Edges must reference only defined nodes.
    for a, b in g.edges:
        if a not in defined or b not in defined:
            violations.append(f"edge references undefined node: {a} --> {b}")

    # 2. No orphaned nodes (no in-edges and no out-edges).
    orphans = [n for n in g.nodes if g.indeg[n] == 0 and g.outdeg[n] == 0]
    if orphans:
        violations.append("orphaned nodes with no edges: " + ", ".join(orphans))

    # 3. Every non-terminal node must be able to reach a terminal (no dead ends).
    terminals = set(g.terminals())
    reaches_terminal = set(terminals)
    changed = True
    while changed:
        changed = False
        for n in g.nodes:
            if n in reaches_terminal:
                continue
            if any(c in reaches_terminal for c in g.children[n]):
                reaches_terminal.add(n)
                changed = True
    dead_ends = [n for n in g.nodes if n not in reaches_terminal]
    if dead_ends:
        violations.append(
            "nodes cannot reach any terminal (dead end / stranded): "
            + ", ".join(dead_ends)
        )

    # 4. Every node must be reachable from some root (no unreachable islands).
    roots = set(g.roots())
    reached = set(roots)
    stack = list(roots)
    while stack:
        n = stack.pop()
        for c in g.children[n]:
            if c not in reached:
                reached.add(c)
                stack.append(c)
    unreachable = [n for n in g.nodes if n not in reached]
    if unreachable:
        violations.append("nodes unreachable from any start node: " + ", ".join(unreachable))

    return violations


def extract_blocks(text: str) -> List[Tuple[str, str]]:
    """Return list of (mermaid_direction, diagram_body) for each flowchart block."""
    return [(d, b) for d, b in _BLOCK_RE.findall(text)]


def check_text(text: str) -> List[str]:
    """Lint every flowchart block in a document. Returns aggregated violations."""
    problems: List[str] = []
    blocks = extract_blocks(text)
    # Absence of a diagram is not an incoherence (some docs only reference the
    # topology library); the caller asserts a diagram exists where required.
    if not blocks:
        return problems
    for idx, (direction, body) in enumerate(blocks, 1):
        g = parse_flowchart(body)
        for v in check_graph(g):
            problems.append(f"diagram #{idx} ({direction}): {v}")
    return problems


_SELFTEST = {
    "coherent": (
        "flowchart TD\n"
        "    A[Start] --> B[Work]\n"
        "    B --> V1{Validation gate}\n"
        "    V1 -->|pass| T1[Return evidence]\n"
        "    V1 -->|repair| R1[Repair]\n"
        "    R1 --> V2[Revalidate]\n"
        "    V2 --> T1\n"
        "    V2 -->|fail| X1[Stop]\n"
        "    A --> C[Parallel discovery]\n"
        "    C --> B\n"
    ),
    "orphan": (
        "flowchart TD\n"
        "    A[Start] --> B[Work]\n"
        "    B --> T1[Return evidence]\n"
        "    X[Orphaned node]\n"
    ),
    "dead_end": (
        "flowchart TD\n"
        "    A[Start] --> B[Work]\n"
        "    B --> T1[Return evidence]\n"
        "    B --> V1[Validation gate]\n"
        "    V1 --> L[Loop node]\n"
        "    L --> L2[Loop node 2]\n"
        "    L2 --> L\n"
    ),
    "unreachable": (
        "flowchart TD\n"
        "    A[Start] --> T1[Return evidence]\n"
        "    L[Lost node] --> B[Lost node 2]\n"
        "    B --> L\n"
    ),
    "undefined_edge": (
        "flowchart TD\n"
        "    A[Start] --> B\n"
    ),
}


def selftest() -> int:
    fails = 0

    ok = check_text(_SELFTEST["coherent"])
    if ok:
        print("  [FAIL] coherent diagram should pass, got:", ok)
        fails += 1
    else:
        print("  [ok] coherent diagram passes")

    for name, expect_have in [
        ("orphan", "orphaned nodes"),
        ("dead_end", "cannot reach any terminal"),
        ("unreachable", "unreachable from any start"),
        ("undefined_edge", "edge references undefined node"),
    ]:
        problems = check_text(_SELFTEST[name])
        if not any(expect_have in p for p in problems):
            print(f"  [FAIL] {name} diagram should report '{expect_have}', got: {problems}")
            fails += 1
        else:
            print(f"  [ok] {name} diagram detected")

    return fails


def lint_paths(paths: List[str]) -> List[str]:
    problems: List[str] = []
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        for v in check_text(text):
            problems.append(f"{path}: {v}")
    return problems


def main(argv: List[str]) -> int:
    if "--selfcheck" in argv:
        fails = selftest()
        print("graph_coherence selfcheck: " + ("PASS" if fails == 0 else f"{fails} FAIL"))
        return 1 if fails else 0

    paths = [p for p in argv if not p.startswith("--")]
    if not paths:
        print(__doc__)
        return 0
    problems = lint_paths(paths)
    if not problems:
        print("PASS: all diagrams are coherent")
        return 0
    for p in problems:
        print(f"INCOHERENT: {p}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
