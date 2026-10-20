"""Tests of scripts/check-references, driven through its command line.

Each case builds a references/ tree in a temporary skill directory and a fake
`rewrite` (passed as $REWRITE) that prints a canned `recipe rules --json --all`
document and answers `recipe show` for a fixed set of Recipes.

    python3 -m unittest discover -s skills/rewrite-migration/tests

Set CHECK_REFERENCES_LIVE=1 (and $REWRITE, or a `rewrite` on PATH) to also
check this skill's own references against a real CLI.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SCRIPT = SKILL / "scripts" / "check-references"

FAKE_REWRITE = textwrap.dedent(
    """\
    #!{python}
    import json, sys
    from pathlib import Path
    here = Path(__file__).parent
    args = sys.argv[1:]
    if args == ["recipe", "rules", "--json", "--all"]:
        sys.stdout.write((here / "rules.json").read_text())
        sys.exit(int((here / "rules.exit").read_text()))
    if len(args) == 3 and args[:2] == ["recipe", "show"]:
        known = json.loads((here / "recipes.json").read_text())
        if args[2] in known:
            print(known[args[2]])
            print("Display name")
            sys.exit(0)
        print("rewrite: Recipe " + args[2] + " does not exist.", file=sys.stderr)
        sys.exit(1)
    print("unexpected arguments: " + " ".join(args), file=sys.stderr)
    sys.exit(64)
    """
)


def rule(rule_id: str, module: str = "rewrite-spring", guide: str | None = None, retired: bool = False) -> dict:
    return {
        "id": rule_id,
        "area": rule_id.split("/")[0],
        "module": module,
        "title": "A title",
        "severity": "BLOCKER",
        "guide": guide if guide is not None else f"rewrite-migration#{rule_id}",
        "retired": retired,
    }


class CheckReferencesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="check-references-"))
        self.addCleanup(shutil.rmtree, self.tmp)
        self.skill = self.tmp / "skill"
        (self.skill / "references").mkdir(parents=True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        fake = self.bin / "rewrite"
        fake.write_text(FAKE_REWRITE.format(python=sys.executable))
        fake.chmod(0o755)
        self.catalogue([])
        self.recipes({})

    def catalogue(self, rules: list[dict], schema: str = "rewrite.rules/1", exit_code: int = 0) -> None:
        document = {"schema": schema, "cli": "8.0.0-test", "rules": rules}
        (self.bin / "rules.json").write_text(json.dumps(document))
        (self.bin / "rules.exit").write_text(str(exit_code))

    def recipes(self, names: dict[str, str]) -> None:
        """Recipe names `recipe show` knows, mapped to the name it prints on its first line."""
        (self.bin / "recipes.json").write_text(json.dumps(names))

    def reference(self, relative: str, text: str) -> None:
        path = self.skill / "references" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text))

    def check(self) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "REWRITE": str(self.bin / "rewrite")}
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--skill", str(self.skill)],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

    def assertProblems(self, result: subprocess.CompletedProcess[str], *expected: str) -> None:
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertEqual(list(expected), result.stdout.splitlines(), result.stderr)

    def test_passes_when_every_rule_has_exactly_one_section(self) -> None:
        self.catalogue([rule("jackson/custom-http-converter"), rule("build/recipe-error", module="rewrite-core")])
        self.reference(
            "rewrite-spring/jackson.md",
            """\
            # Jackson

            ## jackson/custom-http-converter

            Trace the mapper to its producer.
            """,
        )
        self.reference("rewrite-core/build.md", "## build/recipe-error\n\nRead the message.\n")

        result = self.check()

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("", result.stderr)
        self.assertEqual(["references cover 2 rules"], result.stdout.splitlines())


    def test_fails_on_a_rule_without_a_section(self) -> None:
        self.catalogue([rule("jackson/custom-http-converter"), rule("security/access-decision-manager-removed")])
        self.reference("rewrite-spring/jackson.md", "## jackson/custom-http-converter\n")

        self.assertProblems(
            self.check(),
            "security/access-decision-manager-removed: no '## security/access-decision-manager-removed' section "
            "under references/ (module rewrite-spring)",
        )

    def test_a_retired_rule_needs_no_section_and_may_keep_one(self) -> None:
        self.catalogue([rule("jackson/old-one", retired=True), rule("jackson/kept-one", retired=True, guide="")])
        self.reference("rewrite-spring/jackson.md", "## jackson/kept-one\n\nStill documented.\n")

        result = self.check()

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(["references cover 0 rules"], result.stdout.splitlines())

    def test_fails_on_a_rule_with_two_sections_in_different_files(self) -> None:
        self.catalogue([rule("jackson/custom-http-converter")])
        self.reference("rewrite-spring/jackson.md", "# Jackson\n\n## jackson/custom-http-converter\n")
        self.reference("rewrite-jackson/jackson.md", "## jackson/custom-http-converter\n")

        self.assertProblems(
            self.check(),
            "jackson/custom-http-converter: 2 sections "
            "(references/rewrite-jackson/jackson.md:1, references/rewrite-spring/jackson.md:3)",
        )

    def test_fails_on_a_section_that_names_no_catalogue_rule(self) -> None:
        self.catalogue([rule("jackson/custom-http-converter")])
        self.reference(
            "rewrite-spring/jackson.md",
            """\
            ## jackson/custom-http-converter

            ## jackson/custom-http-convertor
            """,
        )

        self.assertProblems(
            self.check(),
            "references/rewrite-spring/jackson.md:3: '## jackson/custom-http-convertor' names no catalogue rule",
        )

    def test_prose_headings_in_module_files_are_not_rule_sections(self) -> None:
        self.catalogue([rule("jackson/custom-http-converter")])
        self.reference(
            "rewrite-spring/cloud.md",
            """\
            ## OpenFeign encoders and decoders

            ## jackson/custom-http-converter

            ## Jackson/Custom-Http-Converter
            """,
        )

        self.assertProblems(
            self.check(),
            "references/rewrite-spring/cloud.md:5: '## Jackson/Custom-Http-Converter' names no catalogue rule",
        )

    def test_headings_in_fenced_code_blocks_are_not_sections(self) -> None:
        self.catalogue([rule("jackson/custom-http-converter")])
        self.reference(
            "rewrite-spring/jackson.md",
            """\
            ```markdown
            ## jackson/custom-http-converter
            ```

            ~~~
            ## jackson/not-a-rule
            ~~~
            """,
        )

        self.assertProblems(
            self.check(),
            "jackson/custom-http-converter: no '## jackson/custom-http-converter' section under references/ "
            "(module rewrite-spring)",
        )

    def test_a_fence_closes_only_on_a_fence_at_least_as_long(self) -> None:
        self.catalogue([rule("jackson/custom-http-converter")])
        self.reference(
            "rewrite-spring/jackson.md",
            """\
            ````markdown
            ```
            ## jackson/custom-http-converter
            ```
            ````

            ## jackson/custom-http-converter
            """,
        )

        result = self.check()

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_fails_on_a_rule_heading_with_whitespace_the_exact_lookup_misses(self) -> None:
        self.catalogue([rule("jackson/custom-http-converter"), rule("jackson/mapper-method-removed")])
        self.reference(
            "rewrite-spring/jackson.md",
            "##  jackson/custom-http-converter\n\n## jackson/mapper-method-removed \n",
        )

        self.assertProblems(
            self.check(),
            "jackson/custom-http-converter: no '## jackson/custom-http-converter' section under references/ "
            "(module rewrite-spring)",
            "jackson/mapper-method-removed: no '## jackson/mapper-method-removed' section under references/ "
            "(module rewrite-spring)",
            "references/rewrite-spring/jackson.md:1: '##  jackson/custom-http-converter' has whitespace around the "
            "rule id, so the exact heading lookup does not find it",
            "references/rewrite-spring/jackson.md:3: '## jackson/mapper-method-removed ' has whitespace around the "
            "rule id, so the exact heading lookup does not find it",
        )

    def test_fails_on_a_guide_that_does_not_point_at_this_skill(self) -> None:
        self.catalogue([rule("jackson/custom-http-converter", guide="spring-boot4-followup#jackson")])
        self.reference("rewrite-spring/jackson.md", "## jackson/custom-http-converter\n")

        self.assertProblems(
            self.check(),
            "jackson/custom-http-converter: guide is 'spring-boot4-followup#jackson', "
            "expected 'rewrite-migration#jackson/custom-http-converter'",
        )

    def test_migration_sections_must_name_a_recipe_by_its_fully_qualified_name(self) -> None:
        self.recipes(
            {
                "org.openrewrite.java.spring.boot4.UpgradeSpringBoot_4_0": "org.openrewrite.java.spring.boot4.UpgradeSpringBoot_4_0",
                "UpgradeSpringBoot_4_1": "org.openrewrite.java.spring.boot4.UpgradeSpringBoot_4_1",
            }
        )
        self.reference(
            "migrations/spring-boot4.md",
            """\
            # Spring Boot 4

            ## org.openrewrite.java.spring.boot4.UpgradeSpringBoot_4_0

            ## UpgradeSpringBoot_4_1

            ## org.openrewrite.java.spring.boot4.UpgradeSpringBoot_5_0
            """,
        )

        self.assertProblems(
            self.check(),
            "references/migrations/spring-boot4.md:5: '## UpgradeSpringBoot_4_1' is not a Recipe that "
            "'rewrite recipe show' knows",
            "references/migrations/spring-boot4.md:7: '## org.openrewrite.java.spring.boot4.UpgradeSpringBoot_5_0' "
            "is not a Recipe that 'rewrite recipe show' knows",
        )

    def test_a_rule_id_heading_in_migrations_still_counts_as_its_section(self) -> None:
        self.catalogue([rule("build/recipe-error", module="rewrite-core")])
        self.recipes({"build/recipe-error": "build/recipe-error"})
        self.reference("migrations/spring-boot4.md", "## build/recipe-error\n")

        self.assertProblems(
            self.check(),
            "build/recipe-error: no '## build/recipe-error' section under references/ (module rewrite-core)",
        )

    def test_reports_a_catalogue_that_cannot_be_read_apart_from_drift(self) -> None:
        cases = [
            ("the command fails", dict(rules=[], exit_code=2), "exited 2"),
            ("another major schema", dict(rules=[], schema="rewrite.rules/2"), "schema 'rewrite.rules/2'"),
            ("a rule without an id", dict(rules=[{"module": "rewrite-spring"}]), "rule 1 has no string id"),
            ("a rule that is not an object", dict(rules=["jackson/custom-http-converter"]), "rule 1 has no string id"),
            ("a rule whose id is not a string", dict(rules=[{"id": 7}]), "rule 1 has no string id"),
        ]
        for name, catalogue, message in cases:
            with self.subTest(name):
                self.catalogue(**catalogue)

                result = self.check()

                self.assertEqual(2, result.returncode, result.stdout + result.stderr)
                self.assertEqual("", result.stdout)
                self.assertIn(message, result.stderr)

    def test_reports_a_missing_rewrite_command(self) -> None:
        env = {**os.environ, "REWRITE": str(self.tmp / "no-such-rewrite")}

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--skill", str(self.skill)], capture_output=True, text=True, env=env
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("cannot run", result.stderr)


@unittest.skipUnless(os.environ.get("CHECK_REFERENCES_LIVE") == "1", "set CHECK_REFERENCES_LIVE=1 to run against a real rewrite")
class LiveCatalogueTest(unittest.TestCase):
    def test_this_skills_references_match_the_installed_catalogue(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=600)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
