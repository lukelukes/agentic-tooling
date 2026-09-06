"""Fixture-generation contracts only; actual Gradle execution remains opt-in."""
import tempfile
import unittest
from pathlib import Path

from test_recipes import prepare, migrate, TEST_CONFIG, BUILD_LOGIC_TASKS


class RecipeContracts(unittest.TestCase):
    def test_generated_fixture_uses_jupiter_and_preserves_test_sources(self):
        with tempfile.TemporaryDirectory(prefix=".recipe-contract-test-", dir=Path.cwd()) as directory:
            root = Path(directory)
            prepare(root)
            before = {p.name: p.read_text() for p in (root / "app/src/test/java").glob("*.java")}
            self.assertEqual(len(before), 2)
            self.assertTrue(all("org.junit.jupiter.api.Test" in src for src in before.values()))
            self.assertNotIn("useJUnit()", TEST_CONFIG)
            self.assertEqual(TEST_CONFIG.count("useJUnitPlatform()"), 2)
            self.assertIn("testClassesDirs = sourceSets.test.output.classesDirs", TEST_CONFIG)
            self.assertIn("classpath = sourceSets.test.runtimeClasspath", TEST_CONFIG)
            self.assertIn(TEST_CONFIG, (root / "build.gradle").read_text())
            migrate(root)
            self.assertEqual(before, {p.name: p.read_text() for p in (root / "app/src/test/java").glob("*.java")})
            self.assertIn(TEST_CONFIG, (root / "build-logic/src/main/groovy/java-conventions.gradle").read_text())
            self.assertIn("classifier('test-fixtures')", (root / "build-logic/src/main/groovy/java-conventions.gradle").read_text())

    def test_recipe_task_exceptions_never_include_product_tests(self):
        self.assertTrue(all(p.startswith(":build-logic:") for p in BUILD_LOGIC_TASKS))
        self.assertFalse(any(p.endswith(":test") or p.endswith(":integrationTest") for p in BUILD_LOGIC_TASKS))


if __name__ == "__main__":
    unittest.main()
