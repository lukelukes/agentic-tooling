"""Checks of this skill's own text that the rewrite CLI contract depends on.

The contract is "Architecture: Worklist view, Resolutions, agent contract",
sections 4 and 5, of the rewrite Boot 4 spec. Exact phrases are asserted only
where the CLI or a human relies on them verbatim: names, schemas, commands and
the never-edit rule.

    python3 -m unittest discover -s skills/rewrite-migration/tests
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SKILL_MD = SKILL / "SKILL.md"


def frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


class SkillTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SKILL_MD.read_text(encoding="utf-8")

    def test_frontmatter_names_the_skill_the_cli_hint_starts(self) -> None:
        fields = frontmatter(self.text)

        self.assertEqual("rewrite-migration", fields.get("name"))
        self.assertEqual("true", fields.get("disable-model-invocation"))
        self.assertTrue(fields.get("description"))

    def test_only_the_read_verify_resolve_and_rules_commands_are_pre_approved(self) -> None:
        self.assertEqual(
            "Bash(rewrite run show *) Bash(rewrite run verify *) Bash(rewrite run resolve *) "
            "Bash(rewrite recipe rules *)",
            frontmatter(self.text).get("allowed-tools"),
        )

    def test_stays_under_500_lines(self) -> None:
        self.assertLess(len(self.text.splitlines()), 500)

    def test_states_the_contract_it_relies_on(self) -> None:
        for phrase in [
            "rewrite.worklist/1",
            "rewrite run show <id> --worklist --json",
            "rewrite run verify <id> --level compile",
            "rewrite run verify <id> --level test",
            "--by agent",
            "rewrite recipe rules --json",
            "`fixed`",
            "`preserved`",
            "`adopted`",
            "`no-change`",
            "`deferred`",
            "`BLOCKER`",
            "`BEHAVIOUR`",
            "`PRESERVED`",
            "dependency resolution",
            "`## <ruleId>`",
        ]:
            with self.subTest(phrase):
                self.assertIn(phrase, self.text)

    def test_forbids_editing_the_oracle(self) -> None:
        self.assertIn("Never edit `golden/**`, `pins.csv`, `pins.lock` or pin assertions", self.text)

    def test_stop_rules_include_three_verifications_without_progress(self) -> None:
        self.assertRegex(self.text, r"3 Verifications in a row that resolved no new key")
        self.assertIn("never a convergence test", self.text)

    def test_no_text_says_review_items_live_in_files(self) -> None:
        """Review Items are Data Table rows, never text left in files (spec section 4)."""
        files = [SKILL_MD, *sorted((SKILL / "references").rglob("*.md")), SKILL / "agents" / "openai.yaml"]
        for path in files:
            text = path.read_text(encoding="utf-8").lower()
            for wording in ["search marker", "review marker", "recipe marker", "markers"]:
                with self.subTest(path=str(path.relative_to(SKILL)), wording=wording):
                    self.assertNotIn(wording, text)

    def test_codex_interface_invokes_this_skill(self) -> None:
        text = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")

        self.assertIn("$rewrite-migration", text)
        self.assertNotIn("spring-boot4-followup", text)


if __name__ == "__main__":
    unittest.main()
