import json
import tempfile
import unittest
from pathlib import Path

try:
    from auto_release import compute_next_version, determine_bump, rewrite_release_files
except ModuleNotFoundError:
    from scripts.auto_release import compute_next_version, determine_bump, rewrite_release_files


class AutoReleaseTests(unittest.TestCase):
    def test_bump_levels_and_highest_wins(self):
        self.assertEqual(determine_bump(["fix: typo"]), "patch")
        self.assertEqual(determine_bump(["feat: add node"]), "minor")
        self.assertEqual(determine_bump(["fix: x", "refactor!: API"]), "major")
        self.assertEqual(determine_bump(["docs: x\n\nBREAKING CHANGE: API"]), "major")

    def test_version_contents_and_tag_are_bases(self):
        self.assertEqual(
            compute_next_version("0.2.0", "v0.1.0", ["fix: x"], ["v0.1.0"]),
            "0.2.1",
        )
        self.assertEqual(
            compute_next_version("0.2.0", "v0.2.0", ["feat: x"], ["v0.2.0", "v0.3.0"]),
            "0.3.1",
        )

    def test_rewrite_release_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".codex-plugin").mkdir()
            (root / "VERSION").write_text("0.2.0\n")
            (root / ".codex-plugin" / "plugin.json").write_text(
                '{\n  "name": "x",\n  "version": "0.2.0"\n}\n'
            )
            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\nAll notable releases.\n\n## [0.2.0] - 2026-01-01\n\n- Old\n"
            )
            rewrite_release_files(root, "0.2.1", ["fix: one", "docs: two"], "2026-02-03")
            self.assertEqual((root / "VERSION").read_text(), "0.2.1\n")
            self.assertEqual(json.loads((root / ".codex-plugin" / "plugin.json").read_text())["version"], "0.2.1")
            changelog = (root / "CHANGELOG.md").read_text()
            self.assertIn("## [0.2.1] - 2026-02-03\n\n- fix: one\n- docs: two", changelog)
            self.assertLess(changelog.index("[0.2.1]"), changelog.index("[0.2.0]"))


if __name__ == "__main__":
    unittest.main()
