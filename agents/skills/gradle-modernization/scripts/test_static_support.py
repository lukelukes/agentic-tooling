"""Root-boundary and lexical contracts. All fixtures remain under the working directory."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from audit_gradle_project import Audit, block, parse_properties
from static_support import ConfinedFiles, Groovy


class StaticContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".gradle-static-test-", dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.root = self.work / "root"
        self.root.mkdir()

    def put(self, name, text):
        path = self.work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_external_includes_and_project_mappings_are_not_inspected(self):
        self.put("root/settings.gradle", "includeBuild '../sibling'\ninclude 'app'\nproject(':app').projectDir = file('../sibling')\n")
        self.put("sibling/settings.gradle", "rootProject.name='forbidden'\n")
        self.put("sibling/build.gradle", "afterEvaluate {}\n")
        original = Path.lstat
        def guarded(path, *args, **kwargs):
            if path.is_relative_to(self.work / "sibling"):
                self.fail("scanner inspected a path outside scan root")
            return original(path, *args, **kwargs)
        with patch.object(Path, "lstat", guarded):
            audit = Audit(self.root)
            audit.run()
        self.assertEqual(len(audit.builds), 1)
        self.assertNotIn(":app", audit.builds[0].projects)
        self.assertTrue(audit.facts["coverage"]["skipped_paths"])
        self.assertFalse(any(f.id == "G8" for f in audit.findings))

    def test_symlinked_files_and_directories_are_not_read(self):
        self.put("root/settings.gradle", "includeBuild 'link'\n")
        outside = self.put("sibling/build.gradle", "afterEvaluate {}\n")
        (self.root / "link").symlink_to(outside.parent, target_is_directory=True)
        (self.root / "build.gradle").symlink_to(outside)
        audit = Audit(self.root)
        audit.run()
        self.assertFalse(any(f.id == "G8" for f in audit.findings))
        self.assertTrue(all("symlink" in row["reason"] for row in audit.facts["coverage"]["skipped_paths"]))

    def test_unreadable_file_is_a_coverage_gap(self):
        self.put("root/settings.gradle", "rootProject.name='x'\n")
        denied = self.put("root/build.gradle", "afterEvaluate {}\n")
        original = Path.open
        def guarded(path, *args, **kwargs):
            if path == denied:
                raise PermissionError("fixture")
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", guarded):
            audit = Audit(self.root)
            audit.run()
        self.assertTrue(any("PermissionError" in row["reason"] for row in audit.facts["coverage"]["skipped_paths"]))
        self.assertTrue(any(f.id == "coverage" for f in audit.findings))

    def test_unreadable_properties_are_unknown_not_disabled(self):
        self.put("root/settings.gradle", "rootProject.name='x'\n")
        denied = self.put("root/gradle.properties", "org.gradle.caching=true\n")
        original = Path.open
        def guarded(path, *args, **kwargs):
            if path == denied:
                raise PermissionError("fixture")
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", guarded):
            audit = Audit(self.root)
            audit.run()
        self.assertIsNone(audit.facts["flags"]["org.gradle.caching"])
        self.assertFalse(any(f.id in {"P1", "P2", "P3"} for f in audit.findings))

    def test_unreadable_wrapper_is_not_reported_as_missing_checksum(self):
        self.put("root/settings.gradle", "rootProject.name='x'\n")
        denied = self.put("root/gradle/wrapper/gradle-wrapper.properties", "distributionSha256Sum=secret\n")
        original = Path.open
        def guarded(path, *args, **kwargs):
            if path == denied:
                raise PermissionError("fixture")
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", guarded):
            audit = Audit(self.root)
            audit.run()
        self.assertEqual(audit.facts["distribution_sha256"], "not-checked")
        self.assertFalse(any(f.id == "Sec1" for f in audit.findings))

    def test_rule_tokens_cannot_come_from_literal_arguments(self):
        self.put("root/settings.gradle", "rootProject.name='x'\n")
        self.put("root/build.gradle", "configurations.all { println 'exclude' }\n")
        audit = Audit(self.root)
        audit.run()
        self.assertFalse(any(f.id == "D8" for f in audit.findings))

    def test_non_regular_input_is_rejected(self):
        path = self.root / "not-a-file"
        path.mkdir()
        fs = ConfinedFiles(self.root)
        self.assertEqual(fs.read(path), "")
        self.assertTrue(any(row["reason"] == "not a regular file" for row in fs.skipped.values()))

    def test_lexical_views_keep_offsets_and_ignore_literal_braces(self):
        text = 'publishing { def example = "} repositories {"\nrepositories { mavenCentral() } }\n'
        src = Groovy(text)
        self.assertEqual(len(src.text), len(text))
        self.assertEqual(len(src.code), len(text))
        self.assertEqual(src.code.count("\n"), text.count("\n"))
        matches = list(src.matches(r"repositories\s*\{"))
        self.assertEqual(len(matches), 1)
        self.assertEqual(src.parents(matches[0].start()), ["publishing"])
        self.assertIn("mavenCentral", block(text, "publishing"))
        self.assertEqual(block(text, "repositories"), "")

    def test_comments_do_not_change_rule_matches(self):
        # Small metamorphic test: comment contents cannot introduce executable rules.
        for comment in ("// afterEvaluate {}\n", "/* repositories { } */", "/*\n tasks.create('x')\n */"):
            src = Groovy(comment + "\nafterEvaluate {}\n")
            self.assertEqual(len(list(src.matches(r"\bafterEvaluate\s*\{"))), 1)
            self.assertEqual(list(src.matches(r"repositories\s*\{")), [])

    def test_multiline_block_headers_keep_repository_scope(self):
        src = Groovy("publishing\n{\n repositories\n { mavenCentral() }\n}\n")
        matches = list(src.matches(r"repositories\s*\{"))
        self.assertEqual(src.parents(matches[0].start()), ["publishing"])

    def test_properties_accept_common_java_separators(self):
        self.assertEqual(parse_properties("# x\na = true\nb: false\nc value\n"),
                          {"a": "true", "b": "false", "c": "value"})

    def test_included_build_settings_catalogs_and_locks_are_independent(self):
        self.put("root/settings.gradle", "rootProject.name='root'\nincludeBuild 'logic'\n"
                 "dependencyResolutionManagement { versionCatalogs { libs { library('x','g','a').version('1') } } }\n")
        self.put("root/gradle.lockfile", "empty=runtimeClasspath\n")
        self.put("root/build.gradle", "dependencyLocking { lockAllConfigurations() }\n")
        self.put("root/logic/settings.gradle", "rootProject.name='logic'\nincludeBuild 'nested'\n"
                 "dependencyResolutionManagement { repositories { mavenCentral(); maven { url = uri('https://example.org') } } }\n")
        self.put("root/logic/gradle/libs.versions.toml", '[libraries]\nour_lib = {module="g:a",version="1"}\n')
        self.put("root/logic/build.gradle", "dependencyLocking { lockAllConfigurations() }\n")
        self.put("root/logic/gradle.lockfile", "empty=runtimeClasspath\n")
        self.put("root/logic/nested/settings.gradle", "rootProject.name='nested'\n")
        audit = Audit(self.root)
        audit.run()
        facts = audit.facts["build_facts"]
        self.assertEqual(facts["."]["lockfiles"], 1)
        self.assertEqual(facts["logic"]["lockfiles"], 1)
        self.assertEqual(facts["logic/nested"]["lockfiles"], 0)
        self.assertFalse(facts["."]["version_catalog_file"])
        self.assertTrue(facts["logic"]["version_catalog_file"])
        self.assertTrue(any(f.id == "D7" and f.build == "logic" for f in audit.findings))
        self.assertTrue(any(f.id == "D3" and f.build == "logic" for f in audit.findings))
        self.assertFalse(any(f.id == "C1" and f.build == "logic" for f in audit.findings))

    def test_rule_coverage_is_distinct_from_files_read(self):
        self.put("root/settings.gradle", "includeBuild 'logic'\n")
        self.put("root/logic/settings.gradle.kts", 'rootProject.name = "logic"\n')
        self.put("root/logic/build.gradle", "plugins { id 'java' }\n")
        audit = Audit(self.root)
        audit.run()
        coverage = {(r["build"], r["rule"]): r for r in audit.facts["coverage"]["rules"]}
        self.assertEqual(coverage[("logic", "D7")]["status"], "not-checked")
        self.assertEqual(coverage[(".", "D7")]["status"], "static-partial")
        self.assertEqual(coverage[(".", "Te1")]["status"], "not-checked")
        self.assertIsNone(audit.facts["build_facts"]["logic"]["version_catalog_declaration_observed"])
        self.assertFalse(any(f.id == "D2" and f.build == "logic" for f in audit.findings))

    def test_new_deprecation_patterns_preserve_receiver_uncertainty(self):
        self.put("root/settings.gradle", "rootProject.name='root'\n")
        self.put("root/build.gradle", "def xs = configurations.findAll { it.canBeResolved }\n"
                 "def props = project.properties\ntasks.named('test') { afterTest { descriptor, result -> } }\n"
                 "def ordinary = [1, 2].findAll { it > 1 }\n")
        audit = Audit(self.root)
        audit.run()
        self.assertTrue(any(f.id == "9.4.0" and f.where.endswith(":1") for f in audit.findings))
        self.assertTrue(any(f.id == "9.6.0" and f.where.endswith(":2") for f in audit.findings))
        self.assertFalse(any(f.id == "9.4.0" and f.where.endswith(":4") for f in audit.findings))


if __name__ == "__main__":
    unittest.main()
