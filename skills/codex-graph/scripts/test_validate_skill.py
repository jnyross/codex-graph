import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BUNDLE = Path(__file__).resolve().parents[1]
VALIDATOR = BUNDLE / "scripts" / "validate_skill.py"


def run_validator(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(root)],
        capture_output=True,
        text=True,
    )

def append_to_skill(root: Path, text: str) -> None:
    path = root / "SKILL.md"
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")

def replace_skill_link(root: Path, target: str) -> None:
    path = root / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace(f"({target})", f"(https://example.com/{Path(target).stem})"),
        encoding="utf-8",
    )


def move_heading_into_fence(root: Path, relative_path: str, heading: str) -> None:
    path = root / relative_path
    text = path.read_text(encoding="utf-8").replace(heading, heading.removeprefix("## "), 1)
    path.write_text(
        text + f"\n```markdown\n{heading}\n```\n",
        encoding="utf-8",
    )


class SkillBundleAcceptanceTests(unittest.TestCase):
    def test_real_bundle_and_structural_negative_controls(self):
        self.assertEqual(run_validator(BUNDLE).returncode, 0)

        with self.subTest(name="angle-bracketed HTTPS"), tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "codex-graph"
            shutil.copytree(BUNDLE, root)
            append_to_skill(root, "\n[Official](<https://example.com/docs>)\n")
            result = run_validator(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        cases = {
            "missing owner": lambda root: (root / "references" / "authority-and-decisions.md").unlink(missing_ok=True),
            "missing heading": lambda root: (root / "references" / "authority-and-decisions.md").write_text("# Authority and Decisions\n"),
            "missing authority owner link": lambda root: replace_skill_link(
                root, "references/authority-and-decisions.md"
            ),
            "missing evidence owner link": lambda root: replace_skill_link(
                root, "references/evidence-and-acceptance.md"
            ),
            "required heading only in fence": lambda root: move_heading_into_fence(
                root,
                "references/authority-and-decisions.md",
                "## Protected-domain mutation gate",
            ),
            "broken relative link": lambda root: append_to_skill(
                root, "\n[missing](references/missing.md)\n"
            ),
            "malformed machine data": lambda root: (root / "broken.json").write_text("{not json}\n"),
            "malformed YAML": lambda root: (
                root / "agents" / "openai.yaml"
            ).write_text(
                (root / "agents" / "openai.yaml")
                .read_text(encoding="utf-8")
                .replace('"Codex Graph Prompt"', "'"),
                encoding="utf-8",
            ),
            "orphaned graph node": lambda root: append_to_skill(
                root,
                "\n```mermaid\nflowchart TD\n A[Start] --> T[Done]\n X[Orphan]\n```\n",
            ),
            "undefined graph endpoint": lambda root: append_to_skill(
                root,
                "\n```mermaid\nflowchart TD\n A[Start] --> T\n```\n",
            ),
            "path without terminal": lambda root: append_to_skill(
                root,
                "\n```mermaid\nflowchart TD\n A[Start] --> B[Loop]\n B --> A\n```\n",
            ),
        }

        for name, mutate in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "codex-graph"
                shutil.copytree(BUNDLE, root)
                mutate(root)
                result = run_validator(root)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
