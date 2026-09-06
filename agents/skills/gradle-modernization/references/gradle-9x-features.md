# Gradle 9.x Features by Version

Source: official release notes at `https://docs.gradle.org/<version>/release-notes.html`. Documentation review: Sept 2026; latest release listed here 9.7.1 (2026-08-19). ACT items still need an applicability check against the actual build and the user's approval of the change group.

Each entry is tagged:
- **ACT** — something to change in a Java project's build to adopt it
- **AUTO** — happens automatically on upgrade, nothing to change, but may need awareness
- **INFO** — plugin-author or tooling change; only relevant if the project has custom plugins/tasks

Use SKILL.md's prerequisite-ordered wrapper procedure with a compatible exact version and its checksum. From 9.0.0 a partial version works, but discovering the newest version is not a compatibility decision; pin an exact version.

## Contents

- [9.0.0 (2025-07-31) — major release](#900)
- [9.1.0 (2025-09-18)](#910)
- [9.2.0 / 9.2.1 (2025-10 / 2025-11-17)](#920)
- [9.3.0 / 9.3.1 (2026-01-16 / 2026-01-29)](#930)
- [9.4.0 / 9.4.1 (2026-03-04 / 2026-03-19)](#940)
- [9.5.0 (2026-04-28)](#950)
- [9.6.0 / 9.6.1 (2026-06-18 / 2026-06-26)](#960)
- [9.7.0 / 9.7.1 (2026-08 / 2026-08-19)](#970)
- [Quick lookup: feature → minimum version](#quick-lookup)

---

<a id="900"></a>
## 9.0.0 (2025-07-31) — major release

Upgrade guide: https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html

| Tag | Feature | What to do |
|---|---|---|
| **AUTO/ACT** | **Requires JVM 17+ to run Gradle.** Compiling/testing Java 8+ is still supported via toolchains. | If the daemon JVM is < 17, set a daemon toolchain (`./gradlew updateDaemonJvm --jvm-version=21`, stable since 9.2) or ensure CI uses JDK 17+. Keep `java { toolchain { languageVersion = JavaLanguageVersion.of(N) } }` for the project's own target. |
| **AUTO** | **Groovy 4** embedded (was Groovy 3). Affects `.gradle` scripts. | Rare breakages: `Map`/GString coercions, removed `groovy.util` classes (`XmlSlurper` → `groovy.xml.XmlSlurper`), `@Grab`. Run `./gradlew help --warning-mode=all` after upgrade. |
| **AUTO** | Kotlin 2.2 embedded, JSpecify nullability annotations on the Gradle API. | Only matters for Kotlin build logic / binary plugins. |
| **ACT** | **Configuration Cache is the preferred mode.** Gradle prompts to enable it if no incompatibilities are found. Unsupported workloads may fall back instead of failing. | Follow `verification.md`: strict store/reuse plus actual task execution on the CI workload before enabling the property. Fallback is not proof of compatibility. |
| **AUTO** | **Reproducible archives by default.** `Jar`, `War`, `Zip`, `Tar`, `Ear` now have deterministic file order, fixed timestamps, normalized permissions. | Remove any manual `preserveFileTimestamps = false` / `reproducibleFileOrder = true` — they're redundant now. If a build *relied* on real timestamps, use `reproducibleFileTimestamp` (9.7.0). |
| **AUTO** | Semantic versioning: all releases are `MAJOR.MINOR.PATCH`. `@Incubating` APIs may change in minor releases. | Pin wrapper to a full version (`9.7.1`), not `9.7`. |
| **ACT** | Wrapper accepts major/minor-only versions: `--gradle-version=9` → latest 9.x.y. | Useful for scripted upgrades; still commit the resolved full version. |
| **AUTO** | `JAVA_HOME` now used for toolchain auto-detection (consistent with IDEs). | Nothing. Reduces "toolchain not found" surprises. |
| **INFO** | Detached configurations can resolve their own project; new `RootComponentIdentifier`. | Only for custom dependency-graph tooling. |
| **INFO** | Kotlin DSL script compilation avoidance (ABI fingerprinting). | N/A for Groovy DSL. |
| **ACT** | **Gradle Best Practices guide launched** in the docs. | This is the source for `best-practices.md`. |

Removals/behaviour changes in 9.0.0 worth checking for in old builds (from the upgrade guide):
- **Custom `Test` tasks no longer inherit the `test` source set's `testClassesDirs`/`classpath`** — they may run zero tests and still succeed. Set both explicitly and compare test counts.
- Selecting a variant by configuration name for Maven repos (`configuration:` on external deps) — removed.
- Many deprecated `Project`/`Task` conventions APIs (`project.convention`, `getConvention()`); use extensions.
- `org.gradle.util.*` internal helpers commonly abused in scripts (`GUtil`, `ConfigureUtil`) — removed.
- `--offline` and other flags unchanged, but `gradle.properties` in subprojects is now discouraged (see 9.2.0 practice).

<a id="910"></a>
## 9.1.0 (2025-09-18)

| Tag | Feature | What to do |
|---|---|---|
| **AUTO** | **Java 25 supported** for the daemon and toolchains. | Toolchain can now target 25. Tooling API users must enable native access (JEP 472). |
| **ACT** | **`--task-graph`** prints the task dependency tree without executing (incubating here, stable in 9.4.0). | Use during audits: `./gradlew build --task-graph`. Replaces third-party "taskTree" plugins. |
| **ACT** | Project report shows physical project locations. | `./gradlew projects` now tells you if a subproject dir is non-standard (see "Avoid empty projects" practice). |
| **ACT** | **`--console=colored`**: colours without progress bars. | Good default for CI logs: `org.gradle.console=colored` in `gradle.properties` or CI env `GRADLE_OPTS`. |
| **AUTO** | Rich console shows "(N lines not showing)" indicator. | Nothing. |
| **AUTO** | Much clearer **version-constraint conflict errors**, with a suggested `dependencyInsight` command. | Nothing; use the suggested command when conflicts appear. |
| **ACT** | **Configuration Cache read-only mode**: `-Dorg.gradle.configuration-cache.read-only=true`. Reuses entries, never writes. | For PR/CI builds that shouldn't pay the cost of storing entries. Main-branch builds populate; PR builds read-only. |
| **AUTO** | Configuration Cache **reused when `-P` properties change** if the property isn't read at configuration time. | Prefer `providers.gradleProperty('x')` wired into task inputs over reading `project.findProperty('x')` at configuration time — the former keeps cache hits. |
| **AUTO** | Encryption keystore honours JVM default type (FIPS-friendly). | Nothing. |
| **INFO** | `AttributeContainer.addAllLater()`, `Gradle.getBuildPath()`, `MavenPublication.pom.distributionManagement {}`. | `distributionManagement` is handy if you publish to GitHub Packages and want it in the POM. |
| **INFO** | Antlr: `packageName` property replaces `-package` argument (the argument form is deprecated, error in 10). Antlr generated sources auto-tracked. | If the project uses the `antlr` plugin: `tasks.named('generateGrammarSource') { packageName = 'com.example.parser' }` and delete manual `outputDirectory` fiddling. |
| **INFO** | EAR: `deploymentDescriptor { version = '11' }` for Jakarta EE 11. | Only for `ear` plugin users. |
| **AUTO** | `--dry-run` now respected in composite builds. | Nothing. |
| **AUTO** | `Project.getDependencyFactory()` promoted to stable. | Nothing. |

<a id="920"></a>
## 9.2.0 / 9.2.1 (2025-10 / 2025-11-17)

9.2.1 fixes startup on arm32/ppc64le/s390x, a `shouldRunAfter` cycle crash, a `DirectoryProperty` decoration failure, and a `ConcurrentModificationException` in task-dependency resolution. Prefer 9.2.1 over 9.2.0.

| Tag | Feature | What to do |
|---|---|---|
| **AUTO** | **Windows on ARM (ARM64)** supported (plain console only). | Nothing. |
| **AUTO** | **Performance**: up to 40 % faster time-to-first-task on large builds (work-graph construction), 7–12 % less memory. Biggest win with a Configuration Cache hit. | Nothing — one more reason to enable the configuration cache. |
| **ACT** | **Daemon toolchain is stable** (was incubating since 8.8). `updateDaemonJvm` writes `gradle/gradle-daemon-jvm.properties`. | Offer pinning the existing compatible daemon JVM independently of compilation/test toolchains. Changing JVM version/vendor is a policy change to offer separately; do not default to 21. |
| **AUTO** | Dependency verification failure messages suggest `--export-keys` when key servers are disabled. | Nothing. |
| **INFO** | `publishing.softwareComponentFactory` exposed; provider-based `addVariantsFromConfiguration(Provider<ConsumableConfiguration>)`. | Only for custom publishing components. |
| **AUTO** | Antlr tasks grouped under "Antlr" in `./gradlew tasks`. | Nothing. |
| **ACT** | New best practices: **Name Your Root Project**, **Do not use gradle.properties in subprojects**, **Apply Exclusions Narrowly**, **Prefer @PathSensitivity.NONE/RELATIVE**. | See `best-practices.md`. |

<a id="930"></a>
## 9.3.0 / 9.3.1 (2026-01-16 / 2026-01-29)

9.3.1 fixes JUnit3 test discovery, `setScanForTestClasses(false)` skipping JUnit 4 tests, wrong JUnit XML file names, build-cache breakage with emoji/non-BMP output names, cross-project dependency manipulation, and **two security advisories** (repositories with unknown/unresponsive hosts were not being disabled → risk of resolving from a wrong repo). **Prefer 9.3.1; do not stay on 9.3.0.**

| Tag | Feature | What to do |
|---|---|---|
| **AUTO** | **HTML test report restructured**: nested classes shown under their outer class; parameterized methods grouped into a suite; suites contain their classes; **packages no longer shown as containers**; stdout/stderr attached to the individual test, not the class. | Nothing in the build. Tell users their test report looks different. CI tooling that scraped the HTML report may need updating; XML reports are unchanged. |
| **AUTO** | Aggregate test reports (`test-report-aggregation` plugin / `TestReport`) support overlapping structures — one tab per source. | Nothing. |
| **ACT** | **Problems report rendered in console** with `--warning-mode=all`. | Use `./gradlew help --warning-mode=all` in the audit to see deprecations inline. |
| **AUTO** | Worker exit code 137 etc. now explained ("likely SIGKILL / OOM"). | If you see this, raise `org.gradle.jvmargs` / worker memory. |
| **INFO** | `AttributeContainer.named(Class, String)` — `attribute(Usage.USAGE_ATTRIBUTE, named(Usage, 'java-runtime'))` without `objects`. | Slightly tidier custom configurations. |
| **INFO** | TestKit `BuildResult.getOutputReader()` streams output. | Plugin functional tests with big logs. |
| **AUTO** | Gradle distributions now ship `.asc` PGP signatures alongside `.sha256`. | Supports the "validate distribution checksum" practice. |
| **AUTO** | **Repositories are disabled for more failure types** (e.g. bad hostname) and stay disabled for the build → resolution fails rather than silently falling through to the next repo. | Fix any repository URL typos; they now fail loudly. This is the reproducibility/security fix. |
| **AUTO** | `AbstractArchiveTask.useFileSystemPermissions()` promoted. | Nothing. |
| **ACT** | New best practices: **Use Convention Plugins**, **Validate Gradle wrapper JAR checksum**, **Use unique output files and directories**. | See `best-practices.md`. |

<a id="940"></a>
## 9.4.0 / 9.4.1 (2026-03-04 / 2026-03-19)

9.4.1 fixes a Kotlin plugin variant resolution error, build-script cache keys including the build dir path, "file name too long" in nested test reports, a progress-bar clearing bug, and a `projects` task lifecycle error. Prefer 9.4.1.

| Tag | Feature | What to do |
|---|---|---|
| **AUTO** | **Java 26 supported** for daemon and toolchains. | Toolchain can target 26. |
| **ACT** | **Non-class-based testing** on JUnit Platform: `testDefinitionDirs`. Engines such as Cucumber can discover resource-based tests without a placeholder runner. | Propose a separate migration if useful. Do not delete product/test runner sources in this skill. Preserve engine configuration and scenario selection; a build-only experiment can set `testDefinitionDirs` and existing engine dependencies on the appropriate test runtime configuration. Compare scenario identities/outcomes, not just build success. |
| **AUTO** | JUnit `TestReporter.publishEntry/publishFile` data captured into HTML (Data / Attachments tabs) and XML (`<properties>`, `[[ATTACHMENT|path]]`). | Nothing; UI-test screenshots on failure now show in the report. |
| **INFO** | `Test.addTestMetadataListener(TestMetadataListener)`. | Copy attachments to CI artifact dirs, etc. |
| **AUTO** | Progress bars: ligature-safe, Unicode, OSC 9;4 native progress in Ghostty/iTerm2. | Nothing. |
| **AUTO** | Problems HTML report redesigned. `org.gradle.warning.mode=none` suppresses the report link (report still generated). | Nothing. |
| **ACT** | **PMD plugin**: CSV, Code Climate, SARIF report formats (configure on the `Pmd` task, e.g. `tasks.named('pmdMain', Pmd) { reports { sarif.required = true } }`). | If PMD results feed a security dashboard, enable SARIF. |
| **ACT** | **Wrapper Bearer-token auth** for distribution download, per-host credentials. | For builds downloading Gradle from an internal artifact server with token auth. |
| **AUTO** | Daemon logs older than 14 days auto-cleaned. | Nothing. |
| **INFO** | `Configuration.extendsFrom(Provider<Configuration>)` — no more `.get()` when wiring `dependencyScope` → `resolvable`. | Tidier custom configurations: `extendsFrom(parent)` instead of `extendsFrom(parent.get())`. |
| **AUTO** | **Configuration Cache reused when `gradle.properties` changes** if the changed property isn't read at configuration time. | Same advice as 9.1: read properties via providers wired to task inputs. |
| **AUTO** | Configuration Cache report names the *kind* of closure (doLast / onlyIf / cacheIf …) that captured unsupported state. | Makes CC migration easier. |
| **INFO** | `java-gradle-plugin`: plugin `id` defaults to the registration name. | `register('com.example.conventions') { implementationClass = '...' }` — drop the redundant `id =`. |
| **INFO** | **Stricter plugin validation** auto-enabled for projects applying `maven-publish`/`ivy-publish`/`com.gradle.plugin-publish` (not for buildSrc / included builds). | If publishing a plugin, fix any new `validatePlugins` failures. Consider `tasks.named('validatePlugins') { enableStricterValidation = true }` everywhere. |
| **ACT** | `org.gradle.tooling.parallel` decouples IDE-sync parallelism from `org.gradle.parallel`. | Optional: `org.gradle.tooling.parallel=true` + `org.gradle.parallel=false` if task-level parallelism causes issues but IDE sync should stay fast. |
| **AUTO** | `--task-graph` promoted to stable. `ProjectLayout.getSettingsDirectory()` promoted. | Nothing. |
| **ACT** | New docs section **Securing Your Gradle Builds**; new best practice **Prefer the -bin distribution**. | Check `distributionUrl` ends in `-bin.zip`, not `-all.zip`. |

<a id="950"></a>
## 9.5.0 (2026-04-28)

| Tag | Feature | What to do |
|---|---|---|
| **ACT** | **Task provenance**: failure messages say which script/plugin registered the task; `./gradlew tasks --provenance` and `help --task X` show it. | Use in audits to find which `subprojects {}` block or legacy script defined a task before extracting convention plugins. |
| **AUTO** | INFO-level log explains why an existing daemon was rejected (JVM incompatible). | Diagnostic only. |
| **ACT** | **Wrapper download retries**: `retries=3` / `retryBackOffMs=1000` in `gradle-wrapper.properties` (off by default). | Recommend for CI with flaky networks. |
| **INFO** | Type-safe accessors for precompiled **Kotlin** *settings* plugins. | N/A for Groovy. |
| **ACT** | `gradle init --into <dir>` creates the target directory. | Only when scaffolding new projects. |
| **INFO** | `DomainObjectCollection.disallowChanges()` locks a container. | Plugin authors protecting their configured collections. |
| **ACT** | `GRADLE_DAEMON_BIND_ADDRESS` env var for restricted network setups. | Only if daemon connection issues appear in locked-down CI/containers. |
| **ACT** | `--develocity-url https://…` publishes a Build Scan without touching the build. | Publishes build data to that URL; don't add it as part of an audit unless the user wants scans. |
| **AUTO** | `--help` output grouped into sections. Tooling API exposes help/version. Samples page removed from docs (examples inline now). | Nothing. |

<a id="960"></a>
## 9.6.0 / 9.6.1 (2026-06-18 / 2026-06-26)

9.6.1 fixes dependency-cache file permissions (0600 → 0644 regression), a `DefaultBuildOperationQueue` deadlock, and adds `org.gradle.console.interactive` as a property. Prefer 9.6.1.

| Tag | Feature | What to do |
|---|---|---|
| **AUTO** | Configuration Cache reused across `org.gradle.project.*` system props and `ORG_GRADLE_PROJECT_*` env vars when unused at configuration time (parity with 9.1's `-P` and 9.4's `gradle.properties`). | Big CI win for builds passing many project properties. |
| **ACT** | **`--non-interactive`** / `org.gradle.console.interactive=false`: disables all prompts. | Set on CI and for agent-driven builds. |
| **AUTO** | **`NO_COLOR`** env var honoured. | Nothing. |
| **AUTO** | HTML test report columns are sortable. | Nothing. |
| **ACT** | **DEPRECATION — implicit property/method lookup in parent projects.** In Groovy DSL, `child/build.gradle` referencing `foo` defined via `ext.foo` in the root now warns; `findProperty()`, `property()`, `hasProperty()` resolving from a parent also warn. **Removed in Gradle 10.** Opt into the future behaviour early with `enableFeaturePreview('NO_IMPLICIT_LOOKUP_IN_PARENT_PROJECTS')` in `settings.gradle`. | This is the single most common Groovy-DSL deprecation in multi-project builds. Fixes: move shared values to `gradle.properties` (root) and read via `providers.gradleProperty(...)`, or into a convention plugin extension, or reference explicitly `rootProject.ext.foo` (least preferred). See `gradle-10-deprecations.md`. |
| **AUTO** | **Groovy DSL type coercion for lazy properties**: `String` → `File`/`RegularFileProperty`/`DirectoryProperty` (relative to project dir); single `T` or `T[]` → `ListProperty<T>`/`SetProperty<T>`. | Assignments that used to throw `IllegalArgumentException` now just work — makes plugin `Property<T>` migrations less disruptive for Groovy users. |
| **INFO** | `validatePlugins` gives specific errors for `@Optional` misuse (no I/O annotation; combined with `@Internal`). | Plugin authors. |
| **AUTO** | **Lower I/O**: file-based journals rewritten; big gains on low-IOPS cloud CI storage (EBS etc.). | Nothing; expect faster CI. |
| **AUTO** | `Wrapper.getNetworkTimeout()` promoted. | Nothing. |
| **ACT** | Docs: **Gradle on CI** section returns (GitHub Actions, GitLab CI, Jenkins, TeamCity, CircleCI, Travis, Docker). New practices **Avoid afterEvaluate**, **Validate the Gradle Wrapper** (updated). | See `best-practices.md`. |

<a id="970"></a>
## 9.7.0 / 9.7.1 (2026-08 / 2026-08-19) — current

9.7.1 fixes `BaseExecSpec` stream API conformance, the "Click to see difference" format for failed tests in IDEs, bundled Antlr leaking into the kapt classpath, a `Transformer` regression, `ant.taskdef` classloading, and `@Option` annotation argument order in Kotlin scripts. Prefer 9.7.1.

| Tag | Feature | What to do |
|---|---|---|
| **INFO** | **Isolated Projects** moves from experimental to **incubating**: `--isolated-projects` / `org.gradle.isolated-projects=true`. Parallel project configuration; foundation for incremental configuration. Diagnostics mode: `org.gradle.isolated-projects.diagnostics=true`. Legacy `org.gradle.unsafe.isolated-projects` names deprecated. Requires Configuration Cache compatibility. **"Not yet recommended for production use."** | Do not enable by default. Optionally run once with diagnostics to list cross-project `project(':x').tasks`-style violations — those are also things convention plugins fix. Rename any `org.gradle.unsafe.isolated-projects*` properties. |
| **INFO** | `ResolutionResult` can be a task input under Configuration Cache (`configurations.runtimeClasspath.map { it.incoming.resolutionResult }`). | Simplifies SBOM/license-report tasks. |
| **INFO** | Third-party `-javaagent:` (e.g. JaCoCo) works with Configuration Cache in TestKit daemon mode. | Plugin authors measuring coverage of functional tests. |
| **AUTO** | Fewer spurious CC invalidations from IntelliJ (`idea.io.use.nio2` now set every build). | Nothing; IDE users get more cache hits. |
| **AUTO** | **Resilient sync**: partial models returned to IDEs when part of the build fails (IntelliJ 2026.2+). | Nothing. |
| **AUTO** | Test framework **initialization failures always logged to console** (TestNG constructor exceptions, JUnit 4 suite failures, Jupiter `@BeforeAll` aborts). `TestFailureDetails.isFrameworkFailure()`. | Nothing; previously you had to open the XML to see these. |
| **INFO** | TestNG 7.10+ `threadPoolFactoryClass` must implement `IExecutorServiceFactory`. | Only if the project sets `threadPoolFactoryClass`. |
| **AUTO** | Source locations for up to 2050 problems per build (was 50). `--warning-mode=all` removes the cap. | Better deprecation triage. |
| **ACT** | Dependency verification: `origin` / `reason` attributes on `<trusted-key>` and `<pgp>`; failure messages say how many other keys are already trusted for the module/group (key-rotation signal). New schema `dependency-verification-1.4.xsd`. | If verification is on, annotate trusted keys when adding them. |
| **ACT** | **`reproducibleFileTimestamp`** on archive tasks — honour `SOURCE_DATE_EPOCH`: `tasks.withType(AbstractArchiveTask).configureEach { reproducibleFileTimestamp = providers.environmentVariable('SOURCE_DATE_EPOCH').map { java.time.Instant.ofEpochSecond(it as long).toEpochMilli() } }`. | For reproducible-builds compliance (the "byte-for-byte reproducible" practice). |
| **INFO** | `ResolvedArtifactResult.getAttributes()/getCapabilities()` (`getVariant()` to be deprecated); `BuildCacheEntryWriter.getInputStream()`; `DomainObjectCollection.getElements()` provider. | Plugin authors. |
| **ACT** | **Groovydoc supports Java toolchains** (`javaLauncher`) and a `maxMemory` property, runs in a worker. | If the project generates Groovydoc, nothing to change unless it needs a specific JDK. |
| **ACT** | **Lazy variants of eager `File` properties** on built-in tasks (incubating): `Javadoc.destinationDirectory`, `War.webXmlFile`, `CreateStartScripts.outputDirectory`, and 11 more across `Groovydoc`, `ScalaDoc`, `GenerateMavenPom`, `GroovyCompileOptions`, `JacocoTaskExtension`, `CodeQualityExtension`, `ProcessForkOptions`. Old getters still work and share state. | When rewriting, prefer `destinationDirectory = layout.buildDirectory.dir('docs/javadoc')` over `destinationDir = file(...)`. Mark as incubating in the report. |
| **AUTO** | Kotlin DSL accessor generation no longer stored in the build cache. | N/A for Groovy. |
| **ACT** | **File system watching works with a custom `--project-cache-dir`** / `org.gradle.projectcachedir`. | If the project moved `.gradle/` out of the tree and disabled `org.gradle.vfs.watch`, re-enable it. |
| **INFO** | **`ENHANCED_GRAPH_ORDERING` feature preview** — classpath ordering ignores constraint edges; becomes default in Gradle 10. Sort orders: `DEFAULT` (breadth-first), `CONSUMER_FIRST`, `DEPENDENCY_FIRST`. | Test with `enableFeaturePreview('ENHANCED_GRAPH_ORDERING')` in `settings.gradle` before Gradle 10 if the build is sensitive to classpath order (shading, SPI loading, resource shadowing). |
| **AUTO** | `DependencyHandler.project()` / `project(String)` and `DependencyFactory.createProjectDependency(...)` promoted to stable. | Nothing. |
| **ACT** | Seven new best practices (task names, `Project` in task actions, `map`/`flatMap`, attributes on configurations, `@Incubating`, reproducible output, untrusted projects) + Configuration Cache docs overhaul. | See `best-practices.md`. |

---

<a id="quick-lookup"></a>
## Quick lookup: feature → minimum version

| Want this | Needs |
|---|---|
| Configuration cache prompt + graceful fallback | 9.0.0 |
| Reproducible archives by default | 9.0.0 |
| Daemon runs on JDK 17+ only | 9.0.0 |
| `--task-graph` | 9.1.0 (stable 9.4.0) |
| `--console=colored` | 9.1.0 |
| CC read-only mode | 9.1.0 |
| CC survives unused `-P` changes | 9.1.0 |
| Java 25 toolchain/daemon | 9.1.0 |
| Antlr `packageName` | 9.1.0 |
| Daemon toolchain stable (`updateDaemonJvm`) | 9.2.0 |
| Windows ARM64 | 9.2.0 |
| Problems in console with `--warning-mode=all` | 9.3.0 |
| Strict repository disabling (security fix) | 9.3.1 |
| Restructured HTML test report | 9.3.0 |
| Non-class-based tests / Cucumber without workaround | 9.4.0 |
| PMD SARIF/CSV/CodeClimate | 9.4.0 |
| Wrapper Bearer-token auth | 9.4.0 |
| CC survives unused `gradle.properties` changes | 9.4.0 |
| `extendsFrom(Provider)` | 9.4.0 |
| Java 26 | 9.4.0 |
| Task provenance / `tasks --provenance` | 9.5.0 |
| Wrapper download retries | 9.5.0 |
| `--non-interactive`, `NO_COLOR` | 9.6.0 |
| Groovy DSL lazy-property coercions | 9.6.0 |
| Parent-project lookup deprecation + `NO_IMPLICIT_LOOKUP_IN_PARENT_PROJECTS` | 9.6.0 |
| CC survives unused env/sys-prop project properties | 9.6.0 |
| `reproducibleFileTimestamp` / SOURCE_DATE_EPOCH | 9.7.0 |
| Lazy `destinationDirectory` etc. on built-in tasks | 9.7.0 (incubating) |
| Isolated Projects incubating | 9.7.0 |
| `ENHANCED_GRAPH_ORDERING` preview | 9.7.0 |
| FS watching with custom project cache dir | 9.7.0 |
