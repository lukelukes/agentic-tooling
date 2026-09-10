# Gradle 9.x Features by Version

Source: the official release notes at `https://docs.gradle.org/<version>/release-notes.html`. Documentation review date: September 2026. The latest release in this file is 9.7.1 (2026-08-19). Each item needs an applicability check against the actual build and the user's approval of the change group.

Each row is a change to make in the build, or a behavior change that can break the build. Changes that need no action, and plugin-author API additions, are not listed. Read the release notes for those.

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

---

<a id="900"></a>
## 9.0.0 (2025-07-31), major release

Upgrade guide: https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html

| Feature | Action |
|---|---|
| **Gradle needs JVM 17 or higher to run.** Toolchains continue to support compilation and tests for Java 8 and higher. | If the daemon JVM is older than 17, set a daemon toolchain with `./gradlew updateDaemonJvm --jvm-version=21`. This is stable since 9.2. Or make sure that the JVM that runs Gradle is 17 or higher. Keep `java { toolchain { languageVersion = JavaLanguageVersion.of(N) } }` for the target of the project. |
| **Groovy 4** is embedded. Gradle 8 had Groovy 3. This applies to `.gradle` build scripts. | Failures are rare. Examples: `Map` and GString coercions, removed `groovy.util` classes such as `XmlSlurper`, which is now `groovy.xml.XmlSlurper`, and `@Grab`. Run `./gradlew help --warning-mode=all` after the upgrade. |
| **The configuration cache is the preferred mode.** Gradle asks you to enable it if it finds no incompatibilities. Unsupported workloads can fall back instead of fail. | Follow `verification.md`. Do a strict store and reuse check with actual task execution on the verification workload before you enable the property. Fallback is not proof of compatibility. |
| **Archives are reproducible by default.** `Jar`, `War`, `Zip`, `Tar` and `Ear` now have a deterministic file order, fixed timestamps and normalized permissions. | Remove manual `preserveFileTimestamps = false` and `reproducibleFileOrder = true` settings. They are redundant. If a build depended on real timestamps, use `reproducibleFileTimestamp` from 9.7.0. |
| Semantic versioning. All releases are `MAJOR.MINOR.PATCH`. `@Incubating` APIs can change in minor releases. | Pin the wrapper to a full version such as `9.7.1`. Do not pin `9.7`. |
| The wrapper accepts major-only and minor-only versions. `--gradle-version=9` selects the latest 9.x.y. | This is useful for scripted upgrades. Commit the resolved full version. |
| **The Gradle Best Practices guide** is published in the documentation. | This guide is the source for `best-practices.md`. |

Removals and behavior changes in 9.0.0 to examine in old builds. Source: the upgrade guide.
- **Custom `Test` tasks no longer inherit `testClassesDirs` and `classpath` from the `test` source set.** Such tasks can run zero tests and still succeed. Set both properties explicitly. Compare the test counts.
- Variant selection by configuration name for Maven repositories, `configuration:` on external dependencies, is removed.
- Many deprecated `Project` and `Task` convention APIs are removed, for example `project.convention` and `getConvention()`. Use extensions.
- Internal `org.gradle.util.*` helpers that build scripts often used, for example `GUtil` and `ConfigureUtil`, are removed.
- `--offline` and other flags are unchanged. `gradle.properties` in subprojects is now discouraged. See the 9.2.0 practice.

<a id="910"></a>
## 9.1.0 (2025-09-18)

| Feature | Action |
|---|---|
| **`--task-graph`** prints the task dependency tree without execution. It is incubating in 9.1.0 and stable in 9.4.0. | Use it during audits: `./gradlew build --task-graph`. It replaces third-party "taskTree" plugins. |
| The project report shows the physical project locations. | `./gradlew projects` now shows if a subproject directory is non-standard. See the "Avoid empty projects" practice. |
| **`--console=colored`** gives colors without progress bars. | Use it for logs that are written to a file. Set `org.gradle.console=colored` in `gradle.properties`. |
| **Configuration cache read-only mode**: `-Dorg.gradle.configuration-cache.read-only=true`. Gradle reuses entries and does not write entries. | Use it for builds that must reuse entries and must not write entries. |
| The configuration cache is **reused when `-P` properties change**, if the build does not read the property at configuration time. | Use `providers.gradleProperty('x')` wired into task inputs. Do not read `project.findProperty('x')` at configuration time. The provider form keeps cache hits. |
| Antlr: the `packageName` property replaces the `-package` argument. The argument form is deprecated and is an error in Gradle 10. Antlr generated sources are tracked automatically. | If the project uses the `antlr` plugin, set `tasks.named('generateGrammarSource') { packageName = 'com.example.parser' }`. Remove manual `outputDirectory` changes. |

<a id="920"></a>
## 9.2.0 / 9.2.1 (2025-10 / 2025-11-17)

9.2.1 fixes startup on arm32, ppc64le and s390x, a `shouldRunAfter` cycle crash, a `DirectoryProperty` decoration failure, and a `ConcurrentModificationException` in task-dependency resolution. Use 9.2.1, not 9.2.0.

