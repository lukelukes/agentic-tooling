---
name: gradle-modernization
description: Audit a Java project's Gradle build (Groovy DSL) against Gradle 9.x features and the official best practices.
disable-model-invocation: true
---

# Gradle Modernization (Groovy DSL, Gradle 9.x)

The work has two phases:

1. **Audit and report.**
2. **Apply changes, one approved group at a time.** After each group, make sure that build behavior did not change.

Do not change build files before the user has seen the audit. A green build is not proof on its own. Make sure that the tests ran.

## Scope

- DSL: Groovy (`.gradle` files).
- Start version: usually 9.x, sometimes 8.x.
- Target version: the latest 9.x release that all plugins support. This is not always the newest release.
- Gradle below 8.x: write a staged migration plan from the official upgrade guides. Do not apply the 8.x/9.x recipes directly.
- Kotlin DSL and Android/AGP are out of scope. In mixed builds, report them as coverage gaps.

## Requirements

- Python 3.10 or later for the helper scripts. Python 3.11 or later resolves catalog plugin aliases in the plugin inventory.
- Resolve `scripts/` and `references/` relative to this skill directory, not to the audited project.
- Write audit outputs and logs to a scratch directory in the project, for example `.gradle-modernization/`. Add it to `.gitignore` so that it stays out of the diff.

## Reference files

| File | Use |
|---|---|
| `references/gradle-9x-features.md` | Full audit, or a question about one 9.x version or feature. One section per version 9.0 to 9.7. Items tagged ACT, AUTO or INFO. |
| `references/best-practices.md` | Full audit, or a question about one practice. 44 official practices plus companions C1 (dependency locking) and C2 (consistent resolution). Each has Detect, Fix and Risk. |
| `references/gradle-10-deprecations.md` | Every version transition and Gradle 10 readiness. Triage index with source links. |
| `references/report-template.md` | Structure of the audit report. |
| `references/verification.md` | Baseline capture, before/after comparison, configuration-cache check, dependency diff. |
| `scripts/gather_facts.py` | **The single fact-gathering command.** Runs the static scan, the plugin inventory and every Gradle command. Run it in Phase 1. Run it again with `--compare-with` after each Phase 2 group. |
| `scripts/audit_gradle_project.py` | The static scanner that `gather_facts.py` embeds. Run it alone only for a static-only look. |
| `scripts/compare_runs.py` | Log and JUnit XML summarizer and differ that `gather_facts.py` embeds. Use it directly for ad-hoc logs. |
| `evals/README.md` | Maintenance and tests for this skill. |

For a targeted question, read only the related reference section and answer. Examples: "Why does 9.6 warn about `ext`?" or "Should I use `--console=colored`?". Do the full checklist only for an audit request.

## Phase 1: Audit

### Step 1. Gather facts

Identify the CI verification tasks first. These are `check`, `test` and custom `Test` tasks. Do not include `publish`, deploy or docker tasks. Then run:

```sh
python <skill>/scripts/gather_facts.py <root> --tasks <ci tasks> [--test-xml :task=DIR ...]
```

The command writes `<root>/.gradle-modernization/baseline/` and prints a summary. The output directory has its own `.gitignore`. Read the sections of `facts.json` that you need. Do not read the raw logs unless necessary.

The command does these steps in this order:

- **Static.** The read-only scanner and a plugin inventory. `static.plugins` lists id, version, catalog alias, `apply plugin:` usage and buildscript classpath.
- **Prerequisites.** `git status`, `java -version` and launcher resolution. The launcher is `gradlew`, or else `gradle` on PATH. A PATH launcher is recorded as a gap because the versions can differ.
- **Dynamic.** Skipped with a recorded reason if Gradle cannot run. In that case, every "build-reported" line in the report is *not checked*. The dynamic steps are:
  - `--version`.
  - `help --warning-mode=all`. Deprecations are deduplicated.
  - The **baseline**: the CI tasks with `--no-build-cache --rerun-tasks --console=plain --warning-mode=all`, in the configuration-cache mode that the project already has.
  - The **configuration-cache pair**: the same tasks twice with `--configuration-cache --configuration-cache-problems=fail`. The first run must store. The second run must reuse. The tests must execute in both runs. The store run is compared with the baseline.
  - `tasks --provenance` on 9.5 and later, else `tasks --all`.
  - `dependencies` for each project, split into one report per configuration. Configurations: compile, runtime, test, annotation processor and every other `*Classpath`. Missing configurations are recorded as N/A.
  - `buildEnvironment`.
- **JUnit XML.** Mapped automatically from `build/test-results/<task>`. Use `--test-xml :task=DIR` for relocated reports.

A test-like task is a blocker lead in each of these cases, even if the counts look correct:
- The task has no XML.
- The XML is older than the run (`stale_xml`).
- The task outcome is `NO-SOURCE`.
- The XML directory is missing.

**Caution:** Gradle 9.0 can stop the execution of custom `Test` tasks without an error. This happens when the task inherited `testClassesDirs` or `classpath` from the `test` source set.

