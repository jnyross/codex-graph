#!/usr/bin/env python3
"""Compute and apply an automatic semantic-version release."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

Version = tuple[int, int, int]


def parse_version(value: str) -> Version:
    match = re.fullmatch(r"\s*v?(\d+)\.(\d+)\.(\d+)\s*", value)
    if not match:
        raise ValueError(f"Invalid semantic version: {value!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def format_version(version: Version) -> str:
    return ".".join(str(part) for part in version)


def determine_bump(commits: Iterable[str]) -> str | None:
    """Return the highest bump represented by commit messages, or None."""
    level = None
    for message in commits:
        header = message.splitlines()[0] if message.splitlines() else message
        if "BREAKING CHANGE" in message or re.match(r"^[^:\s]+(?:\([^)]*\))?!:", header):
            return "major"
        if re.match(r"^feat(?:\([^)]*\))?:", header):
            level = "minor"
        elif level is None and message.strip():
            level = "patch"
    return level


def bump_version(base: Version, level: str) -> Version:
    if level == "major":
        return (base[0] + 1, 0, 0)
    if level == "minor":
        return (base[0], base[1] + 1, 0)
    if level == "patch":
        return (base[0], base[1], base[2] + 1)
    raise ValueError(f"Unknown bump level: {level}")


def compute_next_version(
    current_version: str,
    latest_tag: str | None,
    commits: Sequence[str],
    existing_tags: Iterable[str] = (),
) -> str | None:
    """Compute the next available version above VERSION and the latest tag."""
    level = determine_bump(commits)
    if level is None:
        return None
    bases = [parse_version(current_version)]
    if latest_tag:
        bases.append(parse_version(latest_tag))
    version = max(bases)
    existing = {parse_version(tag) for tag in existing_tags}
    candidate = bump_version(version, level)
    while candidate in existing:
        candidate = bump_version(candidate, "patch")
    return format_version(candidate)


def rewrite_release_files(
    root: str | Path,
    version: str,
    subjects: Sequence[str],
    release_date: str | None = None,
) -> None:
    """Update VERSION, plugin.json, and prepend a changelog release section."""
    root = Path(root)
    version_path = root / "VERSION"
    version_text = version_path.read_text()
    version_path.write_text(version + ("\n" if version_text.endswith("\n") else ""))

    plugin_path = root / ".codex-plugin" / "plugin.json"
    plugin_text = plugin_path.read_text()
    plugin = json.loads(plugin_text)
    plugin["version"] = version
    trailing_newline = "\n" if plugin_text.endswith("\n") else ""
    plugin_path.write_text(json.dumps(plugin, indent=2) + trailing_newline)

    changelog_path = root / "CHANGELOG.md"
    changelog = changelog_path.read_text()
    heading_date = release_date or date.today().isoformat()
    entries = "\n".join(f"- {subject}" for subject in subjects)
    section = f"## [{version}] - {heading_date}\n\n{entries}\n\n"
    marker = "\n## ["
    insertion = changelog.find(marker)
    if insertion == -1:
        changelog = changelog.rstrip() + "\n\n" + section
    else:
        changelog = changelog[: insertion + 1] + section + changelog[insertion + 1 :]
    changelog_path.write_text(changelog)


def release_subjects(commits: Iterable[str]) -> list[str]:
    """Return subjects suitable for release notes and the changelog."""
    return [
        commit.splitlines()[0]
        for commit in commits
        if commit.splitlines()
        and not re.match(r"^Merge pull request #\d+ from ", commit.splitlines()[0])
    ]


def git_output(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True)


def release_commits(root: Path) -> tuple[str | None, list[str]]:
    tags = git_output(root, "tag", "--list", "v*.*.*", "--sort=-version:refname").splitlines()
    latest_tag = tags[0] if tags else None
    revision_range = f"{latest_tag}..HEAD" if latest_tag else "HEAD"
    log = git_output(root, "log", "--no-merges", revision_range, "--format=%s%x00%b%x1e")
    messages = []
    for record in log.split("\x1e"):
        fields = record.strip("\x00\n").split("\x00", 1)
        if len(fields) == 2 and not fields[0].startswith("chore(release):"):
            messages.append(f"{fields[0]}\n{fields[1]}".strip())
    return latest_tag, messages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--date")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    latest_tag, commits = release_commits(root)
    current = (root / "VERSION").read_text().strip()
    tags = git_output(root, "tag", "--list", "v*.*.*").splitlines()
    version = compute_next_version(current, latest_tag, commits, tags)
    if version is None:
        print("No releasable commits since the last release tag.", file=sys.stderr)
        return 0
    subjects = release_subjects(commits)
    rewrite_release_files(root, version, subjects, args.date)
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
