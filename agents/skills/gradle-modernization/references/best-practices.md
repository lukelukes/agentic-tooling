# Gradle Best Practices — Audit Checklist (Groovy DSL)

Source: https://docs.gradle.org/9.7.1/userguide/best_practices_index.html (44 practices). Each entry: the official title, the Gradle version it was added to the guide, **Detect** (what to look for in the project), **Fix** (Groovy DSL), and a risk rating. These are context-dependent recommendations, not 44 mandatory rewrites.

Walk every entry during a full audit: ✅ followed · ❌ violated (evidence + applicability confirmed) · ➖ not applicable · ❓ not checked · ⚠ suspected. Static absence, an unreadable file or an unexecuted plugin is not proof of a violation. Optional naming/structure preferences do not rank alongside security or build blockers.

## Contents

- [General](#general) (9)
- [Structuring Builds](#structuring) (5)
- [Dependencies](#dependencies) (9)
- [Tasks](#tasks) (11)
- [Performance](#performance) (5)
- [Security](#security) (4)
- [Testing](#testing) (1)
- [Companion recommendations: dependency locking, consistent resolution](#companions)
- [Version catalog cheat sheet](#catalog)
- [Convention plugin skeleton](#conventions)

---

<a id="general"></a>
## General

### G1. Use Kotlin DSL — added 8.14
**Out of scope for this skill** (user decision: Groovy DSL only). Mention once in the report under "Not applied", do not recommend.

### G2. Use the Latest Minor Version of Gradle — added 8.14
**Detect:** `distributionUrl` in `gradle/wrapper/gradle-wrapper.properties` vs the current latest (9.7.1 as of Sept 2026; check https://gradle.org/releases/). Also flag `.0` releases where a `.1` patch exists (9.2.1, 9.3.1, 9.4.1, 9.6.1, 9.7.1).
**Fix:** Follow SKILL.md's prerequisite-ordered wrapper upgrade using an exact compatible target and its distribution checksum; run the wrapper task twice. Then `./gradlew help --warning-mode=all` plus the verification workload.
**Risk:** Plugin-dependent, including within 9.x (incubating APIs can change). Medium–High for 8.x → 9.x (JDK 17 daemon, Groovy 4, reproducible archives, removed APIs — read `gradle-9x-features.md` §9.0.0).

### G3. Apply Plugins Using the plugins Block — added 8.14
**Detect:** `apply plugin: 'java'`, `apply plugin: JavaPlugin`, `buildscript { dependencies { classpath '...' } }` used only to load plugins, `apply from: 'x.gradle'` scripts that apply plugins.
**Fix:**
```groovy
plugins {
    id 'java-library'
    alias(libs.plugins.spotless)     // third-party via catalog
}
```
Third-party plugin versions go in `libs.versions.toml` `[plugins]`. Plugin repositories go in `settings.gradle` `pluginManagement { repositories { gradlePluginPortal() } }`.
**Risk:** Low–Medium; conditional application and script plugins may need convention extraction rather than a direct syntax swap. Project `plugins {}` has ordering restrictions and cannot simply be inserted into applied script plugins. Preserve application order and plugin versions.

### G4. Do Not Use Internal APIs — added 8.14
**Detect:** imports or references to `org.gradle.internal.*`, `org.gradle.api.internal.*`, `org.gradle.util.*` (most of which was removed in 9.0), casts to `*Internal` types, `DefaultXxx` classes.
**Fix:** Replace with the public equivalent; if none exists, isolate the usage in one place in `build-logic/` and comment it. Common swaps: `GUtil.toCamelCase` → own helper; `ConfigureUtil.configure` → `Action<T>`; `ProjectInternal.getServices()` → `@Inject` service injection.
**Risk:** Medium (behaviour of replacement may differ).

### G5. Set build flags in gradle.properties — added 9.0.0
**Detect:** `org.gradle.*` flags passed via CI scripts, `GRADLE_OPTS`, `gradlew` wrapper edits, or `-D`/`--` flags in README instructions instead of the root `gradle.properties`.
**Fix:** Preserve existing values; centralize what the build already relies on. Example settings, not a bundle to paste blindly:
```properties
org.gradle.caching=true
org.gradle.configuration-cache=true
org.gradle.parallel=true
org.gradle.jvmargs=-Xmx2g -Dfile.encoding=UTF-8
```
Machine-specific overrides belong in `~/.gradle/gradle.properties`, outside version control. Enable configuration cache only after the store/reuse check; offer parallelism and heap/encoding changes as separate items.
**Risk:** Low for relocating equivalent settings; Medium for changing execution, cache or encoding policy.

### G6. Name Your Root Project — added 9.2.0
**Detect:** `settings.gradle` lacks `rootProject.name = '...'`. Without it the name is the directory name, which differs between clones/CI checkouts and breaks build cache keys, published coordinates, and IDE project names.
**Fix:** `rootProject.name = 'my-service'` in `settings.gradle` — after `pluginManagement {}` / `plugins {}` if present (those must come first), otherwise as the first statement.
**Risk:** Low. Check `archivesName`/publication artifactIds that may have depended on the directory name.

### G7. Do not use gradle.properties in subprojects — added 9.2.0
**Detect:** `gradle.properties` in a declared subproject, relative to its owning build. Root properties of `buildSrc` and included builds are legitimate; unrelated fixtures and external builds are not subprojects. Check whether a script deliberately loads the file.
**Fix:** Move the values into the owning build's root properties or a convention-plugin extension, preserving overrides and existing consumers, then delete the obsolete files.
**Risk:** Low–Medium (verify no subproject read them via `project.findProperty`).

### G8. Avoid afterEvaluate — added 9.6.0
**Detect:** `afterEvaluate {`, `project.afterEvaluate`, `gradle.projectsEvaluated`.
**Fix:** Depends on why it's there:
- Reacting to a plugin being applied → `plugins.withId('java') { ... }` / `pluginManager.withPlugin(...)`.
- Reading a value set later → use `Property<T>`/`Provider<T>` and wire lazily (`task.foo = extension.bar`), never `.get()` at configuration time.
- Configuring all tasks of a type → `tasks.withType(Test).configureEach { ... }`.
- Configuring after extension is populated → `extension.items.all { ... }` / `configureEach`.
**Risk:** Medium — ordering semantics change; run the build after each removal.

### G9. Consider use of @Incubating APIs carefully — added 9.7.0
**Detect:** `[Incubating]` warnings in build output, or `--warning-mode=all` listing incubating features; use of `testing.suites`, `dependencyResolutionManagement.repositories` (incubating but explicitly recommended), Isolated Projects.
**Fix:** Nothing automatic. In the report, list incubating features the build depends on and note that they may change between 9.x minors (SemVer only covers stable APIs). Prefer stable alternatives in shared build logic.
**Risk:** N/A (advisory).

---

<a id="structuring"></a>
## Structuring Builds

### S1. Modularize Your Builds — added 9.0.0
**Detect:** A single-project build with several distinct concerns (e.g. `src/main/java/com/x/{api,persistence,web,cli}`), or one huge project with feature-flag source sets. Also very large `build.gradle` files (>150 lines) doing many things.
**Fix:** Advisory unless the user asks. Describe a split (`:api`, `:core`, `:app`) and note it enables parallel compilation, build-cache reuse, and clearer dependencies. Source moves are out of this skill's scope — propose, don't execute.
**Risk:** High (source moves).

### S2. Do Not Put Source Files in the Root Project — added 9.0.0
**Detect:** Multi-project build where root has `src/main/**` or applies `java`. The root should only hold `settings.gradle`, `gradle.properties`, `gradle/`, and an (optional, minimal) `build.gradle`.
**Fix:** Advisory: move root sources into a subproject (`:app`), remove `java` from root `build.gradle`. Propose in report; don't move sources.
**Risk:** High (source moves, publication coordinates change).

### S3. Favor build-logic Composite Builds for Build Logic — added 9.0.0
**Detect:** `buildSrc/` directory. `buildSrc` is on every project's classpath, any change invalidates the whole build's classpath and disables CC reuse more aggressively; an included `build-logic` build behaves like a normal plugin dependency.
**Fix:**
```
build-logic/
  settings.gradle          -> rootProject.name = 'build-logic'; dependencyResolutionManagement { repositories { gradlePluginPortal(); mavenCentral() } }
  build.gradle             -> plugins { id 'groovy-gradle-plugin' }
  src/main/groovy/*.gradle -> precompiled script plugins
```
Root `settings.gradle`: `pluginManagement { includeBuild 'build-logic' }`. Move `buildSrc/src/main/groovy/*.gradle` across unchanged; binary plugin classes need `gradlePlugin { plugins { register(...) } }` in `build-logic/build.gradle`. If `build-logic` needs the version catalog, add `versionCatalogs { libs { from(files('../gradle/libs.versions.toml')) } }` in its settings.
**Risk:** Medium. Existing `buildSrc` builds work fine; only migrate when also doing S5 or when `buildSrc` changes are slowing everyone down.

### S4. Avoid Unintentionally Creating Empty Projects — added 9.1.0
**Detect:** `include 'services:payment'` (nested path) without `project(':services').projectDir` mapping creates an empty `:services` project. Also directories with no `build.gradle` that are still `include`d. Check `./gradlew projects` (9.1+ shows locations).
**Fix:** Use flat project names with explicit directories:
```groovy
include 'payment'
project(':payment').projectDir = file('services/payment')
```
or, if the hierarchy is wanted, ensure intermediate projects are intentional and have no `java` plugin.
**Risk:** Low–Medium (project paths change → update `project(':services:payment')` references and CI task paths).

### S5. Use Convention Plugins — added 9.3.0
**Detect:** `subprojects {}` / `allprojects {}` blocks configuring plugins, dependencies, or tasks; `apply from: "$rootDir/gradle/java.gradle"`; the same 20 lines repeated in every `build.gradle`; `configure(subprojects.findAll { ... })`.
**Fix:** Use the [behaviour-preserving skeleton](#conventions) as the single extraction recipe. Copy only the existing plugins, Java settings, compiler flags, test framework, dependencies and parallelism; do not introduce JUnit Platform, Java 21 or publishing as part of extraction. For each subproject, remove its old configuration when enabling its convention so it is not configured twice. Delete the old shared block only after all its consumers have migrated. Use task provenance (9.5+) to confirm origins, and the verification protocol to compare behaviour.
**Risk:** Medium. Do it subproject-by-subproject; run the verification workload after each. Measure configuration times if performance is the reason for extracting.

---

<a id="dependencies"></a>
## Dependencies

### D1. Single GAV String — added 8.14
**Detect:** `implementation group: 'x', name: 'y', version: 'z'` (named-argument notation). **Deprecated; removed in Gradle 10.**
**Fix:** `implementation 'x:y:z'` — or better, a catalog alias (D2). `exclude group: ..., module: ...` inside the closure is fine and stays map-style.
**Risk:** Low. Pure syntax.

### D2. Use Version Catalogs to Centralize Dependency Versions — added 9.0.0
**Detect:** Inspect default, named, imported, published and programmatic catalogs, including settings plugins. Remaining dependency literals and shared version variables are migration candidates, not proof of an invalid build.
**Fix:** See [Version catalog cheat sheet](#catalog). Preserve existing architecture and migrate incrementally. Keep `project(':x')`, `platform(...)`/`enforcedPlatform(...)` and all declaration-site semantics (the BOM itself can become a catalog entry). Do not put non-dependency strings in the catalog.
**Risk:** Low for simple coordinates; Medium for rich versions/variants. Partial migrations with documented exceptions are valid; correctness outranks eliminating every GAV string.

### D3. Name Version Catalog Entries Appropriately — added 9.0.0
**Detect:** Aliases like `junit_jupiter`, `org-apache-commons-lang3`, `ktor-ktor-client`, `spring-boot-starter-web` (dashes inside artifact ids), `core`, `sdk`, plugin libraries without `-plugin` suffix.
**Fix (rules from the docs):**
1. Dashes separate *segments*; segments become dots in scripts (`libs.jackson.databind`).
2. First segment from the group, without TLD: `com.fasterxml.jackson.core` → `jackson`.
3. Second segment from the artifact id: `armeria-grpc` → `armeria-grpc`.
4. Drop generic terms that stand alone: `core`, `java`, `gradle`, `module`, `sdk`.
5. Don't repeat: `io.ktor:ktor-client-core` → `ktor-client-core`, not `ktor-ktor-client-core`.
6. Dashes *inside* an artifact id become camelCase: `spring-boot-starter-web` → `springBootStarterWeb` (so `libs.spring.bootStarterWeb` or `libs.springBootStarterWeb`).
7. Plugins referenced as libraries get `-plugin`: `dependency-check-plugin`.
Example: `jackson-databind`, `jackson-dataformatCsv`, `slf4j-api`, `junit-jupiter`, `assertj-core`→`assertj` (rule 4).
**Risk:** Low (rename aliases + references together).

### D4. Set up your Dependency Repositories in the Settings file — added 9.0.0
**Detect:** Project dependency repositories, including `allprojects { repositories { ... } }`. First distinguish four scopes: project dependencies, `pluginManagement`, `buildscript`, and `publishing`. The latter three are not interchangeable with `dependencyResolutionManagement`.
**Fix:** `settings.gradle`:
```groovy
pluginManagement {
    repositories { gradlePluginPortal(); mavenCentral() }
}
dependencyResolutionManagement {
    repositoriesMode = RepositoriesMode.FAIL_ON_PROJECT_REPOS
    repositories { mavenCentral() }
}
```
Remove only equivalent project dependency repository blocks after preserving repository order, credentials, content filters and metadata policies. Keep publishing destinations in `publishing.repositories`; keep buildscript repositories until their classpath consumers are migrated; plugin resolution uses `pluginManagement.repositories`. Each included build owns its own settings. `FAIL_ON_PROJECT_REPOS` is an enforcement decision to offer, not a mechanical relocation.
**Risk:** Medium. Lost repository scope/order or filters can change artifact provenance even with identical versions. Verify dependency artifacts and publication destinations separately.

### D5. Don't Explicitly Depend on the Kotlin Standard Library — added 9.0.0
**Detect:** `implementation 'org.jetbrains.kotlin:kotlin-stdlib...'` in a project applying a Kotlin plugin.
**Fix:** Remove the line (the Kotlin plugin adds it). ➖ for pure-Java projects.
**Risk:** Low.

### D6. Avoid Redundant Dependency Declarations — added 9.0.0
**Detect:** Same coordinates declared in two configurations of one project (`api` + `implementation`, `compileOnly` + `implementation`, `implementation` + `testImplementation`); same dep in a subproject and in the convention plugin it applies.
**Fix:** Keep the widest-correct one (`api` ⊃ `implementation` ⊃ `testImplementation` for the test classpath). `compileOnly` + `implementation` is almost always a bug: pick one.
**Risk:** Low–Medium (classpath scope changes; run tests).

### D7. Use Content Filtering with multiple Repositories — added 9.1.0
**Detect:** Two or more repositories in `dependencyResolutionManagement.repositories` without `content { }` / `exclusiveContent { }`. Common: `mavenCentral()` + a corporate Nexus/Artifactory + `google()` + JitPack + `mavenLocal()`.
**Fix:**
```groovy
dependencyResolutionManagement {
    repositories {
        exclusiveContent {
            forRepository { maven { url = uri('https://repo.example.com/internal') } }
            filter { includeGroupByRegex 'com\\.example(\\..*)?' }
        }
        mavenCentral()   // fallback last
    }
}
```
Prefer `exclusiveContent` (dependency can *only* come from there). Put the unfiltered fallback last and make sure it's trusted. `mavenLocal()` should be removed or filtered to specific groups.
**Risk:** Medium — a wrong filter makes resolution fail (loudly, which is the point). Run `./gradlew dependencies` after.

### D8. Apply Exclusions Narrowly — added 9.2.0
**Detect:** `configurations.all { exclude ... }`, `configurations.configureEach { exclude ... }`, `configurations.implementation { exclude group: 'x' }` (whole configuration), `exclude group: 'x'` without `module:` (whole group).
**Fix:** Move each exclusion onto the specific dependency that pulls the unwanted transitive in, and name the module:
```groovy
implementation(libs.hibernate.core) {
    exclude group: 'javassist', module: 'javassist'
}
```
Use `./gradlew dependencyInsight --dependency javassist --configuration runtimeClasspath` to find which direct dep brings it. If the goal is "this library must never be on the classpath", a `constraints { implementation('x:y') { version { rejectAll() } } }` or a capability conflict is more explicit than a blanket exclude.
**Risk:** Medium. A blanket exclude may have been masking several paths; after narrowing, re-check `dependencies --configuration runtimeClasspath`.

### D9. Always Declare Attributes on Consumable and Resolvable Configurations — added 9.7.0
**Detect:** `configurations.consumable('x')` / `configurations.resolvable('x')` / `configurations.create('x') { canBeConsumed = true }` with no `attributes { }` block; project dependencies using `project(path: ':p', configuration: 'x')`.
**Fix:**
```groovy
configurations {
    consumable('customElements') {
        attributes {
            attribute(Category.CATEGORY_ATTRIBUTE, objects.named(Category, Category.LIBRARY))
            attribute(Usage.USAGE_ATTRIBUTE, objects.named(Usage, Usage.JAVA_RUNTIME))   // or a custom Attribute
        }
        outgoing { artifact(someTask) }
    }
}
```
Mirror the same attributes on the consumer's `resolvable` configuration and depend on `project(':producer')` without naming the configuration.
**Risk:** Medium (custom cross-project wiring). ➖ for builds with no custom configurations.

---

<a id="tasks"></a>
## Tasks

### T1. Avoid DependsOn — added 8.14
**Detect:** `dependsOn` used to make task B run after task A *because B consumes A's output* (as opposed to lifecycle wiring like `check.dependsOn integrationTest`, which is fine).
**Fix:** Wire the output as an input so Gradle infers the dependency:
```groovy
def gen = tasks.register('generateDocs', GenerateDocs) { outputDir = layout.buildDirectory.dir('docs') }
tasks.register('packageDocs', Zip) { from(gen) }          // task dependency inferred
// or: from(gen.flatMap { it.outputDir }) when outputDir is a DirectoryProperty
```
**Risk:** Low–Medium.

### T2. Favor @CacheableTask and @DisableCachingByDefault over cacheIf/doNotCacheIf — added 8.14
**Detect:** `outputs.cacheIf { true }` / `outputs.doNotCacheIf(...)` in build scripts on custom task *types*; custom task classes with neither annotation.
**Fix:** On the task class: `@CacheableTask` (with `@PathSensitive` on every file input) or `@DisableCachingByDefault(because = '...')`. Keep `cacheIf` only for genuinely per-instance decisions.
**Risk:** Low. ➖ if no custom task types.

### T3. Group and Describe custom Tasks — added 9.0.0
**Detect:** `tasks.register('foo')` without `group` and `description`; tasks appearing under "Other tasks" in `./gradlew tasks --all`.
**Fix:** `tasks.register('foo') { group = 'verification'; description = 'Runs the contract tests.' }`. Use standard group names (`build`, `verification`, `documentation`, `publishing`, `help`) or a project-specific one.
**Risk:** Low.

### T4. Do not call get() on a Provider outside a Task action — added 9.1.0
**Detect:** `.get()` / `.getOrElse()` / `.getAsFile()` on `Property`/`Provider`/`NamedDomainObjectProvider` at script top level or inside `tasks.register { }` configuration (outside `doFirst`/`doLast`). Also `tasks.named('x').get()`, `configurations.foo.get()`.
**Fix:** Pass the provider through: `outputFile = otherTask.flatMap { it.outputFile }`; `from(provider)`; `inputs.files(provider)`. In `doLast`, `.get()` is fine.
**Risk:** Low–Medium.

### T5. Don't resolve Configurations before Task Execution — added 9.1.0
**Detect:** `configurations.runtimeClasspath.files`, `.resolve()`, `.resolvedConfiguration`, `.asPath`, `.each { }` at configuration time (top level, inside `tasks.register { }` body, in `afterEvaluate`).
**Fix:** Declare the configuration as a task input and read it in the action: `classpath = configurations.runtimeClasspath` (a `FileCollection` is lazy) then `classpath.files` inside `doLast`. For custom tasks: `@Classpath abstract ConfigurableFileCollection getRuntimeClasspath()`.
**Risk:** Medium — usually the fix is easy, but it exposes hidden ordering assumptions.

### T6. Avoid using eager APIs on File Collections — added 9.1.0
**Detect:** Materializing/iterating a file collection at configuration time via `.files`, `.asPath`, `.iterator()`, `.each`, or `.collect`. Distinguish `fileCollection.filter {}` (returns a live collection) from `fileCollection.files.findAll {}` (materializes first).
**Fix:** Keep the collection lazy and let the task consume it; use `.elements` for a provider, `FileCollection.filter {}` for a live filtered collection, or `FileTree.matching { include ... }` for tree patterns. See the [9.7.1 FileCollection API](https://docs.gradle.org/9.7.1/javadoc/org/gradle/api/file/FileCollection.html).
**Risk:** Low–Medium.

### T7. Prefer @PathSensitivity.NONE for file inputs and @PathSensitivity.RELATIVE for directories — added 9.2.0
**Detect:** Custom task classes with `@InputFile`/`@InputFiles`/`@InputDirectory` lacking `@PathSensitive`, or using `ABSOLUTE`. `ABSOLUTE` means no cache hits across checkouts/machines.
**Fix:** `@PathSensitive(PathSensitivity.NONE) @InputFile` for single files where only content matters; `@PathSensitive(PathSensitivity.RELATIVE) @InputDirectory` / `@InputFiles` for trees where relative layout matters. Use `NAME_ONLY` when the file name matters (e.g. resource bundles).
**Risk:** Low. ➖ if no custom task types.

### T8. Use unique output files and directories — added 9.3.0
**Detect:** Two tasks writing into the same `layout.buildDirectory.dir('generated')`; tasks with `outputs.dir(buildDir)`; overlapping outputs warnings in build cache debugging.
**Fix:** One output location per task, named after the task: `layout.buildDirectory.dir("generated/sources/${name}")`. Never use the project build dir or a shared parent as a task output.
**Risk:** Low–Medium (downstream consumers must point at the new location — wire via providers, not strings).

### T9. Don't hardcode task names when referring to them — added 9.7.0
**Detect:** `tasks.named('compileJava')` is fine (documented public name); but `tasks.named('generateFooSources')` referencing a *third-party plugin's* undocumented task, or `dependsOn 'someInternalTask'` strings pointing at plugin internals.
**Fix:** Depend on the plugin's documented extension or on the task's *outputs* (`sourceSets.main.output`, `tasks.withType(SomePluginTask)`), or use `tasks.withType(X).configureEach`. Keep name references only for names the plugin documents as API (`compileJava`, `test`, `jar`, `assemble`, `check`, `build`, `javadoc`, `publish*`).
**Risk:** Low.

### T10. Don't access a Project instance during Task Execution — added 9.7.0
**Detect:** `project.` inside `doLast`/`doFirst` or `@TaskAction` (e.g. `project.copy { }`, `project.exec { }`, `project.file(...)`, `project.version`, `project.buildDir`, `project.logger` — the last is OK-ish but use `logger`). Configuration Cache fails on these.
**Fix:** Inject public services on a task class: `@Inject abstract FileSystemOperations getFs()` (copy/delete/sync), `@Inject abstract ExecOperations getExecOps()`, `@Inject abstract ProjectLayout getLayout()`, `@Inject abstract ArchiveOperations getArchives()`. Capture simple configuration values before the action and declare them as task inputs where they affect output. Move service-using actions into build-logic task classes; do not use internal `project.services` access as a shortcut.
**Risk:** Medium (this is most of the Configuration Cache migration work).

### T11. Wiring Task Outputs with map and flatMap — added 9.7.0
**Detect:** `outputFile = otherTask.get().outputFile`; `from(otherTask.get().outputs)`; `other.map { it.outputFile }` creates a nested provider when `outputFile` is a property. Check the resulting type and producer wiring rather than assuming every `map` loses dependencies.
**Fix:** `flatMap` when the mapped value is itself a `Provider`/`Property`: `inputFile = other.flatMap { it.outputFile }`. `map` when the result is a plain value: `archiveName = other.map { it.archiveFileName.get() }` is wrong — prefer `flatMap { it.archiveFileName }`. Rule of thumb: `flatMap` for `Property`/`Provider` results, `map` for plain values.
**Risk:** Low.

---

<a id="performance"></a>
## Performance

### P1. Enable UTF-8 — added 9.0.0
**Detect:** `org.gradle.jvmargs` lacks `-Dfile.encoding=UTF-8`; `JavaCompile` tasks without `options.encoding = 'UTF-8'`; `Javadoc` without `options.encoding`.
**Fix:** `gradle.properties`: `org.gradle.jvmargs=-Xmx2g -Dfile.encoding=UTF-8`. Convention plugin: `tasks.withType(JavaCompile).configureEach { options.encoding = 'UTF-8' }`, `tasks.withType(Javadoc).configureEach { options.encoding = 'UTF-8' }`, `tasks.withType(Test).configureEach { systemProperty 'file.encoding', 'UTF-8' }`. (On JDK 18+ the default is already UTF-8 — JEP 400 — but Gradle's daemon JVM and older toolchains may not be.)
**Risk:** Low.

### P2. Use the Build Cache — added 9.1.0
**Detect:** `org.gradle.caching` absent or `false`.
**Fix:** Offer `org.gradle.caching=true` after checking custom task correctness (declared inputs/outputs, no absolute-path inputs). Remote-cache push policy is a separate decision; preserve existing read/write policy and fork-PR restrictions.
**Risk:** Low. Custom tasks with `ABSOLUTE` path sensitivity or undeclared inputs may produce stale results — audit T7/T8 first.

### P3. Use the Configuration Cache — added 9.1.0
**Detect:** `org.gradle.configuration-cache` absent or `false`; build prints "Configuration cache is not enabled…" prompt (9.0+).
**Fix:** Follow `verification.md`: existing-mode baseline, then two identical strict configuration-cache runs with actual task execution on the CI workload. Fix reported problems, then enable the property only for the demonstrated workload. Warn mode may help diagnosis but is not verification. Mark truly incompatible tasks with `notCompatibleWithConfigurationCache('reason')` and report which workloads cannot store/reuse; graceful fallback is not cache compatibility.
**Risk:** Medium — the fix is per-problem; each is usually T10 (Project in action), T5 (eager resolution), or a plugin that needs upgrading.

### P4. Avoid Expensive Computations in Configuration Phase — added 9.0.0
**Detect:** Top-level script code that runs `git` (`'git rev-parse HEAD'.execute()`), reads/parses files, walks directories, does network I/O, or loops over `subprojects` computing things — outside any task.
**Fix:** Move into a task or a `ValueSource`:
```groovy
abstract class GitHash implements ValueSource<String, ValueSourceParameters.None> {
    @Inject abstract ExecOperations getExecOps()
    String obtain() { def out = new ByteArrayOutputStream(); execOps.exec { commandLine 'git','rev-parse','--short','HEAD'; standardOutput = out }; out.toString().trim() }
}
def gitHash = providers.of(GitHash) {}
tasks.named('jar', Jar) { manifest { attributes('Git-Hash': gitHash) } }   // provider, resolved at execution
```
`ValueSource` results are CC-compatible and tracked as build inputs.
**Risk:** Low–Medium.

### P5. Prefer the -bin Gradle Distribution — added 9.4.0
**Detect:** `distributionUrl=…-all.zip`. The `-all` distribution includes sources/docs and is ~3× larger; IDEs no longer need it.
**Fix:** `./gradlew wrapper --gradle-version=9.7.1 --distribution-type=bin`. Update `distributionSha256Sum` (see Sec1).
**Risk:** Low.

---

<a id="security"></a>
## Security

### Sec1. Validate the Gradle Distribution SHA-256 Checksum — added 9.1.0
**Detect:** `gradle-wrapper.properties` lacks `distributionSha256Sum`.
**Fix:** `./gradlew wrapper --gradle-version=9.7.1 --gradle-distribution-sha256-sum=<sha>` where `<sha>` comes from https://gradle.org/release-checksums/. Re-do on every wrapper upgrade.
**Risk:** Low.

### Sec2. Validate the Gradle Wrapper on every Upgrade — added 9.3.0 (updated 9.6.0)
**Detect:** No wrapper-validation step in CI; `gradle-wrapper.jar` committed without verification.
**Fix:** CI: `gradle/actions/wrapper-validation@v4` on GitHub Actions; elsewhere compare `sha256sum gradle/wrapper/gradle-wrapper.jar` against https://gradle.org/release-checksums/ (wrapper jar checksum) as a pipeline step. Locally, after `./gradlew wrapper`, run it a second time so the jar is regenerated by the *new* Gradle.
**Risk:** Low.

### Sec3. Do not Run ./gradlew on Untrusted Projects — added 9.7.0
**Detect:** Advisory, CI-focused: `pull_request_target` workflows that run `./gradlew` on fork PRs with repository secrets.
**Fix:** `settings.gradle`, `buildSrc`, included builds and plugins execute arbitrary code on any invocation, including `help`. Don't run fork PRs under `pull_request_target` with secrets; use `pull_request` or a secrets-free job. Wrapper validation (Sec2) only covers a tampered wrapper jar, not build logic.
**Risk:** N/A.

### Sec4. Build Output Should Be Byte-for-Byte Reproducible — added 9.7.0
**Detect:** Archives with timestamps (pre-9.0 default), `Manifest` attributes with `new Date()`, `Built-By: ${System.getProperty('user.name')}`, generated sources embedding build time, `buildTime` in `application.properties`.
**Fix:** 9.0+ makes archives reproducible by default. Remove volatile manifest attributes; if a timestamp is required use `SOURCE_DATE_EPOCH` via `reproducibleFileTimestamp` (9.7.0). Verify with *independently regenerated* outputs: `./gradlew clean assemble --no-build-cache --rerun-tasks` in two separate clean checkouts (or the same checkout with `build/` deleted between runs) and compare `sha256sum build/libs/*.jar`. Comparing an up-to-date or cache-restored artifact with itself proves nothing.
**Risk:** Low.

---

<a id="testing"></a>
## Testing

### Te1. Test your custom Task and Plugins with TestKit — added 9.4.0
**Detect:** `build-logic/` or `buildSrc/` with non-trivial plugins/tasks and no `src/test` or `src/functionalTest` using `org.gradle.testkit.runner.GradleRunner`.
**Fix:** Add TestKit fixtures to build logic, preserving its current test framework. Run identical arguments twice with strict configuration cache, `--no-build-cache` and `--rerun-tasks`; assert store then reuse, expected task outcomes and outputs. One green TestKit run does not establish reuse. Exercise each claimed Gradle/JDK boundary and known plugin constraints.
**Risk:** Low (additive).

---

<a id="companions"></a>
## Companion recommendations (not in the official 44, but referenced by them)

The docs' version-catalog practice (D2) says catalogs "only influence declared versions, not resolved versions" and to combine them with **dependency locking** and **version alignment**. These two entries make that actionable. Treat them as recommended-by-reference, not as scored practices.

### C1. Lock resolved dependency versions (dependency locking)
**Why:** A catalog declares requested versions, not the resolved graph. Locking records resolved module versions, especially useful for dynamic/range selectors; it does not make mutable artifacts byte-identical. Fixed immutable dependencies do not inherently drift on every refresh. Dependency verification, artifact immutability and reproducible task outputs are complementary controls.
**Detect:** The scanner resolves locking per project into `facts.build_facts.<build>.locking` (`:path` → declared_in, activated, lockfile, entries). A `dependencyLocking {}` block that only sets `lockMode` locks nothing: it needs `lockAllConfigurations()` or per-configuration `activateDependencyLocking()`. Scope matters: top-level in the root script covers the root project only; `allprojects {}` / `subprojects {}` cover all/non-root projects; a convention plugin covers the projects that apply it. Every covered project needs its own `<project>/gradle.lockfile` (or the custom `lockFile`); with `LockMode.STRICT` a missing lockfile fails resolution. Plugin-supplied locking and custom lock locations are not visible statically. Changing dependencies such as `-SNAPSHOT` can change bytes without changing coordinates; locking does not solve that, and Gradle warns about persisting them. See [locking documentation](https://docs.gradle.org/9.7.1/userguide/dependency_locking.html).
**Fix (Groovy, put it in the convention plugin so every subproject gets it):**
```groovy
dependencyLocking {
    lockAllConfigurations()
    lockMode = LockMode.DEFAULT           // bootstrap; switch to STRICT after every locked configuration has state
    // ignoredDependencies.add('com.example.internal:*')   // optional: never lock these
    // lockFile = layout.projectDirectory.file('gradle/gradle.lockfile')  // optional: move it; default is <project>/gradle.lockfile
}
```
Lock build logic too (root `build.gradle` / `build-logic`):
```groovy
buildscript {
    dependencyLocking { lockAllConfigurations() }   // → buildscript-gradle.lockfile
}
```
Do not add a top-level `dependencyLocking {}` to `settings.gradle` or promise a native `settings-gradle.lockfile`; Settings does not expose that project extension. Keep settings plugin versions explicit in `plugins`/`pluginManagement`; plugin artifact verification is a separate concern. Buildscript classpath locking above is a different scope from settings plugin management.

**Generate lockfiles (first time, and whenever you deliberately change deps):**
```bash
./gradlew dependencies --write-locks                  # resolves every lockable configuration in the invoked project
./gradlew resolveAndLockAll --write-locks             # if you define a task that resolves all configs (see below) — recommended in multi-project builds
./gradlew build --write-locks                         # any invocation that resolves the configs works
```
Per-project convenience task (apply a convention to each relevant project, or invoke each project's task explicitly; defining it only in the root does not resolve subprojects):
```groovy
tasks.register('resolveAndLockAll') {
    notCompatibleWithConfigurationCache('resolves configurations at execution time to write lock files')
    doFirst { assert gradle.startParameter.writeDependencyLocks : 'run with --write-locks' }
    doLast {
        configurations.matching { it.canBeResolved }.each { it.resolve() }
    }
}
```
**Update selectively:**
```bash
./gradlew dependencies --update-locks 'org.springframework:*,com.fasterxml.jackson.core:jackson-databind'
```
`--update-locks` unlocks the named modules for resolution (trailing wildcards in group/module are supported). Resolution rules can also cause other module versions to update; review the **entire** lockfile/dependency diff, not just the requested modules. See [selective lock updates](https://docs.gradle.org/9.7.1/userguide/dependency_locking.html#sec:selectively-updating-lock-state-entries).

**Lockfile format** (one per project, since Gradle 7 the single-file format is the default):
```
# This is a Gradle generated file for dependency locking.
# Manual edits can break the build and are not advised.
# This file is expected to be part of source control.
com.fasterxml.jackson.core:jackson-databind:2.19.2=compileClasspath,runtimeClasspath
org.slf4j:slf4j-api:2.0.17=compileClasspath,runtimeClasspath,testCompileClasspath,testRuntimeClasspath
empty=annotationProcessor
```
Commit it. Never hand-edit. The `empty=` line lists configurations that resolved to nothing — it's expected.

**Interactions to know:**
- Lock entries act like strict constraints and can affect classpath order. Investigate ordering changes; offer the 9.7.0 `ENHANCED_GRAPH_ORDERING` preview as a separate Gradle-10 experiment, not as an automatic fix.
- Works with the Configuration Cache and the build cache. `--write-locks`/`--update-locks` runs should be done without CC reuse (they resolve at execution).
- `LockMode.STRICT` + a missing lockfile fails the build — generate lockfiles in the same change that enables locking, or start with `DEFAULT`, commit lockfiles, then switch to `STRICT`.
- Dynamic versions in the catalog are still allowed; the lockfile freezes what they resolved to. Prefer removing them anyway (D2).
- Dependency **verification** (`gradle/verification-metadata.xml`, checksums/PGP) is separate: locking pins versions, verification checks bytes/signatures. Generating metadata records what was downloaded, not proof that it was trustworthy. Bootstrap with a workload that resolves all relevant configurations; `help` alone need not resolve application dependencies.
- Renovate supports `gradle.lockfile` maintenance (`lockFileMaintenance`). Check your dependency bot's support before relying on it; otherwise `--update-locks` is a manual PR step.
- IDE sync resolves configurations too; with STRICT mode an out-of-date lockfile breaks IntelliJ import until regenerated — expected, but tell the team.

**Risk:** Low to enable; Medium in process terms (every dependency change now touches the lockfile — this is the point).

### C2. Align versions across classpaths (consistent resolution)
**Why:** Without it `runtimeClasspath` can resolve a *higher* version of a library than `compileClasspath` (a runtime-only dep pulls it up), so you compile against one version and run against another. This is the "version alignment" the catalog practice points to.
**Detect:** `./gradlew dependencies --configuration compileClasspath` vs `runtimeClasspath` show different versions for the same module; no `consistentResolution` block.
**Fix (convention plugin):**
```groovy
java {
    consistentResolution {
        useCompileClasspathVersions()     // runtime resolves to the versions compile chose
    }
}
```
For broader alignment across a family of modules (all Jackson artifacts at one version) use a **platform**: `implementation platform(libs.jackson.bom)` — or, for producers without a BOM, a `ComponentMetadataRule` declaring a virtual platform.
**Risk:** Medium — compile/runtime differences can be intentional. Investigate why runtime selected a higher version; do not label every divergence a bug or force alignment without evidence.

<a id="catalog"></a>
## Version catalog cheat sheet (`gradle/libs.versions.toml`)

```toml
[versions]
jackson = "2.19.2"          # shared by several artifacts → use version.ref
junit = "5.13.4"
spring-boot = "3.5.4"

[libraries]
jackson-databind      = { module = "com.fasterxml.jackson.core:jackson-databind", version.ref = "jackson" }
jackson-dataformatCsv = { module = "com.fasterxml.jackson.dataformat:jackson-dataformat-csv", version.ref = "jackson" }
slf4j-api             = { module = "org.slf4j:slf4j-api", version = "2.0.17" }              # single-use → inline
junit-bom             = { module = "org.junit:junit-bom", version.ref = "junit" }
junit-jupiter         = { module = "org.junit.jupiter:junit-jupiter" }                       # version from BOM
junit-platformLauncher = { module = "org.junit.platform:junit-platform-launcher" }
commons-lang3         = { group = "org.apache.commons", name = "commons-lang3", version = { strictly = "[3.8, 4.0[", prefer = "3.17.0" } }
spring-boot-dependencies = { module = "org.springframework.boot:spring-boot-dependencies", version.ref = "spring-boot" }

[bundles]
jackson = ["jackson-databind", "jackson-dataformatCsv"]

[plugins]
spring-boot = { id = "org.springframework.boot", version.ref = "spring-boot" }
spotless    = { id = "com.diffplug.spotless", version = "7.2.1" }
```

Usage in Groovy DSL:
```groovy
plugins {
    id 'java-library'
    alias(libs.plugins.spring.boot)
}
dependencies {
    implementation platform(libs.spring.boot.dependencies)
    implementation libs.bundles.jackson
    implementation libs.slf4j.api
    implementation libs.commons.lang3
    testImplementation platform(libs.junit.bom)
    testImplementation libs.junit.jupiter
    testRuntimeOnly libs.junit.platformLauncher
}
```

Catalog TOML does **not** support classifiers, artifact types, excludes or capability requirements. Keep declaration-site semantics; rich version fields such as `strictly`/`prefer` are supported. Example for an existing classified dependency (not a new dependency to add):

```groovy
dependencies {
    implementation(variantOf(libs.my.lib) { classifier('test-fixtures') })
}
```

Keep existing `artifact {}`, `attributes {}`, `capabilities {}`, exclusion and platform wrappers when replacing coordinates. [Official catalog limitations](https://docs.gradle.org/9.7.1/userguide/version_catalogs.html#sec:toml-limitations).

Migration procedure:
1. `grep -rn --include=build.gradle -E "['\"][A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+:[^'\"]+['\"]" .` to list every GAV literal; also grep `ext {`, `Version =`, `version:`.
2. Build the `[versions]`/`[libraries]`/`[plugins]` tables; group by `version.ref` where 2+ artifacts share a version.
3. Replace each literal with the alias. Groovy: `implementation libs.foo.bar` (no parentheses needed) or `implementation(libs.foo.bar) { exclude ... }`.
4. Remove now-unused `ext`/`def` version variables and `buildscript { dependencies { classpath } }` entries that became `[plugins]`.
5. Compare relevant compile/runtime/test/processor configurations, selected artifacts and publication metadata using `verification.md`. Equal resolved versions are necessary but not sufficient.

Reserved aliases include `extensions`, `class`, `convention`; `bundles`, `versions`, `plugins` cannot be the first subgroup in dependency aliases. Underscores are valid; dashes/camelCase are naming preferences, not correctness requirements. Preserve public catalog aliases unless the user wants a rename, and check generated-accessor collisions.

Sharing a catalog with `build-logic/`: in `build-logic/settings.gradle` add
```groovy
dependencyResolutionManagement {
    versionCatalogs { libs { from(files('../gradle/libs.versions.toml')) } }
}
```
Then in precompiled Groovy script plugins the accessor isn't type-safe; use `def libs = project.extensions.getByType(VersionCatalogsExtension).named('libs')` and `libs.findLibrary('junit-jupiter').get()`.

<a id="conventions"></a>
## Convention plugin skeleton (Groovy, build-logic)

Two parts. **Part A** is behaviour-preserving extraction: it reproduces what a typical `subprojects {}` block already does, with every value taken from the *existing* build (placeholders in `<>`). **Part B** lists policy upgrades that change behaviour; each is a separate approval item.

```
build-logic/
├── settings.gradle
├── build.gradle
└── src/main/groovy/
    ├── java-conventions.gradle
    ├── library-conventions.gradle
    └── application-conventions.gradle
```

`build-logic/settings.gradle`
```groovy
rootProject.name = 'build-logic'
dependencyResolutionManagement {
    repositories { gradlePluginPortal(); mavenCentral() }
    versionCatalogs { libs { from(files('../gradle/libs.versions.toml')) } }
}
```

`build-logic/build.gradle`
```groovy
plugins { id 'groovy-gradle-plugin' }
dependencies {
    // Only needed for third-party plugins the convention scripts apply. Reference them as
    // libraries in the catalog with a -plugin suffix (rule D3.7), e.g.
    //   [libraries] spotless-plugin = { module = "com.diffplug.spotless:spotless-plugin-gradle", version.ref = "spotless" }
    // implementation libs.spotless.plugin
}
```

### Part A — behaviour-preserving base

`build-logic/src/main/groovy/java-conventions.gradle` — copy values from the existing build, don't "improve" them here:
```groovy
plugins { id 'java' }

// Only if the existing shared logic uses a catalog:
// def libs = project.extensions.getByType(VersionCatalogsExtension).named('libs')

// Copy the existing java {} settings verbatim. If there is no toolchain, do not
// introduce one: source/target compatibility and the compiler JDK are different.
// Preserve options.release independently; omit settings that were not present.

tasks.withType(JavaCompile).configureEach {
    // options.encoding = <existing explicit setting, otherwise omit>
    // options.compilerArgs = <copy the existing list verbatim, or omit>
}
tasks.withType(Test).configureEach {
    // Copy the existing useJUnitPlatform()/useJUnit()/useTestNG() setup, or omit.
    // maxParallelForks / forkEvery / jvmArgs: copy existing values or omit
}
dependencies {
    // Only what the subprojects {} block already added to every project, expressed via the catalog:
    // testImplementation libs.findLibrary('junit-jupiter').get()
}
```

`build-logic/src/main/groovy/library-conventions.gradle`
```groovy
plugins {
    id 'java-conventions'
    id 'java-library'
    // id 'maven-publish'   // only if the subprojects being migrated already apply it
}
```

`build-logic/src/main/groovy/application-conventions.gradle`
```groovy
plugins {
    id 'java-conventions'
    id 'application'
}
```

Root `settings.gradle`: `pluginManagement { includeBuild 'build-logic' }` — as the first block.
Subproject `build.gradle`: `plugins { id 'library-conventions' }` (or `application-conventions`).

Verification for Part A: check task origins where provenance is supported, then follow `verification.md` for task membership/outcomes, fresh test identities, dependencies, variants and publication metadata. Explain new build-logic compilation tasks separately; no product test task may disappear.

### Part B — optional policy upgrades (each is its own approval item)

| Option | Snippet (in `java-conventions.gradle`) | What changes / verify |
|---|---|---|
| Toolchain instead of `sourceCompatibility` | `java { toolchain { languageVersion = JavaLanguageVersion.of(N) } }` | Compiles with a provisioned JDK N rather than `JAVA_HOME`; needs `foojay-resolver-convention` in settings for auto-provisioning. Verify CI has/gets that JDK. |
| Raise Java target | `JavaLanguageVersion.of(21)` + `options.release = 21` | Bytecode level changes; consumers on older JVMs break. Product decision. |
| Compiler strictness | `options.compilerArgs.addAll(['-Xlint:all', '-Werror'])` | Existing warnings become build failures. Run first without `-Werror` and count. |
| JUnit Platform | `useJUnitPlatform()` + `junit-platform-launcher` runtimeOnly | JUnit 4 tests need the vintage engine or migration; test count must not drop. |
| Test parallelism | `maxParallelForks = Runtime.runtime.availableProcessors().intdiv(2) ?: 1` | Exposes shared-state/port/temp-dir conflicts. Run the full suite several times. |
| Sources/Javadoc jars | `java { withSourcesJar(); withJavadocJar() }` | New artifacts published; Javadoc errors fail the build. |
| UTF-8 everywhere (P1) | `options.encoding = 'UTF-8'`; `systemProperty 'file.encoding','UTF-8'` in tests | Safe if sources are already UTF-8; otherwise garbled resources. |