A failed baseline is reported with the log tail in the summary and exit code 1. The configuration-cache pair is then skipped. Report the blocker. Do not make a green baseline by other means.

Options: `--static-only`, `--skip-cc`, `--projects`, `--configurations`, `--timeout`. The timeout applies to each Gradle command. The default is 1800 s.

### Step 2. Interpret the facts

- `facts.gaps` and `static.facts.coverage` list skipped paths, unreadable paths, Kotlin DSL, dynamic includes and unsupported syntax. These are gaps, not passes.
- The scanner is lexical. It masks strings and comments but does not evaluate Groovy. Use these confidence levels:
  - **confirmed**: a directly observed fact.
  - **likely**: an executable pattern.
  - **suspected**: a heuristic.
- Check the applicability of each finding against the actual receiver. Dependency, plugin, buildscript and publishing repositories are different things.
- Use `static.facts.build_facts` and the `build` identity of each finding for the settings, catalog and locking checks of included builds.
- `build_facts.<build>.locking` lists, for each project: the script that declares locking, whether it activates locking with `lockAllConfigurations()` or `activateDependencyLocking()`, and whether `gradle.lockfile` exists and has entries. A `dependencyLocking {}` block that only sets `lockMode` locks nothing. Locking in `allprojects {}` with lock files in only some projects is a C1 finding, not a pass.
- The scanner does not follow symlinks and does not read outside `<root>`. If `settings.gradle` includes an external build, gather facts for that build separately.
- A platform or aggregation project has no `runtimeClasspath`. Record it as N/A.

### Step 3. Walk the references

1. Read `best-practices.md` from top to bottom. Mark each practice: ✅ followed, ❌ violated, ➖ N/A, ❓ not checked, ⚠ suspected (scanner lead, not verified).
2. Read `gradle-9x-features.md` for every version between the current version and the target version.
3. For **every version transition**, also read `gradle-10-deprecations.md` and the official upgrade guide pinned to the target version. For 8.x to 9.x, also read the major upgrade guide and the latest 8.x guide.
4. Review breaking changes and changed bundled-tool defaults, even if the build shows no warnings.
5. Do not infer a removal deadline from a chapter title.

### Step 4. Plugin compatibility inventory

This step is mandatory when the target version differs from the current version.

- List every plugin with its version and the Gradle and JDK ranges it supports. Sources: the plugin portal page and the plugin release notes.
- Keep four JDK concerns separate: daemon JVM, compilation toolchain, bytecode target (`options.release`) and test runtime.
- A plugin that does not support the target Gradle blocks the wrapper upgrade. Update or replace the plugin first.

### Step 5. Write the report

Use `report-template.md`. For each finding, give: rule ID, location, evidence, confidence, consequence, verification method and risk.

- Put build blockers and measurable benefits before naming preferences.
- Measure representative timings before you propose a performance-driven restructuring.
- Order the candidate groups by prerequisites first, then by risk.
- "No changes recommended" is a valid result. Do not add speculative violations to raise a best-practice score.

### Step 6. Stop

Ask the user which groups to apply.

## Phase 2: Apply approved groups

Apply one group at a time. For each group:

### Isolate the change

- Start from a clean tree. Commit or stash pending work first, or record which files were already dirty.
- Make only the edits of this group. `git diff` must show only this group.
- Rollback: `git checkout -- <files>` and remove the new files that the group created.
- Do not stage or commit unless the user asks.

### Compare with the Phase 1 baseline

Run the same command into a new directory and compare:

```sh
python <skill>/scripts/gather_facts.py <root> --tasks <same tasks> --out .gradle-modernization/group-<n> --compare-with .gradle-modernization/baseline [--ignore-task :build-logic:compileGroovyPlugins ...]
```

Exit code 0 means that nothing unexpected changed. The comparison covers:

- Task membership and outcomes. Use `--ignore-task` for build-logic compilation tasks that the group adds on purpose. Test identities and outcomes per task, not only counts. No new deprecations.
- Dependency reports per configuration, with unified diffs in `dependency-diffs/`. Resolved versions, selected variants, classifiers and classpath order must be equal, unless the stated purpose of the group changes them. Use `dependencyInsight --dependency <module> --configuration <name>` for each difference. If the group changes publishing configuration, compare the generated POM and `.module` metadata. Generate them locally. Do not publish.
- Configuration cache. The strict store-then-reuse pair of the new run must pass, as in Phase 1.
- Reproducibility claims (Sec4). Rebuild with `--no-build-cache --rerun-tasks` in a clean checkout and compare the `sha256sum` of the artifacts. A comparison of a cached output with itself proves nothing.

If Gradle cannot run, say so. Give the user the exact commands and the expected outputs. Do not mark the group as verified.

### Report the result

Show a diff summary and the comparison result. If anything regressed, roll the group back and report it.

## Group-specific rules

### Wrapper upgrades

Do the steps in this order:

