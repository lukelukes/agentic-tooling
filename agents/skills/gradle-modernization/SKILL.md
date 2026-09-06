---
name: gradle-modernization
description: Audit a Java project's Gradle build (Groovy DSL) against Gradle 9.x features and official best practices, then apply approved fixes with behavior-preserving verification. Use for modernizing, upgrading, cleaning up or reviewing Java build.gradle / settings.gradle / gradle.properties; version catalogs, convention plugins, locking, configuration cache, Gradle-10 readiness or deprecation warnings. Also use for targeted questions about what newer Gradle versions offer. Not a Kotlin DSL migration, Android/AGP upgrade or product-test migration workflow; route those to domain-specific guidance.
---

# Gradle Modernization (Groovy DSL, Gradle 9.x)

Two phases: **audit and report**, then **apply changes one approved group at a time, checking that behaviour is preserved**. Don't rewrite build files before the user has seen the audit. A green build is not proof on its own: check that the tests actually ran.

Scope: Groovy DSL (`.gradle`). Starting point usually 9.x, sometimes 8.x. Target: the latest *compatible* 9.x release — not automatically the newest.

For Gradle <8.x, provide a staged migration plan using the relevant official guides; do not apply the 8/9.x recipes directly. Kotlin DSL and Android/AGP are out of scope; note them as coverage gaps in mixed builds.

Helpers require Python 3.10+. Resolve `scripts/` and `references/` relative to this skill's directory, not the audited project's working directory. Keep audit outputs and logs in a scratch directory (e.g. `.gradle-modernization/` in the project, gitignored) so they don't pollute the diff.

## Reference files

| File | When |
|---|---|
| `references/gradle-9x-features.md` | Full audit, or any question about a specific 9.x version/feature. Per-version 9.0 → 9.7, tagged ACT/AUTO/INFO. |
| `references/best-practices.md` | Full audit, or a question about a specific practice. 44 official practices + companions (dependency locking C1, consistent resolution C2), each with Detect / Fix / Risk. |
| `references/gradle-10-deprecations.md` | Every version transition and Gradle-10 readiness; source-pinned triage index. |
| `references/report-template.md` | Writing the audit report. |
| `references/verification.md` | Baseline capture, before/after comparison, configuration-cache check, dependency diffing. |
| `scripts/audit_gradle_project.py` | Read-only static scan, run first. `scripts/test_audit.py` is its regression suite. |
| `scripts/compare_runs.py` | Summarize a Gradle log + JUnit XML into JSON; diff two summaries (task outcomes, test identities, cache store/reuse, deprecation count). |
| `evals/README.md` | Maintaining/testing this skill. |

**Targeted questions** ("why does 9.6 warn about `ext`?", "should I use `--console=colored`?"): read only the relevant reference section and answer. Reserve the full checklist walk for an actual audit request.

## Phase 1 — Audit