| Feature | Action |
|---|---|
| **The daemon toolchain is stable.** It was incubating since 8.8. `updateDaemonJvm` writes `gradle/gradle-daemon-jvm.properties`. | Offer to pin the existing compatible daemon JVM. Keep this separate from the compilation and test toolchains. A change of JVM version or vendor is a policy change. Offer it separately. Do not default to 21. |
| New best practices: **Name Your Root Project**, **Do not use gradle.properties in subprojects**, **Apply Exclusions Narrowly**, **Prefer @PathSensitivity.NONE/RELATIVE**. | See `best-practices.md`. |

<a id="930"></a>
## 9.3.0 / 9.3.1 (2026-01-16 / 2026-01-29)

9.3.1 fixes JUnit3 test discovery, `setScanForTestClasses(false)` that skipped JUnit 4 tests, incorrect JUnit XML file names, build-cache failures with emoji or non-BMP output names, and cross-project dependency manipulation. It also fixes **two security advisories**: repositories with unknown or unresponsive hosts were not disabled, so a dependency could resolve from an incorrect repository. **Use 9.3.1. Do not stay on 9.3.0.**

| Feature | Action |
|---|---|
| **The HTML test report is restructured.** Nested classes are shown under their outer class. Parameterized methods are grouped into a suite. Suites contain their classes. **Packages are no longer shown as containers.** Stdout and stderr are attached to the individual test, not to the class. | Update scripts and tools that parse the HTML report. XML reports are unchanged. Tell users that the report looks different. |
| **The Problems report is rendered in the console** with `--warning-mode=all`. | Use `./gradlew help --warning-mode=all` in the audit to see deprecations inline. |
| **Repositories are disabled for more failure types**, for example an incorrect hostname. They stay disabled for the build. Resolution fails and does not silently continue to the next repository. | Correct all repository URL errors. They now cause failures. This is the reproducibility and security fix. |
| New best practices: **Use Convention Plugins**, **Validate Gradle wrapper JAR checksum**, **Use unique output files and directories**. | See `best-practices.md`. |

<a id="940"></a>
## 9.4.0 / 9.4.1 (2026-03-04 / 2026-03-19)

9.4.1 fixes a Kotlin plugin variant resolution error, build-script cache keys that included the build directory path, "file name too long" in nested test reports, a progress-bar clearing defect, and a `projects` task lifecycle error. Use 9.4.1.

| Feature | Action |
|---|---|
| **Non-class-based testing** on the JUnit Platform: `testDefinitionDirs`. Engines such as Cucumber can discover resource-based tests without a placeholder runner. | Propose a separate migration if it is useful. Do not delete product or test runner sources in this skill. Keep the engine configuration and the scenario selection. A build-only experiment can set `testDefinitionDirs` and the existing engine dependencies on the applicable test runtime configuration. Compare scenario identities and outcomes. Build success alone is not sufficient. |
| **PMD plugin**: CSV, Code Climate and SARIF report formats. Configure them on the `Pmd` task, for example `tasks.named('pmdMain', Pmd) { reports { sarif.required = true } }`. | If PMD results go to a security dashboard, enable SARIF. |
| **Wrapper Bearer-token authentication** for the distribution download, with per-host credentials. | Use it for builds that download Gradle from an internal artifact server with token authentication. |
| **The configuration cache is reused when `gradle.properties` changes**, if the build does not read the changed property at configuration time. | Same action as 9.1: read properties through providers wired to task inputs. |
| **Stricter plugin validation** is enabled automatically for projects that apply `maven-publish`, `ivy-publish` or `com.gradle.plugin-publish`. It is not enabled for buildSrc or included builds. | If the project publishes a plugin, correct all new `validatePlugins` failures. Consider `tasks.named('validatePlugins') { enableStricterValidation = true }` in all projects. |
| `org.gradle.tooling.parallel` separates IDE-sync parallelism from `org.gradle.parallel`. | Optional. Set `org.gradle.tooling.parallel=true` and `org.gradle.parallel=false` if task-level parallelism causes problems but IDE sync must stay fast. |
| New documentation section **Securing Your Gradle Builds**. New best practice **Prefer the -bin distribution**. | Make sure that `distributionUrl` ends in `-bin.zip`, not `-all.zip`. |

<a id="950"></a>
## 9.5.0 (2026-04-28)

| Feature | Action |
|---|---|
| **Task provenance**: failure messages name the script or plugin that registered the task. `./gradlew tasks --provenance` and `help --task X` show it. | Use it in audits to find which `subprojects {}` block or legacy script defined a task. Do this before you extract convention plugins. |
| **Wrapper download retries**: `retries=3` and `retryBackOffMs=1000` in `gradle-wrapper.properties`. Off by default. | Recommend them for unreliable networks. |
| `gradle init --into <dir>` creates the target directory. | This applies only when you scaffold new projects. |
| `GRADLE_DAEMON_BIND_ADDRESS` environment variable for restricted network setups. | Use it only if daemon connection problems occur in restricted networks or containers. |
| `--develocity-url https://…` publishes a Build Scan without a change to the build. | This publishes build data to that URL. Do not add it as part of an audit unless the user wants scans. |

