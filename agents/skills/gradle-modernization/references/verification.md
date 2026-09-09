# Verification

Commands below are templates: substitute the skill directory and the project root. Put logs and summaries in a scratch directory such as `.gradle-modernization/` inside the project so they stay out of the diff.

## Isolating a change group

Start from a clean working tree, or at least note which files are already dirty (`git status --porcelain`). Make only the group's edits, then `git diff --stat` should list exactly the group's files. Rollback:

```sh
git checkout -- <files the group edited>
rm <files the group created>
```

Use one group per verification cycle so a regression points at one change. Don't stage or commit unless asked.

## Baseline

Inventory the CI commands. The verification workload is the build/test part (`check`, `test`, custom `Test` tasks, `assemble`), not `publish`, deploy, Docker push or release tasks. If `publishToMavenLocal` is part of CI, it writes to `~/.m2`; run it only if a publication comparison is needed.

One command gathers everything:

```sh
python <skill>/scripts/gather_facts.py <root> --tasks <tasks> \
  [--test-xml :app:integrationTest=app/build/qa/integration-xml ...]   # only for relocated XML
```

Output under `<root>/.gradle-modernization/baseline/` (the parent directory gets a `.gitignore` containing `*`):

| File | Content |
|---|---|
| `facts.json` | Everything below plus prerequisites, static findings, plugin inventory, gaps and the list of commands run with exit codes and durations |
| `deprecations.log` | `help --warning-mode=all`; the count and distinct messages are in `facts.json` |
| `baseline.log` / `baseline.json` | Forced-execution run in the project's existing configuration-cache mode; the summary lists each task's outcome (`EXECUTED`, `UP-TO-DATE`, `FROM-CACHE`, `NO-SOURCE`, `SKIPPED`, `FAILED`), the parsed test cases per Test task, `stale_xml` (XML older than the run), test-like tasks with no XML, and XML directories no executed task claims |
| `cc-store.*`, `cc-reuse.*`, `cc-pair.json`, `baseline-vs-cc-store.json` | Strict configuration-cache pair (`--configuration-cache --configuration-cache-problems=fail`) and its comparison with the baseline |
| `provenance.log` | `tasks --provenance --all` (9.5+) or `tasks --all` |
| `dependencies/<project>/<configuration>.txt` | One report per resolvable configuration, header and timing stripped so plain diffs are meaningful; `facts.json` lists N/A and `FAILED` entries |
| `buildEnvironment.log` | Buildscript classpaths |

The baseline records: Gradle version, launcher and daemon JVM, declared configuration-cache flag. Compiler toolchain, `options.release` and test framework still come from reading the build scripts. Lifecycle tasks such as `check` alone are not execution evidence: look at the tasks with real actions (`:app:compileJava`, `:app:test`). A Test task that is `NO-SOURCE`, produced no cases, or whose XML is stale is a lead to investigate `testClassesDirs`/`classpath` wiring rather than a green build to accept.

A failed baseline exits 1 with the log tail in the summary and skips the cache pair; the other phases still run. `--static-only` skips Gradle entirely, `--skip-cc` skips the pair, `--timeout` caps each Gradle command (default 1800 s).

## After a change group

Run the identical command into a new directory and compare it with the baseline:

```sh
python <skill>/scripts/gather_facts.py <root> --tasks <tasks> \
  --out .gradle-modernization/group-1 --compare-with .gradle-modernization/baseline \
  --ignore-task :build-logic:compileGroovyPlugins   # etc., for intentionally added tasks
```

`comparison.json` (and the summary) reports task membership/outcome changes, test cases that appeared, disappeared or changed outcome, a rise in deprecation warnings, and every dependency report that differs, with unified diffs under `dependency-diffs/`. The new run's own configuration-cache pair is checked as in Phase 1. Exit code 0 means nothing unexpected changed. Comparing test *identities* per task matters more than counts: a task that silently dropped half its tests while another gained some would pass a count check.

For ad-hoc logs, the embedded tools are still available directly: `compare_runs.py summarize LOG --test-xml :task=DIR` and `compare_runs.py compare BEFORE.json AFTER.json [--cache-pair]`.

## Configuration cache

`gather_facts.py` runs the workload twice with identical arguments (`--configuration-cache --configuration-cache-problems=fail --no-build-cache --rerun-tasks --console=plain --warning-mode=all`) and checks that the first run printed `Configuration cache entry stored.` and the second `Reusing configuration cache.`, with the Test tasks executing both times; it also compares the store run against the non-cache baseline. Warn mode (`--configuration-cache-problems=warn`) is useful for diagnosis but isn't verification.

This is a compatibility test, not a benchmark. Benchmark cold/warm builds separately, without forced reruns, with several samples, before recommending performance-driven restructuring.

## Dependencies, artifacts and publications

`gather_facts.py` captures `compileClasspath`, `runtimeClasspath`, `testCompileClasspath`, `testRuntimeClasspath`, annotation processors and any other resolvable `*Classpath` per project (root build and included builds via `-p`; buildSrc is not addressable standalone), and `--compare-with` diffs them. Look at `FAILED` entries even when the task succeeded. `buildEnvironment.log` shows buildscript classpaths.

For any difference, `dependencyInsight --dependency <module> --configuration <name>` (add `--all-variants` where useful) shows requested/resolved versions, selected variants, attributes and capabilities. Classifier and classpath-order changes don't show in the tree; check the actual resolved file list if those matter (a tiny task printing `configurations.runtimeClasspath.files` is enough).

For publishing changes, generate POMs / `.module` metadata locally (`generatePomFileFor…Publication`, `generateMetadataFileFor…Publication`) and diff them: coordinates, dependency scopes, variants, attached artifacts. Reproducibility claims need a rebuild in a clean checkout with `--no-build-cache --rerun-tasks` and a `sha256sum` comparison of the artifacts.

## Skill regression checks

From the skill directory:

```sh
python -B scripts/test_audit.py
python -B -m unittest discover -s scripts -p 'test_*.py' -v
```

These don't run Gradle (`test_gather_facts.py` drives the orchestrator through a fake launcher). `scripts/test_recipes.py` is the opt-in real-Gradle integration test: it builds a fixture with classifier/rich-version dependencies and unit + integration Test tasks, migrates it to a catalog + convention plugin, enables strict locking, checks the configuration-cache store/reuse pair, and checks that a suppressed Test task is caught. It needs a Gradle launcher and network access to fetch JUnit Jupiter:

```sh
python -B <skill>/scripts/test_recipes.py --gradle gradle --results ./recipe-results
```

Run it against each Gradle version you care about (latest 8.x, an early 9.x, the current 9.x).