0. **Prerequisites.** JDK available (Gradle 9 daemon needs 17+). If Gradle can't run, the audit is static-only and every "build-reported" line in the report is marked *not checked*. Note `git status` so later diffs are attributable to the skill's edits.
1. **Static facts.** `python scripts/audit_gradle_project.py <root> --json`. The scanner recursively discovers builds under `<root>` and classifies project, settings, applied and precompiled scripts. It does not follow symlinks or read outside `<root>`; if `settings.gradle` includes an external build, run the scanner on it separately. Read `facts.coverage`: skipped/unreadable paths, Kotlin DSL, dynamic includes and unsupported syntax are gaps, not passes. The lexical scanner masks strings/comments but does not evaluate Groovy, so **confirmed** means a directly observed fact, **likely** an executable pattern, **suspected** a heuristic. Check applicability of each finding against the actual receivers (dependency/plugin/buildscript/publishing repositories are different things). Use `facts.build_facts` and each finding's `build` identity for included-build settings/catalog/locking checks. `facts.build_facts.<build>.locking` lists, per project, which script declares locking, whether it actually activates anything (`lockAllConfigurations()` / `activateDependencyLocking()`), and whether that project's `gradle.lockfile` exists and has entries. A `dependencyLocking {}` block that only sets `lockMode` locks nothing, and `allprojects {}` locking with lockfiles in only some projects is a C1 finding, not a pass.
2. **Dynamic facts** (if Gradle runs). Save the output of each under the scratch directory:
   - `./gradlew help --warning-mode=all` — deprecations (9.3+ prints Problems inline; 9.7 gives source locations).
   - **Baseline** of the CI verification tasks (typically `check`, `test`, custom `Test` tasks; not `publish`/deploy/docker tasks) in the project's **existing configuration-cache mode**: `--no-build-cache --rerun-tasks --console=plain --warning-mode=all`. Summarize with `compare_runs.py summarize`, mapping each `Test` task to its XML directory. If the baseline fails, report the blocker rather than manufacturing a green baseline.
   - **Configuration cache**: run the same tasks **twice** with `--configuration-cache --configuration-cache-problems=fail --no-build-cache --rerun-tasks --console=plain`. First run must store, second must reuse, and the test tasks must execute both times (`compare_runs.py compare --cache-pair`). `UP-TO-DATE`, `FROM-CACHE` or warn-mode success does not establish compatibility.
   - `./gradlew tasks --provenance` (9.5+) — which plugin/script registered each task. Older versions: task report + manual attribution.
   - Dependency baselines: `:<project>:dependencies --configuration <name>` for compile/runtime, test compile/runtime, annotation processors, custom source sets and build-logic classpaths as applicable. A platform/aggregation project may have no `runtimeClasspath`; record N/A.
   - **Gradle 9.0 can silently stop running custom `Test` tasks** that relied on inheriting `testClassesDirs`/`classpath`. Unexpected `NO-SOURCE`, missing XML or a changed test set is a blocker even if aggregate counts look fine.
3. **Walk the references.** `best-practices.md` top to bottom, mark each: ✅ followed · ❌ violated · ➖ N/A · ❓ not checked · ⚠ suspected (scanner lead, unverified). Then `gradle-9x-features.md` for every version between current and target. For **every version transition**, also read `gradle-10-deprecations.md` and the target-pinned official upgrade guide (plus the major/latest-8.x guides when crossing 8 → 9). Review breaking changes and bundled-tool defaults even without warnings. Don't infer a removal deadline from a chapter title.
4. **Plugin compatibility inventory** — mandatory when the target version differs from current. List every plugin with its version and the Gradle/JDK range it supports (plugin portal page, release notes). Distinguish four JDK concerns: daemon JVM, compilation toolchain, bytecode target (`options.release`), test runtime. A plugin that doesn't support the target Gradle blocks the wrapper upgrade until it's updated or replaced.
5. **Write the report** from `report-template.md`. Each finding: rule ID, location, evidence, confidence, consequence, verification method, risk. Prioritize build blockers and measurable benefits over naming preferences. Measure representative timings before proposing performance-driven restructuring. Order candidates by *prerequisites*, then risk. "No changes recommended" is a valid result; don't inflate a best-practice score with speculative violations.
6. **Stop and ask** which groups to apply.

## Phase 2 — Apply (approved groups only)

One group at a time. For each:

- **Isolate the change.** Start from a clean tree (commit or stash pending work first, or note which files were already dirty). Make only the group's edits, so `git diff` shows exactly this group. Rollback is `git checkout -- <files>` plus removing any new files the group created. Don't stage or commit unless asked.
- **Verify by comparing with the Phase 1 baseline.** Re-run the same commands and compare with `compare_runs.py compare`:
   - Task membership and outcomes match (explain intentionally added build-logic compilation tasks with `--ignore-task`). Test identities and outcomes per task match, not just counts. No new deprecations.
   - Dependency reports: resolved versions, selected variants/classifiers and classpath order match unless the group's stated purpose changes them. Use `dependencyInsight --dependency <module> --configuration <name>` for any difference. When publishing configuration changes, compare generated POM / `.module` metadata (generate locally, don't publish).
   - Configuration cache groups: strict store-then-reuse pair as in Phase 1.
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

## Maintenance

`LATEST_GRADLE` / `LAST_VERIFIED` record the documentation review date. Use version-pinned official sources for API claims. When updating rules, run `python -B scripts/test_audit.py` and `python -B -m unittest discover -s scripts -p 'test_*.py'`. `scripts/test_recipes.py --gradle <launcher>` runs the recipes against a real Gradle (see `references/verification.md`). `evals/` holds agent-level scenarios.
