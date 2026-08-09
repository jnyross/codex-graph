import json
import tempfile
import unittest
from pathlib import Path

try:
    from auto_release import (
        compute_next_version,
        determine_bump,
        release_subjects,
        rewrite_release_files,
    )
except ModuleNotFoundError:
    from scripts.auto_release import (
        compute_next_version,
        determine_bump,
        release_subjects,
        rewrite_release_files,
    )


def write_release_fixture(root: Path, changelog: str) -> None:
    (root / ".codex-plugin").mkdir()
    (root / "VERSION").write_text("0.2.0\n")
    (root / ".codex-plugin" / "plugin.json").write_text(
        '{\n  "name": "x",\n  "version": "0.2.0"\n}\n'
    )
    (root / "CHANGELOG.md").write_text(changelog)


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

    def test_merge_subjects_are_excluded_from_release_subjects(self):
        self.assertEqual(
            release_subjects(
                [
                    "Merge pull request #12 from example/feature",
                    "feat: add feature",
                ]
            ),
            ["feat: add feature"],
        )

    def test_rewrite_release_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_release_fixture(
                root,
                "# Changelog\n\nAll notable releases.\n\n## [0.2.0] - 2026-01-01\n\n- Old\n",
            )
            rewrite_release_files(root, "0.2.1", ["fix: one", "docs: two"], "2026-02-03")
            self.assertEqual((root / "VERSION").read_text(), "0.2.1\n")
            self.assertEqual(json.loads((root / ".codex-plugin" / "plugin.json").read_text())["version"], "0.2.1")
            changelog = (root / "CHANGELOG.md").read_text()
            self.assertIn("## [0.2.1] - 2026-02-03\n\n- fix: one\n- docs: two", changelog)
            self.assertLess(changelog.index("[0.2.1]"), changelog.index("[0.2.0]"))

    def test_release_consumes_unreleased_section(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_release_fixture(
                root,
                "# Changelog\n\nAll notable releases.\n\n"
                "## Unreleased\n\n"
                "### Fixed\n\n"
                "- fix: one — richer detail about the fix\n"
                "- docs: uncorrelated note\n\n"
                "## [0.2.0] - 2026-01-01\n\n- Old\n",
            )
            rewrite_release_files(root, "0.2.1", ["fix: one (#9)"], "2026-02-03")
            changelog = (root / "CHANGELOG.md").read_text()
            self.assertNotIn("Unreleased", changelog)
            self.assertIn(
                "## [0.2.1] - 2026-02-03\n\n"
                "### Fixed\n\n"
                "- fix: one — richer detail about the fix\n"
                "- docs: uncorrelated note\n\n"
                "## [0.2.0]",
                changelog,
            )
            self.assertEqual(changelog.count("richer detail"), 1)
            self.assertNotIn("- fix: one (#9)", changelog)

    def test_populated_unreleased_appends_unrepresented_subjects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_release_fixture(
                root,
                "# Changelog\n\n## Unreleased\n\n"
                "- fix: one — curated details\n\n"
                "## [0.2.0] - 2026-01-01\n\n- Old\n",
            )
            rewrite_release_files(
                root,
                "0.2.1",
                ["fix: one (#9)", "feat: unrelated (#10)"],
                "2026-02-03",
            )
            changelog = (root / "CHANGELOG.md").read_text()
            self.assertIn(
                "## [0.2.1] - 2026-02-03\n\n"
                "- fix: one — curated details\n\n"
                "- feat: unrelated (#10)\n\n"
                "## [0.2.0]",
                changelog,
            )
            self.assertEqual(changelog.count("fix: one"), 1)
            self.assertEqual(changelog.count("feat: unrelated (#10)"), 1)

    def test_curated_pr_suffix_before_details_suppresses_generated_subject(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_release_fixture(
                root,
                "# Changelog\n\n## Unreleased\n\n"
                "- fix: one (#9) — curated details\n\n"
                "## [0.2.0] - 2026-01-01\n\n- Old\n",
            )
            rewrite_release_files(root, "0.2.1", ["fix: one (#9)"], "2026-02-03")
            changelog = (root / "CHANGELOG.md").read_text()
            self.assertIn(
                "## [0.2.1] - 2026-02-03\n\n"
                "- fix: one (#9) — curated details\n\n"
                "## [0.2.0]",
                changelog,
            )
            self.assertEqual(changelog.count("fix: one (#9)"), 1)

    def test_fenced_heading_does_not_end_unreleased_section(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            curated_body = (
                "\n\n```markdown\n"
                "## literal heading\n"
                "```\n\n"
                "- fix: one — curated details\n\n"
            )
            write_release_fixture(
                root,
                "# Changelog\n\n## Unreleased"
                + curated_body
                + "## [0.2.0] - 2026-01-01\n\n- Old\n",
            )
            rewrite_release_files(
                root,
                "0.2.1",
                ["fix: one (#9)", "feat: unrelated (#10)"],
                "2026-02-03",
            )
            changelog = (root / "CHANGELOG.md").read_text()
            self.assertIn(
                "## [0.2.1] - 2026-02-03"
                + curated_body
                + "- feat: unrelated (#10)\n\n"
                "## [0.2.0]",
                changelog,
            )
            self.assertEqual(changelog.count("fix: one"), 1)
            self.assertEqual(changelog.count("feat: unrelated (#10)"), 1)

    def test_malformed_bracketed_unreleased_heading_is_not_promoted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_release_fixture(
                root,
                "# Changelog\n\n## [Unreleased\n\n- malformed\n\n"
                "## [0.2.0] - 2026-01-01\n\n- Old\n",
            )
            rewrite_release_files(root, "0.2.1", ["fix: generated (#11)"], "2026-02-03")
            changelog = (root / "CHANGELOG.md").read_text()
            self.assertIn("## [Unreleased\n\n- malformed", changelog)
            self.assertIn(
                "## [0.2.1] - 2026-02-03\n\n"
                "- fix: generated (#11)\n\n"
                "## [Unreleased",
                changelog,
            )

    def test_bracketed_unreleased_heading_and_exact_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_release_fixture(
                root,
                "# Changelog\n\n## [Unreleased]\n\n- fix: one (#9)\n\n"
                "## [0.2.0] - 2026-01-01\n\n- Old\n",
            )
            rewrite_release_files(root, "0.2.1", ["fix: one (#9)"], "2026-02-03")
            changelog = (root / "CHANGELOG.md").read_text()
            self.assertNotIn("Unreleased", changelog)
            self.assertEqual(changelog.count("- fix: one (#9)"), 1)

    def test_empty_unreleased_uses_generated_subjects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_release_fixture(
                root,
                "# Changelog\n\n## Unreleased\n\n"
                "## [0.2.0] - 2026-01-01\n\n- Old\n",
            )
            rewrite_release_files(
                root,
                "0.2.1",
                ["fix: one (#9)", "docs: two (#10)"],
                "2026-02-03",
            )
            changelog = (root / "CHANGELOG.md").read_text()
            self.assertNotIn("Unreleased", changelog)
            self.assertIn(
                "## [0.2.1] - 2026-02-03\n\n"
                "- fix: one (#9)\n"
                "- docs: two (#10)\n\n"
                "## [0.2.0]",
                changelog,
            )


if __name__ == "__main__":
    unittest.main()