<a id="960"></a>
## 9.6.0 / 9.6.1 (2026-06-18 / 2026-06-26)

9.6.1 fixes dependency-cache file permissions, a 0600 to 0644 regression, and a `DefaultBuildOperationQueue` deadlock. It adds `org.gradle.console.interactive` as a property. Use 9.6.1.

| Feature | Action |
|---|---|
| **`--non-interactive`** and `org.gradle.console.interactive=false` disable all prompts. | Set it for unattended and agent-driven builds. |
| **DEPRECATION: implicit property and method lookup in parent projects.** In the Groovy DSL, a `child/build.gradle` that refers to `foo` defined through `ext.foo` in the root now warns. `findProperty()`, `property()` and `hasProperty()` that resolve from a parent also warn. **Removed in Gradle 10.** Opt into the future behavior early with `enableFeaturePreview('NO_IMPLICIT_LOOKUP_IN_PARENT_PROJECTS')` in `settings.gradle`. | This is the most common Groovy DSL deprecation in multi-project builds. Fixes: move shared values to the root `gradle.properties` and read them with `providers.gradleProperty(...)`. Or move them into a convention plugin extension. Or refer to them explicitly as `rootProject.ext.foo`. The explicit reference is the least preferred fix. See `gradle-10-deprecations.md`. |
| Documentation: new practices **Avoid afterEvaluate** and **Validate the Gradle Wrapper**, updated. | See `best-practices.md`. |

<a id="970"></a>
## 9.7.0 / 9.7.1 (2026-08 / 2026-08-19), current

9.7.1 fixes `BaseExecSpec` stream API conformance, the "Click to see difference" format for failed tests in IDEs, bundled Antlr that leaked into the kapt classpath, a `Transformer` regression, `ant.taskdef` classloading, and `@Option` annotation argument order in Kotlin scripts. Use 9.7.1.

| Feature | Action |
|---|---|
| **Isolated Projects** is incubating: `org.gradle.isolated-projects=true`. The legacy `org.gradle.unsafe.isolated-projects` property names are deprecated. **"Not yet recommended for production use."** | Rename all `org.gradle.unsafe.isolated-projects*` properties. Do not enable the feature by default. Optionally, run once with `org.gradle.isolated-projects.diagnostics=true` to list cross-project violations such as `project(':x').tasks`. |
| TestNG 7.10 or later: `threadPoolFactoryClass` must implement `IExecutorServiceFactory`. | This applies only if the project sets `threadPoolFactoryClass`. |
| Dependency verification: `origin` and `reason` attributes on `<trusted-key>` and `<pgp>`. Failure messages say how many other keys are already trusted for the module or group. This is a key-rotation signal. New schema `dependency-verification-1.4.xsd`. | If verification is enabled, annotate trusted keys when you add them. |
| **`reproducibleFileTimestamp`** on archive tasks applies `SOURCE_DATE_EPOCH`: `tasks.withType(AbstractArchiveTask).configureEach { reproducibleFileTimestamp = providers.environmentVariable('SOURCE_DATE_EPOCH').map { java.time.Instant.ofEpochSecond(it as long).toEpochMilli() } }`. | Use it for reproducible-builds compliance. See the "byte-for-byte reproducible" practice. |
| **Groovydoc supports Java toolchains** through `javaLauncher` and a `maxMemory` property. It runs in a worker. | If the project generates Groovydoc, no change is necessary unless it needs a specific JDK. |
| **Lazy variants of eager `File` properties** on built-in tasks, incubating: `Javadoc.destinationDirectory`, `War.webXmlFile`, `CreateStartScripts.outputDirectory`, and 11 more across `Groovydoc`, `ScalaDoc`, `GenerateMavenPom`, `GroovyCompileOptions`, `JacocoTaskExtension`, `CodeQualityExtension` and `ProcessForkOptions`. The old getters still work and share state. | When you rewrite, use `destinationDirectory = layout.buildDirectory.dir('docs/javadoc')`. Do not use `destinationDir = file(...)`. Mark the feature as incubating in the report. |
| **File system watching works with a custom `--project-cache-dir`** or `org.gradle.projectcachedir`. | If the project moved `.gradle/` out of the tree and disabled `org.gradle.vfs.watch`, enable it again. |
| **`ENHANCED_GRAPH_ORDERING` feature preview**: classpath ordering ignores constraint edges. It becomes the default in Gradle 10. Sort orders: `DEFAULT`, breadth-first, `CONSUMER_FIRST`, `DEPENDENCY_FIRST`. | If the build is sensitive to classpath order, for example shading, SPI loading or resource shadowing, test with `enableFeaturePreview('ENHANCED_GRAPH_ORDERING')` in `settings.gradle` before Gradle 10. |
| Seven new best practices: task names, `Project` in task actions, `map` and `flatMap`, attributes on configurations, `@Incubating`, reproducible output, untrusted projects. The configuration cache documentation is rewritten. | See `best-practices.md`. |
