#!/usr/bin/env python3
"""Tests for gather_facts.py using a fake Gradle launcher (no real Gradle needed).

The fake launcher answers --version, help, the verification tasks, tasks, dependencies
and buildEnvironment with canned output, writes JUnit XML for :app:test and tracks the
configuration-cache store/reuse state through a marker file. Behaviour is switched
with environment variables so failure paths can be exercised too.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from gather_facts import deprecation_messages, parse_version_output, split_dependencies  # noqa: E402

FAKE_LAUNCHER = r'''#!/usr/bin/env python3
import os, subprocess, sys, time
from pathlib import Path
args = sys.argv[1:]
root = Path(os.environ["FAKE_ROOT"])
version = os.environ.get("FAKE_VERSION", "9.7.1")
def done(): print("\nBUILD SUCCESSFUL in 1s"); sys.exit(0)
if "--version" in args:
    print(f"------------------------------------------------------------\nGradle {version}\n------------------------------------------------------------\n\nLauncher JVM:  21.0.2 (Vendor 21.0.2+13)\nDaemon JVM:    /opt/jdk21 (no JDK specified, using current Java home)\nOS:            Linux 6.0 amd64")
    sys.exit(0)
if "help" in args:
    if os.environ.get("FAKE_FAIL_HELP"):
        print("FAILURE: Build failed with an exception.\n\nBUILD FAILED in 1s"); sys.exit(1)
    print("> Task :help\n\nThe Project.foo property has been deprecated. This is scheduled to be removed in Gradle 10.\nThe Project.foo property has been deprecated. This is scheduled to be removed in Gradle 10.\nThe bar method has been deprecated.")
    done()
if "tasks" in args:
    print("> Task :tasks\n\nBuild tasks\n-----------\ncheck - Runs all checks. (registered by plugin 'java')")
    done()
if "buildEnvironment" in args:
    print("> Task :buildEnvironment\n\nclasspath\nNo dependencies")
    done()
if any(a.endswith(":dependencies") for a in args):
    if os.environ.get("FAKE_FAIL_DEPS"):
        print("FAILURE: Build failed with an exception.\n\nBUILD FAILED in 1s"); sys.exit(1)
    project = [a for a in args if a.endswith(":dependencies")][0]
    name = "app" if project.startswith(":app") else "root"
    lib = os.environ.get("FAKE_LIB_VERSION", "2.0")
    print(f"> Task {project}\n\n------------------------------------------------------------\nProject ':{name}'\n------------------------------------------------------------\n")
    if name == "app":
        print(f"annotationProcessor - Annotation processors and their dependencies for source set 'main'.\nNo dependencies\n\ncompileClasspath - Compile classpath for source set 'main'.\n+--- com.example:lib:{lib}\n\\--- com.example:other:1.0\n     \\--- com.example:transitive:0.9\n\nimplementation - Implementation only dependencies for source set 'main'. (n)\n\\--- com.example:lib:{lib} (n)\n\nruntimeClasspath - Runtime classpath of source set 'main'.\n\\--- com.example:lib:{lib}\n\nintegrationTestRuntimeClasspath - Runtime classpath of source set 'integrationTest'.\n\\--- com.example:lib:{lib}\n\n(n) - A dependency or dependency configuration that cannot be resolved.\n\nA web-based, searchable dependency report is available by adding the --scan option.")
    else:
        print("No configurations")
    done()
# verification tasks
if os.environ.get("FAKE_HANG"):
    # This descendant deliberately inherits stdout. A timeout implemented with
    # capture_output can kill this wrapper and still hang waiting for the pipe.
    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    time.sleep(60)
if os.environ.get("FAKE_FAIL"):
    print("> Task :app:compileJava FAILED\n\nFAILURE: Build failed with an exception.\n\nBUILD FAILED in 1s"); sys.exit(1)
if "--configuration-cache" in args:
    marker = root / ".fake-cc"
    reused = marker.exists()
    print("Reusing configuration cache." if reused else "Calculating task graph as no cached configuration is available for tasks: check")
    marker.write_text("x")
print("> Task :app:compileJava\n> Task :app:test\n> Task :app:integrationTest NO-SOURCE\n> Task :app:check")
xml = root / "app/build/test-results/test"
xml.mkdir(parents=True, exist_ok=True)
(xml / "TEST-FooTest.xml").write_text('<testsuite name="FooTest"><testcase classname="FooTest" name="works"/><testcase classname="FooTest" name="skips"><skipped/></testcase></testsuite>')
os.utime(xml / "TEST-FooTest.xml", None)
if "--configuration-cache" in args and not os.environ.get("FAKE_NO_STORE"):
    print("Configuration cache entry " + ("reused." if reused else "stored."))
done()
'''

FIXTURE = {
    "settings.gradle": "rootProject.name = 'demo'\ninclude 'app'\n",
    "gradle.properties": "org.gradle.configuration-cache=false\n",
    "gradle/libs.versions.toml": "[versions]\nboot = \"3.2.0\"\n[plugins]\nspring-boot = { id = \"org.springframework.boot\", version.ref = \"boot\" }\n",
    "build.gradle": "plugins { id 'base' }\nbuildscript { dependencies { classpath 'com.acme:tool:4.1' } }\n",
    "app/build.gradle": "plugins { id 'java'\n id 'com.diffplug.spotless' version '6.25.0'\n alias(libs.plugins.spring.boot) }\napply plugin: 'jacoco'\n",
}


def write_fixture(root: Path, launcher: bool = True):
    for rel, content in FIXTURE.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(content)
    if launcher:
        fake = root / "gradlew"
        fake.write_text(FAKE_LAUNCHER)
        fake.chmod(0o755)


def run(root: Path, *extra, env=None) -> tuple[int, str, dict]:
    environment = {**os.environ, "FAKE_ROOT": str(root), **(env or {})}
    proc = subprocess.run([sys.executable, "-B", str(SCRIPTS / "gather_facts.py"), str(root), *extra],
                          capture_output=True, text=True, timeout=60, env=environment)
    out_dir = root / ".gradle-modernization" / "baseline"
    for token in extra:
        if token.startswith("--out"):
            out_dir = Path(extra[extra.index(token) + 1])
    facts = json.loads((out_dir / "facts.json").read_text()) if (out_dir / "facts.json").exists() else {}
    return proc.returncode, proc.stdout + proc.stderr, facts


class Parsing(unittest.TestCase):
    def test_version_output(self):
        v = parse_version_output("Gradle 9.7.1\n\nLauncher JVM:  21 (x)\nDaemon JVM:    /opt/jdk (auto)\nOS:            Linux\n")
        self.assertEqual(v, {"gradle": "9.7.1", "launcher_jvm": "21 (x)", "daemon_jvm": "/opt/jdk (auto)", "os": "Linux"})

    def test_deprecations_are_deduplicated(self):
        info = deprecation_messages("a has been deprecated.\na has been deprecated.\nb has been deprecated.\nfine\n")
        self.assertEqual(info["count"], 3)
        self.assertEqual(info["unique"][0], {"message": "a has been deprecated.", "times": 2})

    def test_split_dependencies(self):
        text = ("> Task :app:dependencies\n\n----\nProject ':app'\n----\n\ncompileClasspath - Compile classpath for source set 'main'.\n"
                "+--- a:b:1\n\\--- c:d:2\n     \\--- e:f:3\n\nimplementation - Implementation only. (n)\n\\--- a:b:1 (n)\n\n"
                "runtimeClasspath - Runtime classpath.\nNo dependencies\n\n(n) - cannot be resolved.\n\nA web-based, searchable dependency report ...\n\nBUILD SUCCESSFUL in 1s\n")
        sections = split_dependencies(text)
        self.assertEqual(sorted(sections), ["compileClasspath", "implementation", "runtimeClasspath"])
        self.assertEqual(sections["compileClasspath"].splitlines()[1:], ["+--- a:b:1", "\\--- c:d:2", "     \\--- e:f:3"])
        self.assertEqual(sections["runtimeClasspath"].splitlines()[1], "No dependencies")


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix=".gather-facts-test-", dir=Path.cwd())
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_static_only_when_no_launcher(self):
        write_fixture(self.root, launcher=False)
        code, out, facts = run(self.root, "--gradle", str(self.root / "missing-launcher"))
        self.assertEqual(facts["dynamic"]["status"], "not-run", out)
        self.assertEqual(code, 1, "an unusable launcher is a failed dynamic phase")
        plugins = {(p.get("id"), p.get("version"), p["via"]) for p in facts["static"]["plugins"]}
        self.assertIn(("com.diffplug.spotless", "6.25.0", "plugins-block"), plugins)
        self.assertIn(("org.springframework.boot", "3.2.0", "catalog-alias"), plugins)
        self.assertIn(("jacoco", None, "apply-plugin"), plugins)
        self.assertIn((None, "4.1", "buildscript-classpath"), plugins)
        self.assertTrue((self.root / ".gradle-modernization" / ".gitignore").exists())
        self.assertIn("Dynamic: not-run", out)

    def test_static_only_flag(self):
        write_fixture(self.root)
        code, out, facts = run(self.root, "--static-only")
        self.assertEqual(code, 0, out)
        self.assertEqual(facts["dynamic"]["status"], "skipped")
        self.assertEqual([c["label"] for c in facts["commands"] if "gradlew" in " ".join(c["argv"])], [])

    def test_full_run_with_fake_launcher(self):
        write_fixture(self.root)
        code, out, facts = run(self.root)
        self.assertEqual(code, 0, out)
        dyn = facts["dynamic"]
        self.assertEqual(dyn["version"]["gradle"], "9.7.1")
        self.assertEqual(dyn["deprecations"]["count"], 3)
        self.assertEqual(dyn["deprecations"]["unique"][0]["times"], 2)
        base = dyn["baseline"]
        self.assertTrue(base["successful"])
        self.assertEqual(base["outcomes"], {"EXECUTED": 3, "NO-SOURCE": 1})
        self.assertEqual(base["tests"][":app:test"]["counts"], {"passed": 1, "skipped": 1})
        self.assertEqual(base["test_like_tasks_without_xml"], [":app:integrationTest"])
        self.assertEqual(base["stale_xml"], [])
        self.assertTrue(dyn["cc_pair"]["ok"], dyn["cc_pair"])
        self.assertTrue(dyn["baseline_vs_cc_store"]["ok"])
        self.assertTrue(dyn["provenance"]["with_provenance"])
        deps = dyn["dependencies"]
        self.assertEqual(sorted(deps), ["app", "root"])
        app = deps["app"]["configurations"]
        self.assertEqual(app["testCompileClasspath"], "N/A")
        self.assertTrue(app["compileClasspath"]["resolvable"])
        self.assertIn("integrationTestRuntimeClasspath", app)
        self.assertTrue((self.root / ".gradle-modernization/baseline/dependencies/app/compileClasspath.txt").exists())
        self.assertNotIn("implementation", app)
        for name in ("baseline.log", "cc-store.log", "cc-reuse.log", "provenance.log", "buildEnvironment.log", "static.json", "baseline.json"):
            self.assertTrue((self.root / ".gradle-modernization/baseline" / name).exists(), name)
        self.assertIn("pair OK", out)
        self.assertLess(len(out.splitlines()), 40, "stdout must stay a short summary")

    def test_old_gradle_has_no_provenance(self):
        write_fixture(self.root)
        code, out, facts = run(self.root, "--skip-cc", env={"FAKE_VERSION": "8.14.2"})
        self.assertEqual(code, 0, out)
        self.assertFalse(facts["dynamic"]["provenance"]["with_provenance"])
        self.assertTrue(any(g["phase"] == "provenance" for g in facts["gaps"]))
        self.assertTrue(any(g["reason"] == "--skip-cc" for g in facts["gaps"]))

    def test_failed_baseline_is_reported_not_hidden(self):
        write_fixture(self.root)
        code, out, facts = run(self.root, env={"FAKE_FAIL": "1"})
        self.assertEqual(code, 1)
        self.assertFalse(facts["ok"])
        self.assertFalse(facts["dynamic"]["baseline"]["successful"])
        self.assertIn("BUILD FAILED", facts["dynamic"]["baseline"]["failure_tail"])
        self.assertNotIn("cc-store", facts["dynamic"])
        self.assertIn("baseline build failed", out)
        self.assertEqual(facts["dynamic"]["stopped_after"], "baseline")
        self.assertNotIn("dependencies", facts["dynamic"], "the subsequent phases do not run after a failed baseline")
        self.assertIn("STOPPED", out)

    def test_timeout_terminates_launcher_descendants(self):
        write_fixture(self.root)
        started = time.monotonic()
        code, out, facts = run(self.root, "--timeout", "1", env={"FAKE_HANG": "1"})
        elapsed = time.monotonic() - started
        self.assertEqual(code, 1, out)
        self.assertLess(elapsed, 8, "timeout must not wait for a descendant holding the output descriptor")
        self.assertEqual(facts["dynamic"]["stopped_after"], "baseline")
        baseline = next(c for c in facts["commands"] if c["label"] == "baseline")
        self.assertEqual(baseline["exit"], -1)
        self.assertIn("terminated the command process group", facts["dynamic"]["baseline"]["failure_tail"])
        self.assertIn("[gather_facts] baseline: running", out)

    def test_failed_help_stops_before_baseline(self):
        write_fixture(self.root)
        code, out, facts = run(self.root, env={"FAKE_FAIL_HELP": "1"})
        self.assertEqual(code, 1)
        self.assertEqual(facts["dynamic"]["stopped_after"], "deprecations")
        self.assertNotIn("baseline", facts["dynamic"])
        self.assertIn("STOPPED", out)

    def test_failed_dependencies_stops_before_build_environment(self):
        write_fixture(self.root)
        code, out, facts = run(self.root, "--skip-cc", env={"FAKE_FAIL_DEPS": "1"})
        self.assertEqual(code, 1)
        self.assertEqual(facts["dynamic"]["stopped_after"], "dependencies")
        self.assertEqual(len(facts["dynamic"]["dependencies"]), 1, "stops at the first failed project report")
        self.assertNotIn("build_environment", facts["dynamic"])
        self.assertIn("STOPPED", out)

    def test_missing_store_fails_cache_pair(self):
        write_fixture(self.root)
        code, out, facts = run(self.root, env={"FAKE_NO_STORE": "1"})
        self.assertEqual(code, 1)
        self.assertFalse(facts["dynamic"]["cc_pair"]["ok"])
        self.assertIn("neither stored nor reused", out)

    def test_open_c3_records_a_baseline_gap_before_the_run(self):
        write_fixture(self.root)
        (self.root / "app/build.gradle").write_text(FIXTURE["app/build.gradle"] +
                                                   "dependencies { testImplementation 'org.mockito:mockito-core:5.18.0' }\n")
        code, out, facts = run(self.root, "--skip-cc")
        self.assertEqual(code, 0, out)
        self.assertTrue(any(f["id"] == "C3" for f in facts["static"]["findings"]))
        self.assertIn("C3 open", out)
        self.assertEqual([g["phase"] for g in facts["gaps"] if "C3 open" in g["reason"]], ["baseline"])

    def test_cache_already_on_reuses_in_both_runs(self):
        write_fixture(self.root)
        (self.root / ".fake-cc").write_text("x")  # the baseline already stored the entry
        code, out, facts = run(self.root)
        self.assertEqual(code, 0, out)
        self.assertTrue(facts["dynamic"]["cc_pair"]["ok"])
        self.assertFalse(facts["dynamic"]["cc-store"]["configuration_cache"]["stored"])
        self.assertTrue(facts["dynamic"]["cc-store"]["configuration_cache"]["reused"])
        self.assertIn("stored=False reused=True; pair OK", out)

    def test_compare_with_previous_run(self):
        write_fixture(self.root)
        code, out, _ = run(self.root, "--out", str(self.root / ".gradle-modernization/before"))
        self.assertEqual(code, 0, out)
        (self.root / ".fake-cc").unlink()
        code, out, facts = run(self.root, "--out", str(self.root / ".gradle-modernization/after"),
                               "--compare-with", str(self.root / ".gradle-modernization/before"))
        self.assertEqual(code, 0, out)
        self.assertTrue(facts["comparison"]["ok"])
        (self.root / ".fake-cc").unlink()
        code, out, facts = run(self.root, "--out", str(self.root / ".gradle-modernization/changed"),
                               "--compare-with", str(self.root / ".gradle-modernization/before"), env={"FAKE_LIB_VERSION": "2.1"})
        self.assertEqual(code, 1)
        changed = facts["comparison"]["dependencies"]["changed"]
        self.assertEqual(sorted(c["report"] for c in changed), ["app/compileClasspath.txt", "app/integrationTestRuntimeClasspath.txt", "app/runtimeClasspath.txt"])
        diff = (self.root / ".gradle-modernization/changed" / changed[0]["diff"]).read_text()
        self.assertIn("-+--- com.example:lib:2.0", diff)
        self.assertIn("+--- com.example:lib:2.1", diff)
        self.assertIn("DIFFERENCES", out)

    def test_new_and_missing_dependency_reports(self):
        write_fixture(self.root)
        before = self.root / ".gradle-modernization/before"
        code, out, _ = run(self.root, "--out", str(before), "--skip-cc")
        self.assertEqual(code, 0, out)
        (before / "dependencies/app/runtimeClasspath.txt").unlink()
        (before / "dependencies/app/legacyClasspath.txt").write_text("legacyClasspath\nNo dependencies\n")
        code, out, facts = run(self.root, "--out", str(self.root / ".gradle-modernization/after"), "--skip-cc", "--compare-with", str(before))
        self.assertEqual(code, 1)
        self.assertEqual(facts["comparison"]["dependencies"]["new"], ["app/runtimeClasspath.txt"])
        self.assertEqual(facts["comparison"]["dependencies"]["missing"], ["app/legacyClasspath.txt"])
        self.assertIn("disappeared: app/legacyClasspath.txt", out)
        self.assertIn("new dependency reports", out)


if __name__ == "__main__":
    unittest.main()
