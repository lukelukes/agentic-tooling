---
name: gradle-modernization
description: Audit a Java project's Gradle build (Groovy DSL) against Gradle 9.x features and official best practices, then apply approved fixes with behavior-preserving verification. Use for modernizing, upgrading, cleaning up or reviewing Java build.gradle / settings.gradle / gradle.properties; version catalogs, convention plugins, locking, configuration cache, Gradle-10 readiness or deprecation warnings. Also use for targeted questions about what newer Gradle versions offer. Not a Kotlin DSL migration, Android/AGP upgrade or product-test migration workflow; route those to domain-specific guidance.
---

# Gradle Modernization (Groovy DSL, Gradle 9.x)

Two phases: **audit and report**, then **apply changes one approved group at a time, checking that behaviour is preserved**. Don't rewrite build files before the user has seen the audit. A green build is not proof on its own: check that the tests actually ran.

Scope: Groovy DSL (`.gradle`). Starting point usually 9.x, sometimes 8.x. Target: the latest *compatible* 9.x release — not automatically the newest.

For Gradle <8.x, provide a staged migration plan using the relevant official guides; do not apply the 8/9.x recipes directly. Kotlin DSL and Android/AGP are out of scope; note them as coverage gaps in mixed builds.

Helpers require Python 3.10+ (3.11+ to resolve catalog plugin aliases in the inventory). Resolve `scripts/` and `references/` relative to this skill's directory, not the audited project's working directory. Keep audit outputs and logs in a scratch directory (e.g. `.gradle-modernization/` in the project, gitignored) so they don't pollute the diff.

## Reference files

| File | When |
|---|---|
| `references/gradle-9x-features.md` | Full audit, or any question about a specific 9.x version/feature. Per-version 9.0 → 9.7, tagged ACT/AUTO/INFO. |
| `references/best-practices.md` | Full audit, or a question about a specific practice. 44 official practices + companions (dependency locking C1, consistent resolution C2), each with Detect / Fix / Risk. |
| `references/gradle-10-deprecations.md` | Every version transition and Gradle-10 readiness; source-pinned triage index. |
| `references/report-template.md` | Writing the audit report. |
| `references/verification.md` | Baseline capture, before/after comparison, configuration-cache check, dependency diffing. |
| `scripts/gather_facts.py` | **The one fact-gathering command** (static scan + plugin inventory + every Gradle run). Run it in Phase 1, and again with `--compare-with` after each Phase 2 group. |
| `scripts/audit_gradle_project.py` | The static scanner `gather_facts.py` embeds; run alone only for a quick static-only look. |
| `scripts/compare_runs.py` | Log/JUnit-XML summarizer and differ that `gather_facts.py` embeds; use directly for ad-hoc logs. |
| `evals/README.md` | Maintaining/testing this skill. |

**Targeted questions** ("why does 9.6 warn about `ext`?", "should I use `--console=colored`?"): read only the relevant reference section and answer. Reserve the full checklist walk for an actual audit request.

## Phase 1 — Audit

