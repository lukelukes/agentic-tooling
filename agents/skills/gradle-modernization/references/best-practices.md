# Gradle Best Practices: Audit Checklist (Groovy DSL)

Source: https://docs.gradle.org/9.7.1/userguide/best_practices_index.html (44 practices). Each entry has the official title, the Gradle version that added it to the guide, **Detect**, **Fix** in Groovy DSL, and a risk rating. These practices depend on context. They are not 44 mandatory rewrites.

Examine every entry during a full audit. Mark each entry: ✅ followed · ❌ violated (evidence and applicability confirmed) · ➖ not applicable · ❓ not checked · ⚠ suspected. Static absence, an unreadable file or an unexecuted plugin is not proof of a violation. Optional naming or structure preferences do not have the same rank as security or build blockers.

## Contents

- [General](#general) (9)
- [Structuring Builds](#structuring) (5)
- [Dependencies](#dependencies) (9)
- [Tasks](#tasks) (11)
- [Performance](#performance) (5)
- [Security](#security) (4)
- [Testing](#testing) (1)
- [Companion recommendations: dependency locking, consistent resolution, Mockito agent](#companions)
- [Version catalog cheat sheet](#catalog)
- [Convention plugin skeleton](#conventions)

---

<a id="general"></a>
## General

### G1. Use Kotlin DSL (added 8.14)
**Out of scope for this skill.** The user decision is Groovy DSL only. Mention it one time in the report under "Not applied". Do not recommend it.

### G2. Use the Latest Minor Version of Gradle (added 8.14)
**Detect:** Compare `distributionUrl` in `gradle/wrapper/gradle-wrapper.properties` with the current latest release. The latest release is 9.7.1 as of September 2026. Check https://gradle.org/releases/. Also flag `.0` releases that have a `.1` patch: 9.2.1, 9.3.1, 9.4.1, 9.6.1, 9.7.1.
**Fix:** Follow the wrapper upgrade sequence in SKILL.md. Use an exact compatible target version and its distribution checksum. Run the wrapper task two times. Then run `./gradlew help --warning-mode=all` and the verification workload.
**Risk:** Depends on the plugins, also inside 9.x, because incubating APIs can change. Medium to High for 8.x to 9.x: JDK 17 daemon, Groovy 4, reproducible archives, removed APIs. Read `gradle-9x-features.md` §9.0.0.

### G3. Apply Plugins Using the plugins Block (added 8.14)
**Detect:** `apply plugin: 'java'`, `apply plugin: JavaPlugin`, `buildscript { dependencies { classpath '...' } }` used only to load plugins, `apply from: 'x.gradle'` scripts that apply plugins.
**Fix:**
```groovy
plugins {
    id 'java-library'
    alias(libs.plugins.spotless)     // third-party plugin from the catalog
}
```
Put third-party plugin versions in `libs.versions.toml` under `[plugins]`. Put plugin repositories in `settings.gradle` under `pluginManagement { repositories { gradlePluginPortal() } }`.
**Risk:** Low to Medium. Conditional application and script plugins can need convention extraction instead of a syntax change. A project `plugins {}` block has order restrictions. You cannot insert it into an applied script plugin. Keep the application order and the plugin versions.

### G4. Do Not Use Internal APIs (added 8.14)
**Detect:** Imports or references to `org.gradle.internal.*`, `org.gradle.api.internal.*`, `org.gradle.util.*` (most of it removed in 9.0), casts to `*Internal` types, `DefaultXxx` classes.
**Fix:** Replace each usage with the public equivalent. If there is no public equivalent, isolate the usage in one place in `build-logic/` and add a comment. Common replacements: `GUtil.toCamelCase` becomes your own helper; `ConfigureUtil.configure` becomes `Action<T>`; `ProjectInternal.getServices()` becomes `@Inject` service injection.
**Risk:** Medium. The replacement can behave differently.

### G5. Set build flags in gradle.properties (added 9.0.0)
**Detect:** `org.gradle.*` flags in shell scripts, `GRADLE_OPTS`, edited `gradlew` scripts, or `-D`/`--` flags in README instructions, and not in the root `gradle.properties`.
**Fix:** Keep the existing values. Centralize the flags that the build already uses. Example settings follow. Do not paste them as a bundle.
```properties
org.gradle.caching=true
org.gradle.configuration-cache=true
org.gradle.parallel=true
org.gradle.jvmargs=-Xmx2g -Dfile.encoding=UTF-8
```
Put machine-specific overrides in `~/.gradle/gradle.properties`, outside version control. Enable the configuration cache only after the store and reuse check. Offer parallelism, heap and encoding changes as separate items.
**Risk:** Low if you move equivalent settings. Medium if you change execution, cache or encoding policy.

### G6. Name Your Root Project (added 9.2.0)
**Detect:** `settings.gradle` has no `rootProject.name = '...'`. Without it, the name is the directory name. The directory name is different between clones. This breaks build cache keys, published coordinates and IDE project names.
**Fix:** Add `rootProject.name = 'my-service'` to `settings.gradle`. Put it after `pluginManagement {}` and `plugins {}` if they exist, because those blocks must come first. Otherwise make it the first statement.
**Risk:** Low. Check `archivesName` and publication artifact IDs that can depend on the directory name.

### G7. Do not use gradle.properties in subprojects (added 9.2.0)
**Detect:** A `gradle.properties` file in a declared subproject, relative to its owner build. Root properties of `buildSrc` and included builds are correct. Unrelated fixtures and external builds are not subprojects. Check if a script loads the file on purpose.
**Fix:** Move the values to the root properties of the owner build or to a convention plugin extension. Keep the overrides and the existing consumers. Then delete the obsolete files.
**Risk:** Low to Medium. Make sure that no subproject reads the values through `project.findProperty`.

### G8. Avoid afterEvaluate (added 9.6.0)
**Detect:** `afterEvaluate {`, `project.afterEvaluate`, `gradle.projectsEvaluated`.
**Fix:** The fix depends on the reason for the block:
- Reaction to an applied plugin: use `plugins.withId('java') { ... }` or `pluginManager.withPlugin(...)`.
- Read of a value that is set later: use `Property<T>` or `Provider<T>` and connect it lazily, for example `task.foo = extension.bar`. Do not call `.get()` at configuration time.
- Configuration of all tasks of one type: use `tasks.withType(Test).configureEach { ... }`.
- Configuration after an extension is populated: use `extension.items.all { ... }` or `configureEach`.
**Risk:** Medium. The order semantics change. Run the build after each removal.

### G9. Consider use of @Incubating APIs carefully (added 9.7.0)
**Detect:** `[Incubating]` warnings in the build output, or `--warning-mode=all` lists incubating features. Examples: `testing.suites`, `dependencyResolutionManagement.repositories` (incubating but recommended by the docs), Isolated Projects.
**Fix:** No automatic fix. In the report, list the incubating features that the build uses. Note that they can change between 9.x minor releases, because SemVer covers only stable APIs. Prefer stable alternatives in shared build logic.
**Risk:** Not applicable. Advisory.

---

<a id="structuring"></a>
## Structuring Builds

### S1. Modularize Your Builds (added 9.0.0)
**Detect:** A single-project build with several different concerns, for example `src/main/java/com/x/{api,persistence,web,cli}`. One large project with feature-flag source sets. Very large `build.gradle` files (more than 150 lines) that do many things.
**Fix:** Advisory unless the user asks. Describe a split, for example `:api`, `:core`, `:app`. Note that a split enables parallel compilation, build cache reuse and clearer dependencies. Source moves are out of scope for this skill. Propose them. Do not execute them.
**Risk:** High. Source moves.

### S2. Do Not Put Source Files in the Root Project (added 9.0.0)
**Detect:** A multi-project build where the root has `src/main/**` or applies `java`. The root must hold only `settings.gradle`, `gradle.properties`, `gradle/`, and an optional minimal `build.gradle`.
**Fix:** Advisory. Propose a move of the root sources into a subproject, for example `:app`, and removal of `java` from the root `build.gradle`. Do not move sources.
**Risk:** High. Source moves. Publication coordinates change.

### S3. Favor build-logic Composite Builds for Build Logic (added 9.0.0)
**Detect:** A `buildSrc/` directory. `buildSrc` is on the classpath of every project. Each change invalidates the classpath of the whole build and disables configuration cache reuse more often. An included `build-logic` build behaves like a normal plugin dependency.
**Fix:**
```
build-logic/
  settings.gradle          -> rootProject.name = 'build-logic'; dependencyResolutionManagement { repositories { gradlePluginPortal(); mavenCentral() } }
  build.gradle             -> plugins { id 'groovy-gradle-plugin' }
  src/main/groovy/*.gradle -> precompiled script plugins
```
Add `pluginManagement { includeBuild 'build-logic' }` to the root `settings.gradle`. Move `buildSrc/src/main/groovy/*.gradle` without changes. Binary plugin classes need `gradlePlugin { plugins { register(...) } }` in `build-logic/build.gradle`. If `build-logic` needs the version catalog, add `versionCatalogs { libs { from(files('../gradle/libs.versions.toml')) } }` to its settings.
**Risk:** Medium. Existing `buildSrc` builds work. Migrate only together with S5, or when `buildSrc` changes slow down the team.

### S4. Avoid Unintentionally Creating Empty Projects (added 9.1.0)
**Detect:** `include 'services:payment'` (nested path) without a `project(':services').projectDir` mapping creates an empty `:services` project. Also included directories with no `build.gradle`. Check `./gradlew projects`. From 9.1 it shows the locations.
**Fix:** Use flat project names with explicit directories:
```groovy
include 'payment'
project(':payment').projectDir = file('services/payment')
```
If the hierarchy is wanted, make sure that the intermediate projects are intentional and do not apply `java`.
**Risk:** Low to Medium. Project paths change. Update `project(':services:payment')` references and documented task paths.

### S5. Use Convention Plugins (added 9.3.0)
**Detect:** `subprojects {}` or `allprojects {}` blocks that configure plugins, dependencies or tasks. `apply from: "$rootDir/gradle/java.gradle"`. The same 20 lines in every `build.gradle`. `configure(subprojects.findAll { ... })`.
**Fix:** Use the [behavior-preserving skeleton](#conventions) as the only extraction recipe. Copy only the existing plugins, Java settings, compiler flags, test framework, dependencies and parallelism. Do not add JUnit Platform, Java 21 or publishing as part of the extraction. For each subproject, remove its old configuration when you enable its convention plugin, so that it is not configured two times. Delete the old shared block only after all its consumers are migrated. Use task provenance (9.5+) to confirm the origin of tasks. Use the verification protocol to compare the behavior.
**Risk:** Medium. Migrate one subproject at a time. Run the verification workload after each. Measure the configuration time if performance is the reason for the extraction.

---

<a id="dependencies"></a>
## Dependencies

### D1. Single GAV String (added 8.14)
**Detect:** `implementation group: 'x', name: 'y', version: 'z'` (named-argument notation). **Deprecated. Removed in Gradle 10.**
**Fix:** `implementation 'x:y:z'`, or a catalog alias (D2). `exclude group: ..., module: ...` inside the closure is correct and stays in map form.
**Risk:** Low. Syntax only.

### D2. Use Version Catalogs to Centralize Dependency Versions (added 9.0.0)
**Detect:** Examine the default, named, imported, published and programmatic catalogs, including settings plugins. Remaining dependency literals and shared version variables are migration candidates. They are not proof of an invalid build.
**Fix:** See the [Version catalog cheat sheet](#catalog). Keep the existing architecture. Migrate in steps. Keep `project(':x')`, `platform(...)`, `enforcedPlatform(...)` and all declaration-site semantics. The BOM itself can become a catalog entry. Do not put non-dependency strings in the catalog.
**Risk:** Low for simple coordinates. Medium for rich versions and variants. A partial migration with documented exceptions is valid. Correctness has a higher rank than removal of every GAV string.

### D3. Name Version Catalog Entries Appropriately (added 9.0.0)
**Detect:** Aliases such as `junit_jupiter`, `org-apache-commons-lang3`, `ktor-ktor-client`, `spring-boot-starter-web` (dashes inside artifact IDs), `core`, `sdk`, and plugin libraries without the `-plugin` suffix.
**Fix:** Apply the rules from the docs:
1. Dashes separate segments. Segments become dots in scripts: `libs.jackson.databind`.
2. The first segment comes from the group, without the TLD: `com.fasterxml.jackson.core` becomes `jackson`.
3. The second segment comes from the artifact ID: `armeria-grpc` stays `armeria-grpc`.
4. Remove generic terms that stand alone: `core`, `java`, `gradle`, `module`, `sdk`.
5. Do not repeat words: `io.ktor:ktor-client-core` becomes `ktor-client-core`, not `ktor-ktor-client-core`.
6. Dashes inside an artifact ID become camelCase: `spring-boot-starter-web` becomes `springBootStarterWeb`. In scripts: `libs.spring.bootStarterWeb` or `libs.springBootStarterWeb`.
7. Plugins referenced as libraries get `-plugin`: `dependency-check-plugin`.
Examples: `jackson-databind`, `jackson-dataformatCsv`, `slf4j-api`, `junit-jupiter`. `assertj-core` becomes `assertj` (rule 4).
**Risk:** Low. Rename the aliases and the references together.

### D4. Set up your Dependency Repositories in the Settings file (added 9.0.0)
**Detect:** Project dependency repositories, including `allprojects { repositories { ... } }`. First identify the four scopes: project dependencies, `pluginManagement`, `buildscript` and `publishing`. The last three are not interchangeable with `dependencyResolutionManagement`.
**Fix:** In `settings.gradle`:
```groovy
pluginManagement {
    repositories { gradlePluginPortal(); mavenCentral() }
}
dependencyResolutionManagement {
    repositoriesMode = RepositoriesMode.FAIL_ON_PROJECT_REPOS
    repositories { mavenCentral() }
}
```
Remove only the equivalent project dependency repository blocks. Keep the repository order, credentials, content filters and metadata policies. Keep publishing destinations in `publishing.repositories`. Keep buildscript repositories until their classpath consumers are migrated. Plugin resolution uses `pluginManagement.repositories`. Each included build has its own settings. `FAIL_ON_PROJECT_REPOS` is an enforcement decision to offer. It is not a mechanical move.
**Risk:** Medium. A lost repository scope, order or filter can change the artifact provenance with identical versions. Compare the dependency artifacts and the publication destinations separately.

### D5. Don't Explicitly Depend on the Kotlin Standard Library (added 9.0.0)
**Detect:** `implementation 'org.jetbrains.kotlin:kotlin-stdlib...'` in a project that applies a Kotlin plugin.
**Fix:** Remove the line. The Kotlin plugin adds it. Mark ➖ for pure Java projects.
**Risk:** Low.

### D6. Avoid Redundant Dependency Declarations (added 9.0.0)
**Detect:** The same coordinates declared in two configurations of one project: `api` and `implementation`, `compileOnly` and `implementation`, `implementation` and `testImplementation`. The same dependency in a subproject and in the convention plugin that it applies.
**Fix:** Keep the widest correct configuration. For the test classpath, `api` contains `implementation`, and `implementation` contains `testImplementation`. `compileOnly` together with `implementation` is usually an error. Select one.
**Risk:** Low to Medium. The classpath scope changes. Run the tests.

### D7. Use Content Filtering with multiple Repositories (added 9.1.0)
**Detect:** Two or more repositories in `dependencyResolutionManagement.repositories` without `content { }` or `exclusiveContent { }`. Common example: `mavenCentral()` plus a corporate Nexus or Artifactory, `google()`, JitPack and `mavenLocal()`.
**Fix:**
```groovy
dependencyResolutionManagement {
    repositories {
        exclusiveContent {
            forRepository { maven { url = uri('https://repo.example.com/internal') } }
            filter { includeGroupByRegex 'com\\.example(\\..*)?' }
        }
        mavenCentral()   // unfiltered fallback, last
    }
}
```
Prefer `exclusiveContent`. Then the dependency can come only from that repository. Put the unfiltered fallback last. Make sure that the fallback is trusted. Remove `mavenLocal()` or filter it to specific groups.
**Risk:** Medium. A wrong filter makes the resolution fail. The failure is visible. Run `./gradlew dependencies` after the change.

### D8. Apply Exclusions Narrowly (added 9.2.0)
**Detect:** `configurations.all { exclude ... }`, `configurations.configureEach { exclude ... }`, `configurations.implementation { exclude group: 'x' }` (whole configuration), `exclude group: 'x'` without `module:` (whole group).
**Fix:** Move each exclusion onto the specific dependency that brings the unwanted transitive dependency. Name the module:
```groovy
implementation(libs.hibernate.core) {
    exclude group: 'javassist', module: 'javassist'
}
```
Use `./gradlew dependencyInsight --dependency javassist --configuration runtimeClasspath` to find the direct dependency that brings it. If the goal is "this library must not be on the classpath", use `constraints { implementation('x:y') { version { rejectAll() } } }` or a capability conflict. These are more explicit than a global exclude.
**Risk:** Medium. A global exclude can hide several paths. After you narrow it, check `dependencies --configuration runtimeClasspath` again.

### D9. Always Declare Attributes on Consumable and Resolvable Configurations (added 9.7.0)
**Detect:** `configurations.consumable('x')`, `configurations.resolvable('x')` or `configurations.create('x') { canBeConsumed = true }` with no `attributes { }` block. Project dependencies that use `project(path: ':p', configuration: 'x')`.
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
Declare the same attributes on the `resolvable` configuration of the consumer. Depend on `project(':producer')` without a configuration name.
**Risk:** Medium. Custom cross-project wiring. Mark ➖ for builds with no custom configurations.

---

<a id="tasks"></a>
## Tasks

### T1. Avoid DependsOn (added 8.14)
**Detect:** `dependsOn` used to run task B after task A because B consumes the output of A. Lifecycle wiring such as `check.dependsOn integrationTest` is correct.
**Fix:** Connect the output as an input. Gradle then infers the dependency:
```groovy
def gen = tasks.register('generateDocs', GenerateDocs) { outputDir = layout.buildDirectory.dir('docs') }
tasks.register('packageDocs', Zip) { from(gen) }          // task dependency inferred
// or: from(gen.flatMap { it.outputDir }) when outputDir is a DirectoryProperty
```
**Risk:** Low to Medium.

### T2. Favor @CacheableTask and @DisableCachingByDefault over cacheIf/doNotCacheIf (added 8.14)
**Detect:** `outputs.cacheIf { true }` or `outputs.doNotCacheIf(...)` in build scripts on custom task types. Custom task classes with neither annotation.
**Fix:** On the task class, add `@CacheableTask` with `@PathSensitive` on every file input, or `@DisableCachingByDefault(because = '...')`. Keep `cacheIf` only for decisions that differ per instance.
**Risk:** Low. Mark ➖ if there are no custom task types.

### T3. Group and Describe custom Tasks (added 9.0.0)
**Detect:** `tasks.register('foo')` without `group` and `description`. Tasks listed under "Other tasks" in `./gradlew tasks --all`.
**Fix:** `tasks.register('foo') { group = 'verification'; description = 'Runs the contract tests.' }`. Use the standard group names `build`, `verification`, `documentation`, `publishing`, `help`, or a project-specific name.
**Risk:** Low.

### T4. Do not call get() on a Provider outside a Task action (added 9.1.0)
**Detect:** `.get()`, `.getOrElse()` or `.getAsFile()` on `Property`, `Provider` or `NamedDomainObjectProvider` at the script top level, or inside a `tasks.register { }` configuration block outside `doFirst` and `doLast`. Also `tasks.named('x').get()` and `configurations.foo.get()`.
**Fix:** Pass the provider through: `outputFile = otherTask.flatMap { it.outputFile }`, `from(provider)`, `inputs.files(provider)`. Inside `doLast`, `.get()` is correct.
**Risk:** Low to Medium.

### T5. Don't resolve Configurations before Task Execution (added 9.1.0)
**Detect:** `configurations.runtimeClasspath.files`, `.resolve()`, `.resolvedConfiguration`, `.asPath` or `.each { }` at configuration time. Configuration time includes the top level, the body of `tasks.register { }` and `afterEvaluate`.
**Fix:** Declare the configuration as a task input. Read it in the action. `classpath = configurations.runtimeClasspath` is lazy, because a `FileCollection` is lazy. Then read `classpath.files` inside `doLast`. For custom tasks, use `@Classpath abstract ConfigurableFileCollection getRuntimeClasspath()`.
**Risk:** Medium. The fix is usually simple, but it shows hidden order assumptions.

### T6. Avoid using eager APIs on File Collections (added 9.1.0)
**Detect:** A file collection that is materialized or iterated at configuration time through `.files`, `.asPath`, `.iterator()`, `.each` or `.collect`. `fileCollection.filter {}` returns a live collection. `fileCollection.files.findAll {}` materializes first.
**Fix:** Keep the collection lazy. Let the task consume it. Use `.elements` for a provider, `FileCollection.filter {}` for a live filtered collection, or `FileTree.matching { include ... }` for tree patterns. See the [9.7.1 FileCollection API](https://docs.gradle.org/9.7.1/javadoc/org/gradle/api/file/FileCollection.html).
**Risk:** Low to Medium.

### T7. Prefer @PathSensitivity.NONE for file inputs and @PathSensitivity.RELATIVE for directories (added 9.2.0)
**Detect:** Custom task classes with `@InputFile`, `@InputFiles` or `@InputDirectory` without `@PathSensitive`, or with `ABSOLUTE`. `ABSOLUTE` gives no cache hits across checkouts or machines.
**Fix:** Use `@PathSensitive(PathSensitivity.NONE) @InputFile` for single files where only the content matters. Use `@PathSensitive(PathSensitivity.RELATIVE) @InputDirectory` or `@InputFiles` for trees where the relative layout matters. Use `NAME_ONLY` when the file name matters, for example resource bundles.
**Risk:** Low. Mark ➖ if there are no custom task types.

### T8. Use unique output files and directories (added 9.3.0)
**Detect:** Two tasks that write into the same `layout.buildDirectory.dir('generated')`. Tasks with `outputs.dir(buildDir)`. Overlapping output warnings in build cache diagnostics.
**Fix:** Use one output location per task, named after the task: `layout.buildDirectory.dir("generated/sources/${name}")`. Do not use the project build directory or a shared parent directory as a task output.
**Risk:** Low to Medium. Downstream consumers must point to the new location. Connect them with providers, not with strings.

### T9. Don't hardcode task names when referring to them (added 9.7.0)
**Detect:** `tasks.named('compileJava')` is correct, because the name is a documented public name. `tasks.named('generateFooSources')` for an undocumented task of a third-party plugin is not. `dependsOn 'someInternalTask'` strings that point to plugin internals are not.
**Fix:** Depend on the documented extension of the plugin or on the outputs of the task, for example `sourceSets.main.output` or `tasks.withType(SomePluginTask)`. Or use `tasks.withType(X).configureEach`. Keep name references only for names that the plugin documents as API: `compileJava`, `test`, `jar`, `assemble`, `check`, `build`, `javadoc`, `publish*`.
**Risk:** Low.

### T10. Don't access a Project instance during Task Execution (added 9.7.0)
**Detect:** `project.` inside `doLast`, `doFirst` or `@TaskAction`. Examples: `project.copy { }`, `project.exec { }`, `project.file(...)`, `project.version`, `project.buildDir`, `project.logger`. Use `logger` instead of `project.logger`. The configuration cache fails on these.
**Fix:** Inject public services into a task class: `@Inject abstract FileSystemOperations getFs()` for copy, delete and sync; `@Inject abstract ExecOperations getExecOps()`; `@Inject abstract ProjectLayout getLayout()`; `@Inject abstract ArchiveOperations getArchives()`. Capture simple configuration values before the action. Declare them as task inputs if they change the output. Move actions that use services into task classes in build logic. Do not use internal `project.services` access as a shortcut.
**Risk:** Medium. This is most of the configuration cache migration work.

### T11. Wiring Task Outputs with map and flatMap (added 9.7.0)
**Detect:** `outputFile = otherTask.get().outputFile`. `from(otherTask.get().outputs)`. `other.map { it.outputFile }` makes a nested provider when `outputFile` is a property. Check the result type and the producer wiring. Do not assume that every `map` loses the dependency.
**Fix:** Use `flatMap` when the mapped value is a `Provider` or `Property`: `inputFile = other.flatMap { it.outputFile }`. Use `map` when the result is a plain value. `archiveName = other.map { it.archiveFileName.get() }` is wrong. Use `flatMap { it.archiveFileName }`. Rule: `flatMap` for `Property` and `Provider` results, `map` for plain values.
**Risk:** Low.

---

<a id="performance"></a>
## Performance

### P1. Enable UTF-8 (added 9.0.0)
**Detect:** `org.gradle.jvmargs` without `-Dfile.encoding=UTF-8`. `JavaCompile` tasks without `options.encoding = 'UTF-8'`. `Javadoc` without `options.encoding`.
**Fix:** In `gradle.properties`: `org.gradle.jvmargs=-Xmx2g -Dfile.encoding=UTF-8`. In the convention plugin: `tasks.withType(JavaCompile).configureEach { options.encoding = 'UTF-8' }`, `tasks.withType(Javadoc).configureEach { options.encoding = 'UTF-8' }`, `tasks.withType(Test).configureEach { systemProperty 'file.encoding', 'UTF-8' }`. On JDK 18+ the default is UTF-8 (JEP 400). The Gradle daemon JVM and older toolchains can be different.
**Risk:** Low.

### P2. Use the Build Cache (added 9.1.0)
**Detect:** `org.gradle.caching` absent or `false`.
**Fix:** Offer `org.gradle.caching=true` after you check the correctness of the custom tasks: declared inputs and outputs, no absolute-path inputs. The remote cache push policy is a separate decision. Keep the existing read and write policy and the fork PR restrictions.
**Risk:** Low. Custom tasks with `ABSOLUTE` path sensitivity or undeclared inputs can give stale results. Audit T7 and T8 first.

### P3. Use the Configuration Cache (added 9.1.0)
**Detect:** `org.gradle.configuration-cache` absent or `false`. The build prints the "Configuration cache is not enabled…" prompt (9.0+).
**Fix:** Follow `verification.md`: a baseline in the existing mode, then two identical strict configuration cache runs with real task execution on the verification workload. Fix the reported problems. Then enable the property only for the workload that passed. Warn mode can help with diagnosis, but it is not verification. Mark incompatible tasks with `notCompatibleWithConfigurationCache('reason')`. Report the workloads that cannot store or reuse. Graceful fallback is not cache compatibility.
**Risk:** Medium. Each problem needs its own fix. The usual causes are T10 (Project in an action), T5 (eager resolution), or a plugin that needs an upgrade.

### P4. Avoid Expensive Computations in Configuration Phase (added 9.0.0)
**Detect:** Top-level script code, outside a task, that runs `git` (`'git rev-parse HEAD'.execute()`), reads or parses files, walks directories, does network I/O, or loops over `subprojects` to compute values.
**Fix:** Move the code into a task or a `ValueSource`:
```groovy
abstract class GitHash implements ValueSource<String, ValueSourceParameters.None> {
    @Inject abstract ExecOperations getExecOps()
    String obtain() { def out = new ByteArrayOutputStream(); execOps.exec { commandLine 'git','rev-parse','--short','HEAD'; standardOutput = out }; out.toString().trim() }
}
def gitHash = providers.of(GitHash) {}
tasks.named('jar', Jar) { manifest { attributes('Git-Hash': gitHash) } }   // provider, resolved at execution
```
`ValueSource` results are compatible with the configuration cache and are tracked as build inputs.
**Risk:** Low to Medium.

### P5. Prefer the -bin Gradle Distribution (added 9.4.0)
**Detect:** `distributionUrl=…-all.zip`. The `-all` distribution includes sources and docs. It is about 3 times larger. IDEs do not need it.
**Fix:** `./gradlew wrapper --gradle-version=9.7.1 --distribution-type=bin`. Update `distributionSha256Sum` (see Sec1).
**Risk:** Low.

---

<a id="security"></a>
## Security

### Sec1. Validate the Gradle Distribution SHA-256 Checksum (added 9.1.0)
**Detect:** `gradle-wrapper.properties` has no `distributionSha256Sum`.
**Fix:** `./gradlew wrapper --gradle-version=9.7.1 --gradle-distribution-sha256-sum=<sha>`. Get `<sha>` from https://gradle.org/release-checksums/. Do this again on every wrapper upgrade.
**Risk:** Low.

### Sec2. Validate the Gradle Wrapper on every Upgrade (added 9.3.0, updated 9.6.0)
**Detect:** `gradle-wrapper.jar` committed without verification. The scanner does not check this. Pipeline configuration is out of scope.
**Fix:** Compare `sha256sum gradle/wrapper/gradle-wrapper.jar` with the wrapper jar checksum at https://gradle.org/release-checksums/. After `./gradlew wrapper`, run the wrapper task a second time, so that the new Gradle regenerates the jar.
**Risk:** Low.

### Sec3. Do not Run ./gradlew on Untrusted Projects (added 9.7.0)
**Detect:** Advisory. This skill does not check it. Pipeline configuration is out of scope. Mark it ➖.
**Fix:** `settings.gradle`, `buildSrc`, included builds and plugins execute arbitrary code on each invocation, including `help`. Do not run `./gradlew` on untrusted changes with access to secrets. Wrapper validation (Sec2) covers only a modified wrapper jar. It does not cover build logic.
**Risk:** Not applicable.

### Sec4. Build Output Should Be Byte-for-Byte Reproducible (added 9.7.0)
**Detect:** Archives with timestamps (the default before 9.0). `Manifest` attributes with `new Date()` or `Built-By: ${System.getProperty('user.name')}`. Generated sources that contain the build time. `buildTime` in `application.properties`.
**Fix:** From 9.0, archives are reproducible by default. Remove volatile manifest attributes. If a timestamp is required, use `SOURCE_DATE_EPOCH` through `reproducibleFileTimestamp` (9.7.0). Check the result with outputs that are generated independently: run `./gradlew clean assemble --no-build-cache --rerun-tasks` in two separate clean checkouts, or in the same checkout with `build/` deleted between the runs. Compare `sha256sum build/libs/*.jar`. A comparison of an up-to-date or cache-restored artifact with itself is not proof.
**Risk:** Low.

---

<a id="testing"></a>
## Testing

### Te1. Test your custom Task and Plugins with TestKit (added 9.4.0)
**Detect:** `build-logic/` or `buildSrc/` with non-trivial plugins or tasks, and no `src/test` or `src/functionalTest` that uses `org.gradle.testkit.runner.GradleRunner`.
**Fix:** Add TestKit fixtures to the build logic. Keep its current test framework. Run identical arguments two times with strict configuration cache, `--no-build-cache` and `--rerun-tasks`. Assert store, then reuse, the expected task outcomes and the outputs. One green TestKit run does not prove reuse. Test each claimed Gradle and JDK boundary and each known plugin constraint.
**Risk:** Low. Additive.

---

<a id="companions"></a>
## Companion recommendations (not in the official 44, but referenced by them)

The version catalog practice (D2) says that catalogs "only influence declared versions, not resolved versions". It says to combine them with **dependency locking** and **version alignment**. These two entries make that applicable. Treat them as recommended by reference. Do not score them as practices.

### C1. Lock resolved dependency versions (dependency locking)
**Why:** A catalog declares the requested versions, not the resolved graph. Locking records the resolved module versions. It is most useful for dynamic and range selectors. It does not make mutable artifacts byte-identical. Fixed immutable dependencies do not drift on each refresh. Dependency verification, artifact immutability and reproducible task outputs are complementary controls.
**Detect:** The scanner records the locking state per project in `facts.build_facts.<build>.locking` (`:path` to declared_in, activated, lockfile, entries). A `dependencyLocking {}` block that only sets `lockMode` locks nothing. It needs `lockAllConfigurations()` or `activateDependencyLocking()` per configuration. The scope matters. A top-level block in the root script covers only the root project. `allprojects {}` and `subprojects {}` cover all projects or all non-root projects. A convention plugin covers the projects that apply it. Every covered project needs its own `<project>/gradle.lockfile`, or the custom `lockFile`. With `LockMode.STRICT`, a missing lock file fails the resolution. Locking from plugins and custom lock locations are not visible statically. Changing dependencies such as `-SNAPSHOT` can change bytes without a change of coordinates. Locking does not solve that. Gradle warns when it persists them. See the [locking documentation](https://docs.gradle.org/9.7.1/userguide/dependency_locking.html).
**Fix (Groovy, in the convention plugin so that every subproject gets it):**
```groovy
dependencyLocking {
    lockAllConfigurations()
    lockMode = LockMode.DEFAULT           // bootstrap; use STRICT after every locked configuration has state
    // ignoredDependencies.add('com.example.internal:*')   // optional: never lock these
    // lockFile = layout.projectDirectory.file('gradle/gradle.lockfile')  // optional; default is <project>/gradle.lockfile
}
```
Lock the build logic too, in the root `build.gradle` or `build-logic`:
```groovy
buildscript {
    dependencyLocking { lockAllConfigurations() }   // writes buildscript-gradle.lockfile
}
```
Do not add a top-level `dependencyLocking {}` to `settings.gradle`. Do not promise a native `settings-gradle.lockfile`. Settings does not expose that project extension. Keep settings plugin versions explicit in `plugins` or `pluginManagement`. Plugin artifact verification is a separate concern. Buildscript classpath locking is a different scope from settings plugin management.

**Generate lock files (the first time, and each time you change dependencies on purpose):**
```bash
./gradlew dependencies --write-locks                  # resolves every lockable configuration in the invoked project
./gradlew resolveAndLockAll --write-locks             # if you define a task that resolves all configurations (see below); recommended in multi-project builds
./gradlew build --write-locks                         # any invocation that resolves the configurations works
```
Per-project task. Apply a convention plugin to each relevant project, or invoke the task of each project explicitly. A task defined only in the root does not resolve the subprojects:
```groovy
tasks.register('resolveAndLockAll') {
    notCompatibleWithConfigurationCache('resolves configurations at execution time to write lock files')
    doFirst { assert gradle.startParameter.writeDependencyLocks : 'run with --write-locks' }
    doLast {
        configurations.matching { it.canBeResolved }.each { it.resolve() }
    }
}
```
**Update selected modules:**
```bash
./gradlew dependencies --update-locks 'org.springframework:*,com.fasterxml.jackson.core:jackson-databind'
```
`--update-locks` unlocks the named modules for resolution. Trailing wildcards in group and module are supported. Resolution rules can also change other module versions. Review the whole lock file and dependency diff, not only the requested modules. See [selective lock updates](https://docs.gradle.org/9.7.1/userguide/dependency_locking.html#sec:selectively-updating-lock-state-entries).

**Lock file format.** One file per project. From Gradle 7 the single-file format is the default:
```
# This is a Gradle generated file for dependency locking.
# Manual edits can break the build and are not advised.
# This file is expected to be part of source control.
com.fasterxml.jackson.core:jackson-databind:2.19.2=compileClasspath,runtimeClasspath
org.slf4j:slf4j-api:2.0.17=compileClasspath,runtimeClasspath,testCompileClasspath,testRuntimeClasspath
empty=annotationProcessor
```
Commit the file. Do not edit it by hand. The `empty=` line lists the configurations that resolved to nothing. This is expected.

**Interactions:**
- Lock entries act like strict constraints. They can change the classpath order. Investigate order changes. Offer the 9.7.0 `ENHANCED_GRAPH_ORDERING` preview as a separate Gradle 10 experiment, not as an automatic fix.
- Locking works with the configuration cache and the build cache. Run `--write-locks` and `--update-locks` without configuration cache reuse, because they resolve at execution time.
- `LockMode.STRICT` with a missing lock file fails the build. Generate the lock files in the same change that enables locking. Or start with `DEFAULT`, commit the lock files, then change to `STRICT`.
- Dynamic versions in the catalog are still permitted. The lock file freezes their resolved versions. Prefer to remove them (D2).
- Dependency **verification** (`gradle/verification-metadata.xml`, checksums, PGP) is separate. Locking pins versions. Verification checks bytes and signatures. Generated metadata records what was downloaded. It is not proof that the download was trustworthy. Bootstrap it with a workload that resolves all relevant configurations. `help` alone does not have to resolve the application dependencies.
- Renovate supports `gradle.lockfile` maintenance (`lockFileMaintenance`). Check the support of your dependency bot first. Otherwise `--update-locks` is a manual PR step.
- IDE sync also resolves configurations. With STRICT mode, an out-of-date lock file breaks the IntelliJ import until you regenerate it. This is expected. Tell the team.

**Risk:** Low to enable. Medium for the process, because every dependency change now touches the lock file. This is the intent.

### C2. Align versions across classpaths (consistent resolution)
**Why:** Without it, `runtimeClasspath` can resolve a higher version of a library than `compileClasspath`, because a runtime-only dependency pulls it up. Then you compile against one version and run against another. This is the "version alignment" that the catalog practice refers to.
**Detect:** `./gradlew dependencies --configuration compileClasspath` and `runtimeClasspath` show different versions for the same module. No `consistentResolution` block.
**Fix (convention plugin):**
```groovy
java {
    consistentResolution {
        useCompileClasspathVersions()     // runtime resolves to the versions that compile selected
    }
}
```
For alignment across a family of modules, for example all Jackson artifacts at one version, use a **platform**: `implementation platform(libs.jackson.bom)`. For producers without a BOM, use a `ComponentMetadataRule` that declares a virtual platform.
**Risk:** Medium. Compile and runtime differences can be intentional. Investigate why runtime selected a higher version. Do not label every divergence as a defect. Do not force alignment without evidence.

### C3. Pass the Mockito agent explicitly on JDK 21 and above (prerequisite, applied before the baseline)
**Why:** Mockito's inline mock maker, the default since Mockito 5, needs a Java agent in the test JVM. Without `-javaagent` it self-attaches through the attach API at test runtime. JDK 21 prints `WARNING: A Java agent has been loaded dynamically` and Mockito prints `Mockito is currently self-attaching to enable the inline-mock-maker. This will no longer work in future releases of the JDK`. Sandboxed agents cannot self-attach at all, so every test that creates a mock fails, including the baseline of this skill. A future JDK disables dynamic loading by default (JEP 451). `-XX:+EnableDynamicAgentLoading` only hides the warning. It does not help in a sandbox.
**Detect:** `facts.build_facts.<build>.mockito` lists `declared_in` (`org.mockito:mockito-core`, `mockito-junit-jupiter`, `mockito-inline`, a `mockito` catalog alias or `spring-boot-starter-test`, which bundles Mockito) and `agent_in` (a `-javaagent` with Mockito, or a `mockitoAgent` configuration). Declared without an agent is the high finding `C3`. Dynamically: the two warnings above in the test output, or, in a sandbox, `Could not self-attach to current VM` in the Mockito stack trace of the failed tests.
**Fix (Groovy, per project that declares Mockito, or once in the convention plugin). Verified on Gradle 9.7.1, JDK 21, strict configuration-cache store and reuse:**
```groovy
configurations {
    mockitoAgent { transitive = false }        // the agent jar alone; byte-buddy stays on the test classpath as before
}

dependencies {
    // existing test dependencies unchanged
    mockitoAgent libs.mockito.core             // the same version source as testImplementation: catalog alias, or 'org.mockito:mockito-core:<version>'
}

abstract class JavaAgentArgument implements CommandLineArgumentProvider {
    @Classpath abstract ConfigurableFileCollection getAgent()
    @Override Iterable<String> asArguments() { ["-javaagent:${agent.asPath}".toString()] }
}

tasks.withType(Test).configureEach {
    jvmArgumentProviders.add(objects.newInstance(JavaAgentArgument).tap { agent.from(configurations.mockitoAgent) })
}
```
The provider resolves `mockitoAgent` at execution time and declares the jar as a `@Classpath` input of the Test task. The short form from the Mockito documentation also passes the strict pair. It resolves the configuration at configuration time (T5, P4):
```groovy
tasks.withType(Test).configureEach {
    jvmArgs += "-javaagent:${configurations.mockitoAgent.asPath}"
}
```
Do not use a Groovy closure: `jvmArgumentProviders.add({ [...] })` is not coerced to `CommandLineArgumentProvider` and fails at execution with `ClassCastException`, with or without the configuration cache. `({ ... } as CommandLineArgumentProvider)` runs without the cache but fails the strict pair with `invocation of 'configurations' references a Gradle script object from a Groovy closure at execution time`.
A version-less `mockitoAgent 'org.mockito:mockito-core'` resolves only when something supplies the version to that configuration, for example the Spring dependency-management plugin. A `platform()` on `testImplementation` does not cover `mockitoAgent`.
**Risk:** Low. The jar is the one already on the test classpath. The test output loses the two warnings. Nothing else changes. Test identities and outcomes must be equal before and after, except the tests that failed to self-attach in the sandbox.

<a id="catalog"></a>
## Version catalog cheat sheet (`gradle/libs.versions.toml`)

```toml
[versions]
jackson = "2.19.2"          # shared by several artifacts: use version.ref
junit = "5.13.4"
spring-boot = "3.5.4"

[libraries]
jackson-databind      = { module = "com.fasterxml.jackson.core:jackson-databind", version.ref = "jackson" }
jackson-dataformatCsv = { module = "com.fasterxml.jackson.dataformat:jackson-dataformat-csv", version.ref = "jackson" }
slf4j-api             = { module = "org.slf4j:slf4j-api", version = "2.0.17" }              # single use: inline version
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

Catalog TOML does **not** support classifiers, artifact types, excludes or capability requirements. Keep the declaration-site semantics. Rich version fields such as `strictly` and `prefer` are supported. Example for an existing dependency with a classifier. This is not a new dependency to add:

```groovy
dependencies {
    implementation(variantOf(libs.my.lib) { classifier('test-fixtures') })
}
```

Keep the existing `artifact {}`, `attributes {}`, `capabilities {}`, exclusion and platform wrappers when you replace coordinates. See the [official catalog limitations](https://docs.gradle.org/9.7.1/userguide/version_catalogs.html#sec:toml-limitations).

Migration procedure:
1. Run `grep -rn --include=build.gradle -E "['\"][A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+:[^'\"]+['\"]" .` to list every GAV literal. Also grep for `ext {`, `Version =` and `version:`.
2. Build the `[versions]`, `[libraries]` and `[plugins]` tables. Use `version.ref` where two or more artifacts share a version.
3. Replace each literal with the alias. Groovy: `implementation libs.foo.bar` without parentheses, or `implementation(libs.foo.bar) { exclude ... }`.
4. Remove the `ext` and `def` version variables that are no longer used. Remove the `buildscript { dependencies { classpath } }` entries that became `[plugins]`.
5. Compare the relevant compile, runtime, test and processor configurations, the selected artifacts and the publication metadata with `verification.md`. Equal resolved versions are necessary but not sufficient.

Reserved aliases include `extensions`, `class` and `convention`. `bundles`, `versions` and `plugins` cannot be the first subgroup in dependency aliases. Underscores are valid. Dashes and camelCase are naming preferences, not correctness requirements. Keep public catalog aliases unless the user wants a rename. Check for collisions in the generated accessors.

To share a catalog with `build-logic/`, add this to `build-logic/settings.gradle`:
```groovy
dependencyResolutionManagement {
    versionCatalogs { libs { from(files('../gradle/libs.versions.toml')) } }
}
```
In precompiled Groovy script plugins the accessor is not type-safe. Use `def libs = project.extensions.getByType(VersionCatalogsExtension).named('libs')` and `libs.findLibrary('junit-jupiter').get()`.

<a id="conventions"></a>
## Convention plugin skeleton (Groovy, build-logic)

Two parts. **Part A** is behavior-preserving extraction. It reproduces what a typical `subprojects {}` block already does. Take every value from the existing build. Placeholders are in `<>`. **Part B** lists policy upgrades that change behavior. Each one is a separate approval item.

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
    // Only for third-party plugins that the convention scripts apply. Declare them as
    // libraries in the catalog with a -plugin suffix (rule D3.7), for example:
    //   [libraries] spotless-plugin = { module = "com.diffplug.spotless:spotless-plugin-gradle", version.ref = "spotless" }
    // implementation libs.spotless.plugin
}
```

### Part A: behavior-preserving base

`build-logic/src/main/groovy/java-conventions.gradle`. Copy the values from the existing build. Do not change them here:
```groovy
plugins { id 'java' }

// Only if the existing shared logic uses a catalog:
// def libs = project.extensions.getByType(VersionCatalogsExtension).named('libs')

// Copy the existing java {} settings without changes. If there is no toolchain, do not
// add one: source/target compatibility and the compiler JDK are different things.
// Keep options.release as it is. Omit settings that were not present.

tasks.withType(JavaCompile).configureEach {
    // options.encoding = <existing explicit setting, otherwise omit>
    // options.compilerArgs = <copy the existing list without changes, or omit>
}
tasks.withType(Test).configureEach {
    // Copy the existing useJUnitPlatform()/useJUnit()/useTestNG() setup, or omit.
    // maxParallelForks / forkEvery / jvmArgs: copy the existing values or omit
}
dependencies {
    // Only what the subprojects {} block already added to every project, through the catalog:
    // testImplementation libs.findLibrary('junit-jupiter').get()
}
```

`build-logic/src/main/groovy/library-conventions.gradle`
```groovy
plugins {
    id 'java-conventions'
    id 'java-library'
    // id 'maven-publish'   // only if the migrated subprojects already apply it
}
```

`build-logic/src/main/groovy/application-conventions.gradle`
```groovy
plugins {
    id 'java-conventions'
    id 'application'
}
```

Root `settings.gradle`: add `pluginManagement { includeBuild 'build-logic' }` as the first block.
Subproject `build.gradle`: add `plugins { id 'library-conventions' }` or `plugins { id 'application-conventions' }`.

Verification for Part A: check the task origins where provenance is supported. Then follow `verification.md` for task membership and outcomes, fresh test identities, dependencies, variants and publication metadata. Explain new build-logic compilation tasks separately. No product test task may disappear.

### Part B: optional policy upgrades

| Option | Snippet (in `java-conventions.gradle`) | What changes / what to check |
|---|---|---|
| Toolchain, not `sourceCompatibility` | `java { toolchain { languageVersion = JavaLanguageVersion.of(N) } }` | Gradle compiles with a JDK N that it provisions, not with `JAVA_HOME`. Needs `foojay-resolver-convention` in settings for auto-provisioning. Make sure that the JDK is installed on the build machine, or that auto-provisioning is enabled. |
| Raise Java target | `JavaLanguageVersion.of(21)` + `options.release = 21` | The bytecode level changes. Consumers on older JVMs break. Product decision. |
| Compiler strictness | `options.compilerArgs.addAll(['-Xlint:all', '-Werror'])` | Existing warnings become build failures. Run first without `-Werror` and count the warnings. |
| JUnit Platform | `useJUnitPlatform()` + `junit-platform-launcher` runtimeOnly | JUnit 4 tests need the vintage engine or a migration. The test count must not decrease. |
| Test parallelism | `maxParallelForks = Runtime.runtime.availableProcessors().intdiv(2) ?: 1` | Shows shared-state, port and temp-dir conflicts. Run the full suite several times. |
| Sources/Javadoc jars | `java { withSourcesJar(); withJavadocJar() }` | New artifacts are published. Javadoc errors fail the build. |
| UTF-8 everywhere (P1) | `options.encoding = 'UTF-8'`; `systemProperty 'file.encoding','UTF-8'` in tests | Safe if the sources are already UTF-8. Otherwise resources become corrupted. |
