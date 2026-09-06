#!/usr/bin/env python3
"""Regression tests for audit_gradle_project.py. Run: python scripts/test_audit.py

Each case uses a temporary directory under the current working directory (never /tmp).
Assertions cover IDs, evidence, locations, confidence, applicability and coverage.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCANNER = Path(__file__).with_name("audit_gradle_project.py")


def write(root: Path, files: dict[str, str]):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def run(root: Path) -> dict:
    out = subprocess.run([sys.executable, "-B", str(SCANNER), str(root), "--json"], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


WRAPPER_OK = "distributionUrl=https\\://services.gradle.org/distributions/gradle-9.7.1-bin.zip\ndistributionSha256Sum=" + "a" * 64 + "\n"
PROPS_OK = "org.gradle.caching=true\norg.gradle.configuration-cache=true\norg.gradle.parallel=true\norg.gradle.jvmargs=-Xmx2g -Dfile.encoding=UTF-8\n"

CASES = [
    dict(
        name="modern build needs no changes; included build + repos in settings + multi include + catalog import + setup-gradle v4",
        files={
            "gradle/wrapper/gradle-wrapper.properties": WRAPPER_OK,
            "gradle/gradle-daemon-jvm.properties": "toolchainVersion=21\n",
            "gradle.properties": PROPS_OK,
            "settings.gradle": "pluginManagement { includeBuild 'build-logic'; repositories { gradlePluginPortal() } }\n"
                               "rootProject.name = 'modern'\n"
                               "dependencyResolutionManagement { repositoriesMode = RepositoriesMode.FAIL_ON_PROJECT_REPOS\n"
                               "  repositories { mavenCentral() }\n  versionCatalogs { libs { from('com.example:platform-catalog:1.4.0') } } }\n"
                               "include 'app', 'core', 'api'\n",
            "build-logic/gradle.properties": "org.gradle.caching=true\n",
            "build-logic/settings.gradle": "rootProject.name = 'build-logic'\n",
            "build-logic/build.gradle": "plugins { id 'groovy-gradle-plugin' }\n",
            "build-logic/src/main/groovy/java-conventions.gradle": "plugins { id 'java' }\n// we used buildDir and tasks.create long ago\n/* tasks.create('x') */\ndependencyLocking { lockAllConfigurations() }\njava { consistentResolution { useCompileClasspathVersions() } }\n",
            "app/build.gradle": "plugins { id 'java-conventions' }\n", "app/gradle.lockfile": "# This is a Gradle generated file for dependency locking.\nempty=annotationProcessor\n",
            "core/build.gradle": "plugins { id 'java-conventions' }\n", "core/gradle.lockfile": "# This is a Gradle generated file for dependency locking.\nempty=annotationProcessor\n",
            "api/build.gradle": "plugins { id 'java-conventions' }\n", "api/gradle.lockfile": "# This is a Gradle generated file for dependency locking.\nempty=annotationProcessor\n",
            ".github/workflows/ci.yml": "steps:\n  - uses: gradle/actions/setup-gradle@v4\n",
        },
        must_not={"D4", "D7", "G7", "dep", "Sec2", "G2", "P3", "P2", "C2", "S4", "S5"},
        # The included build is now checked independently; its own catalog/locking
        # absence must not be confused with the root project's effective configuration.
        findings=lambda rows: not any(f["id"] in {"D2", "C1"} and f["build"] == "." for f in rows),
        facts=lambda f: f["subprojects"] == [":api", ":app", ":core"] and f["version_catalogs_imported"] and f["distribution_sha256"] == "set-unverified",
    ),
    dict(
        name="commented-out checksum is not a checksum; bogus checksum flagged",
        files={"settings.gradle": "rootProject.name='x'\n",
               "gradle/wrapper/gradle-wrapper.properties": "distributionUrl=https\\://services.gradle.org/distributions/gradle-9.7.1-bin.zip\n# distributionSha256Sum=TODO\n"},
        must={"Sec1"}, facts=lambda f: f["distribution_sha256"] == "absent",
    ),
    dict(
        name="invalid checksum value",
        files={"settings.gradle": "rootProject.name='x'\n",
               "gradle/wrapper/gradle-wrapper.properties": "distributionUrl=https\\://services.gradle.org/distributions/gradle-9.7.1-bin.zip\ndistributionSha256Sum=TODO\n"},
        facts=lambda f: f["distribution_sha256"] == "invalid",
    ),
    dict(
        name="setup-gradle v4 with validate-wrappers:false is flagged",
        files={"settings.gradle": "rootProject.name='x'\n", "gradle/wrapper/gradle-wrapper.properties": WRAPPER_OK,
               ".github/workflows/ci.yml": "steps:\n  - uses: gradle/actions/setup-gradle@v4\n    with:\n      validate-wrappers: false\n"},
        must={"Sec2"},
    ),
    dict(
        name="mixed DSL flagged as out of scope",
        files={"settings.gradle": "rootProject.name='m'\n", "build.gradle.kts": "plugins { java }\n", "gradle/wrapper/gradle-wrapper.properties": WRAPPER_OK},
        must={"scope"},
    ),
    dict(
        name="internal API in buildSrc groovy class",
        files={"settings.gradle": "rootProject.name='i'\n", "gradle/wrapper/gradle-wrapper.properties": WRAPPER_OK,
               "buildSrc/src/main/groovy/X.groovy": "import org.gradle.api.internal.project.ProjectInternal\nclass X {}\n"},
        must={"G4", "S3"},
    ),
    dict(
        name="legacy build: named deps, apply plugin, repos in project, blanket exclude, ext, subproject props, nested include",
        files={
            "gradle/wrapper/gradle-wrapper.properties": "distributionUrl=https\\://services.gradle.org/distributions/gradle-9.3.0-all.zip\n",
            "settings.gradle": "include 'app'\ninclude 'services:lib'\n",
            "gradle.properties": "org.gradle.jvmargs=-Xmx2g\nspringVersion=6.2.0\n",
            "build.gradle": "ext { junitVersion = '5.11.0' }\nallprojects { repositories { mavenCentral() } }\nsubprojects { apply plugin: 'java'\n afterEvaluate { }\n configurations.all { exclude group: 'commons-logging' }\n def h = 'git rev-parse HEAD'.execute().text\n task pc { doLast { println configurations.runtimeClasspath.files } } }\ndef eager = configurations.runtimeClasspath.resolve()\n",
            "app/build.gradle": "apply plugin: 'application'\nmainClassName = 'M'\ndependencies { implementation group: 'g', name: 'a', version: '1'\n implementation 'g:b:1.+' }\ntask copyDocs(type: Copy) { from \"$buildDir/docs\" }\ndef it2 = tasks.register('it', Test) { }\n",
            "services/lib/build.gradle": "plugins { id 'java-library' }\ntest { useJUnit() }\n",
            "services/lib/gradle.properties": "x=1\n",
        },
        must={"G2", "G3", "G8", "D1", "D4", "D8", "9.6.0", "G7", "S4", "S5", "P4", "T5", "dep", "C1", "9.0.0", "P5", "Sec1", "D2", "G6"},
        facts=lambda f: f["subprojects"] == [":app", ":services:lib"],
    ),
    dict(
        name="pull_request_target running gradlew is flagged",
        files={"settings.gradle": "rootProject.name='x'\n", "gradle/wrapper/gradle-wrapper.properties": WRAPPER_OK,
               ".github/workflows/pr.yml": "on: pull_request_target\nsteps:\n  - uses: gradle/actions/setup-gradle@v4\n  - run: ./gradlew build\n"},
        must={"Sec3"},
    ),
    dict(
        name="nested included builds, nested buildSrc and cycle are discovered once",
        files={
            "settings.gradle": "rootProject.name='root'\nincludeBuild 'logic'\n",
            "logic/settings.gradle": "includeBuild 'nested'\nincludeBuild '..'\n",
            "logic/nested/settings.gradle": "rootProject.name='nested'\n",
            "logic/nested/build.gradle": "apply plugin: 'java'\n",
            "logic/buildSrc/build.gradle": "plugins { id 'groovy-gradle-plugin' }\n",
        },
        facts=lambda f: {b["dir"] for b in f["builds"]} == {".", "logic", "logic/nested", "logic/buildSrc"},
        findings=lambda rows: any(f["id"] == "G3" and f["where"] == "logic/nested/build.gradle:1"
                                  and f["confidence"] == "likely" and f["evidence"] == "apply plugin: 'java'"
                                  and f["applicability"] == "needs-review" for f in rows),
    ),
    dict(
        name="repository roles remain separate, even with braces in strings",
        files={
            "settings.gradle": "rootProject.name='repos'\n",
            "build.gradle": "publishing { repositories { maven { url = uri('https://repo/{x}') } } }\n"
                            "buildscript { repositories { mavenCentral() } }\n"
                            "repositories { mavenCentral() }\n",
        },
        findings=lambda rows: [(f["where"], f["confidence"]) for f in rows if f["id"] == "D4"] == [("build.gradle:3", "likely")],
    ),
    dict(
        name="comments and code-looking quoted, triple-quoted and slashy literals are not code",
        files={
            "settings.gradle": "rootProject.name='strings'\n// includeBuild '../forbidden'\n",
            "build.gradle": "def example = '''\napply plugin: 'java'\nafterEvaluate {}\ntasks.create('x')\nrepositories {}\n'''\n"
                            'def another = """\nsubprojects {}\n"""\n'
                            "def slashy = /tasks.create('fake')/\n"
                            "def dollar = $/afterEvaluate { repositories {} }/$\n"
                            "// buildDir\n/* tasks.create('old') */\n",
        },
        must_not={"G3", "G8", "dep", "D4", "S5"},
    ),
    dict(
        name="programmatic catalog and per-configuration locking are recognized",
        files={
            "settings.gradle": "rootProject.name='catalog'\ndependencyResolutionManagement { versionCatalogs { libs { library('guava', 'com.google.guava', 'guava').version('33.0.0-jre') } } }\n",
            "build.gradle": "configurations.configureEach { resolutionStrategy.activateDependencyLocking() }\n",
            "gradle.lockfile": "empty=runtimeClasspath\n",
        },
        must_not={"D2", "C1"},
        facts=lambda f: f["version_catalog_declaration_observed"] and len(f["locking_observations"]) == 1
            and f["locking_observations"][0]["file"] == "build.gradle" and f["locking_observations"][0]["activated"]
            and f["dependency_locking_configured"] is True,
    ),
    dict(
        name="multiple imported catalogs are retained",
        files={"settings.gradle": "rootProject.name='catalogs'\ndependencyResolutionManagement { versionCatalogs { tools { from(files('gradle/tools.toml')) }; tests { from('org.example:tests:1') } } }\n"},
        must_not={"D2"},
        facts=lambda f: {c["name"] for c in f["version_catalogs_imported"]} == {"tools", "tests"},
    ),
    dict(
        name="Kotlin scripts are not read or audited",
        files={"settings.gradle.kts": 'rootProject.name = "kotlin"\nval example = "jcenter()"\n',
               "build.gradle.kts": 'plugins { java }\n'},
        must={"scope", "coverage"}, must_not={"D4", "G6"},
        facts=lambda f: not any(p.endswith('.kts') for p in f["coverage"]["scanned_files"]),
    ),
    dict(
        name="applied scripts are not orphan projects and still get code rules",
        files={"settings.gradle": "rootProject.name='applied'\n",
               "build.gradle": "apply from: 'gradle/common.gradle'\n",
               "gradle/common.gradle": "afterEvaluate {}\n"},
        must={"G3", "G8"}, must_not={"S4"},
        findings=lambda rows: any(f["id"] == "G8" and f["where"] == "gradle/common.gradle:1" for f in rows),
    ),
    dict(
        name="explicit task actions do not trigger eager resolution rules",
        files={"settings.gradle": "rootProject.name='actions'\n",
               "build.gradle": "tasks.register('x') { doLast { println configurations.runtimeClasspath.resolve(); println value.get() } }\n"},
        must_not={"T4", "T5"},
    ),
    dict(
        name="dynamic discovery is reported, not silently considered complete",
        files={"settings.gradle": "rootProject.name='dynamic'\nincludeBuild computeLogicPath()\ninclude projectNames\nproject(':app').projectDir = directoryProvider.get().asFile\n"},
        must={"coverage"},
        facts=lambda f: len(f["coverage"]["unresolved"]) == 3 and f["coverage"]["complete"] is False,
    ),
    dict(
        name="included build locking is not claimed as root build locking",
        files={"settings.gradle": "rootProject.name='unlocked'\nincludeBuild 'logic'\n",
               "logic/settings.gradle": "rootProject.name='logic'\n",
               "logic/build.gradle": "dependencyLocking { lockAllConfigurations() }\n",
               "logic/gradle.lockfile": "empty=runtimeClasspath\n"},
        findings=lambda rows: any(f["id"] == "C1" and f["confidence"] == "suspected" and 'No locking declaration' in f["message"] for f in rows),
        facts=lambda f: f["lockfiles"] == 0 and f["dependency_locking_configured"] is None,
    ),
    dict(
        name="absence findings acknowledge plugin-supplied configuration",
        files={"settings.gradle": "plugins { id 'com.example.settings' version '1' }\n"},
        findings=lambda rows: all(f["confidence"] == "suspected" for f in rows if f["id"] in {"G6", "D2", "C1"}),
    ),
    dict(
        name="workflow signals are not merged across unrelated files",
        files={"settings.gradle": "rootProject.name='ci'\n",
               ".github/workflows/issue.yml": "on: pull_request_target\njobs: {}\n",
               ".github/workflows/build.yml": "on: push\nsteps:\n  - run: ./gradlew build\n"},
        must_not={"Sec3"},
    ),
    dict(
        name="allprojects dependencyLocking block without activation locks nothing",
        files={"settings.gradle": "rootProject.name='lock'\ninclude 'app', 'core'\n",
               "build.gradle": "allprojects {\n    dependencyLocking {\n        lockMode = LockMode.STRICT\n    }\n}\n",
               "app/build.gradle": "plugins { id 'java' }\n", "core/build.gradle": "plugins { id 'java' }\n",
               "app/gradle.lockfile": "com.google.guava:guava:33.0.0-jre=compileClasspath,runtimeClasspath\nempty=annotationProcessor\n"},
        findings=lambda rows: any(f["id"] == "C1" and f["confidence"] == "confirmed" and f["where"] == "build.gradle"
                                  and "without lockAllConfigurations" in f["message"] for f in rows),
        facts=lambda f: f["locking"][":core"]["declared_in"] == ["build.gradle"] and f["locking"][":core"]["activated"] is False
            and f["locking"][":app"]["entries"] == 1 and f["dependency_locking_configured"] is False,
    ),
    dict(
        name="activated allprojects locking with STRICT mode reports each project missing a lockfile",
        files={"settings.gradle": "rootProject.name='lock'\ninclude 'app', 'core', 'util'\n",
               "build.gradle": "allprojects { dependencyLocking { lockAllConfigurations(); lockMode = LockMode.STRICT } }\n",
               "app/build.gradle": "plugins { id 'java' }\n", "core/build.gradle": "plugins { id 'java' }\n",
               "util/build.gradle": "plugins { id 'java' }\n",
               "app/gradle.lockfile": "empty=annotationProcessor\n"},
        findings=lambda rows: any(f["id"] == "C1" and f["severity"] == "high" and "STRICT" in f["message"]
                                  and ":core" in f["message"] and ":util" in f["message"] and ":app" not in f["message"]
                                  for f in rows),
        facts=lambda f: f["lock_mode"] == "STRICT" and f["locking"][":app"]["activated"] and f["dependency_locking_configured"] is False,
    ),
    dict(
        name="subprojects locking with every subproject lockfile present is clean; root is deliberately excluded",
        files={"settings.gradle": "rootProject.name='lock'\ninclude 'app', 'core'\n",
               "build.gradle": "subprojects { dependencyLocking.lockAllConfigurations() }\n",
               "app/build.gradle": "plugins { id 'java' }\n", "core/build.gradle": "plugins { id 'java' }\n",
               "app/gradle.lockfile": "empty=annotationProcessor\n", "core/gradle.lockfile": "empty=annotationProcessor\n"},
        must_not={"C1"},
        facts=lambda f: f["dependency_locking_configured"] is True and f["locking"][":"]["declared_in"] == [],
    ),
    dict(
        name="convention-plugin locking covers only the projects applying it",
        files={"settings.gradle": "pluginManagement { includeBuild 'build-logic' }\nrootProject.name='lock'\ninclude 'app', 'core', 'legacy'\n",
               "build-logic/settings.gradle": "rootProject.name='build-logic'\n",
               "build-logic/build.gradle": "plugins { id 'groovy-gradle-plugin' }\n",
               "build-logic/src/main/groovy/java-conventions.gradle": "plugins { id 'java' }\ndependencyLocking { lockAllConfigurations() }\n",
               "app/build.gradle": "plugins { id 'java-conventions' }\n", "app/gradle.lockfile": "empty=annotationProcessor\n",
               "core/build.gradle": "plugins { id 'java-conventions' }\n",
               "legacy/build.gradle": "plugins { id 'java' }\n"},
        findings=lambda rows: any(f["id"] == "C1" and f["build"] == "." and "no gradle.lockfile" in f["message"] and ":core" in f["message"] for f in rows)
            and any(f["id"] == "C1" and f["build"] == "." and "not :legacy" in f["message"] for f in rows),
        facts=lambda f: f["locking"][":core"]["declared_in"] == ["build-logic/src/main/groovy/java-conventions.gradle"]
            and f["locking"][":legacy"]["declared_in"] == [],
    ),
    dict(
        name="empty lockfile and lockfile without a matching declaration are flagged low",
        files={"settings.gradle": "rootProject.name='lock'\ninclude 'app'\n",
               "build.gradle": "dependencyLocking { lockAllConfigurations() }\n",
               "gradle.lockfile": "",
               "app/build.gradle": "plugins { id 'java' }\n", "app/gradle.lockfile": "empty=annotationProcessor\n"},
        findings=lambda rows: any(f["id"] == "C1" and f["where"] == "gradle.lockfile" and "no locked modules" in f["message"] for f in rows)
            and any(f["id"] == "C1" and f["severity"] == "low" and ":app" in f["message"] and "no locking declaration applies" in f["message"] for f in rows),
    ),
]


def main():
    failed = 0
    for case in CASES:
        with tempfile.TemporaryDirectory(prefix=".gradle-audit-test-", dir=Path.cwd()) as td:
            root = Path(td)
            write(root, case["files"])
            res = run(root)
            ids = {f["id"] for f in res["findings"]}
            problems = []
            for m in case.get("must", set()):
                if m not in ids:
                    problems.append(f"missing {m}")
            for m in case.get("must_not", set()):
                if m in ids:
                    problems.append(f"false positive {m}: " + "; ".join(f['message'] for f in res['findings'] if f['id'] == m)[:160])
            if "facts" in case and not case["facts"](res["facts"]):
                problems.append("facts assertion failed")
            if "findings" in case and not case["findings"](res["findings"]):
                problems.append("finding evidence/location/confidence assertion failed")
            status = "PASS" if not problems else "FAIL"
            failed += bool(problems)
            print(f"[{status}] {case['name']}")
            for p in problems:
                print(f"       - {p}")
    # bad-argument exit codes
    with tempfile.TemporaryDirectory(prefix=".gradle-audit-test-", dir=Path.cwd()) as td:
        rc = subprocess.run([sys.executable, "-B", str(SCANNER), str(Path(td) / "nonexistent")], capture_output=True, timeout=30).returncode
    print(f"[{'PASS' if rc == 2 else 'FAIL'}] nonexistent directory exits 2")
    failed += rc != 2
    print(f"\n{len(CASES) + 1 - failed}/{len(CASES) + 1} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
