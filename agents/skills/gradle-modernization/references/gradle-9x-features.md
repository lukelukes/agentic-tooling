# Gradle 9.x Features by Version

Source: the official release notes at `https://docs.gradle.org/<version>/release-notes.html`. Documentation review date: September 2026. The latest release in this file is 9.7.1 (2026-08-19). Each ACT item needs an applicability check against the actual build. Each ACT item also needs the user's approval of the change group.

Each entry has one tag:
- **ACT**: a change to make in the build of a Java project to adopt the feature.
- **AUTO**: a change that occurs automatically on upgrade. No action is necessary, but the user must know about it.
- **INFO**: a plugin-author or tooling change. It applies only if the project has custom plugins or tasks.

Use the wrapper procedure in SKILL.md. That procedure is ordered by prerequisites. Use a compatible exact version and its checksum. From 9.0.0, a partial version is accepted. Discovery of the newest version is not a compatibility decision. Pin an exact version.

## Contents

- [9.0.0 (2025-07-31), major release](#900)
- [9.1.0 (2025-09-18)](#910)
- [9.2.0 / 9.2.1 (2025-10 / 2025-11-17)](#920)
- [9.3.0 / 9.3.1 (2026-01-16 / 2026-01-29)](#930)
- [9.4.0 / 9.4.1 (2026-03-04 / 2026-03-19)](#940)
- [9.5.0 (2026-04-28)](#950)
- [9.6.0 / 9.6.1 (2026-06-18 / 2026-06-26)](#960)
- [9.7.0 / 9.7.1 (2026-08 / 2026-08-19)](#970)
- [Quick lookup: feature to minimum version](#quick-lookup)

---

<a id="900"></a>
## 9.0.0 (2025-07-31), major release

Upgrade guide: https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html

| Tag | Feature | Action |
|---|---|---|
| **AUTO/ACT** | **Gradle needs JVM 17 or later to run.** Compilation and tests for Java 8 and later are still supported through toolchains. | If the daemon JVM is older than 17, set a daemon toolchain with `./gradlew updateDaemonJvm --jvm-version=21`. This is stable since 9.2. Or make sure that CI uses JDK 17 or later. Keep `java { toolchain { languageVersion = JavaLanguageVersion.of(N) } }` for the target of the project. |
| **AUTO** | **Groovy 4** is embedded. Gradle 8 had Groovy 3. This applies to `.gradle` build scripts. | Failures are rare. Examples: `Map` and GString coercions, removed `groovy.util` classes such as `XmlSlurper`, which is now `groovy.xml.XmlSlurper`, and `@Grab`. Run `./gradlew help --warning-mode=all` after the upgrade. |
| **AUTO** | Kotlin 2.2 is embedded. The Gradle API has JSpecify nullability annotations. | This applies only to Kotlin build logic and binary plugins. |
| **ACT** | **The configuration cache is the preferred mode.** Gradle asks you to enable it if it finds no incompatibilities. Unsupported workloads can fall back instead of fail. | Follow `verification.md`. Do a strict store and reuse check with actual task execution on the verification workload before you enable the property. Fallback is not proof of compatibility. |
| **AUTO** | **Archives are reproducible by default.** `Jar`, `War`, `Zip`, `Tar` and `Ear` now have a deterministic file order, fixed timestamps and normalized permissions. | Remove manual `preserveFileTimestamps = false` and `reproducibleFileOrder = true` settings. They are redundant. If a build depended on real timestamps, use `reproducibleFileTimestamp` from 9.7.0. |
| **AUTO** | Semantic versioning. All releases are `MAJOR.MINOR.PATCH`. `@Incubating` APIs can change in minor releases. | Pin the wrapper to a full version such as `9.7.1`. Do not pin `9.7`. |
| **ACT** | The wrapper accepts major-only and minor-only versions. `--gradle-version=9` selects the latest 9.x.y. | This is useful for scripted upgrades. Commit the resolved full version. |
| **AUTO** | Gradle now uses `JAVA_HOME` for toolchain auto-detection. This agrees with IDE behavior. | No action. This decreases "toolchain not found" errors. |
| **INFO** | Detached configurations can resolve their own project. New `RootComponentIdentifier`. | This applies only to custom dependency-graph tooling. |
| **INFO** | Kotlin DSL script compilation avoidance with ABI fingerprinting. | Not applicable to the Groovy DSL. |
| **ACT** | **The Gradle Best Practices guide** is published in the documentation. | This guide is the source for `best-practices.md`. |

Removals and behavior changes in 9.0.0 to examine in old builds. Source: the upgrade guide.
- **Custom `Test` tasks no longer inherit `testClassesDirs` and `classpath` from the `test` source set.** Such tasks can run zero tests and still succeed. Set both properties explicitly. Compare the test counts.
- Variant selection by configuration name for Maven repositories, `configuration:` on external dependencies, is removed.
- Many deprecated `Project` and `Task` convention APIs are removed, for example `project.convention` and `getConvention()`. Use extensions.
- Internal `org.gradle.util.*` helpers that build scripts often used, for example `GUtil` and `ConfigureUtil`, are removed.
- `--offline` and other flags are unchanged. `gradle.properties` in subprojects is now discouraged. See the 9.2.0 practice.

<a id="910"></a>
## 9.1.0 (2025-09-18)

| Tag | Feature | Action |
|---|---|---|
| **AUTO** | **Java 25 is supported** for the daemon JVM and for toolchains. | A toolchain can now target 25. Tooling API users must enable native access, JEP 472. |
| **ACT** | **`--task-graph`** prints the task dependency tree without execution. It is incubating in 9.1.0 and stable in 9.4.0. | Use it during audits: `./gradlew build --task-graph`. It replaces third-party "taskTree" plugins. |
| **ACT** | The project report shows the physical project locations. | `./gradlew projects` now shows if a subproject directory is non-standard. See the "Avoid empty projects" practice. |
| **ACT** | **`--console=colored`** gives colors without progress bars. | Recommended for CI logs. Set `org.gradle.console=colored` in `gradle.properties` or in the CI `GRADLE_OPTS` variable. |
| **AUTO** | The rich console shows a "(N lines not showing)" indicator. | No action. |
| **AUTO** | **Version-constraint conflict errors** are more precise. They include a suggested `dependencyInsight` command. | No action. Use the suggested command when a conflict occurs. |
| **ACT** | **Configuration cache read-only mode**: `-Dorg.gradle.configuration-cache.read-only=true`. Gradle reuses entries and does not write entries. | Use it for PR or CI builds that must not pay the cost of entry storage. Main-branch builds store entries. PR builds are read-only. |
| **AUTO** | The configuration cache is **reused when `-P` properties change**, if the build does not read the property at configuration time. | Use `providers.gradleProperty('x')` wired into task inputs. Do not read `project.findProperty('x')` at configuration time. The provider form keeps cache hits. |
| **AUTO** | The encryption keystore uses the JVM default type. This is FIPS-compatible. | No action. |
| **INFO** | `AttributeContainer.addAllLater()`, `Gradle.getBuildPath()`, `MavenPublication.pom.distributionManagement {}`. | `distributionManagement` is useful if you publish to GitHub Packages and want it in the POM. |
| **INFO** | Antlr: the `packageName` property replaces the `-package` argument. The argument form is deprecated and is an error in Gradle 10. Antlr generated sources are tracked automatically. | If the project uses the `antlr` plugin, set `tasks.named('generateGrammarSource') { packageName = 'com.example.parser' }`. Remove manual `outputDirectory` changes. |
| **INFO** | EAR: `deploymentDescriptor { version = '11' }` for Jakarta EE 11. | This applies only to `ear` plugin users. |
| **AUTO** | `--dry-run` is now applied in composite builds. | No action. |
| **AUTO** | `Project.getDependencyFactory()` is promoted to stable. | No action. |

<a id="920"></a>
## 9.2.0 / 9.2.1 (2025-10 / 2025-11-17)

9.2.1 fixes startup on arm32, ppc64le and s390x, a `shouldRunAfter` cycle crash, a `DirectoryProperty` decoration failure, and a `ConcurrentModificationException` in task-dependency resolution. Use 9.2.1, not 9.2.0.

| Tag | Feature | Action |
|---|---|---|
| **AUTO** | **Windows on ARM (ARM64)** is supported, with the plain console only. | No action. |
| **AUTO** | **Performance**: up to 40 % faster time-to-first-task on large builds through work-graph construction, and 7 to 12 % less memory. The largest gain occurs with a configuration cache hit. | No action. |
| **ACT** | **The daemon toolchain is stable.** It was incubating since 8.8. `updateDaemonJvm` writes `gradle/gradle-daemon-jvm.properties`. | Offer to pin the existing compatible daemon JVM. Keep this separate from the compilation and test toolchains. A change of JVM version or vendor is a policy change. Offer it separately. Do not default to 21. |
| **AUTO** | Dependency verification failure messages suggest `--export-keys` when key servers are disabled. | No action. |
| **INFO** | `publishing.softwareComponentFactory` is exposed. Provider-based `addVariantsFromConfiguration(Provider<ConsumableConfiguration>)`. | This applies only to custom publishing components. |
| **AUTO** | Antlr tasks are grouped under "Antlr" in `./gradlew tasks`. | No action. |
| **ACT** | New best practices: **Name Your Root Project**, **Do not use gradle.properties in subprojects**, **Apply Exclusions Narrowly**, **Prefer @PathSensitivity.NONE/RELATIVE**. | See `best-practices.md`. |

<a id="930"></a>
## 9.3.0 / 9.3.1 (2026-01-16 / 2026-01-29)

9.3.1 fixes JUnit3 test discovery, `setScanForTestClasses(false)` that skipped JUnit 4 tests, incorrect JUnit XML file names, build-cache failures with emoji or non-BMP output names, and cross-project dependency manipulation. It also fixes **two security advisories**: repositories with unknown or unresponsive hosts were not disabled, so a dependency could resolve from an incorrect repository. **Use 9.3.1. Do not stay on 9.3.0.**

| Tag | Feature | Action |
|---|---|---|
| **AUTO** | **The HTML test report is restructured.** Nested classes are shown under their outer class. Parameterized methods are grouped into a suite. Suites contain their classes. **Packages are no longer shown as containers.** Stdout and stderr are attached to the individual test, not to the class. | No action in the build. Tell users that the test report looks different. CI tooling that reads the HTML report can need an update. XML reports are unchanged. |
| **AUTO** | Aggregate test reports through the `test-report-aggregation` plugin or `TestReport` support overlapping structures, with one tab per source. | No action. |
| **ACT** | **The Problems report is rendered in the console** with `--warning-mode=all`. | Use `./gradlew help --warning-mode=all` in the audit to see deprecations inline. |
| **AUTO** | Worker exit codes such as 137 are now explained, for example "likely SIGKILL / OOM". | If this message occurs, increase `org.gradle.jvmargs` or the worker memory. |
| **INFO** | `AttributeContainer.named(Class, String)`. Example: `attribute(Usage.USAGE_ATTRIBUTE, named(Usage, 'java-runtime'))` without `objects`. | This shortens custom configuration code. |
| **INFO** | TestKit `BuildResult.getOutputReader()` streams output. | Use it in plugin functional tests with large logs. |
| **AUTO** | Gradle distributions now ship `.asc` PGP signatures together with `.sha256`. | This supports the "validate distribution checksum" practice. |
| **AUTO** | **Repositories are disabled for more failure types**, for example an incorrect hostname. They stay disabled for the build. Resolution fails and does not silently continue to the next repository. | Correct all repository URL errors. They now cause failures. This is the reproducibility and security fix. |
| **AUTO** | `AbstractArchiveTask.useFileSystemPermissions()` is promoted. | No action. |
| **ACT** | New best practices: **Use Convention Plugins**, **Validate Gradle wrapper JAR checksum**, **Use unique output files and directories**. | See `best-practices.md`. |

<a id="940"></a>
## 9.4.0 / 9.4.1 (2026-03-04 / 2026-03-19)

9.4.1 fixes a Kotlin plugin variant resolution error, build-script cache keys that included the build directory path, "file name too long" in nested test reports, a progress-bar clearing defect, and a `projects` task lifecycle error. Use 9.4.1.

| Tag | Feature | Action |
|---|---|---|
| **AUTO** | **Java 26 is supported** for the daemon JVM and for toolchains. | A toolchain can target 26. |
| **ACT** | **Non-class-based testing** on the JUnit Platform: `testDefinitionDirs`. Engines such as Cucumber can discover resource-based tests without a placeholder runner. | Propose a separate migration if it is useful. Do not delete product or test runner sources in this skill. Keep the engine configuration and the scenario selection. A build-only experiment can set `testDefinitionDirs` and the existing engine dependencies on the applicable test runtime configuration. Compare scenario identities and outcomes. Build success alone is not sufficient. |
| **AUTO** | JUnit `TestReporter.publishEntry` and `publishFile` data is captured into the HTML report, in the Data and Attachments tabs, and into the XML report, in `<properties>` and `[[ATTACHMENT|path]]`. | No action. UI-test screenshots on failure now show in the report. |
| **INFO** | `Test.addTestMetadataListener(TestMetadataListener)`. | Use it to copy attachments to CI artifact directories. |
| **AUTO** | Progress bars are ligature-safe and Unicode. OSC 9;4 native progress is supported in Ghostty and iTerm2. | No action. |
| **AUTO** | The Problems HTML report is redesigned. `org.gradle.warning.mode=none` hides the report link. The report is still generated. | No action. |
| **ACT** | **PMD plugin**: CSV, Code Climate and SARIF report formats. Configure them on the `Pmd` task, for example `tasks.named('pmdMain', Pmd) { reports { sarif.required = true } }`. | If PMD results go to a security dashboard, enable SARIF. |
| **ACT** | **Wrapper Bearer-token authentication** for the distribution download, with per-host credentials. | Use it for builds that download Gradle from an internal artifact server with token authentication. |
| **AUTO** | Daemon logs older than 14 days are removed automatically. | No action. |
| **INFO** | `Configuration.extendsFrom(Provider<Configuration>)`. `.get()` is no longer necessary when you wire `dependencyScope` to `resolvable`. | This shortens custom configuration code: `extendsFrom(parent)` instead of `extendsFrom(parent.get())`. |
| **AUTO** | **The configuration cache is reused when `gradle.properties` changes**, if the build does not read the changed property at configuration time. | Same action as 9.1: read properties through providers wired to task inputs. |
| **AUTO** | The configuration cache report names the kind of closure that captured unsupported state, for example `doLast`, `onlyIf` or `cacheIf`. | This makes the configuration cache migration easier. |
| **INFO** | `java-gradle-plugin`: the plugin `id` defaults to the registration name. | Write `register('com.example.conventions') { implementationClass = '...' }`. Remove the redundant `id =`. |
| **INFO** | **Stricter plugin validation** is enabled automatically for projects that apply `maven-publish`, `ivy-publish` or `com.gradle.plugin-publish`. It is not enabled for buildSrc or included builds. | If the project publishes a plugin, correct all new `validatePlugins` failures. Consider `tasks.named('validatePlugins') { enableStricterValidation = true }` in all projects. |
| **ACT** | `org.gradle.tooling.parallel` separates IDE-sync parallelism from `org.gradle.parallel`. | Optional. Set `org.gradle.tooling.parallel=true` and `org.gradle.parallel=false` if task-level parallelism causes problems but IDE sync must stay fast. |
| **AUTO** | `--task-graph` is promoted to stable. `ProjectLayout.getSettingsDirectory()` is promoted. | No action. |
| **ACT** | New documentation section **Securing Your Gradle Builds**. New best practice **Prefer the -bin distribution**. | Make sure that `distributionUrl` ends in `-bin.zip`, not `-all.zip`. |

<a id="950"></a>
## 9.5.0 (2026-04-28)

| Tag | Feature | Action |
|---|---|---|
| **ACT** | **Task provenance**: failure messages name the script or plugin that registered the task. `./gradlew tasks --provenance` and `help --task X` show it. | Use it in audits to find which `subprojects {}` block or legacy script defined a task. Do this before you extract convention plugins. |
| **AUTO** | An INFO-level log message explains why Gradle rejected an existing daemon, for example an incompatible JVM. | Diagnostic only. |
| **ACT** | **Wrapper download retries**: `retries=3` and `retryBackOffMs=1000` in `gradle-wrapper.properties`. Off by default. | Recommend them for CI with unreliable networks. |
| **INFO** | Type-safe accessors for precompiled **Kotlin** settings plugins. | Not applicable to the Groovy DSL. |
| **ACT** | `gradle init --into <dir>` creates the target directory. | This applies only when you scaffold new projects. |
| **INFO** | `DomainObjectCollection.disallowChanges()` locks a container. | Plugin authors can use it to protect configured collections. |
| **ACT** | `GRADLE_DAEMON_BIND_ADDRESS` environment variable for restricted network setups. | Use it only if daemon connection problems occur in locked-down CI or containers. |
| **ACT** | `--develocity-url https://…` publishes a Build Scan without a change to the build. | This publishes build data to that URL. Do not add it as part of an audit unless the user wants scans. |
| **AUTO** | `--help` output is grouped into sections. The Tooling API exposes help and version. The samples page is removed from the documentation. Examples are now inline. | No action. |

<a id="960"></a>
## 9.6.0 / 9.6.1 (2026-06-18 / 2026-06-26)

9.6.1 fixes dependency-cache file permissions, a 0600 to 0644 regression, and a `DefaultBuildOperationQueue` deadlock. It adds `org.gradle.console.interactive` as a property. Use 9.6.1.

| Tag | Feature | Action |
|---|---|---|
| **AUTO** | The configuration cache is reused across `org.gradle.project.*` system properties and `ORG_GRADLE_PROJECT_*` environment variables when the build does not read them at configuration time. This matches the 9.1 `-P` and 9.4 `gradle.properties` behavior. | No action. This increases cache hits for builds that pass many project properties. |
| **ACT** | **`--non-interactive`** and `org.gradle.console.interactive=false` disable all prompts. | Set it on CI and for agent-driven builds. |
| **AUTO** | The **`NO_COLOR`** environment variable is applied. | No action. |
| **AUTO** | HTML test report columns can be sorted. | No action. |
| **ACT** | **DEPRECATION: implicit property and method lookup in parent projects.** In the Groovy DSL, a `child/build.gradle` that refers to `foo` defined through `ext.foo` in the root now warns. `findProperty()`, `property()` and `hasProperty()` that resolve from a parent also warn. **Removed in Gradle 10.** Opt into the future behavior early with `enableFeaturePreview('NO_IMPLICIT_LOOKUP_IN_PARENT_PROJECTS')` in `settings.gradle`. | This is the most common Groovy DSL deprecation in multi-project builds. Fixes: move shared values to the root `gradle.properties` and read them with `providers.gradleProperty(...)`. Or move them into a convention plugin extension. Or refer to them explicitly as `rootProject.ext.foo`. The explicit reference is the least preferred fix. See `gradle-10-deprecations.md`. |
| **AUTO** | **Groovy DSL type coercion for lazy properties**: `String` to `File`, `RegularFileProperty` or `DirectoryProperty`, relative to the project directory. Single `T` or `T[]` to `ListProperty<T>` or `SetProperty<T>`. | Assignments that caused an `IllegalArgumentException` now work. This makes plugin `Property<T>` migrations less disruptive for Groovy users. |
| **INFO** | `validatePlugins` gives specific errors for `@Optional` misuse: no I/O annotation, or combined with `@Internal`. | Plugin authors. |
| **AUTO** | **Lower I/O**: file-based journals are rewritten. Large gains on low-IOPS cloud CI storage such as EBS. | No action. Expect faster CI. |
| **AUTO** | `Wrapper.getNetworkTimeout()` is promoted. | No action. |
| **ACT** | Documentation: the **Gradle on CI** section is back, with GitHub Actions, GitLab CI, Jenkins, TeamCity, CircleCI, Travis and Docker. New practices **Avoid afterEvaluate** and **Validate the Gradle Wrapper**, updated. | See `best-practices.md`. |

<a id="970"></a>
## 9.7.0 / 9.7.1 (2026-08 / 2026-08-19), current

9.7.1 fixes `BaseExecSpec` stream API conformance, the "Click to see difference" format for failed tests in IDEs, bundled Antlr that leaked into the kapt classpath, a `Transformer` regression, `ant.taskdef` classloading, and `@Option` annotation argument order in Kotlin scripts. Use 9.7.1.

| Tag | Feature | Action |
|---|---|---|
| **INFO** | **Isolated Projects** moves from experimental to **incubating**: `--isolated-projects` or `org.gradle.isolated-projects=true`. It gives parallel project configuration. It is the foundation for incremental configuration. Diagnostics mode: `org.gradle.isolated-projects.diagnostics=true`. The legacy `org.gradle.unsafe.isolated-projects` names are deprecated. It needs configuration cache compatibility. **"Not yet recommended for production use."** | Do not enable it by default. Optionally, run once with diagnostics to list cross-project violations such as `project(':x').tasks`. Convention plugins also fix those violations. Rename all `org.gradle.unsafe.isolated-projects*` properties. |
| **INFO** | `ResolutionResult` can be a task input under the configuration cache: `configurations.runtimeClasspath.map { it.incoming.resolutionResult }`. | This simplifies SBOM and license-report tasks. |
| **INFO** | Third-party `-javaagent:` such as JaCoCo works with the configuration cache in TestKit daemon mode. | Plugin authors that measure coverage of functional tests. |
| **AUTO** | Fewer unnecessary configuration cache invalidations from IntelliJ. `idea.io.use.nio2` is now set on every build. | No action. IDE users get more cache hits. |
| **AUTO** | **Resilient sync**: partial models are returned to IDEs when part of the build fails. This needs IntelliJ 2026.2 or later. | No action. |
| **AUTO** | Test framework **initialization failures are always logged to the console**: TestNG constructor exceptions, JUnit 4 suite failures, Jupiter `@BeforeAll` aborts. `TestFailureDetails.isFrameworkFailure()`. | No action. Before 9.7.0, these were visible only in the XML. |
| **INFO** | TestNG 7.10 or later: `threadPoolFactoryClass` must implement `IExecutorServiceFactory`. | This applies only if the project sets `threadPoolFactoryClass`. |
| **AUTO** | Source locations for up to 2050 problems per build. The limit was 50. `--warning-mode=all` removes the limit. | This improves deprecation triage. |
| **ACT** | Dependency verification: `origin` and `reason` attributes on `<trusted-key>` and `<pgp>`. Failure messages say how many other keys are already trusted for the module or group. This is a key-rotation signal. New schema `dependency-verification-1.4.xsd`. | If verification is enabled, annotate trusted keys when you add them. |
| **ACT** | **`reproducibleFileTimestamp`** on archive tasks applies `SOURCE_DATE_EPOCH`: `tasks.withType(AbstractArchiveTask).configureEach { reproducibleFileTimestamp = providers.environmentVariable('SOURCE_DATE_EPOCH').map { java.time.Instant.ofEpochSecond(it as long).toEpochMilli() } }`. | Use it for reproducible-builds compliance. See the "byte-for-byte reproducible" practice. |
| **INFO** | `ResolvedArtifactResult.getAttributes()` and `getCapabilities()`. `getVariant()` is to be deprecated. `BuildCacheEntryWriter.getInputStream()`. `DomainObjectCollection.getElements()` provider. | Plugin authors. |
| **ACT** | **Groovydoc supports Java toolchains** through `javaLauncher` and a `maxMemory` property. It runs in a worker. | If the project generates Groovydoc, no change is necessary unless it needs a specific JDK. |
| **ACT** | **Lazy variants of eager `File` properties** on built-in tasks, incubating: `Javadoc.destinationDirectory`, `War.webXmlFile`, `CreateStartScripts.outputDirectory`, and 11 more across `Groovydoc`, `ScalaDoc`, `GenerateMavenPom`, `GroovyCompileOptions`, `JacocoTaskExtension`, `CodeQualityExtension` and `ProcessForkOptions`. The old getters still work and share state. | When you rewrite, use `destinationDirectory = layout.buildDirectory.dir('docs/javadoc')`. Do not use `destinationDir = file(...)`. Mark the feature as incubating in the report. |
| **AUTO** | Kotlin DSL accessor generation is no longer stored in the build cache. | Not applicable to the Groovy DSL. |
| **ACT** | **File system watching works with a custom `--project-cache-dir`** or `org.gradle.projectcachedir`. | If the project moved `.gradle/` out of the tree and disabled `org.gradle.vfs.watch`, enable it again. |
| **INFO** | **`ENHANCED_GRAPH_ORDERING` feature preview**: classpath ordering ignores constraint edges. It becomes the default in Gradle 10. Sort orders: `DEFAULT`, breadth-first, `CONSUMER_FIRST`, `DEPENDENCY_FIRST`. | If the build is sensitive to classpath order, for example shading, SPI loading or resource shadowing, test with `enableFeaturePreview('ENHANCED_GRAPH_ORDERING')` in `settings.gradle` before Gradle 10. |
| **AUTO** | `DependencyHandler.project()`, `project(String)` and `DependencyFactory.createProjectDependency(...)` are promoted to stable. | No action. |
| **ACT** | Seven new best practices: task names, `Project` in task actions, `map` and `flatMap`, attributes on configurations, `@Incubating`, reproducible output, untrusted projects. The configuration cache documentation is rewritten. | See `best-practices.md`. |

---

<a id="quick-lookup"></a>
## Quick lookup: feature to minimum version

| Feature | Minimum version |
|---|---|
| Configuration cache prompt and fallback | 9.0.0 |
| Reproducible archives by default | 9.0.0 |
| Daemon runs on JDK 17 or later only | 9.0.0 |
| `--task-graph` | 9.1.0 (stable 9.4.0) |
| `--console=colored` | 9.1.0 |
| CC read-only mode | 9.1.0 |
| CC reused after unused `-P` changes | 9.1.0 |
| Java 25 toolchain and daemon | 9.1.0 |
| Antlr `packageName` | 9.1.0 |
| Daemon toolchain stable (`updateDaemonJvm`) | 9.2.0 |
| Windows ARM64 | 9.2.0 |
| Problems in console with `--warning-mode=all` | 9.3.0 |
| Strict repository disabling (security fix) | 9.3.1 |
| Restructured HTML test report | 9.3.0 |
| Non-class-based tests, Cucumber without workaround | 9.4.0 |
| PMD SARIF, CSV, CodeClimate | 9.4.0 |
| Wrapper Bearer-token authentication | 9.4.0 |
| CC reused after unused `gradle.properties` changes | 9.4.0 |
| `extendsFrom(Provider)` | 9.4.0 |
| Java 26 | 9.4.0 |
| Task provenance, `tasks --provenance` | 9.5.0 |
| Wrapper download retries | 9.5.0 |
| `--non-interactive`, `NO_COLOR` | 9.6.0 |
| Groovy DSL lazy-property coercions | 9.6.0 |
| Parent-project lookup deprecation, `NO_IMPLICIT_LOOKUP_IN_PARENT_PROJECTS` | 9.6.0 |
| CC reused after unused env or system-property project properties | 9.6.0 |
| `reproducibleFileTimestamp`, SOURCE_DATE_EPOCH | 9.7.0 |
| Lazy `destinationDirectory` and similar on built-in tasks | 9.7.0 (incubating) |
| Isolated Projects incubating | 9.7.0 |
| `ENHANCED_GRAPH_ORDERING` preview | 9.7.0 |
| File system watching with custom project cache directory | 9.7.0 |
