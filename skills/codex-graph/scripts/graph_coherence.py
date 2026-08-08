#!/usr/bin/env python3
"""Objective Mermaid graph-coherence linter for the codex-graph skill.

A generated workflow graph is only executable if it is structurally coherent:
every node is defined, none is orphaned, every non-terminal can reach a
terminal, and every node is reachable from some start. This is a pure-stdlib
parser + checker for `flowchart` / `graph` blocks in any flow direction. It
does not classify the graph into a task family — it verifies structural
executability only, so it stays orthogonal to the progressive-complexity tier
model.

Exit codes:
  0  all checked diagrams are coherent (or --selfcheck passed)
  1  any diagram has an incoherence (or --selfcheck found a bug)
  2  nothing to check (no paths and no piped diagram on stdin)

Usage:
  python3 graph_coherence.py <file.md ...>     # lint every Mermaid diagram
  python3 graph_coherence.py < diagram.mmd     # lint a diagram piped on stdin
  python3 graph_coherence.py --selfcheck       # run built-in unit tests
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Inside a ```mermaid fence the direction is optional (Mermaid defaults to TB)
# and the fence delimits the body.
_FENCED_RE = re.compile(
    r"```mermaid[ \t]*\n[ \t]*(?:flowchart|graph)[ \t]*(TD|TB|BT|LR|RL)?[ \t]*;?[ \t]*\n"
    r"(.*?)(?:\n```|\Z)",
    re.DOTALL,
)
# Unfenced, a direction is required and the header must start its own line, so
# prose mentioning the word is not parsed. The body ends at a fence or the next
# header; `_trim_unfenced_body` then drops trailing prose.
_UNFENCED_RE = re.compile(
    r"(?:^|\n)[ \t]*(?:flowchart|graph)[ \t]+(TD|TB|BT|LR|RL)[ \t]*;?[ \t]*\n"
    r"(.*?)"
    r"(?=\n[ \t]*```|"
    r"\n[ \t]*(?:flowchart|graph)[ \t]+(?:TD|TB|BT|LR|RL)[ \t]*;?[ \t]*\n|\Z)",
    re.DOTALL,
)
# Mermaid ids may start with a digit; hyphens are excluded so a link operator is
# never absorbed into an id.
_ID_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_]*")
# Every link form, with an optional inline label: `-->`, `---`, `--x`, `==>`,
# `-.->`, their long forms, and `A -- text --> B` / `A -. text .-> B`. An inline
# label opens with exactly `--` / `==` (a longer run is an unlabelled link) and
# its text may not contain a node shape (`B[b]`), so `A --- B[b] --> C` stays a
# chain instead of collapsing into one labelled link.
_LABEL = r"(?:(?![A-Za-z0-9_]+[\[({])[^|>\n])*?"
_LINK_RE = re.compile(
    r"""\s*(?:[ox](?=[-=.])|<)?\s*
    (?:
        --(?!-)""" + _LABEL + r"""-{2,}[>xo]?
      | ==(?!=)""" + _LABEL + r"""={2,}[>xo]?
      | -\.""" + _LABEL + r"""\.-+[>xo]?
      | -{2,}[>xo]?
      | ={2,}[>xo]?
      | -\.-+[>xo]?
    )\s*""",
    re.VERBOSE,
)
_SHAPE_OPENERS = "[({>"
# Mermaid's inline class shorthand: `A[Start]:::hot --> B`.
_CLASS_RE = re.compile(r":::[A-Za-z0-9_]+")
# Statement keywords that never declare an executable node.
_KEYWORDS = {
    "subgraph",
    "end",
    "direction",
    "classDef",
    "class",
    "style",
    "linkStyle",
    "click",
    "accTitle",
    "accDescr",
}


class Graph:
    def __init__(
        self,
        nodes: List[str],
        labels: Dict[str, str],
        edges: List[Tuple[str, str]],
        unparsed: Optional[List[str]] = None,
    ):
        self.nodes = nodes
        self.labels = labels
        self.edges = edges
        self.unparsed = unparsed or []
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


def _scan_shape(text: str, start: int) -> Optional[Tuple[str, int]]:
    """Scan a node shape starting at an opener; return (label, index after closer).

    Quote-aware and bracket-depth-aware, so `A["Start (init)"]` and `A[[Sub]]`
    are read whole instead of being cut at the first closing bracket.
    """
    if text[start] == ">":
        end = text.find("]", start + 1)
        if end == -1:
            return None
        return text[start + 1 : end], end + 1
    depth = 0
    quoted = False
    index = start
    while index < len(text):
        char = text[index]
        if quoted:
            if char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[({":
            depth += 1
        elif char in "])}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
        index += 1
    return None


def _link_direction(link: str) -> str:
    """Classify a link operator: forward, reverse, or both (bidirectional).

    `A <-- B` flows right-to-left; `A <--> B`, `A o--o B` and `A x--x B` flow both
    ways. A link with no arrowhead (`A --- B`) is read in the direction it is
    drawn, since treating it as bidirectional would make every diagram that opens
    with one rootless.
    """
    operator = link.strip()
    head = operator.startswith(("<", "o", "x"))
    tail = operator.endswith((">", "x", "o"))
    if head:
        return "both" if tail else "reverse"
    return "forward"


def _clean_label(raw: str) -> str:
    return raw.strip().strip("[({])}").strip().strip('"').strip()


def _split_statements(line: str) -> List[str]:
    """Split a line into statements, ignoring `;` and `%%` inside labels.

    Mermaid treats `;` as a separator and `%%` as a comment only outside label
    text, so `A["Fetch data; parse"]` and `A -->|pass; fail| B` stay in one piece.
    """
    statements: List[str] = []
    current: List[str] = []
    depth = 0
    quoted = False
    piped = False
    index = 0
    while index < len(line):
        char = line[index]
        if quoted:
            if char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[({":
            depth += 1
        elif char in "])}":
            depth = max(0, depth - 1)
        elif char == "|" and depth == 0:
            piped = not piped
        elif depth == 0 and not piped:
            if line.startswith("%%", index):
                break
            if char == ";":
                statements.append("".join(current))
                current = []
                index += 1
                continue
        current.append(char)
        index += 1
    statements.append("".join(current))
    return statements


def _parse_statement(
    stmt: str,
    nodes: List[str],
    labels: Dict[str, str],
    edges: List[Tuple[str, str]],
    unparsed: List[str],
) -> List[str]:
    """Parse one statement; return every id it mentions (declared or referenced).

    Chained links and `&` groups are supported. Anything the scanner cannot read
    is recorded in `unparsed` rather than dropped, so the gap stays visible.
    """
    seen: List[str] = []

    def bail(at: int) -> List[str]:
        if stmt[at:].strip():
            unparsed.append(stmt.strip())
        return seen

    def declare(node_id: str, label: Optional[str]) -> None:
        # Only a shape declaration defines a node; a bare id is a reference,
        # so an id that is never given a shape is reported as undefined.
        if label is None:
            return
        if node_id not in nodes:
            nodes.append(node_id)
        labels[node_id] = _clean_label(label)

    index = 0
    length = len(stmt)
    previous: List[str] = []
    direction = "forward"
    while index < length:
        group: List[str] = []
        while True:
            while index < length and stmt[index].isspace():
                index += 1
            match = _ID_RE.match(stmt, index)
            if not match:
                return bail(index)
            node_id = match.group(0)
            index = match.end()
            label: Optional[str] = None
            if index < length and stmt[index] in _SHAPE_OPENERS:
                scanned = _scan_shape(stmt, index)
                if scanned is None:
                    return bail(index)
                label, index = scanned
            while True:
                node_class = _CLASS_RE.match(stmt, index)
                if not node_class:
                    break
                index = node_class.end()
            declare(node_id, label)
            if node_id not in seen:
                seen.append(node_id)
            group.append(node_id)
            probe = index
            while probe < length and stmt[probe].isspace():
                probe += 1
            if probe < length and stmt[probe] == "&":
                index = probe + 1
                continue
            break
        # A written self-link (`V1 -->|retry| V1`) is a real unbounded loop and
        # must survive; only duplicates from an `&` expansion are dropped.
        emitted: Set[Tuple[str, str]] = set()
        for a in previous:
            for b in group:
                pairs = []
                if direction in ("forward", "both"):
                    pairs.append((a, b))
                if direction in ("reverse", "both"):
                    pairs.append((b, a))
                for pair in pairs:
                    if pair not in emitted:
                        emitted.add(pair)
                        edges.append(pair)
        previous = group
        link = _LINK_RE.match(stmt, index)
        if not link:
            return bail(index)
        direction = _link_direction(link.group(0))
        index = link.end()
        if index < length and stmt[index] == "|":
            close = stmt.find("|", index + 1)
            if close == -1:
                return bail(index)
            index = close + 1
    return seen


def _expand_container_edges(
    edges: List[Tuple[str, str]],
    members: Dict[str, List[str]],
) -> None:
    """Wire edges on a subgraph id through to the members it stands for.

    Mermaid allows `N1 --> P` / `P --> N3` where `P` is a container: the link
    applies to the whole group. Without this, members wired only via their
    container look orphaned.
    """
    for container, group in members.items():
        inside = set(group)
        if not inside:
            continue
        internal = [(a, b) for a, b in edges if a in inside and b in inside]
        entries = [m for m in group if not any(b == m for _, b in internal)]
        exits = [m for m in group if not any(a == m for a, _ in internal)]
        incoming = [a for a, b in list(edges) if b == container and a not in inside]
        outgoing = [b for a, b in list(edges) if a == container and b not in inside]
        for source in incoming:
            for entry in entries:
                if (source, entry) not in edges:
                    edges.append((source, entry))
        for target in outgoing:
            for exit_node in exits:
                if (exit_node, target) not in edges:
                    edges.append((exit_node, target))


def parse_flowchart(body: str) -> Graph:
    nodes: List[str] = []
    labels: Dict[str, str] = {}
    edges: List[Tuple[str, str]] = []
    subgraph_ids: Set[str] = set()
    members: Dict[str, List[str]] = {}
    open_containers: List[str] = []
    unparsed: List[str] = []
    statements = [
        stmt for raw_line in body.splitlines() for stmt in _split_statements(raw_line)
    ]
    for raw_statement in statements:
        line = raw_statement.strip()
        if not line:
            continue
        head = line.split(None, 1)[0].split("[", 1)[0].split("(", 1)[0]
        if head in _KEYWORDS:
            # A subgraph header declares a container, not an executable node.
            # Its id is only a node when it is also used as an edge endpoint.
            if head == "subgraph":
                remainder = line[len("subgraph") :].strip()
                container = _ID_RE.match(remainder)
                container_id = container.group(0) if container else f"__anon{len(members)}"
                subgraph_ids.add(container_id)
                members.setdefault(container_id, [])
                open_containers.append(container_id)
            elif head == "end" and open_containers:
                open_containers.pop()
            continue
        mentioned = _parse_statement(line, nodes, labels, edges, unparsed)
        # A node may be declared before its subgraph and only listed by id
        # inside it, so every id a statement mentions counts as a member.
        for container_id in open_containers:
            for node_id in mentioned:
                if node_id not in members[container_id]:
                    members[container_id].append(node_id)
    _expand_container_edges(edges, members)
    endpoints = {n for edge in edges for n in edge}
    nodes = [n for n in nodes if n not in subgraph_ids or n in endpoints]
    # Mermaid allows a subgraph id as an edge endpoint; then it is a real node.
    nodes.extend(sorted(s for s in subgraph_ids if s in endpoints and s not in nodes))
    return Graph(nodes, labels, edges, unparsed)


def check_graph(g: Graph) -> List[str]:
    """Return coherence violations for one parsed graph (empty = coherent)."""
    violations: List[str] = []
    # An unreadable statement is reported, never skipped: a silently dropped line
    # would hide the node it declares and fake undefined endpoints downstream.
    for stmt in g.unparsed:
        violations.append(f"unparsed diagram statement: {stmt}")
    if not g.nodes and not g.edges:
        violations.append("empty diagram: no nodes parsed")
        return violations
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


def _is_statement_like(line: str) -> bool:
    """Is this line readable as a Mermaid statement (as opposed to prose)?"""
    stripped = line.strip()
    if not stripped:
        return True
    head = stripped.split(None, 1)[0].split("[", 1)[0].split("(", 1)[0]
    if head in _KEYWORDS:
        return True
    residue: List[str] = []
    _parse_statement(stripped, [], {}, [], residue)
    return not residue


def _trim_unfenced_body(body: str) -> str:
    """Drop trailing prose from an unfenced diagram body.

    A blank line inside a diagram is only a grouping device (common in `.mmd`
    files, indented or flush-left), so the body runs on while what follows still
    reads as a statement; a blank line followed by prose ends the diagram.
    """
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if line.strip():
            continue
        following = next((later for later in lines[index + 1 :] if later.strip()), None)
        if following is None or not _is_statement_like(following):
            return "\n".join(lines[:index])
    return body


def extract_blocks(text: str) -> List[Tuple[str, str]]:
    """Return list of (mermaid_direction, diagram_body) for each flowchart block."""
    found: List[Tuple[int, str, str]] = []
    fenced_spans: List[Tuple[int, int]] = []
    for match in _FENCED_RE.finditer(text):
        fenced_spans.append(match.span())
        found.append((match.start(), match.group(1) or "TB", match.group(2)))
    for match in _UNFENCED_RE.finditer(text):
        # A header inside a fence is already covered by the fenced match.
        if any(start <= match.start() < end for start, end in fenced_spans):
            continue
        found.append((match.start(), match.group(1), _trim_unfenced_body(match.group(2))))
    return [(direction, body) for _, direction, body in sorted(found)]


def check_text(text: str) -> List[str]:
    """Lint every flowchart block in a document. Returns aggregated violations."""
    # Windows checkouts hand us CRLF; without normalising, no diagram would match
    # and every document would pass vacuously.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
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
    "chained": (
        "flowchart TB\n"
        "    A[Start] --> B[Work] --> T[Done]\n"
    ),
    "link_variants": (
        "flowchart LR\n"
        "    A[Start] ==> B[Work]\n"
        "    B -.-> C[Check]\n"
        "    C -- gate passes --> T[Done]\n"
    ),
    "quoted_label": (
        "flowchart TD\n"
        '    A["Start (init)"] --> B[Work]\n'
        "    B --> T[Done]\n"
    ),
    "subgraph": (
        "flowchart TD\n"
        "    subgraph S1[Discovery]\n"
        "        A[Start] --> B[Work]\n"
        "    end\n"
        "    B --> T[Done]\n"
    ),
    "semicolon_in_label": (
        "flowchart TD\n"
        '    A["Fetch data; parse"] --> B[Work]\n'
        "    B --> T[Done]\n"
    ),
    "container_edges": (
        "flowchart TD\n"
        "    subgraph P[Parallel]\n"
        "        N2A[Left]\n"
        "        N2B[Right]\n"
        "    end\n"
        "    N1[Start] --> P\n"
        "    P --> N3[Join]\n"
    ),
    "container_members_by_reference": (
        "flowchart TD\n"
        "    N2A[Left]\n"
        "    N2B[Right]\n"
        "    subgraph P[Parallel]\n"
        "        N2A\n"
        "        N2B\n"
        "    end\n"
        "    N1[Start] --> P\n"
        "    P --> N3[Join]\n"
    ),
    "link_directions": (
        "flowchart LR\n"
        "    A[Start] --- B[Work]\n"
        "    T[Done] <-- B\n"
        "    B <--> C[Peer]\n"
    ),
    "hyphenated_edge_label": (
        "flowchart TD\n"
        "    A[Start] -- repair-required --> B[Repair]\n"
        "    B --> T[Done]\n"
    ),
    "tight_spacing": (
        "graph LR\n"
        "    A[Start]-->|go|B[Work];B-->T[Done];\n"
    ),
    "fan_out": (
        "flowchart TD\n"
        "    A[Start] --> B[Left] & C[Right]\n"
        "    B & C --> T[Join]\n"
    ),
    "orphan": (
        "flowchart TD\n"
        "    A[Start] --> B[Work]\n"
        "    B --> T1[Return evidence]\n"
        "    X[Orphaned node]\n"
    ),
    "orphan_other_direction": (
        "flowchart TB\n"
        "    A[Start] --> B[Work]\n"
        "    B --> T1[Return evidence]\n"
        "    X[Orphaned node]\n"
    ),
    "orphan_no_direction": (
        "```mermaid\n"
        "flowchart\n"
        "    A[Start] --> B[Work]\n"
        "    X[Orphaned node]\n"
        "```\n"
    ),
    "orphan_semicolon_header": (
        "flowchart TD;\n"
        "    A[Start] --> B[Work]\n"
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
    "self_loop": (
        "flowchart TD\n"
        "    A[Start] --> V1[Validation gate]\n"
        "    V1 -->|retry| V1\n"
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
    "crlf_orphan": (
        "```mermaid\r\n"
        "flowchart TD\r\n"
        "    A[Start] --> T[Done]\r\n"
        "    X[Orphan]\r\n"
        "```\r\n"
    ),
    "unfenced_blank_line_orphan": (
        "flowchart TD\n"
        "    A[Start] --> T[Done]\n"
        "\n"
        "    X[Orphan]\n"
    ),
    "unfenced_flush_left_orphan": (
        "flowchart TD\n"
        "A[Start] --> B[Work]\n"
        "\n"
        "B --> T[Done]\n"
        "X[Orphan]\n"
    ),
    "chained_undefined": (
        "flowchart TD\n"
        "    A[Start] --> B[Work] --> T\n"
    ),
    "inline_label_specials": (
        "flowchart TD\n"
        "    A[Start] -- fetch & parse --> B[Work]\n"
        "    B -- ok (fast) --> T[Done]\n"
    ),
    "unfenced_blank_line_groups": (
        "flowchart TD\n"
        "    A[Start] --> B[Work]\n"
        "\n"
        "    B --> T[Done]\n"
    ),
    "unfenced_flush_left_groups": (
        "flowchart TD\n"
        "A[Start] --> B[Work]\n"
        "\n"
        "B --> T[Done]\n"
    ),
    "circle_cross_links": (
        "flowchart LR\n"
        "    A[Start] --> B[Work]\n"
        "    B o--o C[Peer]\n"
        "    B x--x D[Other]\n"
        "    B --> T[Done]\n"
    ),
    "unfenced_then_prose": (
        "flowchart TD\n"
        "    A[Start] --> B[Work]\n"
        "    B --> T[Done]\n"
        "\n"
        "Some prose after the diagram.\n"
    ),
    "two_unfenced_diagrams": (
        "flowchart TD\n"
        "    A[Start] --> T[Done]\n"
        "\n"
        "graph LR\n"
        "    C[Begin] --> D[End]\n"
    ),
    "pipe_label_semicolon": (
        "flowchart TD\n"
        "    A[Start] -->|pass; fail| B[Work]\n"
        "    B --> T[Done]\n"
    ),
    "class_shorthand": (
        "flowchart TD\n"
        "    A[Start]:::hot --> B[Work]\n"
        "    B:::cool --> T[Done]\n"
    ),
    "numeric_id": (
        "flowchart TD\n"
        "    1A[Start] --> B[Work]\n"
        "    B --> T[Done]\n"
    ),
    "unparsed_statement": (
        "flowchart TD\n"
        '    A["Start\n'
        '    continued"] --> B[Work]\n'
        "    B --> T[Done]\n"
    ),
    "shapeless_nodes": (
        "flowchart TD\n"
        "    A --> B\n"
        "    B --> C\n"
    ),
}
_PROSE_NOT_A_DIAGRAM = (
    "Some prose describing a graph flowchart TD\n"
    "Then more prose here about nodes.\n"
)


def selftest() -> int:
    fails = 0

    for name in [
        "coherent",
        "chained",
        "link_variants",
        "quoted_label",
        "subgraph",
        "hyphenated_edge_label",
        "container_edges",
        "container_members_by_reference",
        "semicolon_in_label",
        "pipe_label_semicolon",
        "circle_cross_links",
        "inline_label_specials",
        "unfenced_blank_line_groups",
        "unfenced_flush_left_groups",
        "unfenced_then_prose",
        "two_unfenced_diagrams",
        "class_shorthand",
        "numeric_id",
        "link_directions",
        "tight_spacing",
        "fan_out",
    ]:
        problems = check_text(_SELFTEST[name])
        if problems:
            print(f"  [FAIL] {name} diagram should pass, got:", problems)
            fails += 1
        else:
            print(f"  [ok] {name} diagram passes")

    for name, expect_have in [
        ("orphan", "orphaned nodes"),
        ("orphan_other_direction", "orphaned nodes"),
        ("orphan_no_direction", "orphaned nodes"),
        ("orphan_semicolon_header", "orphaned nodes"),
        ("dead_end", "cannot reach any terminal"),
        ("self_loop", "cannot reach any terminal"),
        ("unreachable", "unreachable from any start"),
        ("undefined_edge", "edge references undefined node"),
        ("chained_undefined", "edge references undefined node"),
        ("shapeless_nodes", "edge references undefined node"),
        ("unparsed_statement", "unparsed diagram statement"),
        ("crlf_orphan", "orphaned nodes with no edges"),
        ("unfenced_blank_line_orphan", "orphaned nodes with no edges"),
        ("unfenced_flush_left_orphan", "orphaned nodes with no edges"),
    ]:
        problems = check_text(_SELFTEST[name])
        if not any(expect_have in p for p in problems):
            print(f"  [FAIL] {name} diagram should report '{expect_have}', got: {problems}")
            fails += 1
        else:
            print(f"  [ok] {name} diagram detected")

    if extract_blocks(_PROSE_NOT_A_DIAGRAM) or check_text(_PROSE_NOT_A_DIAGRAM):
        print("  [FAIL] prose mentioning a header keyword should not parse as a diagram")
        fails += 1
    else:
        print("  [ok] prose mentioning a header keyword is not a diagram")

    return fails


def lint_paths(paths: List[str]) -> List[str]:
    problems: List[str] = []
    for path in paths:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            problems.append(f"{path}: cannot read file: {exc}")
            continue
        for v in check_text(text):
            problems.append(f"{path}: {v}")
    return problems


def _report(problems: List[str]) -> int:
    if not problems:
        print("PASS: all diagrams are coherent")
        return 0
    for p in problems:
        print(f"INCOHERENT: {p}", file=sys.stderr)
    return 1


def main(argv: List[str]) -> int:
    if "--selfcheck" in argv:
        fails = selftest()
        print("graph_coherence selfcheck: " + ("PASS" if fails == 0 else f"{fails} FAIL"))
        return 1 if fails else 0

    paths = [p for p in argv if not p.startswith("--")]
    if paths:
        return _report(lint_paths(paths))
    if not sys.stdin.isatty():
        text = sys.stdin.read()
        if text.strip():
            problems = check_text(text)
            if not problems and not extract_blocks(text):
                print("ERROR: no flowchart diagram found on stdin", file=sys.stderr)
                return 2
            return _report([f"<stdin>: {p}" for p in problems])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
