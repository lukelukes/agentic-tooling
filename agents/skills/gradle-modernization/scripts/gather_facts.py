#!/usr/bin/env python3
"""Gather every fact the Gradle modernization audit needs, static and dynamic, in one run.

Usage: gather_facts.py ROOT [--tasks TASK ...] [--out DIR] [--gradle LAUNCHER]
                       [--static-only] [--skip-cc] [--test-xml :task=DIR ...]
                       [--projects :p ...] [--configurations NAME ...]
                       [--compare-with DIR] [--ignore-task :task ...]
                       [--timeout SECONDS] [--json]

Static (never runs Gradle): the read-only scanner (audit_gradle_project.py) plus a
plugin inventory (plugins {} ids/versions/aliases, apply plugin:, buildscript classpath).

Dynamic, in order. The run stops at the first Gradle command that fails. The
subsequent phases do not run. The summary shows the log tail of the failure:
  1. LAUNCHER --version                          Gradle version, launcher/daemon JVM
  2. help --warning-mode=all                     deprecation warnings
  3. TASKS forced-execution baseline             --no-build-cache --rerun-tasks, existing
                                                 configuration-cache mode, test XML auto-mapped
  4. TASKS twice, --configuration-cache          strict store-then-reuse pair
     --configuration-cache-problems=fail
  5. tasks --provenance (9.5+) or tasks --all    who registered each task
  6. dependencies per project                    split into one report per configuration
  7. buildEnvironment                            buildscript classpaths

Everything lands under --out (default ROOT/.gradle-modernization/baseline, self-gitignored):
raw logs, compare_runs-format summaries, per-configuration dependency reports and
facts.json. Stdout is a short summary; --json prints facts.json instead. With
--compare-with DIR the same evidence is compared against an earlier run (tasks, test
identities, deprecations, configuration-cache pair, dependency reports) and unified
diffs are written to dependency-diffs/.

Exit 0 when each phase ran cleanly, 1 when a Gradle command failed (the run stops
there) or a comparison found differences, 2 for bad arguments. facts.json is written
in all cases.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_gradle_project as scanner  # noqa: E402
from compare_runs import compare, mapping, summarize  # noqa: E402

FORCED = ["--no-build-cache", "--rerun-tasks", "--console=plain", "--warning-mode=all"]
CC_FLAGS = ["--configuration-cache", "--configuration-cache-problems=fail"]
DEFAULT_TASKS = ["check"]
DEFAULT_CONFIGURATIONS = ["compileClasspath", "runtimeClasspath", "testCompileClasspath",
                          "testRuntimeClasspath", "annotationProcessor", "testAnnotationProcessor"]
DEPRECATION = re.compile(r"(?m)^.*has been deprecated.*$")
SECTION_HEAD = re.compile(r"^([A-Za-z][\w.-]*)(?: - (.*))?$")
TREE_LINE = re.compile(r"^(?:[+\\|]|\s|No dependencies|\(n\))")
TEST_LIKE = re.compile(r"(?i)tests?$")


def parse_version_output(text: str) -> dict:
    def grab(label):
        m = re.search(rf"(?m)^{label}:\s*(.+?)\s*$", text)
        return m.group(1) if m else None
    m = re.search(r"(?m)^Gradle (\S+)", text)
    return {"gradle": m.group(1) if m else None, "launcher_jvm": grab("Launcher JVM") or grab("JVM"),
            "daemon_jvm": grab("Daemon JVM"), "os": grab("OS")}


def deprecation_messages(text: str) -> dict:
    lines = [line.strip() for line in DEPRECATION.findall(text)]
    unique: dict[str, int] = {}
    for line in lines:
        key = re.sub(r"\s+", " ", line)[:240]
        unique[key] = unique.get(key, 0) + 1
    return {"count": len(lines), "unique": [{"message": k, "times": v} for k, v in
                                            sorted(unique.items(), key=lambda kv: (-kv[1], kv[0]))]}


def split_dependencies(text: str) -> dict[str, str]:
    """Map configuration name -> its block from a `dependencies` task report."""
    sections: dict[str, str] = {}
    current, buffer = None, []
    started = False
    for line in text.splitlines():
        if not started:
            started = line.startswith("Project ") or line.startswith("Root project ")
            continue
        if line.startswith(("A web-based", "BUILD ", "> Task", "Deprecated Gradle", "(*) ", "(c) ", "(n) ")):
            if current:
                sections[current] = "\n".join(buffer).rstrip() + "\n"
            current, buffer = None, []
            if line.startswith(("A web-based", "BUILD ")):
                started = False
            continue
        head = SECTION_HEAD.match(line)
        if head and not TREE_LINE.match(line):
            if current:
                sections[current] = "\n".join(buffer).rstrip() + "\n"
            current, buffer = head.group(1), [line]
        elif current is not None:
            if line.strip() == "" and buffer and buffer[-1].strip() == "":
                continue
            buffer.append(line)
    if current:
        sections[current] = "\n".join(buffer).rstrip() + "\n"
    return sections


def safe_name(project: str) -> str:
    return "root" if project == ":" else project.strip(":").replace(":", "_")


class Gatherer:
    def __init__(self, args):
        self.args = args
        self.root = Path(os.path.abspath(args.root))
        self.out = Path(os.path.abspath(args.out)) if args.out else self.root / ".gradle-modernization" / "baseline"
        self.facts: dict = {"schema_version": 1, "root": str(self.root), "out": str(self.out),
                            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            "arguments": [a for a in sys.argv[1:]], "commands": [], "gaps": [],
                            "prerequisites": {}, "static": None, "dynamic": {"status": "not-run"}, "comparison": None}
        self.audit = None
        self.launcher: list[str] | None = None
        self.failed = False
        self.test_xml: dict[str, Path] = {}

    # ---------------------------------------------------------------- plumbing
    def gap(self, phase, reason):
        self.facts["gaps"].append({"phase": phase, "reason": reason})

    def write(self, name, data):
        path = self.out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str) if not isinstance(data, str) else data)
        return path

    def rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.out))
        except ValueError:
            return str(path)

    def run(self, label, argv, cwd=None, log=None, timeout=None):
        """Run a command, keep its full output in a log, record only metadata in facts."""
        started = time.time()
        try:
            proc = subprocess.run(argv, cwd=cwd or self.root, capture_output=True, text=True,
                                  timeout=timeout or self.args.timeout, errors="replace")
            text, code = proc.stdout + proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as error:
            text = (error.stdout or "") + (error.stderr or "") + f"\n[gather_facts] timed out after {self.args.timeout}s\n"
            code = -1
        except (OSError, ValueError) as error:
            text, code = f"[gather_facts] could not start: {error}\n", -2
        log_path = None
        if log:
            log_path = self.out / log
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(text)
        self.facts["commands"].append({"label": label, "argv": list(map(str, argv)), "cwd": str(cwd or self.root),
                                       "exit": code, "seconds": round(time.time() - started, 1),
                                       "log": self.rel(log_path) if log_path else None})
        return code, text, started

    def gradle(self, label, arguments, log, cwd=None):
        return self.run(label, [*self.launcher, *arguments], cwd=cwd, log=log)

    def tail(self, text, n=25):
        return "\n".join(text.rstrip().splitlines()[-n:])

    # ---------------------------------------------------------------- phases
    def prepare_out(self):
        self.out.mkdir(parents=True, exist_ok=True)
        marker = self.out.parent / ".gitignore" if self.out.parent.name == ".gradle-modernization" else self.out / ".gitignore"
        if not marker.exists():
            marker.write_text("*\n")

    def prerequisites(self):
        pre = self.facts["prerequisites"]
        code, text, _ = self.run("git-status", ["git", "status", "--porcelain"])
        if code == 0:
            dirty = [line for line in text.splitlines() if line.strip()]
            pre["git"] = {"dirty_files": dirty, "clean": not dirty}
            code, head, _ = self.run("git-head", ["git", "rev-parse", "--short", "HEAD"])
            pre["git"]["head"] = head.strip() if code == 0 else None
        else:
            pre["git"] = {"available": False, "reason": self.tail(text, 3)}
        code, text, _ = self.run("java-version", ["java", "-version"])
        pre["java"] = {"available": code == 0, "version_line": text.strip().splitlines()[0] if text.strip() else None,
                       "JAVA_HOME": os.environ.get("JAVA_HOME")}
        launcher = self.args.gradle
        if launcher:
            self.launcher = [launcher]
        elif (self.root / "gradlew").exists():
            wrapper = self.root / "gradlew"
            self.launcher = [str(wrapper)] if os.access(wrapper, os.X_OK) else ["sh", str(wrapper)]
            if not os.access(wrapper, os.X_OK):
                self.gap("prerequisites", "gradlew is not executable; invoked through sh")
        elif shutil.which("gradle"):
            self.launcher = ["gradle"]
            self.gap("prerequisites", "no gradlew in ROOT; using `gradle` from PATH, whose version may differ from the wrapper's")
        pre["launcher"] = self.launcher

    def static(self):
        try:
            self.audit = scanner.audit(self.root)
        except ValueError as error:
            raise SystemExit(f"error: {error}")
        data = scanner.result(self.audit)
        data["plugins"] = self.plugin_inventory()
        self.facts["static"] = data
        self.write("static.json", data)

    def plugin_inventory(self) -> list[dict]:
        """Lexical inventory of plugin requests; versions from catalog aliases resolved when the TOML parses."""
        rows = []
        for build in self.audit.builds:
            catalog = self.catalog_plugins(build.dir / "gradle" / "libs.versions.toml")
            for kind, path in self.audit.classify(build):
                if kind in ("properties", "toml", "plugin-src"):
                    continue
                src = self.audit.source(path)
                where = self.audit.rel(path)
                body = scanner.Groovy(src.body("plugins"))
                for m in body.matches(r"\bid\s*\(?\s*['\"]([^'\"]+)['\"]\s*\)?(?:\s*\.?\s*version\s*\(?\s*['\"]([^'\"]+)['\"])?"):
                    rows.append({"id": m.group(1), "version": m.group(2), "via": "plugins-block", "file": where, "build": self.audit.rel(build.dir), "kind": kind})
                for m in body.matches(r"\balias\s*\(\s*libs\.plugins\.([\w.]+)\s*\)"):
                    alias = m.group(1).replace(".", "-")
                    entry = catalog.get(alias) or catalog.get(m.group(1))
                    rows.append({"id": entry["id"] if entry else None, "version": entry["version"] if entry else None,
                                 "alias": m.group(1), "via": "catalog-alias", "file": where, "build": self.audit.rel(build.dir), "kind": kind})
                for m in src.matches(r"\bapply\s*\(?\s*plugin\s*:\s*['\"]([^'\"]+)['\"]"):
                    rows.append({"id": m.group(1), "version": None, "via": "apply-plugin", "file": where, "build": self.audit.rel(build.dir), "kind": kind})
                buildscript = scanner.Groovy(src.body("buildscript"))
                for m in scanner.Groovy(buildscript.body("dependencies")).matches(r"\bclasspath\s*\(?\s*['\"]([^'\"]+)['\"]"):
                    rows.append({"id": None, "coordinates": m.group(1), "version": m.group(1).split(":")[-1] if m.group(1).count(":") >= 2 else None,
                                 "via": "buildscript-classpath", "file": where, "build": self.audit.rel(build.dir), "kind": kind})
        return rows

    def catalog_plugins(self, toml_path: Path) -> dict:
        if not toml_path.exists():
            return {}
        try:
            import tomllib
            data = tomllib.loads(toml_path.read_text())
        except Exception as error:  # pragma: no cover - depends on the TOML
            self.gap("static", f"could not parse {toml_path.name}: {error}")
            return {}
        versions = data.get("versions", {})
        result = {}
        for alias, entry in data.get("plugins", {}).items():
            if isinstance(entry, str):
                pid, _, version = entry.partition(":")
            else:
                pid = entry.get("id")
                version = entry.get("version")
                if isinstance(version, dict):
                    version = versions.get(version.get("ref"), version) if "ref" in version else version
            result[alias] = {"id": pid, "version": version}
        return result

    def dynamic(self):
        dyn = self.facts["dynamic"]
        if self.args.static_only:
            dyn.update(status="skipped", reason="--static-only")
            return
        if not self.launcher:
            dyn.update(status="not-run", reason="no gradlew in ROOT and no `gradle` on PATH")
            self.gap("dynamic", dyn["reason"])
            return
        code, text, _ = self.gradle("gradle-version", ["--version"], "version.log")
        if code != 0:
            dyn.update(status="not-run", reason=f"launcher failed: {self.tail(text, 5)}")
            self.gap("dynamic", "Gradle could not start; every build-reported fact is not checked")
            self.failed = True
            return
        dyn.update(status="ran", version=parse_version_output(text), tasks=self.args.tasks,
                   configuration_cache_mode_in_properties=(self.facts["static"]["facts"].get("flags") or {}).get("org.gradle.configuration-cache"))
        phases = [("deprecations", self.deprecations), ("baseline", self.baseline),
                  ("configuration-cache", self.configuration_cache), ("provenance", self.provenance),
                  ("dependencies", self.dependencies), ("buildEnvironment", self.build_environment)]
        for phase, step in phases:
            if phase == "configuration-cache" and self.args.skip_cc:
                self.gap("configuration-cache", "--skip-cc")
                continue
            step()
            if self.failed:
                self.stop(phase)
                return

    def stop(self, phase: str):
        """Record that PHASE failed and that the subsequent phases did not run."""
        self.facts["dynamic"]["stopped_after"] = phase
        self.gap("dynamic", f"stopped after `{phase}` failed; the subsequent phases did not run")

    def deprecations(self):
        code, text, _ = self.gradle("deprecations", ["help", "--warning-mode=all", "--console=plain"], "deprecations.log")
        info = deprecation_messages(text)
        info.update(log="deprecations.log", exit=code)
        self.facts["dynamic"]["deprecations"] = info
        if code != 0:
            self.gap("deprecations", f"`help --warning-mode=all` failed: {self.tail(text, 5)}")
            self.failed = True

    def discover_test_xml(self, tasks: dict[str, str]) -> dict:
        found, unmatched = dict(self.test_xml), []
        for build in self.audit.builds:
            if build.kind == "buildSrc":
                continue
            prefix = "" if build.kind == "root" else f":{build.name}"
            for project, pdir in build.projects.items():
                results = pdir / "build" / "test-results"
                if not results.is_dir():
                    continue
                for directory in sorted(results.iterdir()):
                    if not directory.is_dir() or not any(directory.glob("TEST-*.xml")):
                        continue
                    task = f"{prefix}{'' if project == ':' else project}:{directory.name}"
                    if task in tasks:
                        found.setdefault(task, directory)
                    else:
                        unmatched.append({"directory": self.audit.rel(directory), "guessed_task": task})
        test_like = sorted(t for t in tasks if TEST_LIKE.search(t.rsplit(":", 1)[-1]) and t not in found)
        return {"mapping": found, "unmatched_xml": unmatched, "test_like_tasks_without_xml": test_like}

    def summarize_run(self, label, log_name, started) -> dict:
        summary = summarize(self.out / log_name, self.test_xml)
        stale = []
        for task, directory in self.test_xml.items():
            files = list(Path(directory).rglob("TEST-*.xml"))
            newest = max((f.stat().st_mtime for f in files), default=0)
            if files and newest < started:
                stale.append(task)
        summary["stale_xml"] = stale
        summary["test_xml"] = {task: str(directory) for task, directory in self.test_xml.items()}
        self.write(f"{label}.json", summary)
        return summary

    def baseline(self) -> bool:
        code, text, started = self.gradle("baseline", [*self.args.tasks, *FORCED], "baseline.log")
        tasks = {name: outcome or "EXECUTED" for name, outcome in re.findall(r"(?m)^> Task (:[^\s]+)(?: (\S+))?[^\S\n]*$", text)}
        discovery = self.discover_test_xml(tasks)
        self.test_xml = discovery["mapping"]
        summary = self.summarize_run("baseline", "baseline.log", started)
        summary.update(exit=code, unmatched_xml=discovery["unmatched_xml"],
                       test_like_tasks_without_xml=discovery["test_like_tasks_without_xml"])
        self.write("baseline.json", summary)
        self.facts["dynamic"]["baseline"] = self.digest(summary)
        if code != 0 or not summary["successful"]:
            self.gap("baseline", "baseline build failed; tell the user. Do not make a green baseline")
            self.facts["dynamic"]["baseline"]["failure_tail"] = self.tail(text)
            self.failed = True
            return False
        if not self.test_xml:
            self.gap("baseline", "no JUnit XML matched any executed task; pass --test-xml :task=DIR for relocated reports")
        return True

    def digest(self, summary: dict) -> dict:
        outcomes: dict[str, int] = {}
        for outcome in summary["tasks"].values():
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        return {"log": summary["log"], "successful": summary["successful"], "exit": summary.get("exit"),
                "task_count": len(summary["tasks"]), "outcomes": outcomes,
                "tests": {task: {"outcome": row["outcome"], "counts": row["counts"], "directory": row["directory"]}
                          for task, row in summary["tests"].items()},
                "stale_xml": summary.get("stale_xml", []), "unmatched_xml": summary.get("unmatched_xml", []),
                "test_like_tasks_without_xml": summary.get("test_like_tasks_without_xml", []),
                "configuration_cache": summary["configuration_cache"], "deprecations": summary["deprecations"]}

    def configuration_cache(self):
        arguments = [*self.args.tasks, *CC_FLAGS, *FORCED]
        runs = {}
        for label in ("cc-store", "cc-reuse"):
            code, text, started = self.gradle(label, arguments, f"{label}.log")
            summary = self.summarize_run(label, f"{label}.log", started)
            summary["exit"] = code
            self.write(f"{label}.json", summary)
            runs[label] = summary
            if code != 0:
                self.facts["dynamic"][label] = {**self.digest(summary), "failure_tail": self.tail(text)}
                self.gap("configuration-cache", f"{label} run failed (exit {code}); see {label}.log")
                self.failed = True
                break
            self.facts["dynamic"][label] = self.digest(summary)
        if len(runs) == 2:
            pair = compare(runs["cc-store"], runs["cc-reuse"], cache_pair=True, ignore_tasks=set(self.args.ignore_task))
            self.write("cc-pair.json", pair)
            self.facts["dynamic"]["cc_pair"] = pair
            baseline = json.loads((self.out / "baseline.json").read_text())
            versus = compare(baseline, runs["cc-store"], ignore_tasks=set(self.args.ignore_task))
            self.write("baseline-vs-cc-store.json", versus)
            self.facts["dynamic"]["baseline_vs_cc_store"] = versus
            if not pair["ok"]:
                self.failed = True

    def provenance(self):
        version = self.facts["dynamic"]["version"]["gradle"] or "0"
        supported = scanner.version_tuple(version) >= (9, 5)
        arguments = ["tasks", "--provenance", "--all", "--console=plain"] if supported else ["tasks", "--all", "--console=plain"]
        code, text, _ = self.gradle("provenance", arguments, "provenance.log")
        self.facts["dynamic"]["provenance"] = {"log": "provenance.log", "exit": code, "with_provenance": supported,
                                               "lines": len(text.splitlines())}
        if not supported:
            self.gap("provenance", f"Gradle {version} < 9.5: task report has no --provenance; attribute tasks manually")
        if code != 0:
            self.gap("provenance", f"task report failed: {self.tail(text, 5)}")
            self.failed = True

    def dependencies(self):
        wanted = self.args.configurations
        targets = []
        if self.args.projects:
            targets = [(p, None) for p in self.args.projects]
        else:
            for build in self.audit.builds:
                if build.kind == "buildSrc":
                    self.gap("dependencies", "buildSrc classpaths are not captured (not addressable standalone); use buildEnvironment.log and manual review")
                    continue
                for project in sorted(build.projects):
                    targets.append((project, None if build.kind == "root" else build.dir))
        reports = {}
        for project, build_dir in targets:
            label = safe_name(project) if build_dir is None else f"{build_dir.name}__{safe_name(project)}"
            task = f"{'' if project == ':' else project}:dependencies"
            arguments = (["-p", str(build_dir)] if build_dir else []) + [task, "--console=plain"]
            code, text, _ = self.gradle(f"dependencies {label}", arguments, f"dependencies/{label}.log")
            entry = {"project": project, "build": str(build_dir.relative_to(self.root)) if build_dir else ".",
                     "log": f"dependencies/{label}.log", "exit": code, "configurations": {}}
            if code != 0:
                entry["error"] = self.tail(text, 5)
                self.gap("dependencies", f"{label}: `{task}` failed (exit {code}): {self.tail(text, 5)}")
                self.failed = True
                reports[label] = entry
                break
            else:
                sections = split_dependencies(text)
                entry["configurations_seen"] = sorted(sections)
                for name in wanted:
                    if name in sections:
                        path = self.write(f"dependencies/{label}/{name}.txt", sections[name])
                        entry["configurations"][name] = {"report": self.rel(path), "resolvable": "(n)" not in sections[name].splitlines()[0],
                                                         "failed_entries": sections[name].count("FAILED")}
                    else:
                        entry["configurations"][name] = "N/A"
                for name in sorted(set(sections) - set(wanted)):
                    if name.endswith(("Classpath", "AnnotationProcessor")) and "(n)" not in sections[name].splitlines()[0]:
                        path = self.write(f"dependencies/{label}/{name}.txt", sections[name])
                        entry["configurations"][name] = {"report": self.rel(path), "resolvable": "(n)" not in sections[name].splitlines()[0],
                                                         "failed_entries": sections[name].count("FAILED"), "extra": True}
            reports[label] = entry
        self.facts["dynamic"]["dependencies"] = reports

    def build_environment(self):
        code, text, _ = self.gradle("buildEnvironment", ["buildEnvironment", "--console=plain"], "buildEnvironment.log")
        self.facts["dynamic"]["build_environment"] = {"log": "buildEnvironment.log", "exit": code}
        if code != 0:
            self.gap("buildEnvironment", f"failed: {self.tail(text, 5)}")
            self.failed = True

    # ---------------------------------------------------------------- comparison
    def compare_with(self, before_dir: Path):
        result = {"before": str(before_dir), "ok": True, "problems": [], "runs": {}, "dependencies": {"changed": [], "missing": [], "new": []}}
        ignore = set(self.args.ignore_task)
        for label, cache_pair in (("baseline", False), ("cc-store", False), ("cc-reuse", False)):
            before, after = before_dir / f"{label}.json", self.out / f"{label}.json"
            if not before.exists() or not after.exists():
                result["runs"][label] = "missing on one side"
                continue
            outcome = compare(json.loads(before.read_text()), json.loads(after.read_text()), cache_pair, ignore)
            result["runs"][label] = outcome
            if not outcome["ok"]:
                result["problems"].extend(f"{label}: {p}" for p in outcome["problems"])
        before_reports = {p.relative_to(before_dir / "dependencies"): p for p in (before_dir / "dependencies").rglob("*.txt")} if (before_dir / "dependencies").is_dir() else {}
        after_reports = {p.relative_to(self.out / "dependencies"): p for p in (self.out / "dependencies").rglob("*.txt")} if (self.out / "dependencies").is_dir() else {}
        for key in sorted(set(before_reports) | set(after_reports), key=str):
            if key not in after_reports:
                result["dependencies"]["missing"].append(str(key))
                continue
            if key not in before_reports:
                result["dependencies"]["new"].append(str(key))
                continue
            old, new = before_reports[key].read_text(), after_reports[key].read_text()
            if old != new:
                diff = "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"before/{key}", f"after/{key}"))
                path = self.write(f"dependency-diffs/{str(key).replace('/', '__').replace('.txt', '.diff')}", diff)
                result["dependencies"]["changed"].append({"report": str(key), "diff": self.rel(path)})
        if result["dependencies"]["changed"]:
            result["problems"].append(f"{len(result['dependencies']['changed'])} dependency report(s) changed; see dependency-diffs/")
        if result["dependencies"]["missing"]:
            result["problems"].append("dependency report(s) disappeared: " + ", ".join(result["dependencies"]["missing"]))
        result["ok"] = not result["problems"]
        self.write("comparison.json", result)
        self.facts["comparison"] = result
        if not result["ok"]:
            self.failed = True

    # ---------------------------------------------------------------- output
    def summary_text(self) -> str:
        f, s, d = self.facts, self.facts["static"], self.facts["dynamic"]
        lines = [f"Gradle facts for {self.root}", f"  written to {self.out}/facts.json (static.json, *.log, *.json, dependencies/)"]
        sev = {}
        for row in s["findings"]:
            sev[row["severity"]] = sev.get(row["severity"], 0) + 1
        cov = s["facts"].get("coverage", {})
        lines.append(f"Static: {len(s['findings'])} findings (" + ", ".join(f"{k} {sev.get(k, 0)}" for k in ("high", "medium", "low")) +
                     f"); wrapper {s['facts'].get('gradle_version')}; {len(s['plugins'])} plugin requests; "
                     f"coverage gaps {len(cov.get('skipped_paths', [])) + len(cov.get('unresolved', []))}")
        pre = f["prerequisites"]
        git = pre.get("git", {})
        lines.append("Prerequisites: java " + (pre.get("java", {}).get("version_line") or "not found") +
                     f"; launcher {' '.join(pre.get('launcher') or ['none'])}; git " +
                     ("clean" if git.get("clean") else f"{len(git.get('dirty_files', []))} dirty file(s)" if "dirty_files" in git else "unavailable"))
        if d.get("status") != "ran":
            lines.append(f"Dynamic: {d.get('status')} — {d.get('reason', '')}".rstrip(" —"))
        else:
            v = d["version"]
            lines.append(f"Dynamic: Gradle {v.get('gradle')}; daemon JVM {v.get('daemon_jvm')}; tasks {' '.join(d['tasks'])}; "
                         f"configuration-cache in gradle.properties: {d.get('configuration_cache_mode_in_properties')}")
            dep = d.get("deprecations", {})
            lines.append(f"  deprecations: {dep.get('count')} warning line(s), {len(dep.get('unique', []))} distinct")
            for row in dep.get("unique", [])[:3]:
                lines.append(f"    - {row['times']}x {row['message'][:140]}")
            b = d.get("baseline")
            if b:
                outcomes = ", ".join(f"{n} {k}" for k, n in sorted(b["outcomes"].items()))
                lines.append(f"  baseline: {'BUILD SUCCESSFUL' if b['successful'] else 'FAILED'}; {b['task_count']} tasks ({outcomes})")
                for task, row in b["tests"].items():
                    counts = ", ".join(f"{n} {k}" for k, n in sorted(row["counts"].items())) or "no cases"
                    lines.append(f"    {task}: {row['outcome']}, {counts}")
                if b["stale_xml"]:
                    lines.append(f"    STALE XML (older than the run): {', '.join(b['stale_xml'])}")
                if b["test_like_tasks_without_xml"]:
                    lines.append(f"    test-like tasks without XML: {', '.join(b['test_like_tasks_without_xml'])}")
                if b["unmatched_xml"]:
                    lines.append(f"    XML dirs with no matching task: {', '.join(u['directory'] for u in b['unmatched_xml'])}")
                if b.get("failure_tail"):
                    lines.append("    --- log tail ---")
                    lines.extend("    " + line for line in b["failure_tail"].splitlines())
            pair = d.get("cc_pair")
            if pair:
                store, reuse = d["cc-store"]["configuration_cache"], d["cc-reuse"]["configuration_cache"]
                lines.append(f"  configuration cache: stored={store['stored']} reused={reuse['reused']}; pair {'OK' if pair['ok'] else 'PROBLEMS: ' + '; '.join(pair['problems'])}")
                versus = d.get("baseline_vs_cc_store", {})
                lines.append(f"  baseline vs cc-store: {'same tasks/tests' if versus.get('ok') else 'PROBLEMS: ' + '; '.join(versus.get('problems', []))}")
            elif "cc-store" in d:
                lines.append("  configuration cache: store run failed; see cc-store.log")
            prov = d.get("provenance")
            if prov:
                lines.append(f"  provenance: {'tasks --provenance' if prov['with_provenance'] else 'tasks --all (no provenance on this version)'} -> provenance.log (exit {prov['exit']})")
            deps = d.get("dependencies", {})
            captured = sum(1 for e in deps.values() for c in e["configurations"].values() if isinstance(c, dict))
            na = [f"{k}:{c}" for k, e in deps.items() for c, v in e["configurations"].items() if v == "N/A"]
            failed = [k for k, e in deps.items() if e["exit"] != 0]
            if deps:
                lines.append(f"  dependencies: {len(deps)} project(s), {captured} configuration report(s)" +
                             (f"; N/A: {', '.join(na)}" if na else "") + (f"; FAILED: {', '.join(failed)}" if failed else ""))
            if d.get("stopped_after"):
                lines.append(f"  STOPPED: `{d['stopped_after']}` failed; the subsequent phases did not run. Tell the user.")
        if f["comparison"]:
            c = f["comparison"]
            lines.append(f"Comparison with {c['before']}: " + ("no differences" if c["ok"] else "DIFFERENCES"))
            lines.extend(f"  - {p}" for p in c["problems"])
            if c["dependencies"]["new"]:
                lines.append("  new dependency reports (not a regression; explain them): " + ", ".join(c["dependencies"]["new"]))
        if f["gaps"]:
            lines.append("Gaps:")
            lines.extend(f"  - [{g['phase']}] {g['reason']}" for g in f["gaps"])
        return "\n".join(lines)

    def go(self) -> int:
        self.prepare_out()
        self.static()
        self.prerequisites()
        self.dynamic()
        if self.args.compare_with:
            self.compare_with(Path(os.path.abspath(self.args.compare_with)))
        self.facts["ok"] = not self.failed
        self.write("facts.json", self.facts)
        print(json.dumps(self.facts, indent=2, default=str) if self.args.json else self.summary_text())
        return 1 if self.failed else 0


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root")
    parser.add_argument("--tasks", nargs="+", default=DEFAULT_TASKS, help="verification tasks (default: check)")
    parser.add_argument("--out", help="output directory (default ROOT/.gradle-modernization/baseline)")
    parser.add_argument("--gradle", help="launcher (default ROOT/gradlew, else gradle on PATH)")
    parser.add_argument("--static-only", action="store_true")
    parser.add_argument("--skip-cc", action="store_true", help="skip the configuration-cache pair")
    parser.add_argument("--test-xml", action="append", default=[], metavar=":TASK=DIR", help="relocated JUnit XML directories")
    parser.add_argument("--projects", nargs="+", help="project paths for dependency reports (default: every discovered project)")
    parser.add_argument("--configurations", nargs="+", default=DEFAULT_CONFIGURATIONS)
    parser.add_argument("--compare-with", metavar="DIR", help="earlier output directory to compare against")
    parser.add_argument("--ignore-task", action="append", default=[], metavar=":TASK")
    parser.add_argument("--timeout", type=int, default=1800, help="seconds per Gradle command")
    parser.add_argument("--json", action="store_true", help="print facts.json to stdout instead of the summary")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse(argv)
    try:
        overrides = mapping(args.test_xml)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    g = Gatherer(args)
    g.test_xml = {task: (Path(os.path.abspath(args.root)) / d) if not Path(d).is_absolute() else Path(d) for task, d in overrides.items()}
    try:
        return g.go()
    except SystemExit as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