1. **Gather facts — one command.** Identify the CI verification tasks first (`check`, `test`, custom `Test` tasks; not `publish`/deploy/docker), then:
   ```sh
   python <skill>/scripts/gather_facts.py <root> --tasks <ci tasks> [--test-xml :task=DIR ...]
   ```
   It writes `<root>/.gradle-modernization/baseline/` (self-gitignored) and prints a short summary. Read `facts.json` sections as needed rather than the raw logs. What it does, in order:
   - **Static**: the read-only scanner plus a plugin inventory (`static.plugins`: id, version, catalog alias, `apply plugin:`, buildscript classpath).
   - **Prerequisites**: `git status`, `java -version`, launcher resolution (`gradlew`, else `gradle` on PATH — noted as a gap since versions may differ).
   - **Dynamic** (skipped with a recorded reason when Gradle can't run; then every "build-reported" line in the report is *not checked*): `--version`; `help --warning-mode=all` (deprecations, deduplicated); the **baseline** of the CI tasks with `--no-build-cache --rerun-tasks --console=plain --warning-mode=all` in the project's existing configuration-cache mode; the **configuration-cache pair** (same tasks twice with `--configuration-cache --configuration-cache-problems=fail`, first must store, second must reuse, tests must execute both times, and the store run is compared with the baseline); `tasks --provenance` (9.5+, else `tasks --all`); `dependencies` per project split into one report per configuration (compile/runtime/test/annotation-processor plus any extra `*Classpath`; missing ones recorded as N/A); `buildEnvironment`.
   - JUnit XML is auto-mapped from `build/test-results/<task>`; pass `--test-xml :task=DIR` for relocated reports. A test-like task with no XML, XML older than the run (`stale_xml`), `NO-SOURCE`, or a missing XML directory is a blocker lead even when counts look fine: **Gradle 9.0 can silently stop running custom `Test` tasks** that relied on inheriting `testClassesDirs`/`classpath`.
   - A failed baseline is reported (log tail in the summary, exit 1) and the cache pair is skipped; report the blocker rather than manufacturing a green baseline. Options: `--static-only`, `--skip-cc`, `--projects`, `--configurations`, `--timeout` (per Gradle command, default 1800 s).
2. **Interpret the facts.** `facts.gaps` and `static.facts.coverage` (skipped/unreadable paths, Kotlin DSL, dynamic includes, unsupported syntax) are gaps, not passes. The lexical scanner masks strings/comments but does not evaluate Groovy, so **confirmed** means a directly observed fact, **likely** an executable pattern, **suspected** a heuristic. Check applicability of each finding against the actual receivers (dependency/plugin/buildscript/publishing repositories are different things). Use `static.facts.build_facts` and each finding's `build` identity for included-build settings/catalog/locking checks. `build_facts.<build>.locking` lists, per project, which script declares locking, whether it actually activates anything (`lockAllConfigurations()` / `activateDependencyLocking()`), and whether that project's `gradle.lockfile` exists and has entries. A `dependencyLocking {}` block that only sets `lockMode` locks nothing, and `allprojects {}` locking with lockfiles in only some projects is a C1 finding, not a pass. The scanner does not follow symlinks or read outside `<root>`; if `settings.gradle` includes an external build, gather facts for it separately. A platform/aggregation project legitimately has no `runtimeClasspath` (N/A).
3. **Walk the references.** `best-practices.md` top to bottom, mark each: ✅ followed · ❌ violated · ➖ N/A · ❓ not checked · ⚠ suspected (scanner lead, unverified). Then `gradle-9x-features.md` for every version between current and target. For **every version transition**, also read `gradle-10-deprecations.md` and the target-pinned official upgrade guide (plus the major/latest-8.x guides when crossing 8 → 9). Review breaking changes and bundled-tool defaults even without warnings. Don't infer a removal deadline from a chapter title.
4. **Plugin compatibility inventory** — mandatory when the target version differs from current. List every plugin with its version and the Gradle/JDK range it supports (plugin portal page, release notes). Distinguish four JDK concerns: daemon JVM, compilation toolchain, bytecode target (`options.release`), test runtime. A plugin that doesn't support the target Gradle blocks the wrapper upgrade until it's updated or replaced.
5. **Write the report** from `report-template.md`. Each finding: rule ID, location, evidence, confidence, consequence, verification method, risk. Prioritize build blockers and measurable benefits over naming preferences. Measure representative timings before proposing performance-driven restructuring. Order candidates by *prerequisites*, then risk. "No changes recommended" is a valid result; don't inflate a best-practice score with speculative violations.
6. **Stop and ask** which groups to apply.

## Phase 2 — Apply (approved groups only)

One group at a time. For each:

- **Isolate the change.** Start from a clean tree (commit or stash pending work first, or note which files were already dirty). Make only the group's edits, so `git diff` shows exactly this group. Rollback is `git checkout -- <files>` plus removing any new files the group created. Don't stage or commit unless asked.
- **Verify by comparing with the Phase 1 baseline.** Re-run the same command into a new directory and compare:
   ```sh
   python <skill>/scripts/gather_facts.py <root> --tasks <same tasks> --out .gradle-modernization/group-<n> --compare-with .gradle-modernization/baseline [--ignore-task :build-logic:compileGroovyPlugins ...]
   ```
   Exit 0 means nothing unexpected changed. The comparison covers:
   - Task membership and outcomes (explain intentionally added build-logic compilation tasks with `--ignore-task`). Test identities and outcomes per task, not just counts. No new deprecations.
   - Dependency reports per configuration, with unified diffs in `dependency-diffs/`: resolved versions, selected variants/classifiers and classpath order must match unless the group's stated purpose changes them. Use `dependencyInsight --dependency <module> --configuration <name>` for any difference. When publishing configuration changes, compare generated POM / `.module` metadata (generate locally, don't publish).
   - Configuration cache: the new run's own strict store-then-reuse pair must pass, as in Phase 1.
   - Reproducibility claims (Sec4): rebuild with `--no-build-cache --rerun-tasks` into a clean checkout and compare `sha256sum` of artifacts. Comparing a cached output with itself proves nothing.
   - If Gradle can't run, say so and hand the user the exact commands and expected outputs; don't mark the group verified.
- **Show a diff summary** and the comparison result. If anything regressed, roll the group back and report.

### Group-specific rules