1. Clear the deprecation warnings on the current version.
2. Update or replace the plugins that do not support the target version.
3. For 8.x to 9.x: move to the latest 8.x first and clear its warnings. The upgrade guide recommends this.
4. Run `./gradlew wrapper --gradle-version=<target> --gradle-distribution-sha256-sum=<sha>`. Get the checksum from https://gradle.org/release-checksums/. Run the command a second time so that the new Gradle regenerates the wrapper jar and scripts.
5. Run `help --warning-mode=all` on the new version.

Select the latest version that every plugin supports. Report the gap to the newest release.

### Version catalog migration

- Keep the existing catalog architecture: imported, published, programmatic and multiple catalogs.
- Move external library and plugin versions as defined in D3. Do not move unrelated strings.
- The `plugins {}` blocks of settings plugins and precompiled plugins cannot use project catalog `alias()`.
- Catalog TOML supports rich versions such as `strictly` and `prefer`. It does **not** support classifiers, artifact types, excludes, attributes or capability requirements. Keep those at the dependency declaration site. Example: `implementation(variantOf(libs.foo) { classifier('test-fixtures') })`. Keep existing closures and constraints.
- Defer everything that the catalog cannot express identically.
- Success means equal dependency and artifact evidence, not zero GAV strings. An incremental migration is valid.

### Dependency locking

- Locking does not require a catalog or convention-plugin migration.
- Before you propose anything, read the current state per project from `facts.build_facts.<build>.locking`. A declaration that does not activate locking, or an activated project without a lock file, is a defect to fix. It is not existing coverage to keep.
- Keep existing per-configuration locking and custom lock locations.
- Enable locking and generate the lock state in the same group, per project (C1). Use `DEFAULT` mode while bootstrapping. Switch to `STRICT` when each locked configuration has state.
- Include the generated lock files in the diff.
- Resolved versions must not change when you only enable locking.
- A selective update can change other modules through resolution rules. Review the whole lock diff.
- Settings plugin versions and dependency verification are separate concerns.

### Convention plugins

Convention plugin extraction preserves behavior. It is not a policy change.

- Logic moved from `subprojects {}` into `build-logic/src/main/groovy/*-conventions.gradle` must reproduce the existing configuration exactly: same Java target, same compiler arguments, same test framework, same parallelism.
- `best-practices.md` § "Convention plugin skeleton" separates the behavior-preserving base from optional policy upgrades. Each policy upgrade is its own approval item with its own verification. Examples: toolchain bump, `-Werror`, JUnit Platform, `maxParallelForks`, sources jar.
- Use `groovy-gradle-plugin` in `build-logic/build.gradle`.
- Migrate one subproject at a time.
- `tasks --provenance` before and after must show the same task set.

### Configuration cache

- Enable the configuration cache only after store-then-reuse succeeds on the CI task set.
- Mark incompatible tasks with `notCompatibleWithConfigurationCache('reason')`.
- List the blocking plugins in the report. Do not keep the cache off without a statement.

### Product source and test files

Do not edit application source files or test files. Source moves (S1, S2), removal of Cucumber runners and test migrations are proposals, not executions. Build-logic extraction can create or edit `build-logic/src/**` and `buildSrc/src/**`. These are build tooling, not product sources.

### Behavior-affecting groups

These groups are medium or high risk: exclusion narrowing (D8), redundant dependencies (D6), `consistentResolution` (C2), `sourceCompatibility` to toolchain, and test framework changes. Explain the observable effect. Run the full test and dependency comparison above.

## Groovy DSL idioms for rewrites

```groovy
plugins { id 'java-library' }                        // declarative plugin application where valid
dependencies { implementation libs.jackson.databind } // catalog alias
tasks.register('myTask', Copy) { ... }               // register, not create or task x {}
tasks.named('test', Test) { ... }                    // named, not eager test { }
tasks.withType(JavaCompile).configureEach { ... }    // configureEach
layout.buildDirectory.dir('reports')                 // not buildDir
java { toolchain { languageVersion = JavaLanguageVersion.of(17) } }  // keep the existing target; a bump is a policy change
```

Since 9.6.0, the Groovy DSL converts `String` to `File` and a single value to `ListProperty` on lazy properties. `task.workingDir = '../x'` is valid.

## Do not recommend

- Kotlin DSL. This is official practice G1, but it is out of scope by user decision. Mention it once as "not applied".
- Isolated Projects for production. It is incubating in 9.7 and "not yet recommended". A diagnostic run needs both `--isolated-projects` and `-Dorg.gradle.isolated-projects.diagnostics=true`. The diagnostics property alone has no effect.
- `@Incubating` APIs in shared build logic without a statement in the report (practice G9).
- The `ENHANCED_GRAPH_ORDERING` and `NO_IMPLICIT_LOOKUP_IN_PARENT_PROJECTS` feature previews, unless the user wants to test Gradle 10 behavior early. They change classpath order and property resolution.
- Java target bumps, `-Werror`, test framework changes or higher parallelism as part of "modernization". These are policy changes. Offer them separately.
