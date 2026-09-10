# Gradle 8.x Features by Version

Source: the official release notes at `https://docs.gradle.org/<version>/release-notes.html` Each item needs an applicability check against the actual build and the user's approval of the change group.

Each row is a change to make in the build, or a behavior change that can break the build. Changes that need no action, and plugin-author API additions, are not listed. Read the release notes for those.

Use this file when the current version is 8.x. Read every section between the current version and 8.14, then continue with `gradle-9x-features.md` §9.0.0 if the target is 9.x. The deprecations that each 8.x version introduced are indexed in `gradle-9-deprecations.md`. This file records them only as headlines.
## Contents

- [8.0.0 / 8.0.2 (2023-02-13 / 2023-03-03), major release](#800)
- [8.1.0 / 8.1.1 (2023-04-12 / 2023-04-21)](#810)
- [8.2.0 / 8.2.1 (2023-06-30 / 2023-07-10)](#820)
- [8.3.0 (2023-08-17)](#830)
- [8.4.0 (2023-10-04)](#840)
- [8.5.0 (2023-11-29)](#850)
- [8.6.0 (2024-02-02)](#860)
- [8.7.0 (2024-03-22)](#870)
- [8.8.0 (2024-05-31)](#880)
- [8.9.0 (2024-07-11)](#890)
- [8.10.0 / 8.10.2 (2024-08-14 / 2024-09-23)](#8100)
- [8.11.0 / 8.11.1 (2024-11-11 / 2024-11-20)](#8110)
- [8.12.0 / 8.12.1 (2024-12-20 / 2025-01-24)](#8120)
- [8.13.0 (2025-02-25)](#8130)
- [8.14.0 / 8.14.5 (2025-04-25 / 2026-05-07), last 8.x](#8140)

---

<a id="800"></a>
## 8.0.0 / 8.0.2 (2023-02-13 / 2023-03-03), major release

8.0.1 restored the `--no-rebuild` flag that 8.0 had removed without a deprecation cycle. 8.0.2 fixed Metaspace exhaustion, Java builds that failed without an explicit toolchain, silent loss of custom compiler support in `JavaCompile`, remote build-cache misses caused by instrumented class files, and extending an already resolved configuration. Use 8.0.2.

Upgrade guide: https://docs.gradle.org/8.14.5/userguide/upgrading_version_7.html#changes_8.0. There is no `upgrading_major_version_8.html`. The 7.x to 8.0 changes are the last section of the 7.x guide.

| Feature | Action |
|---|---|
| **Toolchain download needs a declared toolchain repository.** There is no default provisioner. Auto-download of a missing JDK works only with a resolver plugin in the settings script. | If `java { toolchain { ... } }` relies on auto-download, add `plugins { id 'org.gradle.toolchains.foojay-resolver-convention' version '<latest>' }` to `settings.gradle`. Without it, a missing JDK is a build error. |
| **`buildSrc` behaves like an included build.** Its tasks can be run directly, for example `gradle buildSrc:test`. Its tests no longer run automatically. Init scripts now apply to `buildSrc`. `buildSrc/settings.gradle` can `includeBuild`. | If CI relied on `buildSrc` tests as a safety net, add `buildSrc:test` to the CI invocation. |
| **Cache retention is configurable.** Retention for the Gradle user home caches uses the `settings.caches` DSL in an init script. This replaces `org.gradle.cache.cleanup`, which 8.1 deprecates. | Optional. In `~/.gradle/init.d/cache-settings.gradle`: `beforeSettings { settings -> settings.caches { downloadedResources.removeUnusedEntriesAfterDays = 45 } }`. |
| Dependency verification: `reason="..."` on `trust` and checksum nodes. `./gradlew --export-keys` exports the trusted keyring on its own. | Only with dependency verification. Add reasons when you trust artifacts. |
| **PMD runs through the worker API and toolchains**, in parallel by default. CodeNarc detects the Groovy runtime version. | Implicit `--add-opens` flags for workers were removed. An old PMD that reflects into JDK internals can fail on Java 16 and later. Update `pmd { toolVersion = '...' }`. |

Removals and behavior changes in 8.0.0 to examine in old builds. Source: the upgrade guide.
- **Warnings that became errors**: `finalizedBy`, `mustRunAfter` and `shouldRunAfter` on tasks of an included build; a toolchain spec without `languageVersion`; automatic toolchain download without a repository; changing the test framework after `options {}`. Call `useJUnitPlatform()` first, then `options {}`.
- **Task validation warnings are errors**: unresolvable input file collections, unreadable inputs or outputs, missing dependencies between tasks that consume another task's output, `java.io.File` as `@InputArtifact`.
- **Removed archive properties** on `Jar`, `War`, `Ear`, `Zip`, `Tar`: `baseName`, `appendix`, `version`, `classifier`, `extension`, `archiveName`, `archivePath`, `destinationDir`. Use `archiveBaseName`, `archiveAppendix`, `archiveVersion`, `archiveClassifier`, `archiveExtension`, `archiveFileName`, `archiveFile`, `destinationDirectory`.
- **Removed** `JavaApplication.mainClassName` and `JavaExec.main`. Use `mainClass`. Removed `Report.destination` and `Report.enabled`. Use `outputLocation` and `required`. `outputLocation` is a `Property` now.
- **Removed** `AbstractTestTask.binResultsDir`, `AbstractExecTask.execResult`, `SourceDirectorySet.outputDir`, `JacocoPluginExtension.reportsDir`, the `JacocoMerge` task, `VersionCatalogBuilder.alias(String)`, `ExternalDependency.setForce(boolean)`, the `Usage.JAVA_*_JARS` constants, `IncrementalTaskInputs`, `WorkerExecutor.submit(Class, Action)`, `AntlrSourceVirtualDirectory`.
- `AbstractCompile.destinationDir` warns and is removed in 9.0. Use `destinationDirectory`. The `Upload` task type still exists but throws. Use `maven-publish`.
- `dependencies { implementation configurations.foo }` fails. Use `configurations.implementation.extendsFrom(configurations.foo)`.
- **Core JVM tasks use toolchains unconditionally.** Without a configured toolchain, the JVM that runs Gradle is used.
- `JavaVersion` renders Java 9 and 10 as `9` and `10`, not `1.9` and `1.10`. Check code that writes `JavaVersion.toString()` into files.
- **Workers no longer receive implicit `--add-opens`.** Annotation processors and code quality tools that reflect into JDK internals can warn or fail. Test workers lost these flags in 7.5. Restore them per task only when a dependency needs them.
- `sourceSets.main.output.classesDirs` no longer depends on `processResources`. A task that consumed `classesDirs` and expected resources must use `sourceSets.main.output`.
- `JavaForkOptions.getJvmArgs()` returns an immutable list. `test.jvmArgs.add('-Xmx1g')` did nothing before and now throws. Use `jvmArgs '-Xmx1g'` or `jvmArgs += ['-Xmx1g']`.
- **Most public plugin, task and extension classes became abstract.** Custom classes that extend them and are created with `new` fail. Make them abstract and create them through `tasks.register` or `ObjectFactory`.
- The `wrapper` task needs `--gradle-distribution-sha256-sum` when `gradle-wrapper.properties` already has `distributionSha256Sum`.
- Nested included builds are addressed by their directory hierarchy: `:nested:nestedNested:compileJava`.
- **Archives are built with Commons Compress**, not Ant. Archives differ byte for byte from 7.x. Expect build-cache and checksum changes.
- PMD: a non-empty `ruleSetConfig` or `ruleSetFiles` disables the default rule sets. `ruleSets = []` is no longer needed.
- `java-base`, not `base`, sets the default `destinationDirectory` of `Jar`, `War` and `Ear`. A project that applies only `base` and creates `Jar` tasks by hand gets no default.
- **Groovy DSL**: implicit fallback to root-project configure methods inside container closures is removed. `configurations { repositories { mavenCentral() } }` throws `MissingMethodException` instead of creating a configuration named `repositories`.
- Kotlin Gradle Plugin 1.6.10 or later is required.

<a id="810"></a>
## 8.1.0 / 8.1.1 (2023-04-12 / 2023-04-21)

8.1.1 fixed a `MethodTooLargeException` from configuration cache instrumentation of classes with thousands of lambdas, precompiled Kotlin plugins built with 8.1 that were unusable on other versions, and `freeCompilerArgs` in `buildSrc`. Use 8.1.1.

| Feature | Action |
|---|---|
| **The configuration cache is stable.** The `org.gradle.unsafe.configuration-cache*` properties were renamed. The old names still work without a warning. | Enable with `org.gradle.configuration-cache=true` only after the strict store-then-reuse check in `verification.md`. Rename `org.gradle.unsafe.configuration-cache` to `org.gradle.configuration-cache`, `...configuration-cache-problems` to `...configuration-cache.problems`, and `...configuration-cache.max-problems` likewise. |
| **Java 20 for toolchains.** Compile, test and run on Java 20 through toolchains. The daemon cannot run on Java 20 until 8.3. | `java { toolchain { languageVersion = JavaLanguageVersion.of(20) } }` with the daemon on Java 19 or lower. |
| **`ValueSource` and `providers.of(...)` are stable.** | Replace `project.exec` and `'git ...'.execute()` at configuration time with `providers.exec { commandLine 'git', 'rev-parse', 'HEAD' }.standardOutput.asText`. The configuration cache requires this. See the error below. |
| **Dataflow actions replace `gradle.buildFinished`**, incubating. `Gradle.buildFinished` is deprecated and does not work with the configuration cache. A `FlowAction` registered with `FlowScope.always(...)` receives the build result through `FlowProviders.getBuildWorkResult()`. | If `build.gradle` uses `gradle.buildFinished { ... }` and the build wants the configuration cache, move the logic into a `FlowAction` class in `buildSrc` or a plugin. Other hooks have no dataflow equivalent. |
| **Clearer error for Groovy closures under the configuration cache.** A `doLast` closure that reads `buildDir` fails with "Cannot reference a Gradle script object from a Groovy closure". | Look for this message in the audit. Replace `doLast { println buildDir }` with task properties or `layout.buildDirectory` captured outside the closure. |
| The `wrapper` task accepts `latest`, `release-candidate` and `nightly` labels. | Do not pin a label. Resolve it and commit the full version. |

Removals and behavior changes in 8.1.0 to examine in old builds. Source: the upgrade guide.
- **With the configuration cache enabled, an external process at configuration time is an error**: `Project.exec`, `Project.javaexec`, `ProcessBuilder`, `Runtime.exec`, Groovy `String.execute()`. Processes inside task actions are unaffected. Use `providers.exec` or a `ValueSource`.
- `JavaExec.getJvmArguments()` and `JavaExecSpec.getJvmArguments()` were added. A build script that defined its own `jvmArguments` on these types must rename it.
- **Deprecations announced for 9.0** (see `gradle-9-deprecations.md`): custom `Test` tasks that inherit `testClassesDirs` and `classpath` from the `test` source set; a `Test` task that succeeds when test sources exist but no test ran; `setCanBeConsumed` and `setCanBeResolved` on core configurations; configurations named `detachedConfiguration*`; `withJavadocJar()`, `withSourcesJar()` and `consistentResolution` without the `java` component; tests on JVM 6 and 7; relative paths for Java executables; `Task.getConvention()` and `getExtensions()` in task actions; `ConfigureUtil`, `GUtil.toCamelCase`, `WrapUtil.toDomainObjectSet`; `JvmVendorSpec.IBM_SEMERU`; `GradleBuild.buildFile`, `--build-file` and `--settings-file`; `WarPlugin.configureConfiguration`; changing Gradle Module Metadata after a publication was read.
- `org.gradle.cache.cleanup` in the user home `gradle.properties` is deprecated. Use `settings.caches { cleanup = Cleanup.DISABLED }` in an init script. The DSL wins when both are present.

<a id="820"></a>
## 8.2.0 / 8.2.1 (2023-06-30 / 2023-07-10)

8.2.1 fixed a `StackOverflowError` with Quarkus 2.16.7, TestKit with Gradle 2.x targets, the Micronaut JaCoCo aggregation plugin, boolean `--no-<option>` task options that received the wrong value, and a dependency-graph build operation regression. Use 8.2.1.

| Feature | Action |
|---|---|
| **Configuration role checks at call time.** A `Configuration` method that does not match the role from `isCanBeResolved()`, `isCanBeConsumed()` and `isCanBeDeclared()` warns. Error in 9.0. | Run `--warning-mode=all` and fix each warning. Common cases: `configurations.implementation.resolve()` or `.files`, which must resolve `compileClasspath` or `runtimeClasspath` instead; `defaultDependencies {}` on a resolvable configuration, which belongs on the declarable one. Resolvable-only methods: `resolve`, `files`, `fileCollection`, `getResolvedConfiguration`, `shouldResolveConsistentlyWith`, `copy*`. Declarable-only: `defaultDependencies`, `getDependencyConstraints`. |
| **Plugin conventions are deprecated.** Top-level `sourceCompatibility`, `archivesBaseName`, `applicationDefaultJvmArgs`, `webAppDirName`, `appDirName` and `projectReportDirName` go through `Convention`. Error in 9.0. | This is the most common source of new warnings in old Groovy builds. Rewrite each: `java { sourceCompatibility = JavaVersion.VERSION_17 }` or a toolchain; `base { archivesName = 'x'; libsDirectory = layout.buildDirectory.dir('libs') }`; `application { applicationDefaultJvmArgs = [...] }`; `war { webAppDirectory = file('src/main/webapp') }`; `ear { appDirectory = file('src/main/app') }`; `tasks.withType(HtmlDependencyReportTask).configureEach { projectReportDirectory = layout.buildDirectory.dir('reports/x') }`. |
| **Test framework runtime dependencies are no longer supplied by Gradle.** Removal in 9.0. | JUnit Platform: add `testRuntimeOnly 'org.junit.platform:junit-platform-launcher'`. JUnit 3: `testRuntimeOnly 'junit:junit:4.13.2'`. JUnit 4 and TestNG are unaffected. JVM test suites add these automatically. |
| `gradle init` defaults to the Kotlin DSL. | Pass `--dsl groovy` when you scaffold. Existing builds are unaffected. |
| **Boolean task options get a `--no-<option>` form.** The `wrapper` task validates the distribution URL before it writes `gradle-wrapper.properties`. | On air-gapped CI the `wrapper` task now needs access to the distribution host, or `validateDistributionUrl = false`. |
| **Security fixes**: dependency-cache path traversal and TAR path traversal. | Upgrade. |
| **Some tasks are configured later or never during dependency resolution.** Gradle builds its view of configurations and artifacts more lazily. | Code that mutates a configuration from inside another object's configure block, for example adding attributes to `configurations.x` inside `tasks.register('y') {}`, can stop applying. Move it to script level. |
| `options.generatedSourceOutputDirectory`, a `DirectoryProperty`, replaces `annotationProcessorGeneratedSourcesDirectory`. `BuildIdentifier.getName()` and `isCurrentBuild()` are deprecated for `getBuildPath()`. `Configuration.getAll()` is deprecated. | `compileJava { options.generatedSourceOutputDirectory = layout.buildDirectory.dir('generated/apt') }`. |

<a id="830"></a>
## 8.3.0 (2023-08-17)

No patch release.

| Feature | Action |
|---|---|
| **`filePermissions {}` and `dirPermissions {}` on every `CopySpec`**, incubating. Stable in 8.8, when `fileMode` and `dirMode` were deprecated. | Replace `fileMode = 0755` with `filePermissions { unix('rwxr-xr-x') }` and `dirMode = 0750` with `dirPermissions { unix('rwxr-x---') }` in `Copy`, `Sync`, `Jar`, `Zip` and `Tar` tasks. |
| **`--test-dry-run`** and `Test.dryRun` list the tests that would run. JUnit and TestNG. Incubating, still incubating in 8.14. | Use `./gradlew test --test-dry-run --tests 'com.example.*'` to check a filter without running it. |
| Configuration cache: `org.gradle.configuration-cache.inputs.unsafe.ignore.file-system-checks=<paths>` ignores file checks that a plugin makes at configuration time. Documented as a temporary workaround. | Use it only when a plugin causes cache misses through `File.exists()` probes, and report the plugin. |

Behavior changes in 8.3.0 to examine in old builds. Source: the upgrade guide.
- **`Project.buildDir` is deprecated** for `layout.buildDirectory`. No warning is printed in 8.x. No removal version is announced. Replace `file("$buildDir/x")` with `layout.buildDirectory.file('x')` and `"$buildDir/dir"` with `layout.buildDirectory.dir('dir')`. Use `.get().asFile` only for non-lazy APIs.
- **`ClientModule` dependencies are deprecated**, removal in 9.0. `implementation module('org:foo:1.0') { dependency 'org:bar:1.0' }` becomes a plain coordinate plus a `ComponentMetadataRule` registered with `dependencies.components.withModule('org:foo', Rule)`.
- **`org.gradle.libraryelements` and `org.gradle.jvm.version` are present at configuration creation.** Reading `org.gradle.jvm.version` finalizes the project toolchain. Build logic that copies attributes eagerly into a new configuration makes later `java { toolchain {} }` edits fail with "property 'languageVersion' is final". Copy attributes with `attributeProvider(key, provider { source.getAttribute(key) })`.
- `artifactView {}` and `incoming.artifacts` no longer snapshot attributes at creation. Workarounds that duplicated attributes into the view can be removed.
- The Tooling API `TestLauncher` fails the build on test failure. Pass `--continue` to keep the old flow.
- **The earliest supported Develocity plugin in 9.0 is 3.13.1.** Versions 3.0 to 3.13 are ignored when applied on 9.x. Upgrade `com.gradle.enterprise` or `com.gradle.develocity` now.

<a id="840"></a>
## 8.4.0 (2023-10-04)

No patch release. Gradle 7.6.3 received the same two security fixes.

| Feature | Action |
|---|---|
| **Role-based configuration factories**: `configurations.consumable('x')`, `resolvable('x')`, `dependencyScope('x')`. Each locks one role. Incubating, still incubating in 8.14. Core plugins move to role-locked configurations in 9.0. | Replace `configurations { myDeps { canBeResolved = false; canBeConsumed = false } }` with `configurations { dependencyScope('myDeps') }` and `configurations { myClasspath { canBeConsumed = false; extendsFrom myDeps } }` with `configurations { resolvable('myClasspath') { extendsFrom configurations.myDeps } }`. Prefer these in convention plugins when the target is 9.x. |
| `minHeapSize` and `maxHeapSize` on `Checkstyle`, `CodeNarc` and `Pmd` tasks. | For large code bases: `tasks.withType(Checkstyle).configureEach { maxHeapSize = '1g' }`. |
| `JvmVendorSpec.JETBRAINS` for toolchains. | Only if the build needs the JetBrains Runtime. |
| **Security fixes**: CVE-2023-44387, copy and archive tasks applied the permissions of a symlink instead of its target; CVE-2023-42445, XML external entity injection through Ivy descriptors. | Upgrade. Archives built from trees with symlinks by earlier versions can carry wrong permissions. |

Behavior changes in 8.4.0 to examine in old builds. Source: the upgrade guide.
- **XML parsers use secure processing.** Build logic that depends on an old XML parser fails. Update it. As a last resort, force the JDK parsers with `systemProp.javax.xml.parsers.SAXParserFactory=com.sun.org.apache.xerces.internal.jaxp.SAXParserFactoryImpl` and the matching `DocumentBuilderFactory` and `TransformerFactory` properties in `gradle.properties`.
- **External DTDs are blocked.** An `ear` build with `deploymentDescriptor { version = '1.3'; withXml { asElement() } }` fails. Use `asNode()`, or `systemProp.javax.xml.accessExternalDTD=http`.
- `GenerateMavenPom.getVersionRangeMapper`, `withCompileScopeAttributes` and `withRuntimeScopeAttributes` are deprecated for 9.0. They were never public API.

<a id="850"></a>
## 8.5.0 (2023-11-29)

No patch release.

| Feature | Action |
|---|---|
| **Reserved configuration name warnings explain the cause.** Creating `customCompileOnly` before the `custom` source set exists warns. Error in 9.0. | Create the source set first: `sourceSets { custom }`, then touch `configurations.customCompileOnly`. |
| **`Copy` and `Sync` canonicalize relative destination paths.** `.` is removed and `..` appears only at the start. A `Sync` with `into('.') { from 'x' }` copied nothing before and copies now. | Verify tasks whose child `into` used `.` or `..`. Their output can change. |
| Dependency verification: `<keyring-format>armored</keyring-format>` or `binary` inside `<configuration>` restricts the keyring to one file. Key ids match case-insensitively. | Only with dependency verification. |
| EAR: `deploymentDescriptor { version = '10' }` generates valid descriptors for Java EE 8, Jakarta EE 9 and 10. | A custom `application.xml` shipped only for a modern descriptor version can be dropped. |
| `FileSystemOperations.copySpec()`, incubating. `Settings.layout` with `settingsDirectory` and `rootDirectory`, incubating. `BuildFeatures` service, incubating, stable in 8.11. Embedded Kotlin 1.9.20. | Custom tasks that used `project.copySpec()` at execution time: inject `FileSystemOperations` and call `fs.copySpec {}`. |

Behavior changes in 8.5.0 to examine in old builds. Source: the upgrade guide.
- **`groovy-base` owns the source and target compatibility conventions of `GroovyCompile`.** A `GroovyCompile` task registered without `groovy-base` must set both itself.
- `Provider.filter` takes a `Spec`, not a `Predicate`. Closures keep working.
- `VersionNumber.parse` and `compareTo` from `org.gradle.util` warn. Removal in 9.0.
- **Resolving a configuration that is also consumable** can select itself as a variant and produce a circular graph. Deprecated, error in 9.0. Mark resolvable configurations `canBeConsumed = false`, or create them with `resolvable(String)`.
- **`include` of a project whose directory does not exist warns.** Error in 9.0. Builds that synthesize projects must create the directory: `project(':x').projectDir.mkdirs()`.

<a id="860"></a>
## 8.6.0 (2024-02-02)

No patch release.

| Feature | Action |
|---|---|
| **Custom configuration cache encryption key.** `GRADLE_ENCRYPTION_KEY` holds a Base64 AES key, for example from `openssl rand -base64 16`. | Only when the Gradle user home is shared across machines or a managed keystore is unwanted. The same key must be present on every run. |
| **`tasks.named { nameSpec }`** filters by name without realizing registered tasks. `tasks.matching {}` realizes every task. Incubating, still incubating in 8.14. | Replace name-based `matching` with `tasks.named { it.startsWith('publish') }.configureEach { ... }`. The closure receives the name, not the task. Keep `matching` when the filter needs task state. |
| `gradle init --use-defaults` and `--package`. Generated convention plugins carry a `buildlogic` prefix. | Scaffolding only. |
| `requireCapability`, `capability` and `withCapability` accept a `Provider`. | Only for capabilities computed from `project.version` or similar. |

Behavior changes in 8.6.0 to examine in old builds. Source: the upgrade guide.
- **`registerFeature('x') { usingSourceSet(sourceSets.main) }` is deprecated.** With `java` applied it throws in 9.0, because `main` is already the main feature. Register the feature with a dedicated source set.
- **Publishing to Maven a dependency with an explicit artifact `name` that differs from the module name** is deprecated. Error in 9.0. Declare the real coordinates. Ivy publishing is unaffected.
- `ArtifactIdentifier` is deprecated for removal in 9.0.
- **Mutating dependencies from a test-suite `dependencies {}` block after they were observed** is deprecated. Error in 9.0. `configurations.testImplementation.dependencies.all { version { require(...) } }` becomes a `prefer` constraint.

<a id="870"></a>
## 8.7.0 (2024-03-22)

No patch release.

| Feature | Action |
|---|---|
| **Java 22 for toolchains.** The daemon cannot run on Java 22 until 8.8. | `java { toolchain { languageVersion = JavaLanguageVersion.of(22) } }` with the daemon on Java 21 or lower. |
| Constraints in the JVM test suite `dependencies {}` block: `implementation(constraint('foo:bar:1.0'))`. Single-string notation only. | Only for builds that use `testing.suites`. |
| `GenerateModuleMetadata`: `suppressedValidationErrors.add('dependencies-without-versions')`. TestNG `threadPoolFactoryClass`, incubating. `gradle init --no-comments`. | Only for the builds that hit these cases. |
| **Archive checksums can change.** Commons Compress 1.25.0 replaces 1.21. ASM 9.6. The version catalog parser is TOML 1.0.0 compliant. | Hand-written catalogs that relied on lenient parsing can fail. Builds that compare archive checksums across Gradle versions see differences. |
| `HasMultipleValues.append*()` and `MapProperty.insert*()`, incubating. **Removed in 8.8.** `BuildServiceRegistry.registerIfAbsent(String, Class)` without an action. JSch replaced by `com.github.mwiede:jsch`, Apache SSHD 2.10.0, JGit 5.13.3. Embedded Kotlin 1.9.22. | Do not use `append` or `insert`. Revert to `add` and `put`. |

Behavior changes in 8.7.0 to examine in old builds. Source: the upgrade guide.
- **Registering plugin conventions** with `project.convention.plugins` warns, in addition to the access warning from 8.2. Register an extension instead.
- **`Project.uri(Object)` warns on invalid URLs** and falls back to a legacy decoder. Error in 9.0. Drop the `file:` scheme for relative paths, encode spaces as `%20` and `%` as `%25`.
- **`SelfResolvingDependency` is deprecated** for removal in 9.0. `ProjectDependency` and `FileCollectionDependency` lose `resolve()` and `getBuildDependencies()`. Resolve through a resolvable configuration: `dependsOn(configurations.runtimeClasspath)`.
- `CollectionUtils.stringize` from `org.gradle.util` warns. Removal in 9.0.

<a id="880"></a>
## 8.8.0 (2024-05-31)

No patch release. This is the version with the largest set of configuration-related deprecations. Read `gradle-9-deprecations.md` § 8.8 with this section.

| Feature | Action |
|---|---|
| **Daemon JVM criteria, `updateDaemonJvm`**, incubating. Writes `gradle/gradle-daemon-jvm.properties` with `toolchainVersion=<major>`. Gradle finds an installed JVM of that version through toolchain discovery. It takes precedence over `JAVA_HOME` and `org.gradle.java.home`. No auto-provisioning until 8.13. Stable in 9.2.0. The 8.8 manual names the file `gradle/daemon-jvm.properties`. The 8.8 source and the 8.9 manual use `gradle/gradle-daemon-jvm.properties`. | Offer to pin the compatible daemon JVM that the build already uses: `./gradlew updateDaemonJvm --jvm-version=17`. Commit the properties file. Every developer and CI agent needs a discoverable JDK of that version. A change of version or vendor is a policy change. Offer it separately. |
| **XML test report filtering.** `reports.junitXml { includeSystemOutLog = false; includeSystemErrLog = true }`. Incubating, still incubating in 8.14. | Use it to shrink CI reports. |
| **Local build-cache retention moves to init scripts.** `buildCache { local { removeUnusedEntriesAfterDays = 30 } }` in `settings.gradle` is deprecated. Removal in 9.0. | Remove it from `settings.gradle`. In `~/.gradle/init.d/cache.gradle`: `beforeSettings { caches { buildCache.setRemoveUnusedEntriesAfterDays(30) } }`. |
| Version catalog plugin aliases without a version: `[plugins] my = { id = "my.plugin" }`. `JacocoReport.sourceEncoding`. | Only when the plugin version is supplied elsewhere, for example by an included build. |
| **The File Permissions API is stable.** `fileMode`, `dirMode`, `FileTreeElement.getMode` and `FileCopyDetails.setMode` are deprecated. Removed in 9.0. | Replace `fileMode = 0755` with `filePermissions { unix('rwxr-xr-x') }` and `dirMode` with `dirPermissions {}` in `Copy`, `Jar`, `Zip`, `Tar` and `Sync` tasks. |
| **Groovy 3.0.21.** Casting a closure to `Action` without a generic type gives the parameter type `Object`. `{ Task it -> ... } as Action` breaks. | Grep `.gradle` files and `buildSrc` for `as Action` and write `as Action<Task>`. |

Behavior changes in 8.8.0 to examine in old builds. Source: the upgrade guide.
- **Mutating a configuration after it was observed** warns in the cases that were not already errors. Error in 9.0. Covers dependencies, constraints, resolution strategy, exclude rules, artifacts, role, `extendsFrom`, `transitive` and `visible`. The usual trigger is `incoming.beforeResolve { dependencies.add(...) }`. Replacements: `dependencies.addLater` or `addAllLater`, `prefer` constraints, `withDependencies {}` or component metadata rules for excludes, and roles set at creation.
- **Dependency-filtered file methods are deprecated**: `Configuration.files(Dependency...)`, `files(Spec)`, `files(Closure)`, `fileCollection(...)`, `ResolvedConfiguration.getFiles(Spec)`, `getFirstLevelModuleDependencies(Spec)` and the `LenientConfiguration` equivalents. Use `incoming.artifactView { componentFilter { it instanceof ModuleComponentIdentifier && it.group == 'g' && it.module == 'm' } }.files`. The filter does not include the component's transitive dependencies.
- `fileMode`, `dirMode` and the mode-based methods are deprecated. `buildCache.local.removeUnusedEntriesAfterDays` is deprecated. See the rows above.
- `append` and `insert` on collection properties are removed. ASM 9.7.

<a id="890"></a>
## 8.9.0 (2024-07-11)

No patch release.

| Feature | Action |
|---|---|
| **`gradle --version` prints the Launcher JVM and the Daemon JVM** and says how the daemon JVM was chosen. `buildEnvironment` prints location, language version, vendor and architecture. | Record both in the audit. Gradle 9 needs a daemon JVM of 17 or higher. `gather_facts.py` captures `--version` and `buildEnvironment`. |
| TestNG `suiteThreadPoolSize` on `TestNGOptions`. | Only for TestNG projects with multiple suites. |

Behavior changes in 8.9.0 to examine in old builds. Source: the upgrade guide.
- **Every auto-provisioned toolchain is downloaded again once**, because the marker file changed to `.ready`. Expect one slow first build on CI agents that auto-provision JDKs.
- **Java projects can no longer compile against the Gradle runtime classpath implicitly.** A project with no declared dependencies that referenced Gradle classes fails. Add `implementation gradleApi()` or apply `java-gradle-plugin`.
- Configuration cache classes moved to `org.gradle.internal.*`. Build logic that referenced `org.gradle.configurationcache.*` breaks. Those were internal.
- File-system watching is disabled on macOS 11 and earlier. Daemon log files are always UTF-8.
- JDK 8 compiler output with annotation processors prints fully qualified type names. This affects only builds that parse compiler output.

<a id="8100"></a>
## 8.10.0 / 8.10.2 (2024-08-14 / 2024-09-23)

8.10.1 fixed a significant dependency-resolution slowdown introduced in 8.10, a broken `equals()` contract for `LifecycleAwareProject`, and Isolated Projects validation that ran when the feature was off. 8.10.2 fixed a regression from 8.10.1, a Kotlin Multiplatform failure with a reused daemon, and `configureEach(Action)` on a task set. Use 8.10.2.

| Feature | Action |
|---|---|
| **DEPRECATION: the daemon on JVM 16 or lower.** Message: "Executing Gradle on JVM versions 16 and lower has been deprecated. This will fail with an error in Gradle 9.0." The wrapper, launcher, Tooling API and TestKit stay compatible with JVM 8. Compilation and tests on older JVMs through toolchains stay supported. | If `./gradlew --version` shows a daemon JVM below 17, this blocks the 9.x upgrade. Options: `org.gradle.java.home` in `gradle.properties`, `JAVA_HOME`, or the daemon JVM criteria. Keep the project toolchain separate from the daemon JVM. |
| Daemon JVM criteria can require a vendor, incubating. Stable in 9.2.0. | Only for builds that already use `updateDaemonJvm`. A vendor change is a policy decision. |

Behavior changes in 8.10.0 to examine in old builds. Source: the upgrade guide.
- **`JavaCompile` can fail on a JRE-only machine even with nothing to compile.** `java-base` derives default compatibility from the compiler. Set `java { sourceCompatibility; targetCompatibility }` or `options.release`, or install a JDK.
- **Deprecated, error in 9.0**: consuming a non-consumable configuration through Ivy metadata when an Ivy dependency is substituted by a project; **extending a configuration from another project**, for example `configurations.foo.extendsFrom(project(':other').configurations.bar)`. Declare a project dependency instead.

<a id="8110"></a>
## 8.11.0 / 8.11.1 (2024-11-11 / 2024-11-20)

8.11.1 fixed `BuildEventsListenerRegistry` corruption with Isolated Projects and parallel configuration, sporadic `ETXTBSY` failures when running executables, an `ArrayIndexOutOfBoundsException` in the problems report, and a bytecode-interception failure that made some tasks unable to run. Use 8.11.1. This is the version with the largest batch of API deprecations for 9.0. Read `gradle-9-deprecations.md` § 8.11 with this section.

| Feature | Action |
|---|---|
| **The HTML problems report** at `build/reports/problems/problems-report.html` collects deprecations and other problems. The console prints "[Incubating] Problem report is available at". `--no-problems-report` disables it. 9.3 renders it in the console with `--warning-mode=all`. | Use it in the audit: run `./gradlew help --warning-mode=all` and open the report to list every deprecation with its location. |
| **`providers.exec`, `providers.javaexec`, `ExecOutput` and the `*PrefixedBy` methods are stable.** | Replace configuration-time `project.exec {}` with `def sha = providers.exec { commandLine 'git', 'rev-parse', '--short', 'HEAD' }.standardOutput.asText.map { it.trim() }`. Pair this with the `project.exec` deprecation below. |
| **Parallel configuration cache load and store**, incubating: `org.gradle.configuration-cache.parallel=true`. Gradle warns that it can expose concurrency issues. | Only after the configuration cache is enabled and verified. Do not enable it in the same change as the cache. Rerun the strict store-then-reuse pair. |
| **`requireFeature('name')`** on a project dependency selects a feature variant without knowing the target's group and name. | Replace `capabilities { requireCapability("${group}:other-foo") }` with `implementation(project(':other')) { capabilities { requireFeature('foo') } }`. `testFixtures(project(':x'))` already covers test fixtures. |
| **`ProjectDependency.getPath()`** replaces `dependencyProject`, which is deprecated in the same release. | Replace `dep.dependencyProject` with `project(dep.path)`. Prefer `incoming.resolutionResult` when the goal is the set of resolved projects. |

Behavior changes in 8.11.0 to examine in old builds. Source: the upgrade guide.
- **`UpdateDaemonJvm.jvmVersion` is a `Property<JavaLanguageVersion>`.** A configured task changes `jvmVersion = JavaVersion.VERSION_17` to `JavaLanguageVersion.of(17)`. The property is renamed again in 8.13.
- **Abbreviated name matching treats digits as word boundaries.** `gradle unique` matched both `uniqueA` and `unique1` before and is ambiguous now. Use full task names in CI scripts.
- `ForkOptions.javaHome` is deprecated in 8.11 and un-deprecated in 8.14. Prefer a toolchain.
- **Deprecated, error or removal in 9.0**: `project.exec {}` and `project.javaexec {}`, which get `ExecOperations` in task actions and `providers.exec` at configuration time; `ProjectDependency.getDependencyProject()`; `ResolvedConfiguration.getFiles()` and `LenientConfiguration.getFiles()`, which become `incoming.files` and `incoming.artifactView { lenient = true }.files`; the `AbstractOptions` map methods `options.define(...)`, `options.fork(map)` and `options.debug(map)`, which become property assignments; wholesale setters `setForkOptions`, `setDebugOptions` and the Scala equivalents; `Javadoc.isVerbose()` and `setVerbose`; `Dependency.contentEquals`; `gradle.useLogger`; `configuration:` on Maven dependencies and `targetConfiguration`; `configurations.add(...)`, `addLater` and `addAllLater`; `extendsFrom` on detached configurations; mutating `buildscript { configurations {} }`.

<a id="8120"></a>
## 8.12.0 / 8.12.1 (2024-12-20 / 2025-01-24)

8.12.1 fixed `FileLockCommunicator` with the macOS 15.1 firewall and with Crowdstrike or SentinelOne, restored the 8.11 default working directory of `ExecSpec`, a Linux build failure after the upgrade from 8.11.1, and the output format of Java compiler problems. Use 8.12.1. The `ExecSpec` fix matters for every `Exec` task that relies on the default working directory.

| Feature | Action |
|---|---|
| **DEPRECATION: Groovy space assignment.** `group 'com.example'`, `version '1.0'`, `description 'x'` and `mainClass 'a.Main'` without `=` are Gradle-generated methods, not Groovy. **Removed in Gradle 10.** | Replace with `group = 'com.example'`. For real methods, use parentheses: `jvmArgs('-Xmx1g')` or `jvmArgs = ['-Xmx1g']`. The upgrade guide gives a `sed` command for bulk rewrites. Common hits: `group`, `version`, `description`, `mainClass`, `archiveBaseName`, `url`, `sourceCompatibility`. See `gradle-10-deprecations.md`. |
| **DEPRECATION: `Task.getProject()` in a task action** warns without the `STABLE_CONFIGURATION_CACHE` preview. **Error in Gradle 10.** With the configuration cache on, the same call is a cache problem. | In `doLast {}` and `doFirst {}`, replace `project.x` with values captured at configuration time, `providers`, `layout` or injected services. See practice T10. |
| **Ambiguous artifact transform chains warn.** Two equal-length chains that produce compatible variants used to be picked silently. Error in 9.0. | Run `--warning-mode=all`. If the warning appears, use the `artifactTransforms` report from 8.13 to list the transforms. In a plain Java build they come from plugins. Report the plugin. |
| **`@ServiceReference` is stable.** `TaskContainer.create()` is `@Deprecated` at source level, without a runtime warning. `DependencyConstraintHandler.addProvider()`. `ProblemReporter.throwing()` prints label, details and solutions. Ant 1.10.15, Zinc 1.10.4, Kotlin 2.0.21. | Replace `tasks.create('x', T)` and `task x(type: T)` with `tasks.register('x', T)`. The Groovy DSL gives no compiler warning, so grep for them. |

Behavior changes in 8.12.0 to examine in old builds. Source: the upgrade guide.
- `./gradlew init tasks` is deprecated. `init` must run alone. Error in 9.0.
- `ReportingExtension.baseDir` is deprecated. Use `reporting { baseDirectory = layout.buildDirectory.dir('reports') }`.
- `DependencyInsightReportTask.getDependencySpec()` is deprecated. It was not meant for build scripts.

<a id="8130"></a>
## 8.13.0 (2025-02-25)

No patch release.

| Feature | Action |
|---|---|
| **Daemon JVM auto-provisioning**, incubating. `updateDaemonJvm` writes `toolchainUrl.<OS>.<ARCH>=...` entries next to `toolchainVendor` and `toolchainVersion`. Gradle downloads the daemon JDK. IntelliJ IDEA reads the file from 2025.1. Stable in 9.2.0. | Apply the foojay resolver in `settings.gradle`, 0.9.0 or later. Then `./gradlew updateDaemonJvm --jvm-version=17 --jvm-vendor=adoptium` and commit the file. Offer to pin the JVM that the build already uses. A version or vendor change is a policy decision. |
| **`layout.settingsDirectory`** gives the directory of `settings.gradle` from any project without `rootProject`. | Replace `rootProject.file('x')`, `rootProject.layout.projectDirectory.file('x')` and `"$rootDir/x"` with `layout.settingsDirectory.file('x')` for shared files such as lint configurations. This removes cross-project access, which Isolated Projects forbids. |
| **`artifactTransforms` report task** lists every registered transform with its action type, cacheability and attributes. | Run `./gradlew :app:artifactTransforms` when the 8.12 ambiguous-chain warning appears or when a transform fails. |
| **JUnit XML timestamps have millisecond precision.** | Tools that parse `timestamp` with a second-precision pattern need an update. |

Behavior changes in 8.13.0 to examine in old builds. Source: the upgrade guide.
- **`JvmTestSuite.testType` is removed**, with the `TestSuiteTargetName` and `TestSuiteType` attributes. A `testType = TestSuiteType.INTEGRATION_TEST` line fails. Delete it.
- **Test Report Aggregation and JaCoCo Report Aggregation** create one test-results variant per suite, not per target. `testType` on `JacocoCoverageReport` and `AggregateTestReport` becomes `testSuiteName = 'test'`.
- `Project.task()` is `@Deprecated` at source level. `task foo(type: Copy) {}` and `project.task('foo')` are the eager forms. Replace with `tasks.register`.
- **`UpdateDaemonJvm.jvmVersion` and `jvmVendor` are deprecated** for `languageVersion` and `vendor`. Running the task with `jvmVendor` set fails. The command-line options stay `--jvm-version` and `--jvm-vendor`.
- **Boolean properties declared as `Boolean isFoo()` warn.** Gradle 9.0 still recognizes them. Gradle 10 does not. A task input can be ignored and the task reported up to date incorrectly. In custom task classes, including Groovy classes in `buildSrc`, add `@Input Boolean getFoo()` and mark the old method `@Deprecated @ReplacedBy('foo')`, or change the type to primitive `boolean`.
- `BuildLauncher.addJvmArguments()` no longer overrides `org.gradle.jvmargs`. Tooling API clients only. Recursive `AttributeContainer` queries in a lazy provider are an error in 9.0. `VariantTransformConfigurationException` becomes internal in 9.0.

<a id="8140"></a>
## 8.14.0 / 8.14.5 (2025-04-25 / 2026-05-07), last 8.x

Five patch releases exist. 8.14.1 fixed `Groovydoc` suppressing the stdout of concurrent tasks and the lazy-configuration change that broke Android code coverage. 8.14.2 fixed selector resolution with dynamic versions. 8.14.3 backported a fix for a dependency that went missing when not all paths excluded it. **8.14.4 (2026-01-23) fixed two security advisories**: repositories that failed to answer, and repositories with an unknown host, were not disabled, so a dependency could resolve from an unintended repository. 8.14.4 also stops forked processes that were not stopped, fixes compile-classpath fingerprints for the same dependency, adds partial cgroups v2 support and improves Java 25 support. 8.14.5 fixed `TransformedClassLoader` thread safety and excludes on dependencies from included builds. **Use 8.14.5. Do not stay on 8.14.3 or earlier.** A project that must remain on 8.x belongs on 8.14.5.

| Feature | Action |
|---|---|
| **Configurations are initialized lazily.** Applying `base`, directly or through `java`, no longer realizes configurations declared with `register()` or the role-based factories. `create()` and the `configurations { name }` shorthand stay eager. | Declare custom configurations with `register` or the role-based factories: `configurations { register('agent') { canBeConsumed = false; canBeResolved = true } }`. Plugins that assumed all configurations were realized can break. The AGP coverage case is fixed in 8.14.1. |
| **Configuration cache integrity check**: `-Dorg.gradle.configuration-cache.integrity-check=true` makes serialization errors name the exact field and task instead of "Index 4 out of bounds for length 3". It grows the cache and slows reads and writes. | Use it only while troubleshooting a cache load failure. Do not commit it to `gradle.properties`. |
| GraalVM Native Image toolchain selection: `java { toolchain { nativeImageCapable = true } }`. Also for the daemon toolchain. | Only if the project builds native images. |
| **The wrapper JAR is an executable JAR** with a `Main-Class`. `./gradlew wrapper` updates it. | Run the wrapper task after the version bump so that the committed JAR matches. |
| **Bundled tools**: Guava 33.4.6, Groovy 3.0.24, JaCoCo 0.8.13. | Build scripts and `buildSrc` code that use Guava from Gradle's classpath see Guava deprecations such as `Charsets`. |

Behavior changes in 8.14.0 to examine in old builds. Source: the upgrade guide.
- **Groovy string-to-enum coercion for `Property<Enum>` is deprecated.** Error in Gradle 10. The guide says that this affects only Groovy plugins and scripts. Assign the constant: `someEnumProperty = SomeEnum.VALUE`.
- `StartParameter.isConfigurationCacheRequested` warns. Removed in Gradle 10. Use `BuildFeatures`: `buildFeatures.configurationCache.requested`.
- `IdeaModule.testSourceDirs` and `testResourceDirs` warn. Removed in 9.0. Use `testSources` and `testResources`.
- `Groovydoc.getAntGroovydoc()`, the `GradlePluginDevelopmentExtension` constructor and `pluginSourceSet()` are deprecated. Removed in 9.0.
- `getAttribute(null)` warns instead of returning `null`. `EclipseClasspath.baseSourceOutputDir` is a `DirectoryProperty`. `Settings.getDefaults()` is removed. Use `settings.defaults {}`.
- `ForkOptions.javaHome` is no longer deprecated. The 8.11 deprecation is reverted because no stable replacement exists.
- **The 8.0 "configuration usage" deprecation is withdrawn.** Adding an artifact to a configuration that is neither resolvable nor consumable no longer warns. Old workarounds are harmless and can be removed.
