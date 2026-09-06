#!/usr/bin/env python3
"""Opt-in smoke test of the skill's recipes against a real Gradle.

Builds a small fixture (classifier + rich-version dependencies, unit and
integration Test tasks with relocated XML), then migrates it to a version
catalog + convention plugin, enables strict locking, checks configuration-cache
store/reuse, and finally checks that a silently-suppressed Test task is caught
by compare_runs. Needs a Gradle launcher and network access for JUnit.
Importing this module does not run Gradle.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from compare_runs import compare, summarize

BUILD_LOGIC_TASKS = {":build-logic:" + name for name in (
    "compileJava", "compileGroovy", "extractPluginRequests", "generatePluginAdapters",
    "compileGroovyPlugins", "pluginDescriptors", "processResources", "classes", "jar")}

TEST_CONFIG = """
dependencies {
    testImplementation 'org.junit.jupiter:junit-jupiter:5.13.4'
    testRuntimeOnly 'org.junit.platform:junit-platform-launcher'
}
tasks.named('test', Test) {
    useJUnitPlatform()
    include '**/*UnitTest.class'
    reports.junitXml.outputLocation = layout.buildDirectory.dir('qa/unit-xml')
}
tasks.register('integrationTest', Test) {
    testClassesDirs = sourceSets.test.output.classesDirs
    classpath = sourceSets.test.runtimeClasspath
    useJUnitPlatform()
    include '**/*IntegrationTest.class'
    reports.junitXml.outputLocation = layout.buildDirectory.dir('qa/integration-xml')
}
"""


TASK = """
abstract class VerifyDependencies extends DefaultTask {
    @Classpath abstract ConfigurableFileCollection getRuntimeClasspath()
    @OutputFile abstract RegularFileProperty getReportFile()
    @TaskAction void verify() {
        def names = runtimeClasspath.files.collect { it.name }.sort()
        assert names == ['lib-1.0-test-fixtures.jar', 'strict-1.0.jar']
        def report = reportFile.get().asFile
        report.parentFile.mkdirs()
        report.text = names.join('\\n')
    }
}
"""
REGISTER = """
tasks.register('verifyRecipe', VerifyDependencies) {
    runtimeClasspath.from(configurations.runtimeClasspath)
    reportFile = layout.buildDirectory.file('recipe.txt')
}
"""


def put(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def prepare(root):
    put(root, "settings.gradle", """
rootProject.name = 'recipe-fixture'
include 'app'
dependencyResolutionManagement {
    repositoriesMode = RepositoriesMode.FAIL_ON_PROJECT_REPOS
    repositories {
        maven { url = uri('repo'); content { includeGroup 'example' } }
        mavenCentral()
    }
}
""")
    put(root, "app/build.gradle", "")
    put(root, "build.gradle", TASK + """
