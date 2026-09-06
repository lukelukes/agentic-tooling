#!/usr/bin/env python3
"""Summarize a Gradle console log (+ JUnit XML) and diff two such summaries.

Usage: compare_runs.py summarize LOG [--test-xml :task=DIR ...] > run.json
       compare_runs.py compare BEFORE.json AFTER.json [--cache-pair] [--ignore-task :task ...]

summarize records every "> Task" line's outcome, the configuration-cache
store/reuse markers, and (per Test task) the set of test cases with outcomes.
compare reports task outcomes that changed, test cases that appeared,
disappeared or changed outcome, and (with --cache-pair) checks that the first
run stored a configuration-cache entry and the second reused it.

Run Gradle with --console=plain so the log is line-oriented; add
--no-build-cache --rerun-tasks when you want every task to actually execute.
Exit code 0 when nothing unexpected changed, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

TASK_LINE = re.compile(r"(?m)^> Task (:[^\s]+)(?: (UP-TO-DATE|FROM-CACHE|NO-SOURCE|SKIPPED|FAILED))?[^\S\n]*$")
CACHE_FLAGS = ("--configuration-cache", "--no-build-cache", "--rerun-tasks")


def parse_cases(content: str) -> list[dict]:
    root = ET.fromstring(content)
    cases = []
    for suite in root.iter("testsuite"):
        for case in suite.findall("testcase"):
            outcome = "passed"
            for tag, status in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
                if case.find(tag) is not None:
                    outcome = status
                    break
            cases.append({"suite": suite.get("name", ""), "class": case.get("classname", ""),
                          "name": case.get("name", ""), "status": outcome})
    return cases


def summarize(log: Path, test_xml: dict[str, Path]) -> dict:
    text = log.read_text(errors="replace")
    tasks = {name: outcome or "EXECUTED" for name, outcome in TASK_LINE.findall(text)}
    tests = {}
    for task, directory in test_xml.items():
        cases = []
        for path in sorted(Path(directory).rglob("TEST-*.xml")):
            cases.extend(parse_cases(path.read_text(errors="replace")))
        counts = Counter(case["status"] for case in cases)
        tests[task] = {"directory": str(directory), "outcome": tasks.get(task, "MISSING"),
                       "counts": dict(counts), "cases": cases}
    return {
        "log": str(log),
        "successful": bool(re.search(r"(?m)^BUILD SUCCESSFUL\b", text)),
        "tasks": dict(sorted(tasks.items())),
        "tests": tests,
        "configuration_cache": {
            "stored": bool(re.search(r"(?m)^Configuration cache entry stored\.", text)),
            "reused": bool(re.search(r"(?m)^Reusing configuration cache\.", text)),
        },
        "deprecations": len(re.findall(r"has been deprecated", text)),
    }


def identities(summary: dict) -> dict[str, Counter]:
    return {task: Counter((c["suite"], c["class"], c["name"], c["status"]) for c in row["cases"])
            for task, row in summary["tests"].items()}


def compare(before: dict, after: dict, cache_pair: bool = False, ignore_tasks: set[str] = frozenset()) -> dict:
    problems = []
    for label, run in (("before", before), ("after", after)):
        if not run["successful"]:
            problems.append(f"{label}: build was not successful")
        for task, row in run["tests"].items():
            if row["outcome"] != "EXECUTED":
                problems.append(f"{label}: test task {task} was {row['outcome']}, not executed")
            if not row["cases"]:
                problems.append(f"{label}: test task {task} produced no test cases")
    changed = sorted(name for name in set(before["tasks"]) | set(after["tasks"])
                     if before["tasks"].get(name) != after["tasks"].get(name) and name not in ignore_tasks)
    if changed:
        problems.append("task membership/outcomes changed: " + ", ".join(
            f"{n} {before['tasks'].get(n, 'MISSING')}->{after['tasks'].get(n, 'MISSING')}" for n in changed))
    left, right = identities(before), identities(after)
    for task in sorted(set(left) | set(right)):
        gone, new = left.get(task, Counter()) - right.get(task, Counter()), right.get(task, Counter()) - left.get(task, Counter())
        if gone or new:
            problems.append(f"{task}: test identities/outcomes changed ({sum(gone.values())} gone, {sum(new.values())} new)")
    if after["deprecations"] > before["deprecations"]:
        problems.append(f"deprecation warnings rose from {before['deprecations']} to {after['deprecations']}")
    if cache_pair:
        if not before["configuration_cache"]["stored"]:
            problems.append("first run did not store a configuration-cache entry")
        if not after["configuration_cache"]["reused"]:
            problems.append("second run did not reuse the configuration cache")
    return {"ok": not problems, "problems": problems, "changed_tasks": changed}


def mapping(values):
    result = {}
    for value in values:
        task, sep, directory = value.partition("=")
        if not sep or not task.startswith(":"):
            raise ValueError(f"expected :task=DIR, got {value!r}")
        result[task] = Path(directory)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("summarize")
    s.add_argument("log", type=Path)
    s.add_argument("--test-xml", action="append", default=[], metavar=":TASK=DIR")
    c = sub.add_parser("compare")
    c.add_argument("before", type=Path)
    c.add_argument("after", type=Path)
    c.add_argument("--cache-pair", action="store_true")
    c.add_argument("--ignore-task", action="append", default=[], metavar=":TASK")
    args = parser.parse_args(argv)
    if args.command == "summarize":
        result = summarize(args.log, mapping(args.test_xml))
        print(json.dumps(result, indent=2))
        return 0 if result["successful"] else 1
    result = compare(json.loads(args.before.read_text()), json.loads(args.after.read_text()),
                     args.cache_pair, set(args.ignore_task))
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