**Wrapper upgrades are ordered by prerequisites.** Sequence: (1) clear deprecation warnings on the current version, (2) update/replace plugins that don't support the target, (3) for 8.x → 9.x, first move to the latest 8.x and clear its warnings (the upgrade guide's own recommendation), (4) then `./gradlew wrapper --gradle-version=<target> --gradle-distribution-sha256-sum=<sha>` (sha from https://gradle.org/release-checksums/) and run it a second time so the new Gradle regenerates the wrapper jar/scripts, (5) `help --warning-mode=all` on the new version. Pick the latest version every plugin supports; note the gap to the newest release in the report.

**Version catalog migration — preserve semantics.** Preserve existing imported/published, programmatic and multiple-catalog architecture. Move external library/plugin versions following D3, not unrelated strings. Settings plugins and precompiled plugins' `plugins {}` blocks cannot use project catalog `alias()`. Catalog TOML supports rich versions (`strictly`, `prefer`, etc.), but **not classifiers, artifact types, excludes, attributes or capability requirements**. Keep those at the dependency declaration site, e.g. `implementation(variantOf(libs.foo) { classifier('test-fixtures') })`, preserving existing closures and constraints. Defer anything not expressible identically. Success means equivalent dependency/artifact evidence, not "zero GAV strings"; incremental migration is valid.

**Dependency locking** does not require a catalog or convention-plugin migration. Before proposing anything, confirm the current state per project from `facts.build_facts.<build>.locking`: a declaration that is not activated, or an activated project without a lockfile, is a defect to fix, not existing coverage to preserve. Preserve existing per-configuration locking and custom lock locations. Enable locking and generate the lock state in the same group, per project (C1); use `DEFAULT` while bootstrapping, then `STRICT` once each locked configuration has state. Include generated lockfiles in the diff. Resolved versions must not change when merely enabling locking. Selective updates may change other modules through resolution rules; review the whole lock diff. Settings plugin versions and dependency verification are separate concerns.

**Convention plugins are extraction, not policy.** Moving `subprojects {}` logic into `build-logic/src/main/groovy/*-conventions.gradle` must reproduce the *existing* configuration exactly (same Java target, same compiler args, same test framework, same parallelism). `best-practices.md` § "Convention plugin skeleton" separates the behaviour-preserving base from optional policy upgrades — each policy upgrade (toolchain bump, `-Werror`, JUnit Platform, `maxParallelForks`, sources jar) is its own approval item with its own verification. Use `groovy-gradle-plugin` in `build-logic/build.gradle`; migrate one subproject at a time; `tasks --provenance` before/after should show the same task set.

**Configuration cache** is enabled only after store-then-reuse succeeds on the CI task set. Mark truly incompatible tasks with `notCompatibleWithConfigurationCache('reason')`; list blocking plugins in the report rather than silently keeping the cache off.

**Don't edit application/product source or test files.** Source moves (S1, S2), deleting Cucumber runners and test migrations are proposals, not executions. Build-logic extraction may create/edit `build-logic/src/**` or `buildSrc/src/**`; these are build tooling, not product sources.

**Behaviour-affecting groups** (exclusion narrowing D8, redundant deps D6, `consistentResolution` C2, `sourceCompatibility` → toolchain, test framework changes) are medium/high risk: explain the observable effect and run the full test/dependency comparison above.

## Groovy DSL idioms for rewrites

```groovy
plugins { id 'java-library' }                        // declarative project plugin application where valid
dependencies { implementation libs.jackson.databind } // catalog alias
tasks.register('myTask', Copy) { ... }               // register, not create / task x {}
tasks.named('test', Test) { ... }                    // named, not test { } eager access
tasks.withType(JavaCompile).configureEach { ... }    // configureEach
layout.buildDirectory.dir('reports')                 // not buildDir
java { toolchain { languageVersion = JavaLanguageVersion.of(17) } }  // match the existing target; a bump is a policy change
```
Since 9.6.0 Groovy DSL coerces `String → File` and single value → `ListProperty` on lazy properties, so `task.workingDir = '../x'` is fine.

## What NOT to recommend

- Kotlin DSL (official practice G1, but out of scope by user decision — mention once as "not applied").
- Isolated Projects for production (incubating in 9.7, "not yet recommended"). A diagnostic run requires both `--isolated-projects` and `-Dorg.gradle.isolated-projects.diagnostics=true`; diagnostics alone has no effect.
- Adopting `@Incubating` APIs in shared build logic without saying so (practice G9).
- `ENHANCED_GRAPH_ORDERING` / `NO_IMPLICIT_LOOKUP_IN_PARENT_PROJECTS` feature previews unless the user wants to test Gradle 10 behaviour early — they change classpath order and property resolution.
- Bumping Java targets, adding `-Werror`, changing test frameworks, or raising parallelism as part of "modernization" — those are policy changes to offer separately.
