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

Record: Gradle version, daemon JVM, compiler toolchain, `options.release`, test framework, and the original configuration-cache mode (don't enable it while establishing the baseline). List every expected `Test` task and its JUnit XML directory (`reports.junitXml.outputLocation` may be relocated). Lifecycle tasks such as `check` alone are not execution evidence: name the tasks with real actions (`:app:compileJava`, `:app:test`).

Forced-execution baseline:

```sh
./gradlew <tasks> --no-build-cache --rerun-tasks --console=plain --warning-mode=all \
  2>&1 | tee .gradle-modernization/baseline.log
python <skill>/scripts/compare_runs.py summarize .gradle-modernization/baseline.log \
  --test-xml :app:test=app/build/test-results/test \
  --test-xml :app:integrationTest=app/build/test-results/integrationTest \
  > .gradle-modernization/baseline.json
```

The summary lists each task's outcome (`EXECUTED`, `UP-TO-DATE`, `FROM-CACHE`, `NO-SOURCE`, `SKIPPED`, `FAILED`), the parsed test cases per Test task, configuration-cache store/reuse markers and the deprecation-warning count. A Test task that is `NO-SOURCE` or produced no cases is flagged; investigate `testClassesDirs`/`classpath` wiring rather than accepting the green build.

## After a change group

Re-run the identical command, summarize to `after.json`, then:

```sh
python <skill>/scripts/compare_runs.py compare \
  .gradle-modernization/baseline.json .gradle-modernization/after.json \
  --ignore-task :build-logic:compileGroovyPlugins   # etc., for intentionally added tasks
```

It reports task membership/outcome changes, test cases that appeared, disappeared or changed outcome, and a rise in deprecation warnings. Exit code 0 means nothing unexpected changed. Comparing test *identities* per task matters more than counts: a task that silently dropped half its tests while another gained some would pass a count check.

## Configuration cache

Run the same workload twice with identical arguments:

```sh
ARGS="<tasks> --configuration-cache --configuration-cache-problems=fail --no-build-cache --rerun-tasks --console=plain"
./gradlew $ARGS 2>&1 | tee .gradle-modernization/cc-store.log
./gradlew $ARGS 2>&1 | tee .gradle-modernization/cc-reuse.log
python <skill>/scripts/compare_runs.py summarize .gradle-modernization/cc-store.log --test-xml ... > cc-store.json
python <skill>/scripts/compare_runs.py summarize .gradle-modernization/cc-reuse.log --test-xml ... > cc-reuse.json
python <skill>/scripts/compare_runs.py compare cc-store.json cc-reuse.json --cache-pair
```

`--cache-pair` additionally checks that the first run printed `Configuration cache entry stored.` and the second `Reusing configuration cache.`, with the Test tasks executing both times. Warn mode (`--configuration-cache-problems=warn`) is useful for diagnosis but isn't verification. Compare the store run against the non-cache baseline too.

This is a compatibility test, not a benchmark. Benchmark cold/warm builds separately, without forced reruns, with several samples, before recommending performance-driven restructuring.

## Dependencies, artifacts and publications

`compare_runs.py` covers tasks and tests only. For each affected project, save `:<project>:dependencies --configuration <name>` before/after for `compileClasspath`, `runtimeClasspath`, `testCompileClasspath`, `testRuntimeClasspath`, annotation processors, custom source sets and build-logic classpaths as applicable, and diff them. Look at `FAILED` entries even when the task succeeded. `buildEnvironment` shows buildscript classpaths.

For any difference, `dependencyInsight --dependency <module> --configuration <name>` (add `--all-variants` where useful) shows requested/resolved versions, selected variants, attributes and capabilities. Classifier and classpath-order changes don't show in the tree; check the actual resolved file list if those matter (a tiny task printing `configurations.runtimeClasspath.files` is enough).

For publishing changes, generate POMs / `.module` metadata locally (`generatePomFileFor…Publication`, `generateMetadataFileFor…Publication`) and diff them: coordinates, dependency scopes, variants, attached artifacts. Reproducibility claims need a rebuild in a clean checkout with `--no-build-cache --rerun-tasks` and a `sha256sum` comparison of the artifacts.

## Skill regression checks

From the skill directory:

```sh
python -B scripts/test_audit.py
python -B -m unittest discover -s scripts -p 'test_*.py' -v
```

These don't run Gradle. `scripts/test_recipes.py` is the opt-in real-Gradle integration test: it builds a fixture with classifier/rich-version dependencies and unit + integration Test tasks, migrates it to a catalog + convention plugin, enables strict locking, checks the configuration-cache store/reuse pair, and checks that a suppressed Test task is caught. It needs a Gradle launcher and network access to fetch JUnit Jupiter:

```sh
python -B <skill>/scripts/test_recipes.py --gradle gradle --results ./recipe-results
```

Run it against each Gradle version you care about (latest 8.x, an early 9.x, the current 9.x).
