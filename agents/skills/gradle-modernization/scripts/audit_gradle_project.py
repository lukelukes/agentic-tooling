#!/usr/bin/env python3
"""Static audit of a Gradle (Groovy DSL) project against references/best-practices.md.

Usage:  python audit_gradle_project.py <project-root> [--json]

Read-only, root-confined, no symlinks followed. Never runs Gradle. Recursively discovers
literal included builds/buildSrc; reports unresolved discovery and skipped files.
Lexical analysis is not Groovy evaluation; findings are leads, not automatic fixes.

Every finding carries a confidence:
   confirmed  - directly observed file/property fact, not policy applicability
   likely     - executable code pattern; verify scope and applicability before acting
  suspected  - heuristic; may be a false positive
Exit codes: 0 ok, 2 bad arguments / not a Gradle project.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

from static_support import ConfinedFiles, Groovy

LATEST_GRADLE = "9.7.1"   # verify at https://gradle.org/releases/ ; bump when a new release ships
LAST_VERIFIED = "2026-09-06"
PATCHED = {"9.2.0": "9.2.1", "9.3.0": "9.3.1", "9.4.0": "9.4.1", "9.6.0": "9.6.1", "9.7.0": "9.7.1"}
SKIP_DIRS = {".git", ".gradle", ".gradle-modernization", "build", "out", "node_modules", ".idea", "target"}
GAV_RE = re.compile(r"""['"]([A-Za-z0-9_.\-]+):([A-Za-z0-9_.\-]+):([^'"\s:]+)['"]""")


# ----------------------------------------------------------------------------- helpers
def strip_comments(src: str) -> str:
    return Groovy(src).text


def block(src: str, name: str) -> str:
    """Return a top-level block, matching braces only in executable code."""
    return Groovy(src).body(name)


def line_of(src: str, pos: int) -> int:
    return src.count("\n", 0, pos) + 1


def parse_properties(txt: str) -> dict:
    props = {}
    for ln in txt.splitlines():
        s = ln.strip()
        if not s or s[0] in "#!":
            continue
        parts = re.split(r"\s*[=:]\s*|\s+", s, maxsplit=1)
        props[parts[0]] = parts[1].strip() if len(parts) == 2 else ""
    return props


def version_tuple(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


# ----------------------------------------------------------------------------- model
@dataclass
class Build:
    name: str
    dir: Path
    kind: str                       # root | buildSrc | included
    settings: Path | None = None
    projects: dict = field(default_factory=dict)   # path ':a:b' -> dir
    kts: list = field(default_factory=list)
    facts: dict = field(default_factory=dict)


@dataclass
class Finding:
    id: str
    severity: str        # high | medium | low
    confidence: str      # confirmed | likely | suspected
    message: str
    where: str | None = None
    evidence: str | None = None
    applicability: str = "needs-review"
    build: str | None = None


class Audit:
    def __init__(self, root: Path):
        self.root = Path(os.path.abspath(root))
        self.fs = ConfinedFiles(self.root, SKIP_DIRS)
        self.facts: dict = {"schema_version": 3, "latest_gradle": LATEST_GRADLE, "rules_last_verified": LAST_VERIFIED}
        self.findings: list[Finding] = []
        self.builds: list[Build] = []
        self.sources = {}
        self.unresolved = []
        self.active_build = None
        self.imported_catalog_coords = {}
        self.rule_coverage = {}

    def source(self, path: Path | None) -> Groovy:
        if path is None or path.name.endswith(".gradle.kts"):
            return Groovy("")
        if path not in self.sources:
            self.sources[path] = Groovy(self.fs.read(path))
            for reason in self.sources[path].issues:
                self.incomplete(path, reason)
        return self.sources[path]

    def incomplete(self, path, reason):
        item = {"path": self.rel(Path(path)), "reason": reason}
        if item not in self.unresolved:
            self.unresolved.append(item)

    def add(self, id, sev, conf, msg, where=None, evidence=None):
        self.findings.append(Finding(id, sev, conf, msg, str(where) if where else None, evidence,
                                     build=self.rel(self.active_build.dir) if self.active_build else None))

    def cover(self, b, rules, files, reason="lexical checks only; applicability/effective configuration require review"):
        inspected = sorted({self.rel(p) for p in files if str(p) in self.fs.scanned})
        for rule in rules:
            row = self.rule_coverage[(self.rel(b.dir), rule)]
            row["files"] = sorted(set(row["files"]) | set(inspected))
            if row["files"]:
                row.update(status="static-partial", reason=reason)

    def rel(self, p: Path) -> str:
        try:
            return str(p.relative_to(self.root))
        except ValueError:
            return str(p)

    # ---------------------------------------------------------------- discovery
    def discover(self):
        self._discover_build("root", self.root, "root")
        index = 0
        while index < len(self.builds):
            b = self.builds[index]
            index += 1
            src = self.source(b.settings)
            matched = set()
            for m in src.matches(r"\bincludeBuild\s*\(?\s*['\"]([^'\"$\\]+)['\"]"):
                matched.add(m.start())
                d = self.fs.safe(b.dir / m.group(1))
                if d is not None:
                    if self.fs.is_dir(d):
                        if all(x.dir != d for x in self.builds):
                            self._discover_build(m.group(1), d, "included")
                    else:
                        self.incomplete(b.settings, f"included build not found: {m.group(1)}")
            for m in re.finditer(r"\bincludeBuild\b", src.code):
                if m.start() not in matched:
                    self.incomplete(b.settings, "dynamic/unsupported includeBuild; inspect manually")
            bs = b.dir / "buildSrc"
            if self.fs.is_dir(bs) and all(x.dir != bs for x in self.builds):
                self._discover_build("buildSrc", bs, "buildSrc")
        self.facts["builds"] = [{"name": b.name, "kind": b.kind, "dir": self.rel(b.dir),
                                 "projects": sorted(b.projects)} for b in self.builds]

    def _discover_build(self, name, d: Path, kind):
        b = Build(name, d, kind)
        for cand in ("settings.gradle", "settings.gradle.kts"):
            if self.fs.exists(d / cand):
                b.settings = d / cand
                break
        src = self.source(b.settings)
        b.projects[":"] = d
        # include 'a', 'b', "c"  /  include('a')  /  include(['a','b'])
        matched = set()
        for m in src.matches(r"\binclude\s*\(?\s*((?:\[\s*)?['\"][^'\"$\\]+['\"](?:\s*,\s*['\"][^'\"$\\]+['\"])*)"):
            matched.add(m.start())
            for p in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)):
                path = ":" + p.strip(":").replace("/", ":")
                pdir = self.fs.safe(d / Path(*path.strip(":").split(":")))
                if pdir is not None:
                    b.projects[path] = pdir
        for m in re.finditer(r"\binclude(?:Flat)?\b", src.code):
            if m.start() not in matched:
                self.incomplete(b.settings, "dynamic/unsupported project include; inspect manually")
        mapped = set()
        for m in src.matches(r"project\s*\(\s*['\"]([^'\"$\\]+)['\"]\s*\)\s*\.projectDir\s*=\s*file\s*\(\s*['\"]([^'\"$\\]+)['\"]\s*\)"):
            key = ":" + m.group(1).lstrip(":")
            mapped.add(src.code.index(".projectDir", m.start(), m.end()))
            pdir = self.fs.safe(d / m.group(2))
            if pdir is not None:
                b.projects[key] = pdir
            else:
                b.projects.pop(key, None)
        for m in re.finditer(r"\.projectDir\s*=", src.code):
            if m.start() not in mapped:
                self.incomplete(b.settings, "dynamic/unsupported projectDir mapping; inferred paths may be incomplete")
        for dp, files in self.fs.walk(d, build_boundaries=True):
            b.kts.extend(p for p in files if p.name.endswith(".gradle.kts"))
        for pdir in b.projects.values():
            p = pdir / "build.gradle.kts"
            if self.fs.exists(p) and p not in b.kts:
                b.kts.append(p)
        self.builds.append(b)

    # ---------------------------------------------------------------- file classification
    def classify(self, b: Build):
        """Yield script roles, excluding Kotlin and other build roots."""
        yielded = set()
        if b.settings and not b.settings.name.endswith(".kts"):
            yielded.add(b.settings); yield "settings", b.settings
        for path, pdir in b.projects.items():
            for cand in ("build.gradle",):
                f = pdir / cand
                if self.fs.exists(f) and f not in yielded:
                    yielded.add(f); yield "project", f
        for dp, files in self.fs.walk(b.dir, build_boundaries=True):
            if any(dp.is_relative_to(other.dir) for other in self.builds if other.dir != b.dir and other.dir.is_relative_to(b.dir)):
                continue
            relative = dp.relative_to(b.dir).parts
            in_plugin_src = b.kind in ("included", "buildSrc") and relative[:2] == ("src", "main")
            for p in files:
                f = p.name
                if p in yielded:
                    continue
                if f == "gradle.properties":
                    yield "properties", p
                elif f.endswith(".toml") and dp.name == "gradle":
                    yield "toml", p
                elif f.endswith(".gradle"):
                    yield ("precompiled" if in_plugin_src else "project-unlisted" if f == "build.gradle" else "applied-script"), p
                elif f.endswith((".groovy", ".java", ".kt")) and in_plugin_src:
                    yield "plugin-src", p

    # ---------------------------------------------------------------- checks
    def run(self):
        self.discover()
        rootb = self.builds[0]
        ids = [f"{prefix}{n}" for prefix, count in (("G", 9), ("S", 5), ("D", 9), ("T", 11),
                                                    ("P", 5), ("Sec", 4), ("Te", 1), ("C", 2))
               for n in range(1, count + 1)]
        ids += sorted({row[0] for row in self.RULES} - set(ids))
        for b in self.builds:
            for rule in ids:
                self.rule_coverage[(self.rel(b.dir), rule)] = {
                    "build": self.rel(b.dir), "rule": rule, "status": "not-checked", "files": [],
                    "reason": "no applicable readable input checked by a static detector; manual/dynamic review required"}
        self.active_build = rootb
        self.check_wrapper()
        self.check_dsl()
        for b in self.builds:
            self.active_build = b
            self.check_settings(b)
            self.check_catalog(b)
        # Retain root-level fact aliases for existing report consumers; per-build facts are authoritative.
        self.facts.update(rootb.facts)
        self.active_build = rootb
        self.check_properties()
        self.check_scripts()
        for b in self.builds:
            self.active_build = b
            self.check_locking(b)
        self.facts.update(rootb.facts)
        self.active_build = rootb
        self.check_ci()
        self.cover(rootb, ["G2", "P5", "Sec1"], [self.root / "gradle/wrapper/gradle-wrapper.properties"])
        self.cover(rootb, ["G5", "P1", "P2", "P3"], [self.root / "gradle.properties"])
        self.cover(rootb, ["Sec2", "Sec3"], [Path(p) for p in self.fs.scanned if Path(p).is_relative_to(self.root / ".github/workflows")])
        self.active_build = None
        self.facts["build_facts"] = {self.rel(b.dir): b.facts for b in self.builds}
        self.facts["coverage"] = {
            "scanned_files": sorted(self.rel(Path(p)) for p in self.fs.scanned),
            "skipped_paths": sorted(self.fs.skipped.values(), key=lambda x: (x["path"], x["reason"])),
            "unresolved": self.unresolved,
            "excluded_directories": sorted(SKIP_DIRS),
            "rules": list(self.rule_coverage.values()),
            "model": "static lexical leads only; no plugin execution or effective configuration evaluation",
            "complete": False,
        }
        if self.fs.skipped or self.unresolved:
            self.add("coverage", "medium", "confirmed", "Static coverage has gaps; inspect facts.coverage before drawing conclusions")

    def check_wrapper(self):
        wp = self.root / "gradle" / "wrapper" / "gradle-wrapper.properties"
        props = parse_properties(self.fs.read(wp))
        if self.fs.unavailable(wp):
            self.facts["gradle_version"] = None
            self.facts["distribution_sha256"] = "not-checked"
            return
        url = props.get("distributionUrl", "").replace("\\:", ":")
        m = re.search(r"gradle-([0-9][0-9.]*(?:-[a-z0-9-]+)?)-(bin|all)\.zip", url)
        if not m:
            self.facts["gradle_version"] = None
            self.add("G2", "high", "confirmed", "No parseable distributionUrl in gradle-wrapper.properties", wp)
        else:
            cur, dist = m.group(1), m.group(2)
            self.facts["gradle_version"], self.facts["distribution_type"] = cur, dist
            if version_tuple(cur) < version_tuple(LATEST_GRADLE):
                self.add("G2", "medium", "confirmed", f"Gradle {cur} < latest {LATEST_GRADLE} (as of {LAST_VERIFIED}; re-check gradle.org/releases)", wp)
            if cur in PATCHED:
                self.add("G2", "high", "confirmed", f"Gradle {cur} has patch release {PATCHED[cur]}" + (" — 9.3.0 has security advisories" if cur == "9.3.0" else ""), wp)
            if version_tuple(cur) < (9,):
                self.add("G2", "high", "confirmed", "8.x → 9.x is a major upgrade: inventory plugin compatibility first (see SKILL.md 'Wrapper upgrades')", wp)
            if dist == "all":
                self.add("P5", "low", "confirmed", "Wrapper uses -all distribution; -bin is smaller and sufficient", wp)
        sha = props.get("distributionSha256Sum")
        if sha is None:
            self.facts["distribution_sha256"] = "absent"
            self.add("Sec1", "medium", "confirmed", "distributionSha256Sum not set (a commented-out line does not count)", wp)
        elif not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
            self.facts["distribution_sha256"] = "invalid"
            self.add("Sec1", "high", "confirmed", f"distributionSha256Sum is not a valid SHA-256 ('{sha[:12]}…')", wp)
        else:
            self.facts["distribution_sha256"] = "set-unverified"
            self.add("Sec1", "low", "suspected", "distributionSha256Sum set but NOT verified against gradle.org/release-checksums — verify manually", wp)
        self.facts["wrapper_retries"] = "retries" in props
        daemon = self.root / "gradle" / "gradle-daemon-jvm.properties"
        self.facts["daemon_jvm_properties"] = self.fs.exists(daemon)
        if not self.facts["daemon_jvm_properties"] and not self.fs.unavailable(daemon):
            self.add("9.2.0", "low", "confirmed", "No gradle/gradle-daemon-jvm.properties found; daemon selection may instead be pinned by CI")

    def check_dsl(self):
        kts = [self.rel(p) for b in self.builds for p in b.kts]
        self.facts["kotlin_dsl_files"] = kts
        if kts:
            self.add("scope", "high", "confirmed", f"Kotlin DSL scripts present ({len(kts)}): this skill covers Groovy DSL only; these files are NOT audited", evidence=", ".join(kts[:5]))
            for p in kts:
                self.incomplete(p, "Kotlin DSL not audited; effective settings/project model unknown")

    def check_settings(self, b: Build):
        sp = b.settings
        facts = b.facts
        facts["subprojects"] = sorted(p for p in b.projects if p != ":")
        if sp is None:
            if not any(self.fs.unavailable(b.dir / name) for name in ("settings.gradle", "settings.gradle.kts")):
                self.add("G6", "high", "confirmed", "No settings script found at build root — every Gradle build should have one", b.dir)
            return
        if sp.name.endswith(".kts"):
            facts["root_project_named"] = None
            return
        src = self.source(sp)
        if self.fs.unavailable(sp):
            facts["root_project_named"] = None
            return
        self.cover(b, ["G6", "S4", "D4", "D7"], [sp])
        s = src.text
        facts["root_project_named"] = bool(re.search(r"rootProject\.name\s*=", src.code))
        if not facts["root_project_named"]:
            self.add("G6", "low", "suspected", "No literal rootProject.name assignment found; a settings plugin may set it", sp)
        drm = block(s, "dependencyResolutionManagement")
        facts["repos_in_settings"] = bool(block(drm, "repositories"))
        facts["fail_on_project_repos"] = "FAIL_ON_PROJECT_REPOS" in Groovy(drm).code
        facts["plugin_management"] = bool(block(s, "pluginManagement"))
        facts["feature_previews"] = [m.group(1) for m in src.matches(r"enableFeaturePreview\s*\(?\s*['\"]([A-Z_]+)")]
        # empty intermediate projects
        for path in facts["subprojects"]:
            parts = path.strip(":").split(":")
            for i in range(1, len(parts)):
                mid = ":" + ":".join(parts[:i])
                if mid not in b.projects:
                    d = b.projects[path]
                    self.add("S4", "medium", "likely", f"'{path}' implies intermediate project '{mid}' which is not declared — probably an empty project", sp)
                    break
        # repository filtering — only within the dependency repositories block
        dep_repos = block(drm, "repositories")
        repo_code = Groovy(dep_repos).code
        n = len(re.findall(r"\b(mavenCentral|google|mavenLocal|jcenter|gradlePluginPortal)\s*\(|\bmaven\s*\{|\bivy\s*\{", repo_code))
        filtered = ("content" in repo_code) or ("exclusiveContent" in repo_code)
        facts["dependency_repo_count"] = n
        if n >= 2 and not filtered:
            self.add("D7", "medium", "likely", f"{n} dependency repositories in dependencyResolutionManagement without content filtering", sp)
        if "mavenLocal()" in repo_code:
            self.add("D7", "medium", "likely", "mavenLocal() in dependency repositories — review reproducibility", sp)
        if "jcenter()" in src.code:
            self.add("D4", "high", "likely", "jcenter() referenced — the repository is shut down", sp)
        if facts["repos_in_settings"] and not facts["fail_on_project_repos"]:
            self.add("D4", "low", "suspected", "No literal FAIL_ON_PROJECT_REPOS found beside settings repositories; verify effective policy", sp)

    def check_properties(self):
        gp = self.root / "gradle.properties"
        props = parse_properties(self.fs.read(gp))
        keys = ["org.gradle.caching", "org.gradle.configuration-cache", "org.gradle.parallel",
                "org.gradle.jvmargs", "org.gradle.console", "org.gradle.isolated-projects"]
        self.facts["flags"] = {k: props.get(k) for k in keys}
        if self.fs.unavailable(gp):
            return
        if re.search(r"\\\s*\n", self.fs.read(gp)):
            self.incomplete(gp, "continued Java properties are not parsed; effective flags unknown")
            self.facts["flags"] = {k: None for k in keys}
            return
        if props.get("org.gradle.caching") != "true":
            self.add("P2", "low", "confirmed", "org.gradle.caching=true not declared in root gradle.properties; effective flag not checked", gp)
        if props.get("org.gradle.configuration-cache") != "true":
            self.add("P3", "medium", "confirmed", "org.gradle.configuration-cache=true not declared in root gradle.properties; assess store/reuse and actual task execution", gp)
        if props.get("org.gradle.parallel") != "true" and len(self.facts.get("subprojects", [])) > 1:
            self.add("G5", "low", "confirmed", "org.gradle.parallel=true not declared in root gradle.properties; effective flag not checked", gp)
        if "file.encoding=UTF-8" not in props.get("org.gradle.jvmargs", ""):
            self.add("P1", "low", "confirmed", "org.gradle.jvmargs lacks -Dfile.encoding=UTF-8", gp)
        if any(k.startswith("org.gradle.unsafe.isolated-projects") for k in props):
            self.add("9.7.0", "low", "confirmed", "Legacy isolated-projects property observed; rename only on 9.7+ (removal version not announced)", gp)
        vers = [k for k in props if re.search(r"version", k, re.I) and not k.startswith("org.gradle")]
        if vers:
            self.add("D2", "low", "likely", f"root gradle.properties holds dependency versions {vers[:5]} — catalog candidates", gp)
        # G7: gradle.properties in a *subproject* of any build. A build's own root properties file is legitimate.
        for b in self.builds:
            self.active_build = b
            for kind, p in self.classify(b):
                if kind == "properties" and p.parent != b.dir and p.parent in b.projects.values():
                    self.fs.read(p)
                    self.cover(b, ["G7"], [p])
                    self.add("G7", "low", "confirmed", f"gradle.properties in subproject of build '{b.name}'", p)

    def check_catalog(self, b: Build):
        facts = b.facts
        cat = b.dir / "gradle" / "libs.versions.toml"
        src = self.source(b.settings)
        imported = []
        for start, end, name in src.blocks:
            if name != "versionCatalogs":
                continue
            catalog = Groovy(src.text[start + 1:end])
            for m in catalog.matches(r"\bfrom\s*\(\s*(?:files\s*\(\s*)?['\"]([^'\"$\\]+)['\"]"):
                parents = catalog.parents(m.start())
                imported.append({"name": parents[-1] if parents else "unknown", "from": m.group(1)})
                if GAV_RE.fullmatch("'" + m.group(1) + "'"):
                    self.incomplete(b.settings, f"published catalog contents not resolved: {m.group(1)}")
                else:
                    target = self.fs.safe(b.dir / m.group(1))
                    if target is not None:
                        self.incomplete(target, "imported catalog contents require a separate semantic review")
        exists = self.fs.exists(cat)
        facts["version_catalog_file"] = None if self.fs.unavailable(cat) else exists
        settings_unknown = (b.settings is not None and (b.settings.name.endswith(".kts") or self.fs.unavailable(b.settings))) or any(
            self.fs.unavailable(b.dir / name) for name in ("settings.gradle", "settings.gradle.kts"))
        facts["version_catalogs_imported"] = imported
        facts["version_catalog_declaration_observed"] = None if settings_unknown else bool(re.search(r"\bversionCatalogs\b", src.code))
        self.imported_catalog_coords[b.dir] = {entry["from"] for entry in imported}
        if facts["version_catalog_file"] is False and facts["version_catalog_declaration_observed"] is False:
            self.add("D2", "medium", "suspected", "No catalog found by static analysis; settings plugins or unsupported DSL may supply one", b.dir)
        if facts["version_catalog_file"]:
            aliases = re.findall(r"^\s*([A-Za-z0-9_.\-]+)\s*=", self.fs.read(cat), re.M)
            bad = [a for a in aliases if "_" in a and a not in ("version", "version.ref")]
            if bad:
                self.add("D3", "low", "likely", f"catalog keys with underscores (valid syntax; optional naming preference): {bad[:5]}", cat)
        self.cover(b, ["D2"], [p for p in (b.settings, cat) if p is not None])
        self.cover(b, ["D3"], [cat])

    RULES = [
        # id, severity, confidence, contexts, regex, message
        ("G3", "low", "likely", {"project", "project-unlisted"}, re.compile(r"^\s*apply\s+plugin\s*:", re.M), "legacy plugin application — consider plugins {} where its scope/ordering permits"),
        ("G3", "medium", "likely", {"project", "project-unlisted"}, re.compile(r"^\s*apply\s+from\s*:", re.M), "apply from: script — candidate for a convention plugin"),
        ("G4", "medium", "likely", {"project", "project-unlisted", "precompiled", "plugin-src", "settings"}, re.compile(r"org\.gradle\.(?:api\.)?internal\.|org\.gradle\.util\.(?!GradleVersion\b)"), "internal API reference"),
        ("G8", "medium", "likely", {"project", "project-unlisted", "precompiled", "plugin-src"}, re.compile(r"\bafterEvaluate\s*[{(]|\bprojectsEvaluated\b"), "afterEvaluate usage"),
        ("D1", "medium", "likely", {"project", "project-unlisted", "precompiled"}, re.compile(r"\b(api|implementation|compileOnly|runtimeOnly|testImplementation|testRuntimeOnly|annotationProcessor|classpath)\s*\(?\s*group\s*:"), "named-argument dependency notation (removed in Gradle 10)"),
        ("D4", "medium", "likely", {"project", "project-unlisted", "precompiled"}, re.compile(r"(?<![\w.])repositories\s*\{"), "possible project dependency repositories — verify scope before centralizing in settings"),
        ("D8", "medium", "likely", {"project", "project-unlisted", "precompiled"}, re.compile(r"configurations\.(all|configureEach)\s*\{[^}]*\bexclude\b", re.S), "blanket exclude on all configurations"),
        ("D8", "low", "likely", {"project", "project-unlisted", "precompiled"}, re.compile(r"\bexclude\s*\(?\s*group\s*:\s*['\"][^'\"]+['\"]\s*\)?\s*(\}|$)", re.M), "exclude by group only (no module:)"),
        ("T1", "low", "suspected", {"project", "project-unlisted", "precompiled"}, re.compile(r"\bdependsOn\b"), "dependsOn — check whether output→input wiring would do"),
        ("T4", "medium", "suspected", {"project", "project-unlisted", "precompiled"}, re.compile(r"\.get\(\)"), ".get() on a provider — violation only if outside doFirst/doLast/@TaskAction"),
        ("T5", "high", "likely", {"project", "project-unlisted", "precompiled"}, re.compile(r"configurations\.\w+\.(?:resolve\(\)|(?:files|resolvedConfiguration|asPath|incoming\.files)\b)"), "configuration resolution outside an explicit task action — verify execution context"),
        ("T10", "medium", "suspected", {"project", "project-unlisted", "precompiled"}, re.compile(r"\bproject\.(copy|exec|file|delete|javaexec|zipTree|tarTree|fileTree)\s*[({]"), "project.<service>() — violation only if inside a task action"),
        ("dep", "medium", "likely", {"project", "project-unlisted", "precompiled"}, re.compile(r"(?<![\w.])buildDir\b|\$buildDir\b|\bproject\.buildDir\b"), "buildDir — use layout.buildDirectory"),
        ("dep", "medium", "likely", {"project", "project-unlisted", "precompiled"}, re.compile(r"tasks\.create\s*\(|^\s*task\s+\w+\s*[({]", re.M), "eager task creation — use tasks.register"),
        ("dep", "medium", "likely", {"project", "project-unlisted", "precompiled"}, re.compile(r"tasks\.withType\s*\([^)]*\)\s*\{"), "eager tasks.withType{} — add .configureEach"),
        ("dep", "high", "likely", {"project", "project-unlisted", "precompiled"}, re.compile(r"^\s*(compile|runtime|testCompile|testRuntime)\s+['\"(]", re.M), "removed configuration (compile/runtime) — implementation/runtimeOnly"),
        ("dep", "medium", "likely", {"project", "project-unlisted", "precompiled"}, re.compile(r"\bmainClassName\s*="), "mainClassName — use application { mainClass = ... }"),
        ("dep", "medium", "likely", {"project", "project-unlisted", "precompiled"}, re.compile(r"^\s*(sourceCompatibility|targetCompatibility)\s*=", re.M), "sourceCompatibility — prefer java { toolchain {} } + options.release (policy decision)"),
        ("dep", "low", "suspected", {"project", "project-unlisted", "precompiled"}, re.compile(r"\buseJUnit\s*\(\s*\)"), "useJUnit() — JUnit 4 intended? JUnit 5 needs useJUnitPlatform()"),
        ("9.0.0", "high", "likely", {"project", "project-unlisted", "precompiled"}, re.compile(r"tasks\.register\s*\(\s*['\"]\w+['\"]\s*,\s*Test\s*\)"), "custom Test task — since 9.0 it no longer inherits testClassesDirs/classpath; verify it still runs tests"),
        ("Sec4", "low", "likely", {"project", "project-unlisted", "precompiled"}, re.compile(r"new\s+Date\s*\(|System\.currentTimeMillis|user\.name|\bLocalDateTime\.now"), "volatile value — check it isn't embedded in build output"),
        ("9.6.0", "medium", "suspected", {"project", "project-unlisted"}, re.compile(r"\bext\.\w+\s*=|^\s*ext\s*\{", re.M), "ext declaration — not itself deprecated; inspect child consumers for implicit parent lookup"),
        ("9.4.0", "medium", "likely", {"project", "project-unlisted", "precompiled", "plugin-src"}, re.compile(r"\b(?:tasks|configurations|sourceSets)\.findAll\s*[{(]"), "DomainObjectCollection.findAll(Closure) deprecated since 9.4; use matching with ordering/timing review (removed in 10)"),
        ("9.4.0", "medium", "suspected", {"project", "project-unlisted", "precompiled", "plugin-src"}, re.compile(r"\b(?:beforeTest|afterTest|beforeSuite|afterSuite|onOutput)\s*\{"), "possible deprecated Test closure listener; verify receiver, then use typed listeners (removed in 10)"),
        ("9.6.0", "medium", "likely", {"project", "project-unlisted", "precompiled", "plugin-src", "settings"}, re.compile(r"\bproject\.(?:properties\b|getProperties\s*\()"), "Project properties enumeration deprecated since 9.6; use explicit providers/maps, preserving ext values (removed in 10)"),
        ("9.1.0", "medium", "suspected", {"project", "project-unlisted", "precompiled"}, re.compile(r"\bconfigurations\.archives\b|\barchives\s*\("), "possible deprecated archives configuration; inspect outgoing artifacts/publication semantics (removed in 10)"),
        ("P4", "medium", "likely", {"project", "project-unlisted", "precompiled", "settings"}, re.compile(r"\.execute\(|Runtime\.getRuntime\(\)\.exec|\.toURL\(\)\.text"), "possible process/network I/O — verify receiver and configuration-time execution (use ValueSource)"),
        ("S5", "medium", "likely", {"project"}, re.compile(r"^\s*(subprojects|allprojects)\s*\{", re.M), "subprojects{}/allprojects{} block — consider behaviour-preserving convention extraction"),
    ]

    def check_scripts(self):
        gav_total = 0
        for b in self.builds:
            self.active_build = b
            for kind, p in self.classify(b):
                if kind in ("properties", "toml"):
                    continue
                raw = self.fs.read(p)
                src = self.source(p)
                s = src.text
                rule_kind = "project-unlisted" if kind == "applied-script" else kind
                if kind == "project-unlisted":
                    self.add("S4", "low", "suspected", f"build.gradle not reachable from any include in build '{b.name}' — orphan or undeclared project?", p)
                if kind in ("project", "project-unlisted", "precompiled", "applied-script"):
                    for literal in src.literals:
                        if literal.delimiter not in ("'", '"'):
                            continue
                        m = GAV_RE.fullmatch(s[literal.start:literal.end])
                        if m is None or not any("dependencies" in parent.split(".") for parent in src.parents(literal.start)):
                            continue
                        coord = f"{m.group(1)}:{m.group(2)}:{m.group(3)}"
                        if coord in self.imported_catalog_coords.get(b.dir, set()):
                            continue
                        gav_total += 1
                    if kind == "project" and p.parent == b.dir and b.kind == "root" and len(b.projects) > 1 \
                            and self.fs.is_dir(b.dir / "src" / "main") and any(Groovy(block(s, "plugins")).matches(r"\bid\s*\(?\s*['\"](java|java-library|application)['\"]")):
                        self.add("S2", "high", "likely", "root project has src/main and declares a Java plugin in a multi-project build", p)
                for rid, sev, conf, ctx, rx, msg in self.RULES:
                    if rule_kind not in ctx:
                        continue
                    if rid == "S5" and (p.parent != b.dir):
                        continue
                    self.cover(b, [rid], [p])
                    # Only the few patterns that actually need literal arguments
                    # match text. All other tokens must be in executable code.
                    needs_literals = rid == "9.0.0" or msg.startswith(("exclude by group", "removed configuration"))
                    matches = src.matches(rx) if needs_literals else rx.finditer(src.code)
                    for m in matches:
                        pos = m.start() + len(m.group()) - len(m.group().lstrip())
                        parents = {part for name in src.parents(pos) for part in name.split(".")}
                        if rid == "D4" and parents & {"publishing", "buildscript", "pluginManagement", "dependencyResolutionManagement"}:
                            continue
                        if rid in ("T4", "T5", "P4") and parents & {"doFirst", "doLast"}:
                            continue
                        ln = line_of(s, pos)
                        ev = raw.splitlines()[ln - 1].strip()[:120] if ln <= len(raw.splitlines()) else None
                        # Syntax does not establish receiver type, control flow, or policy.
                        self.add(rid, sev, conf, msg, f"{self.rel(p)}:{ln}", ev)
        self.facts["gav_literals_in_scripts"] = gav_total
        self.active_build = None
        if gav_total:
            has_cat = self.facts.get("version_catalog_file") or self.facts.get("version_catalog_declaration_observed")
            self.add("D2", "low", "likely", f"{gav_total} 'group:artifact:version' literal(s) in dependency blocks" + (" alongside a catalog" if has_cat else "") + " — optional catalog candidates; preserve declaration-site semantics")
        buildsrc = any(b.kind == "buildSrc" for b in self.builds)
        included = [b.name for b in self.builds if b.kind == "included"]
        self.facts["buildSrc"], self.facts["included_builds"] = buildsrc, included
        if buildsrc and not included:
            self.add("S3", "low", "confirmed", "buildSrc/ in use with no included build-logic build; favor build-logic/ (advisory)")

    LOCK_ACTIVATION = re.compile(r"\blockAllConfigurations\s*\(|\bactivateDependencyLocking\s*\(")

    def _lock_scope(self, src, pos):
        parents = src.parents(pos)
        if "allprojects" in parents:
            return "allprojects"
        if "subprojects" in parents:
            return "subprojects"
        if any(par.startswith("configure") for par in parents):
            return "configure"
        return "self"

    def _lock_declarations(self, src):
        """Each dependencyLocking/activateDependencyLocking use with its scope and whether it activates anything."""
        rows = []
        for m in src.matches(r"\bdependencyLocking\b|\bactivateDependencyLocking\s*\("):
            row = {"pos": m.start(), "scope": self._lock_scope(src, m.start()), "activated": False, "lock_mode": None}
            if m.group().startswith("activateDependencyLocking"):
                row["activated"] = True
            else:
                body = next((src.text[s + 1:e] for s, e, name in src.blocks if name == "dependencyLocking" and s >= m.end() and not src.code[m.end():s].strip()), None)
                if body is None:  # property style: dependencyLocking.lockAllConfigurations()
                    body = src.text[m.end():src.text.find("\n", m.end()) if src.text.find("\n", m.end()) >= 0 else len(src.text)]
                row["activated"] = bool(self.LOCK_ACTIVATION.search(body))
                lm = re.search(r"lockMode\s*=\s*LockMode\.(\w+)", body)
                row["lock_mode"] = lm.group(1) if lm else None
            rows.append(row)
        return rows

    @staticmethod
    def _read_lockfile(text):
        entries = empty = 0
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if not sep:
                continue
            if key == "empty":
                empty += len([c for c in value.split(",") if c])
            else:
                entries += 1
        return entries, empty

    def check_locking(self, b: Build):
        facts = b.facts
        own_sources = []
        project_scripts = {}          # project path -> (script path, Groovy)
        other_scripts = {}            # precompiled/applied script path -> (kind, Groovy)
        for kind, p in self.classify(b):
            if kind in ("project", "project-unlisted", "precompiled", "applied-script"):
                src = self.source(p)
                own_sources.append(src)
                self.cover(b, ["C1"], [p])
                path = next((k for k, d in b.projects.items() if d / "build.gradle" == p), None)
                if path is not None:
                    project_scripts[path] = (p, src)
                else:
                    other_scripts[p] = (kind, src)
        # Precompiled convention plugins live in included builds / buildSrc but apply to this build's projects.
        for other in self.builds:
            if other is b or other.kind not in ("included", "buildSrc"):
                continue
            for kind, p in self.classify(other):
                if kind == "precompiled" and p not in other_scripts:
                    other_scripts[p] = (kind, self.source(p))
        alls = "\n".join(src.code for src in own_sources)
        projects = sorted(b.projects)
        root_path = ":"

        def targets(scope, owner_path):
            if scope == "allprojects":
                return set(projects)
            if scope == "subprojects":
                return set(projects) - {root_path}
            if scope == "configure":
                return None
            return {owner_path}

        applies = {path: [] for path in projects}   # project -> declaration rows applying to it
        unknown_scope = []
        observations = []

        def record(p, kind, rows, owner_path):
            for row in rows:
                obs = {"build": self.rel(b.dir), "file": self.rel(p), "kind": kind, "scope": row["scope"],
                       "activated": row["activated"], "lock_mode": row["lock_mode"]}
                observations.append(obs)
                scoped = targets(row["scope"], owner_path)
                if scoped is None:
                    unknown_scope.append(self.rel(p))
                    continue
                for path in scoped:
                    applies[path].append(obs)

        for path, (p, src) in project_scripts.items():
            record(p, "project", self._lock_declarations(src), path)
        # Convention plugins / applied scripts contribute where a project applies them.
        for p, (kind, src) in other_scripts.items():
            rows = self._lock_declarations(src)
            if not rows:
                continue
            stem = p.name[:-len(".gradle")]
            if kind == "precompiled":
                pattern = r"(?:\bid\s*\(?\s*|\bapply\s*\(?\s*plugin\s*:\s*)['\"]" + re.escape(stem) + r"['\"]"
            else:
                pattern = r"\bapply\s*\(?\s*from\s*:\s*['\"][^'\"]*" + re.escape(p.name) + r"['\"]"
            applied_anywhere = False
            for path, (ps, psrc) in project_scripts.items():
                for m in psrc.matches(pattern):
                    applied_anywhere = True
                    scoped = targets(self._lock_scope(psrc, m.start()), path)
                    for row in rows:
                        obs = {"build": self.rel(b.dir), "file": self.rel(p), "kind": kind, "scope": row["scope"],
                               "activated": row["activated"], "lock_mode": row["lock_mode"], "applied_by": self.rel(ps)}
                        if obs not in observations:
                            observations.append(obs)
                        if scoped is None:
                            unknown_scope.append(self.rel(ps))
                            continue
                        for target in scoped:
                            applies[target].append(obs)
            if not applied_anywhere:
                for row in rows:
                    observations.append({"build": self.rel(b.dir), "file": self.rel(p), "kind": kind, "scope": row["scope"],
                                         "activated": row["activated"], "lock_mode": row["lock_mode"], "applied_by": None})

        custom_location = bool(re.search(r"\blockFile\s*=", alls))
        lm = re.search(r"lockMode\s*=\s*LockMode\.(\w+)", alls)
        facts["lock_mode"] = lm.group(1) if lm else None
        per_project = {}
        for path in projects:
            pdir = b.projects[path]
            lockfile = pdir / "gradle.lockfile"
            present = self.fs.exists(lockfile)
            entries, empty = self._read_lockfile(self.fs.read(lockfile)) if present else (0, 0)
            rows = applies[path]
            per_project[path] = {
                "script": self.rel(project_scripts[path][0]) if path in project_scripts else None,
                "declared_in": sorted({row["file"] for row in rows}),
                "activated": any(row["activated"] for row in rows),
                "lockfile": self.rel(lockfile) if present else None,
                "entries": entries, "empty_configurations": empty,
            }
        facts["locking"] = per_project
        facts["locking_observations"] = observations
        facts["lockfiles"] = sum(1 for row in per_project.values() if row["lockfile"])
        facts["consistent_resolution"] = True if "consistentResolution" in alls else None
        declared = bool(observations)
        declared_applied = any(applies.values())   # at least one declaration resolved to a project of this build
        lockfiles_anywhere = facts["lockfiles"] > 0
        strict = facts["lock_mode"] == "STRICT"

        # 1. Declared but nothing activated.
        for f in sorted({obs["file"] for obs in observations if not obs["activated"]}):
            if not any(obs["activated"] for obs in observations if obs["file"] == f):
                self.add("C1", "medium", "confirmed",
                         "dependencyLocking configured without lockAllConfigurations() or activateDependencyLocking() — no configuration is locked", f)
        # 2. Activated for a project, but no lockfile there.
        missing = [path for path, row in per_project.items() if row["activated"] and not row["lockfile"] and row["script"]]
        if missing and not custom_location:
            self.add("C1", "high" if strict else "medium", "likely",
                     f"locking active for {', '.join(missing[:6])}{'…' if len(missing) > 6 else ''} but no gradle.lockfile in the project directory"
                     + (" — LockMode.STRICT will fail resolution" if strict else "") + "; run `./gradlew dependencies --write-locks` in the same change", self.rel(b.dir))
        elif missing:
            self.add("C1", "low", "suspected",
                     f"custom lockFile location set; default gradle.lockfile absent for {', '.join(missing[:6])} — verify the custom lock state exists", self.rel(b.dir))
        # 3. Lockfile without any locking declaration applying to that project.
        stale = [path for path, row in per_project.items() if row["lockfile"] and not row["declared_in"]]
        if stale and not unknown_scope:
            self.add("C1", "low", "suspected",
                     f"gradle.lockfile present for {', '.join(stale[:6])} but no locking declaration applies statically — plugin-supplied, or stale", self.rel(b.dir))
        # 4. Lockfile with nothing in it.
        for path, row in per_project.items():
            if row["lockfile"] and row["entries"] == 0 and row["empty_configurations"] == 0:
                self.add("C1", "low", "confirmed", "lockfile has no locked modules and no empty= marker; regenerate with --write-locks", row["lockfile"])
        # 5. Some projects covered, others not.
        root_excluded = any(obs["scope"] == "subprojects" for obs in observations)
        uncovered = [path for path, row in per_project.items() if not row["declared_in"] and row["script"] and not row["lockfile"]
                     and not (path == root_path and root_excluded)]
        if declared_applied and uncovered and not unknown_scope:
            self.add("C1", "medium", "likely",
                     f"locking declared for some projects but not {', '.join(uncovered[:6])}{'…' if len(uncovered) > 6 else ''}", self.rel(b.dir))
        if unknown_scope:
            self.add("C1", "low", "suspected",
                     "locking declared inside configure(...) — target projects cannot be resolved statically; check each project's lockfile", sorted(set(unknown_scope))[0])
        if not declared and not lockfiles_anywhere:
            self.add("C1", "medium", "suspected", "No locking declaration or gradle.lockfile found; plugins/custom locations may supply locking", self.rel(b.dir))
        covered = [row for row in per_project.values() if row["declared_in"]]
        facts["dependency_locking_configured"] = (
            None if not declared_applied or unknown_scope
            else bool(covered) and not uncovered and all(row["activated"] and row["lockfile"] for row in covered))
        if declared and block(alls, "buildscript") and not self.fs.exists(b.dir / "buildscript-gradle.lockfile"):
            self.add("C1", "low", "suspected", "No default buildscript-gradle.lockfile found; verify buildscript locking separately", self.rel(b.dir))
        dyn = []
        for src in own_sources:
            for literal in src.literals:
                if literal.delimiter in ("'", '"') and any("dependencies" in parent.split(".") for parent in src.parents(literal.start)):
                    m = GAV_RE.fullmatch(src.text[literal.start:literal.end])
                    if m and re.search(r"\+|^latest\.|^[\[(]", m.group(3)):
                        dyn.append(m.group(3))
        cat = b.dir / "gradle" / "libs.versions.toml"
        if self.fs.exists(cat):
            dyn += re.findall(r"""version\s*=\s*['"]((?:[0-9.]*\+)|latest\.[a-z]+|\[[^\]]*)['"]""", self.fs.read(cat))
        if dyn:
            self.add("C1", "medium", "likely", f"dynamic/range version declarations observed {dyn[:4]} — review locking", self.rel(b.dir))
        # Absence is not evidence of divergent classpaths; C2 needs dynamic comparison.

    def check_ci(self):
        wf = self.root / ".github" / "workflows"
        if not self.fs.is_dir(wf):
            self.facts["ci"] = "no GitHub workflows found (other CI systems not inspected)"
            return
        self.facts["ci"] = []
        for _, files in self.fs.walk(wf):
            for p in files:
                if p.suffix not in (".yml", ".yaml"):
                    continue
                txt = re.sub(r"(?m)^\s*#.*$", "", self.fs.read(p))
                explicit = bool(re.search(r"uses\s*:\s*gradle/(?:actions/wrapper-validation|wrapper-validation-action)@", txt))
                setup = re.search(r"uses\s*:\s*gradle/actions/setup-gradle@v?(\d+)", txt)
                disabled = bool(re.search(r"validate-wrappers\s*:\s*false", txt))
                self.facts["ci"].append({"file": self.rel(p), "wrapper_validation_action_observed": explicit,
                                         "setup_gradle_major": int(setup.group(1)) if setup else None,
                                         "validate_wrappers_disabled_observed": disabled,
                                         "effective_job_protection": "not checked"})
                if re.search(r"pull_request_target", txt) and re.search(r"\./gradlew", txt):
                    self.add("Sec3", "high", "likely", "pull_request_target and ./gradlew in one workflow — inspect checkout ref, permissions, secrets and job conditions", p)
                if explicit or (setup and int(setup.group(1)) >= 4 and not disabled):
                    continue  # candidate only; never claim job-level validation from text presence
                if setup and disabled:
                    self.add("Sec2", "medium", "likely", "setup-gradle and validate-wrappers: false observed without explicit wrapper-validation; inspect jobs", p)
                else:
                    self.add("Sec2", "low", "suspected", "No known wrapper-validation declaration found in workflow; inspect reusable workflows and SHA-pinned actions", p)


