# Verification

The commands below are templates. Replace the skill directory and the project root. Write logs and summaries to a scratch directory inside the project, for example `.gradle-modernization/`. This keeps them out of the diff.

## Isolate a change group

1. Start from a clean working tree. If that is not possible, record the dirty files with `git status --porcelain`.
2. Make only the edits of the group. `git diff --stat` must list only the files of the group.
3. Rollback:

```sh
git checkout -- <files the group edited>
rm <files the group created>
```

Use one group per verification cycle. A regression then points to one change. Do not stage or commit unless the user asks.

## Baseline

The verification workload is the build and test part: `check`, `test`, custom `Test` tasks and `assemble`. It does not include `publish`, deploy, Docker push or release tasks. `publishToMavenLocal` writes to `~/.m2`. Run it only if a publication comparison is necessary.

One command gathers everything:

```sh
python <skill>/scripts/gather_facts.py <root> --tasks <tasks> \
  [--test-xml :app:integrationTest=app/build/qa/integration-xml ...]   # only for relocated XML
```

The output goes to `<root>/.gradle-modernization/baseline/`. The parent directory gets a `.gitignore` that contains `*`.

| File | Content |
|---|---|
| `facts.json` | All items below, plus prerequisites, static findings, plugin inventory, gaps and the list of commands with exit codes and durations |
| `deprecations.log` | Output of `help --warning-mode=all`. The count and the distinct messages are in `facts.json` |
| `baseline.log`, `baseline.json` | Forced-execution run in the configuration-cache mode that the project already has. The summary lists: the outcome of each task (`EXECUTED`, `UP-TO-DATE`, `FROM-CACHE`, `NO-SOURCE`, `SKIPPED`, `FAILED`), the parsed test cases per Test task, `stale_xml` (XML older than the run), test-like tasks with no XML, and XML directories that no executed task claims |
| `cc-store.*`, `cc-reuse.*`, `cc-pair.json`, `baseline-vs-cc-store.json` | Strict configuration-cache pair (`--configuration-cache --configuration-cache-problems=fail`) and its comparison with the baseline |
| `provenance.log` | `tasks --provenance --all` on 9.5 and later, else `tasks --all` |
| `dependencies/<project>/<configuration>.txt` | One report per resolvable configuration. Header and timing are removed so that plain diffs are meaningful. `facts.json` lists N/A and `FAILED` entries |
| `buildEnvironment.log` | Buildscript classpaths |

The baseline records the Gradle version, the launcher JVM, the daemon JVM and the declared configuration-cache flag. Read the compiler toolchain, `options.release` and the test framework from the build scripts.

Lifecycle tasks such as `check` are not execution evidence. Look at the tasks with actions, for example `:app:compileJava` and `:app:test`. A Test task that is `NO-SOURCE`, that produced no test cases, or that has stale XML is a lead. Investigate its `testClassesDirs` and `classpath` wiring. Do not accept it as a green build.

The command stops at the first Gradle command that fails. It exits with code 1 and shows the log tail in the summary. The subsequent phases do not run. Tell the user which command failed. Do not run the command again with different flags.

Options:
- `--static-only` skips Gradle.
- `--skip-cc` skips the configuration-cache pair.
- `--timeout` limits each Gradle command. The default is 1800 s.

## After a change group

Run the identical command into a new directory and compare it with the baseline:

```sh
python <skill>/scripts/gather_facts.py <root> --tasks <tasks> \
  --out .gradle-modernization/group-1 --compare-with .gradle-modernization/baseline \
  --ignore-task :build-logic:compileGroovyPlugins   # for tasks that the group adds on purpose
```

`comparison.json` and the summary report:
- Changes in task membership and outcomes.
- Test cases that appeared, disappeared or changed outcome.
- An increase in deprecation warnings.
- Every dependency report that differs, with unified diffs under `dependency-diffs/`.

The configuration-cache pair of the new run is checked as in Phase 1. Exit code 0 means that nothing unexpected changed.

Compare test identities per task, not counts. A count check passes when one task loses half of its tests and another task gains some.

For ad-hoc logs, use the embedded tools directly: `compare_runs.py summarize LOG --test-xml :task=DIR` and `compare_runs.py compare BEFORE.json AFTER.json [--cache-pair]`.

## Configuration cache

`gather_facts.py` runs the workload twice with identical arguments: `--configuration-cache --configuration-cache-problems=fail --no-build-cache --rerun-tasks --console=plain --warning-mode=all`. It makes sure that:
- The first run prints `Configuration cache entry stored.`
- The second run prints `Reusing configuration cache.`
- The Test tasks execute in both runs.

It also compares the store run with the baseline that has no configuration cache. Warn mode (`--configuration-cache-problems=warn`) is useful for diagnosis. It is not verification.

This is a compatibility test, not a benchmark. Measure cold and warm builds separately, without forced reruns, with several samples, before you recommend a performance-driven restructuring.

## Dependencies, artifacts and publications

`gather_facts.py` captures `compileClasspath`, `runtimeClasspath`, `testCompileClasspath`, `testRuntimeClasspath`, annotation processors and every other resolvable `*Classpath` per project. It covers the root build and included builds through `-p`. `buildSrc` cannot be addressed standalone. `--compare-with` diffs the reports. Look at `FAILED` entries even when the task succeeded. `buildEnvironment.log` shows the buildscript classpaths.

For each difference, run `dependencyInsight --dependency <module> --configuration <name>`. Add `--all-variants` when useful. It shows requested and resolved versions, selected variants, attributes and capabilities. Classifier and classpath-order changes do not show in the tree. If they matter, print the resolved file list with a small task that prints `configurations.runtimeClasspath.files`.

For publishing changes, generate the POM and `.module` metadata locally with `generatePomFileFor…Publication` and `generateMetadataFileFor…Publication`. Diff them: coordinates, dependency scopes, variants, attached artifacts.

For reproducibility claims, rebuild in a clean checkout with `--no-build-cache --rerun-tasks` and compare the `sha256sum` of the artifacts.

## Skill regression checks

From the skill directory:

```sh
python -B scripts/test_audit.py
python -B -m unittest discover -s scripts -p 'test_*.py' -v
```

These tests do not run Gradle. `test_gather_facts.py` drives the orchestrator through a fake launcher.

`scripts/test_recipes.py` is the opt-in integration test with a real Gradle. It builds a fixture with classifier and rich-version dependencies and with unit and integration Test tasks. It migrates the fixture to a catalog and a convention plugin, enables strict locking, checks the configuration-cache store and reuse pair, and makes sure that a suppressed Test task is detected. It needs a Gradle launcher and network access to download JUnit Jupiter:

```sh
python -B <skill>/scripts/test_recipes.py --gradle gradle --results ./recipe-results
```

Run it against each Gradle version of interest: the latest 8.x, an early 9.x and the current 9.x.