subprojects {
    apply plugin: 'java'
    dependencies {
        implementation 'example:lib:1.0:test-fixtures'
        implementation('example:strict:1.0') { version { strictly '1.0' } }
    }
""" + REGISTER + TEST_CONFIG + "}\n")
    for kind in ("Unit", "Integration"):
        put(root, f"app/src/test/java/Recipe{kind}Test.java", f"""
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;
public class Recipe{kind}Test {{
    @Test public void runsAnActualTest() {{ assertEquals(4, 2 + 2); }}
}}
""")
    for module in ("lib", "strict"):
        directory = f"repo/example/{module}/1.0"
        put(root, f"{directory}/{module}-1.0.pom", f"""<project>
<modelVersion>4.0.0</modelVersion><groupId>example</groupId>
<artifactId>{module}</artifactId><version>1.0</version></project>""")
        classifier = "-test-fixtures" if module == "lib" else ""
        with zipfile.ZipFile(root / directory / f"{module}-1.0{classifier}.jar", "w") as jar:
            jar.writestr("fixture.txt", module)


def migrate(root):
    settings = (root / "settings.gradle").read_text()
    put(root, "settings.gradle", "pluginManagement { includeBuild 'build-logic' }\n" + settings)
    put(root, "build.gradle", "")
    put(root, "gradle/libs.versions.toml", """[libraries]
classified = { module = "example:lib", version = "1.0" }
strict = { module = "example:strict", version = { strictly = "1.0" } }
""")
    put(root, "build-logic/settings.gradle", "rootProject.name='build-logic'\n")
    put(root, "build-logic/build.gradle", "plugins { id 'groovy-gradle-plugin' }\n")
    put(root, "build-logic/src/main/groovy/java-conventions.gradle", """
plugins { id 'java' }
def libs = extensions.getByType(VersionCatalogsExtension).named('libs')
dependencies {
    implementation(variantOf(libs.findLibrary('classified').get()) { classifier('test-fixtures') })
    implementation libs.findLibrary('strict').get()
}
""" + TASK + REGISTER + TEST_CONFIG)
    put(root, "app/build.gradle", "plugins { id 'java-conventions' }\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gradle", default="gradle", help="Gradle launcher (default: gradle on PATH)")
    parser.add_argument("--results", type=Path, help="directory to keep logs, summaries and comparisons")
    args = parser.parse_args()
    results = args.results.absolute() if args.results else None
    if results:
        results.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".gradle-recipe-test-", dir=Path.cwd()) as directory:
        root = Path(directory)
        logs = root / ".recipe-logs"
        logs.mkdir()
        common = [args.gradle, "--console=plain", "--no-build-cache", "--rerun-tasks", "--warning-mode=all"]

        def run(*arguments):
            result = subprocess.run(common + list(arguments), cwd=root, capture_output=True, text=True, timeout=600)
            output = result.stdout + result.stderr
            if result.returncode:
                raise RuntimeError(f"Gradle failed: {' '.join(arguments)}\n{output}")
            return output

        print("Recipe tests:", next((l for l in run("--version").splitlines() if l.startswith("Gradle ")), "unknown Gradle"))

        def capture(label, *arguments):
            result = subprocess.run(common + list(arguments), cwd=root, capture_output=True, text=True, timeout=600)
            log = logs / f"{label}.log"
            log.write_text(result.stdout + result.stderr)
            summary = summarize(log, {":app:test": root / "app/build/qa/unit-xml",
                                      ":app:integrationTest": root / "app/build/qa/integration-xml"})
            if results:
                shutil.copyfile(log, results / log.name)
                (results / f"{label}.json").write_text(json.dumps(summary, indent=2))
            if not summary["successful"] and label != "missing-integration":
                raise RuntimeError(f"{label}: build failed\n{result.stdout}\n{result.stderr}")
            return summary

        def verify(label, before, after, cache=False):
            result = compare(before, after, cache, ignore_tasks=BUILD_LOGIC_TASKS)
            if results:
                (results / f"{label}-comparison.json").write_text(json.dumps(result, indent=2))
            if not result["ok"]:
                raise RuntimeError(f"{label}: {result['problems']}")

        prepare(root)
        workload = (":app:verifyRecipe", ":app:test", ":app:integrationTest")
        baseline_evidence = capture("baseline", *workload, "--no-configuration-cache")
        baseline = (root / "app/build/recipe.txt").read_bytes()
        migrate(root)
        migrated = capture("migrated", *workload, "--no-configuration-cache")
        verify("migration", baseline_evidence, migrated)
        assert (root / "app/build/recipe.txt").read_bytes() == baseline, "catalog/convention migration changed selected artifacts"
        put(root, "app/build.gradle", (root / "app/build.gradle").read_text() +
            "dependencyLocking { lockAllConfigurations(); lockMode = LockMode.DEFAULT }\n")
        run(":app:dependencies", "--write-locks", "--no-configuration-cache")
        lock = (root / "app/gradle.lockfile").read_text()
        assert "example:lib:1.0=" in lock and "example:strict:1.0=" in lock, "lock state missing"
        put(root, "app/build.gradle", (root / "app/build.gradle").read_text().replace("LockMode.DEFAULT", "LockMode.STRICT"))
        arguments = (*workload, "--configuration-cache", "--configuration-cache-problems=fail")
        first, second = capture("store", *arguments), capture("reuse", *arguments)
        verify("cache-pair", first, second, cache=True)
        verify("baseline-to-cache", baseline_evidence, first)
        assert (root / "app/build/recipe.txt").read_bytes() == baseline, "locking/cache reuse changed selected artifacts"
        # A green build whose integration tests silently stopped running must be caught.
        put(root, "app/build.gradle", (root / "app/build.gradle").read_text() +
            "tasks.named('integrationTest', Test) { testClassesDirs = files() }\n")
        missing = capture("missing-integration", *workload, "--no-configuration-cache")
        assert not compare(migrated, missing)["ok"], "missing test task was accepted"
        print("PASS: classifier + rich version + convention extraction + strict locking + JUnit XML + cache store/reuse + missing-test detection")


if __name__ == "__main__":
    main()