# ----------------------------------------------------------------------------- main
def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    root = Path(os.path.abspath(argv[1]))
    a = Audit(root)
    if not a.fs.is_dir(root):
        print(f"error: {root} is not a directory", file=sys.stderr); return 2
    if not any(a.fs.exists(root / f) for f in ("settings.gradle", "settings.gradle.kts", "build.gradle", "build.gradle.kts")):
        print(f"error: {root} has no settings.gradle or build.gradle — not a Gradle build root?", file=sys.stderr); return 2
    a.run()
    seen, findings = set(), []
    for f in a.findings:
        k = (f.id, f.message, f.where, f.build)
        if k not in seen:
            seen.add(k); findings.append(f)
    if "--json" in argv:
        print(json.dumps({"facts": a.facts, "findings": [asdict(f) for f in findings]}, indent=2, default=str)); return 0
    print(f"== Gradle static audit: {root} ==  (read-only; no Gradle executed)")
    for k, v in a.facts.items():
        print(f"  {k}: {v}")
    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda x: (order[x.severity], x.id))
    groups: dict = {}
    for f in findings:
        groups.setdefault((f.id, f.message), []).append(f)
    print(f"\n== Findings ({len(findings)}) ==   [severity/confidence] id: message")
    for (rid, msg), rows in groups.items():
        h = rows[0]
        print(f"[{h.severity}/{h.confidence}] {rid}: {msg}" + (f"  ({len(rows)} locations)" if len(rows) > 1 else ""))
        for r in rows[:6]:
            if r.where:
                print(f"      - {r.where}" + (f"    | {r.evidence}" if r.evidence else ""))
        if len(rows) > 6:
            print(f"      ... and {len(rows) - 6} more")
    print("\n'suspected'/'likely' findings need the line read in context before they count as violations.")
    print("Build-reported problems (deprecations, configuration-cache) require running Gradle — see SKILL.md Preflight first.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
