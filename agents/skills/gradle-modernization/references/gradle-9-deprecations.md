# Gradle 9 Readiness: Deprecations to Clear on 8.x

Gradle 9.0.0 was released on 2025-07-31. Source: the [Gradle 8.14.5 upgrade guide](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html), cross-checked against the [9.0 major upgrade guide](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html). This file is a triage index for a build that is on 8.x and wants to move to 9.x. It is not a complete compatibility certificate.

Use it together with `gradle-10-deprecations.md`. That file lists what 9.0 removed, under "Removed in 9.0", and what 9.x deprecates for Gradle 10. This file lists what 8.x deprecated and how to find it in a Groovy build.

Before the 8.x to 9.x transition:
1. Move to 8.14.5 first and clear its warnings. The upgrade guide recommends the latest 8.x before the major upgrade. 8.14.4 fixed two security advisories.
2. Read this file, the pinned 8.x guide, and the 9.0 major guide. Then read `gradle-10-deprecations.md` for the 9.x target version.
3. Include breaking changes and changed bundled-tool defaults, even if the current build shows no warning. See "Breaking changes per 8.x version" below.
4. If you cannot read the official sources, mark the upgrade coverage as incomplete.

Collect the real list from the verification workload:

```bash
./gradlew help --warning-mode=all                   # deprecations at configuration time
./gradlew <verification-tasks> --warning-mode=all   # task-specific warnings
```

From 8.11, open `build/reports/problems/problems-report.html`. It lists every deprecation with its location. Before 8.11, use `--warning-mode=all` and a Build Scan.

## Announced for removal in Gradle 9

Source: the 8.x upgrade guide. These are the items that a Java Groovy DSL build hits most often.

| Deprecated in | Item | Replacement |
|---|---|---|
| 8.2 | **Plugin conventions**: top-level `sourceCompatibility = 17`, `archivesBaseName`, `libsDirName`, `distsDirName`, `applicationDefaultJvmArgs`, `webAppDirName`, `appDirName`, `projectReportDirName`, and `project.convention` | `java { sourceCompatibility = JavaVersion.VERSION_17 }` or a toolchain; `base { archivesName = ...; libsDirectory = ...; distsDirectory = ... }`; `application { applicationDefaultJvmArgs = [...] }`; `war { webAppDirectory = file(...) }`; `ear { appDirectory = file(...) }`; `tasks.withType(HtmlDependencyReportTask).configureEach { projectReportDirectory = ... }`. Removed in 9.0.0. |
| 8.11 | **`project.exec {}` and `project.javaexec {}`**, also bare `exec {}` in scripts | In task actions inject `ExecOperations`. At configuration time use `providers.exec {}` or a `ValueSource`. Removed in 9.0.0. |
| 8.1 | **Custom `Test` tasks that inherit `testClassesDirs` and `classpath`** from the `test` source set | Set both explicitly. In 9.0.0 such tasks run zero tests and succeed. |
| 8.1 | **A `Test` task that succeeds when test sources exist but no test ran** | Fix the framework selection, usually `useJUnitPlatform()`. In 9.0.0 this is an error unless `failOnNoDiscoveredTests = false`. |
| 8.2 | **Test framework runtime dependencies supplied by Gradle** | `testRuntimeOnly 'org.junit.platform:junit-platform-launcher'` for JUnit 5 and Vintage. JUnit 4 and TestNG are unaffected. JVM test suites add these automatically. |
| 8.10 | **The daemon on JVM 8 to 16** | Run the daemon on JVM 17 or later through `JAVA_HOME`, `org.gradle.java.home` or the daemon JVM criteria. Keep compilation and tests on older JVMs through toolchains. Enforced in 9.0.0. |
| 8.11 | **`configuration: 'conf'` on a Maven dependency** and `targetConfiguration` | Remove it. Use attributes or capabilities. Selection by configuration name stays permitted for Ivy components and local projects. |
| 8.3 | **`ClientModule`**: `implementation module('org:foo:1.0') { dependency 'org:bar:1.0' }` | A plain coordinate plus a `ComponentMetadataRule` registered with `dependencies.components.withModule(...)`. |
| 8.1, 8.5, 8.7 | **`org.gradle.util` helpers**: `ConfigureUtil`, `GUtil.toCamelCase`, `WrapUtil.toDomainObjectSet`, `VersionNumber`, `CollectionUtils.stringize` | `Action<T>` parameters instead of `Closure`, plain string and collection code, `GradleVersion` for Gradle versions. 9.0.0 removed `ConfigureUtil`, `ClosureBackedAction` and `CollectionUtils`. |
| 8.11 | **`options.define(encoding: 'UTF-8')`, `options.fork(memoryMaximumSize: '1G')`, `options.debug(debugLevel: 'lines')`** and the setters `setForkOptions`, `setDebugOptions` | `options.encoding = 'UTF-8'`; `options.fork = true; options.forkOptions.memoryMaximumSize = '1G'`; `options.debug = true; options.debugOptions.debugLevel = 'lines'`. |
| 8.8 | **Mutating a configuration after it was observed**: `incoming.beforeResolve { dependencies.add(...) }`, `extendsFrom` or excludes after resolution | `dependencies.addLater(provider)`, `prefer` constraints, `withDependencies {}` or component metadata rules, roles set at creation. |

Two common Groovy DSL patterns are deprecated but are not 9.0 removals. They do not block the upgrade on their own:
- `"$buildDir/..."` and `project.buildDir`, since 8.3, no removal version, no warning printed in 8.x. Replace with `layout.buildDirectory.file(...)` or `.dir(...)`.
- Space assignment `group 'com.example'`, `version '1.0'`, `jvmArgs '-Xmx1g'`, since 8.12, removal in 10.0.0. Replace with `group = 'com.example'` or an explicit call `jvmArgs('-Xmx1g')`. See `gradle-10-deprecations.md`.

### Groovy, JVM and build-logic checks

Each row records the version that deprecated the item, the removal version and the source anchor. `null` means that the 8.x guide names no removal version. Do not infer 9.0 from the chapter. Where the 9.0 major guide confirms a removal, the row says so. The source links are pinned to 8.14.5. Check the actual receiver types and the execution context before you rewrite. A code pattern alone is not proof of a warning.

| Since | Removal | Check and migration | Official source |
|---|---|---|---|
| 8.1 | 9.0.0 | `canBeConsumed = false` or `canBeResolved = false` applied to configurations that core plugins created, such as `implementation` or `runtimeClasspath`. Remove the setting. Create your own configuration with the intended role. `setCanBeConsumed(false)` on `apiElements` and `runtimeElements` does not warn. | [core usage](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#configurations_allowed_usage) |
| 8.1 | 9.0.0 | A configuration named `detachedConfiguration` or `detachedConfiguration<N>`. Rename it. | [reserved names](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#reserved_configuration_names) |
| 8.1 | 9.0.0 | `java { withJavadocJar(); withSourcesJar(); consistentResolution {} }` in a project that applies only `java-base`. Apply `java` or another JVM plugin, or drop the calls. | [java component](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#java_extension_without_java_component) |
| 8.1 | 9.0.0 | `tasks.register('x', Test)` or `task x(type: Test)` without `testClassesDirs` and `classpath`. Set both: `testClassesDirs = sourceSets.integrationTest.output.classesDirs; classpath = sourceSets.integrationTest.runtimeClasspath`. Or register the task as a target of a test suite. Keep the existing `useJUnitPlatform()`, filters and system properties. Confirmed in 9.0.0: such tasks run zero tests. | [Test classpath](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#test_task_default_classpath), [9.0](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#test_tasks_may_no_longer_execute_expected_tests) |
| 8.1 | 9.0.0 | A `Test` task that succeeds with test sources but no executed test. Check the framework selection and the filters. Confirmed in 9.0.0: the task fails unless `failOnNoDiscoveredTests = false`. | [no tests](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#test_task_fail_on_no_test_executed), [9.0](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#test_task_fails_when_no_tests_are_discovered) |
| 8.1 | 9.0.0 | `components.java.withVariantsFromConfiguration(...) { skip() }` or other Gradle Module Metadata edits after `publishing.publications.<name>.artifacts` was read. Move the component changes before any code that reads the publication. Confirmed in 9.0.0. | [GMM](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#gmm_modification_after_publication_populated) |
| 8.1 | 9.0.0 | Tests on JVM 6 or 7 through `executable` or a toolchain. Run tests on JVM 8 or later. | [test JVM](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#minimum_test_jvm_version) |
| 8.1 | 9.0.0 | A `ValidatePlugins` task, usually from `java-gradle-plugin`, in a project without a JVM plugin. Apply `jvm-toolchains` or `java-library`. Confirmed in 9.0.0. | [validatePlugins](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#validate_plugins_without_java_toolchain) |
| 8.1 | 9.0.0 | `ConfigureUtil`, `GUtil.toCamelCase`, `GUtil.toLowerCase`, `WrapUtil.toDomainObjectSet` in `buildSrc` or scripts. Replace `ConfigureUtil.configure(closure, obj)` with `Action`-typed methods or `project.configure(obj, closure)`. Confirmed: 9.0.0 removed `ConfigureUtil`. | [org.gradle.util 8.1](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#org_gradle_util_reports_deprecations_80) |
| 8.1 | 9.0.0 | `vendor = JvmVendorSpec.IBM_SEMERU`. Use `JvmVendorSpec.IBM`. Confirmed in 9.0.0. | [IBM Semeru](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#ibm_semeru_should_not_be_used) |
| 8.1 | 9.0.0 | `-b`, `--build-file`, `-c`, `--settings-file` in CI scripts, and `buildFile = ...` on `GradleBuild` tasks. Use the standard file locations and `dir` on `GradleBuild`. Confirmed in 9.0.0. | [build layout](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#configuring_custom_build_layout) |
| 8.1 | null | `org.gradle.cache.cleanup=false` in the user home `gradle.properties`. Use `caches { cleanup = Cleanup.DISABLED }` in an init script. The 8.x guide names no version. 9.0.0 removed the property. | [cache cleanup](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#disabling_user_home_cache_cleanup), [9.0](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#removal_of_org_gradle_cache_cleanup) |
| 8.1 | 9.0.0 | `executable = 'jdk/bin/java'` style relative paths on `Test`, `JavaExec`, `Javadoc` or compile fork options. Use an absolute path, or better a toolchain through `javaLauncher`. | [relative paths](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#no_relative_paths_for_java_executables) |
| 8.1 | 9.0.0 | `convention` or `extensions` read inside `doFirst`, `doLast` or `@TaskAction`. Read the values at configuration time into task inputs. | [task convention](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#task_convention) |
| 8.1 | 9.0.0 | `WarPlugin.configureConfiguration(configurations)` in build logic. Delete it. | [WarPlugin](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#war_plugin_configure_configurations) |
| 8.2 | 9.0.0 | `configurations.implementation.resolve()`, `.files`, `.copy()`, `.resolvedConfiguration` on declarable configurations, and `defaultDependencies {}` or `dependencyConstraints` on resolvable ones. Resolve `compileClasspath` or `runtimeClasspath`. Put `defaultDependencies` on the declarable configuration. `getAllDependencies()` stays allowed everywhere. | [configuration usage](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_configuration_usage) |
| 8.2 | 9.0.0 | `project.convention`, `convention.getPlugin(JavaPluginConvention)`, `convention.plugins`, `HasConvention` in `buildSrc` and scripts. Use `extensions.getByType(...)`, `project.java`, `project.base`, `project.application`. Confirmed in 9.0.0: `Convention`, `HasConvention`, `Project.getConvention()` and `Task.getConvention()` are removed. | [conventions](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_access_to_conventions), [9.0](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#removal_of_conventions) |
| 8.2 | 9.0.0 | Top-level `sourceCompatibility`, `targetCompatibility`, `docsDir`, `testResultsDir`. Wrap in `java {}` or set a toolchain. Preserve the same Java version. The `java` convention is not in the 9.0 removal table, but the `Convention` type it used is gone. | [java](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#java_convention_deprecation) |
| 8.2 | 9.0.0 | Top-level `archivesBaseName`, `libsDirName`, `distsDirName`. Use `base { archivesName = ...; libsDirectory = layout.buildDirectory.dir(...); distsDirectory = ... }`. Confirmed in 9.0.0. | [base](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#base_convention_deprecation) |
| 8.2 | 9.0.0 | Top-level `applicationDefaultJvmArgs`, `mainClassName`, `applicationName`, `executableDir`. Wrap in `application {}` and use `mainClass`. | [application](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#application_convention_deprecation) |
| 8.2 | 9.0.0 | Top-level `webAppDirName`, `appDirName`, `projectReportDirName`. Use `war { webAppDirectory = file(...) }`, `ear { appDirectory = file(...) }`, `tasks.withType(HtmlDependencyReportTask).configureEach { projectReportDirectory = ... }`. Confirmed in 9.0.0. | [war](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#war_convention_deprecation), [ear](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#ear_convention_deprecation), [project-report](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#project_report_convention_deprecation) |
| 8.2 | 9.0.0 | `useJUnitPlatform()` with only `testImplementation 'org.junit.jupiter:junit-jupiter'` and no launcher, or JUnit 3 tests with `junit:junit:3.x` only. Add `testRuntimeOnly 'org.junit.platform:junit-platform-launcher'`, or `testRuntimeOnly 'junit:junit:4.13.2'` for JUnit 3, or migrate to `testing.suites`. | [test frameworks](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#test_framework_implementation_dependencies) |
| 8.2 | null | `options.annotationProcessorGeneratedSourcesDirectory` on `JavaCompile`. Use `options.generatedSourceOutputDirectory`. `configurations.foo.getAll()`. Iterate `project.configurations`. `BuildIdentifier.name`, `isCurrentBuild()`, `ProjectComponentSelector.buildName`. Use `getBuildPath()`. | [generated sources](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#compile_options_generated_sources_directory), [getAll](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_configuration_get_all), [build identifier](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#build_identifier_name_and_current_deprecation) |
| 8.3 | null | `buildDir`, `project.buildDir`, `"$buildDir/..."`, `buildDir = file(...)`. Use `layout.buildDirectory.file('x')`, `.dir('x')` and `layout.buildDirectory = layout.projectDirectory.dir('out')`. No warning is printed in 8.x. Not mentioned in the 9.0 guide. | [buildDir](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#project_builddir) |
| 8.3 | 9.0.0 | `module('org:foo:1.0') { dependency 'org:bar:1.0' }` inside `dependencies {}`. Replace with a normal coordinate plus a `ComponentMetadataRule` that adds the extra dependencies to the `compile` and `runtime` variants. | [ClientModule](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#declaring_client_module_dependencies) |
| 8.3 | 9.0.0 | `id 'com.gradle.enterprise' version '3.x'` with x below 13.1 in `settings.gradle`. Upgrade to 3.13.1 or later, or to `com.gradle.develocity`. Confirmed: 9.0.0 ignores older versions. | [Develocity](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#unsupported_ge_plugin_3.13), [9.0](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#lowest_supported_gradle_enterprise_plugin_version_change) |
| 8.4 | 9.0.0 | `getVersionRangeMapper()`, `withCompileScopeAttributes(...)`, `withRuntimeScopeAttributes(...)` on `GenerateMavenPom`. Delete. They were never public API. | [GenerateMavenPom](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#generate_maven_pom_method_deprecations) |
| 8.5 | 9.0.0 | `org.gradle.util.VersionNumber.parse(...)` and `compareTo`. Write your own version parsing, or use `GradleVersion` for Gradle versions. | [org.gradle.util 8.5](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#org_gradle_util_reports_deprecations_8) |
| 8.5 | 9.0.0 | A custom configuration that is both consumable and resolvable and is resolved. Mark it `canBeConsumed = false`, or create it with `configurations.resolvable('foo')`. | [root configuration](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#depending_on_root_configuration) |
| 8.5 | 9.0.0 | `include 'x'` in `settings.gradle` where `x/` does not exist or is read-only. Create the directory: `project(':x').projectDir.mkdirs()`. Confirmed: 9.0.0 fails the build. | [project directory](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_missing_project_directory), [9.0](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#project_directories_must_exist_and_be_writeable) |
| 8.6 | 9.0.0 | `java { registerFeature('x') { usingSourceSet(sourceSets.main) } }`. Create a dedicated source set and register the feature with it. | [registerFeature](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecate_register_feature_main_source_set) |
| 8.6 | 9.0.0 | `implementation('org:foo:1.0') { artifact { name = 'notfoo' } }` published to a Maven repository. Declare the real coordinates. Ivy publishing is unaffected. | [artifact name](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#publishing_artifact_name_different_from_artifact_id_maven) |
| 8.6 | 9.0.0 | `configurations.testImplementation.dependencies.all { version { require(...) } }` on dependencies declared in a `testing.suites` block. Use `dependencies { constraints { testImplementation('com:foo') { version { prefer '2.0' } } } }`. `ArtifactIdentifier` in build logic. Remove. Confirmed removed in 9.0.0. | [DependencyCollector](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#dependency_mutate_dependency_collector_after_finalize), [ArtifactIdentifier](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_artifact_identifier) |
| 8.7 | 9.0.0 | `project.convention.plugins.myPlugin = ...` in `buildSrc` plugins. Register an extension: `project.extensions.create('myPlugin', MyExtension)`. | [registration](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_registration_of_plugin_conventions) |
| 8.7 | 9.0.0 | `uri('file:relative/path')`, URLs with spaces, or bad `%` escapes passed to `uri(...)`, `maven { url ... }` or `artifacts`. Drop the `file:` scheme for relative paths. Encode spaces as `%20` and `%` as `%25`. | [URL decoding](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_invalid_url_decoding) |
| 8.7 | 9.0.0 | `.resolve()`, `.resolve(true)`, `.buildDependencies` on `ProjectDependency` or `FileCollectionDependency`, for example `dependsOn(configurations.implementation.dependencies)`, and `instanceof SelfResolvingDependency`. Resolve through a resolvable configuration: `dependsOn(configurations.runtimeClasspath)`. | [SelfResolvingDependency](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecate_self_resolving_dependency) |
| 8.7 | 9.0.0 | `CollectionUtils.stringize(...)`. Use `collect { it.toString() }`. Confirmed: 9.0.0 removed `CollectionUtils`. | [org.gradle.util 8.7](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#org_gradle_util_reports_deprecations), [9.0](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#removal_of_deprecated_org_gradle_util_members) |
| 8.8 | 9.0.0 | `incoming.beforeResolve { dependencies.add(...) }`, `resolutionStrategy` edits, `extendsFrom`, `exclude` or `canBeResolved` changes after a configuration was resolved or consumed, including in `afterEvaluate` of another project. Add dependencies with `dependencies.addLater(provider)` or `addAllLater`, versions with `prefer` constraints, excludes with `withDependencies {}` or component metadata rules. Set roles and hierarchy at creation. | [mutation](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#mutate_configuration_after_locking) |
| 8.8 | null | `configurations.foo.files(dep)`, `files { spec }`, `fileCollection(...)`, `resolvedConfiguration.getFiles(spec)`, `getFirstLevelModuleDependencies(spec)`, `lenientConfiguration.getArtifacts(spec)`. Use `incoming.artifactView { componentFilter { it instanceof ModuleComponentIdentifier && it.group == 'g' && it.module == 'm' } }.files`. The filter does not include transitive dependencies of the component. | [filtered files](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecate_filtered_configuration_file_and_filecollection_methods) |
| 8.8 | null | `fileMode = 0755`, `dirMode = 0755`, `mode` in `Copy`, `Zip`, `Tar`, `Jar` specs and `eachFile { it.mode = ... }`. Use `filePermissions { unix('rwxr-xr-x') }`, `dirPermissions { unix(0755) }` and `permissions {}` on `FileCopyDetails`. The 8.x guide names no version. 9.0.0 removed these methods. | [file modes](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#unix_file_permissions_deprecated), [9.0](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#removal_of_unix_mode_based_file_permissions) |
| 8.8 | 9.0.0 | `buildCache { local { removeUnusedEntriesAfterDays = 30 } }` in `settings.gradle`. Remove it. Set retention in an init script: `beforeSettings { caches { buildCache.setRemoveUnusedEntriesAfterDays(30) } }`. Confirmed in 9.0.0. | [build cache retention](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#directory_build_cache_retention_deprecated) |
| 8.8 | 9.0.0 | `Task.Namer` or `Configuration.Namer` in build logic. Use `Named.Namer.INSTANCE`. | [Namer](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_namers) |
| 8.10 | 9.0.0 | `java -version` of `JAVA_HOME`, `org.gradle.java.home` and the CI agents that run Gradle. The daemon needs JVM 17 or later. The wrapper, launcher, Tooling API, TestKit and test workers stay compatible with JVM 8. Keep the project's own toolchain unchanged. Confirmed in 9.0.0. | [daemon JVM](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#minimum_daemon_jvm_version), [9.0](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#jvm-17) |
| 8.10 | 9.0.0 | Ivy dependencies substituted by project dependencies that select a configuration marked `canBeConsumed = false`. Make the target consumable or select a proper variant. | [Ivy](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#consuming_non_consumable_variants_from_ivy_component) |
| 8.10 | 9.0.0 | `configurations.foo.extendsFrom(project(':other').configurations.bar)` or `rootProject.configurations...` inside `extendsFrom`. Extend only configurations of the same project. Share dependencies through a plugin or a project dependency. | [cross-project extendsFrom](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#extending_configurations_in_same_project) |
| 8.11 | null | `ForkOptions.javaHome` on `JavaCompile` and `GroovyCompile`. Deprecated in 8.11, un-deprecated in 8.14 because no stable replacement exists. Prefer toolchains. No action for 9.0. | [javaHome](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_fork_options_java_home), [8.14](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#undeprecated_fork_options_java_home) |
| 8.11 | 9.0.0 | `buildscript { configurations { create('x') } }` and resolving `buildscript.configurations.x.files`, especially in `settings.gradle`. Use `buildscript.configurations.detachedConfiguration(buildscript.dependencies.create('org:foo:1.0')).files`, or avoid resolution in settings. | [buildscript](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#mutating_buildscript_configurations) |
| 8.11 | 9.0.0 | `configuration: 'x'` in map-style notation and `targetConfiguration = 'x'` on Maven dependencies. Remove. Use attributes or capabilities. | [Maven configuration](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#selecting_variant_by_configuration_name) |
| 8.11 | 9.0.0 | `configurations.add(...)`, `addAll`, `addLater`, `addAllLater` with a detached or copied configuration. Create configurations through `create`, `register`, `resolvable`, `consumable` or `dependencyScope` only. `configurations.detachedConfiguration(...).extendsFrom(...)`. Create a regular configuration instead. | [container](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#adding_to_configuration_container), [detached](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#detached_configurations_cannot_extend) |
| 8.11 | 9.0.0 | `dependency.dependencyProject` on `ProjectDependency`, common in "collect all subprojects on the classpath" logic. Use `project(dependency.path)`, or walk `configuration.incoming.resolutionResult` for project components. | [dependencyProject](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecate_get_dependency_project) |
| 8.11 | 9.0.0 | `configurations.foo.resolvedConfiguration.files` and `resolvedConfiguration.lenientConfiguration.files`. Use `configurations.foo.incoming.files` and `configurations.foo.incoming.artifactView { lenient = true }.files`. These carry task dependencies. | [getFiles](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecate_legacy_configuration_get_files) |
| 8.11 | 9.0.0 | `options.define(...)`, `options.fork(map)`, `options.debug(map)` on `JavaCompile` and `GroovyCompile`, and code that extends `AbstractOptions`. Set the properties directly. `options.forkOptions = new ForkOptions()`, `options.debugOptions = ...`, `setForkOptions(...)`, and the Scala equivalents. Configure the existing object: `options.forkOptions { memoryMaximumSize = '1G' }`. | [AbstractOptions](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_abstract_options), [nested setters](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_nested_properties_setters) |
| 8.11 | 9.0.0 | `exec { commandLine ... }`, `javaexec {}`, `project.exec`, `project.javaexec` in scripts, `buildSrc`, `doLast` blocks and custom tasks. In tasks inject `ExecOperations` and call `execOps.exec {}`. At configuration time use `providers.exec { commandLine ... }.standardOutput.asText`. Preserve `workingDir`, `environment`, `ignoreExitValue` and output capture. Confirmed in 9.0.0. | [exec](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_project_exec), [9.0](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#removal_of_project_exec_project_javaexec_and_script_level_counterparts) |
| 8.11 | 9.0.0 | `javadoc { verbose = true }` or `isVerbose()`. Use `options.verbose()`. `verbose = false` did nothing and can be deleted. `dep1.contentEquals(dep2)`. Use `equals`. `gradle.useLogger(...)` in init scripts. Remove. There is no replacement. | [verbose](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_javadoc_verbose), [contentEquals](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_content_equals), [useLogger](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_use_logger) |
| 8.12 | 9.0.0 | Warning text: "multiple distinct artifact transformation chains of the same length". Look at `dependencies.registerTransform(...)` calls and at the `artifactTransforms` report from 8.13. Add distinguishing attributes or remove redundant transforms. In a plain Java build the transforms come from plugins. Report the plugin. | [transform chains](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_ambiguous_transformation_chains) |
| 8.12 | 9.0.0 | `gradlew init tasks` or any `init` invocation with other tasks in CI scripts. Run `init` alone. | [init alone](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#init_must_run_alone) |
| 8.12 | 10.0.0 | `project.` or bare `project` inside `doLast`, `doFirst` or `@TaskAction`. Capture the values as task inputs, or inject `FileSystemOperations`, `ProjectLayout`, `ExecOperations`. Under the configuration cache this is reported as a cache problem. Not a 9.0 blocker. | [Task.getProject](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#task_project) |
| 8.12 | 10.0.0 | `propertyName value` without `=`: `group 'com.example'`, `version '1.0'`, `description 'x'`, `jvmArgs '-Xmx1g'`, `mainClass 'a.Main'`. Use `propertyName = value`. For real methods use `jvmArgs('-Xmx1g')`. The guide gives a `sed` one-liner. Not a 9.0 blocker. | [space assignment](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#groovy_space_assignment_syntax) |
| 8.12 | null | `reporting { baseDir = ... }`. Use `reporting { baseDirectory = layout.buildDirectory.dir('reports') }`. `dependencyInsight.dependencySpec`. Remove. | [baseDir](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#reporting-base-dir), [dependencySpec](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#dependency-insight-report-task-get-dependency-spec) |
| 8.12, 8.13 | null | Source-level only: `tasks.create(...)`, `task foo {}`, `project.task(...)` are `@Deprecated` with no runtime warning. Prefer `tasks.register(...)`. This affects only builds that compile plugins with warnings as errors. | [tasks.create](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#source_level_deprecation_of_taskcontainer_create_methods), [project.task](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#source_level_deprecation_of_project_task_methods) |
| 8.13 | 9.0.0 | `attributeProvider(attr, provider { container.getAttribute(other) })` that reads the same `AttributeContainer`. Compute the value from a different source. `org.gradle.api.artifacts.transform.VariantTransformConfigurationException` in `catch` blocks. Remove. It becomes internal. | [recursive attributes](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#recursively_querying_attributecontainer_in_lazy_provider), [exception](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_transform_configuration_exception) |
| 8.13 | null | `updateDaemonJvm { jvmVersion = ...; jvmVendor = ... }`. Use `languageVersion = JavaLanguageVersion.of(17)` and `vendor = JvmVendorSpec.ADOPTIUM`. `jvmVendor` fails the task. | [updateDaemonJvm](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_update_daemon_jvm) |
| 8.13 | 10.0.0 | `Boolean isFoo()`, boxed type with `is` prefix, on task classes and extensions in `buildSrc`, especially with `@Input`. Add `Boolean getFoo()` with the annotation and mark the old one `@Deprecated @ReplacedBy('foo')`, or use primitive `boolean`. The 8.x guide says 9.0. The 9.0 guide says that 9.0 still recognizes them and Gradle 10 does not. Treat the effective removal as 10. | [Boolean is](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#groovy_boolean_properties), [9.0](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#is_prefixed_boolean_properties_no_longer_recognized_by_groovy) |
| 8.14 | 10.0.0 | A `Property<SomeEnum>` assigned a string in Groovy. Assign the enum constant. Only Groovy plugins and scripts. `gradle.startParameter.configurationCacheRequested`. Inject `BuildFeatures` and read `configurationCache.requested`. Not 9.0 blockers. | [enum coercion](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_string_to_enum_coercion_for_rich_properties), [isConfigurationCacheRequested](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_startparameter_is_configuration_cache_requested) |
| 8.14 | 9.0.0 | `idea { module { testSourceDirs += ...; testResourceDirs += ... } }`. Use `testSources.from(...)` and `testResources.from(...)`. Confirmed in 9.0.0. `groovydoc.antGroovydoc`, `new GradlePluginDevelopmentExtension(...)`, `gradlePlugin.pluginSourceSet(...)`. Remove. | [IdeaModule](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_collection_methods_warn), [AntGroovydoc](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#antgroovydoc), [plugin development](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#deprecated_plugin_development_methods) |
| 8.14 | null | `attributes.getAttribute(null)`. Never pass `null`. | [null attribute](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#null-attribute-lookup) |
| 8.14 | withdrawn | The 8.0 warning for adding an artifact to a configuration that is neither resolvable nor consumable was withdrawn as too broad. No action. | [withdrawn](https://docs.gradle.org/8.14.5/userguide/upgrading_version_8.html#undeprecated_configuration_uasge) |

Kotlin DSL items are out of scope: the `"name"()` task reference syntax (8.7), `libraries` and `bundles` from catalogs in `plugins {}` (8.1), precompiled scripts published with Gradle below 6.0 (8.1), `kotlin-dsl` with KGP below 1.8.0 (8.1), and the `gradle-enterprise` shorthand in `settings.gradle.kts` (8.8). A mixed DSL is a coverage gap, not a pass.

## Migration recipes for the four most common warnings

**Recipe A: plugin conventions at the top level of `build.gradle`**
```groovy
// before
sourceCompatibility = 17
targetCompatibility = 17
archivesBaseName = 'app'
mainClassName = 'com.example.Main'
applicationDefaultJvmArgs = ['-Xmx512m']
```
```groovy
// after, behavior-preserving
java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}
base { archivesName = 'app' }
application {
    mainClass = 'com.example.Main'
    applicationDefaultJvmArgs = ['-Xmx512m']
}
```
A move from `sourceCompatibility` to a toolchain with `options.release` is a separate policy change. Offer it separately. See practice J1 in `best-practices.md`.

**Recipe B: custom `Test` task without an explicit classpath**
```groovy
// before: runs zero tests on 9.0 and succeeds
tasks.register('integrationTest', Test) {
    useJUnitPlatform()
    filter { includeTestsMatching '*IT' }
}
```
```groovy
// after
tasks.register('integrationTest', Test) {
    testClassesDirs = sourceSets.test.output.classesDirs
    classpath = sourceSets.test.runtimeClasspath
    useJUnitPlatform()
    filter { includeTestsMatching '*IT' }
}
```
Compare the test counts from the JUnit XML before and after. `gather_facts.py` flags a task with no XML or a `NO-SOURCE` outcome as a blocker lead.

**Recipe C: `project.exec` at configuration time**
```groovy
// before
def gitSha = new ByteArrayOutputStream().with { out ->
    exec { commandLine 'git', 'rev-parse', '--short', 'HEAD'; standardOutput = out }
    out.toString().trim()
}
```
```groovy
// after, configuration-cache compatible, stable since 8.11
def gitSha = providers.exec {
    commandLine 'git', 'rev-parse', '--short', 'HEAD'
}.standardOutput.asText.map { it.trim() }
```
Wire `gitSha` into a task input as a provider. Do not call `.get()` at configuration time.

**Recipe D: `project.exec` inside a task action**
```groovy
// before
tasks.register('tool') {
    doLast { project.exec { commandLine 'tool', '--run' } }
}
```
```groovy
// after
abstract class ToolTask extends DefaultTask {
    @Inject abstract ExecOperations getExecOps()
    @TaskAction void run() { execOps.exec { commandLine 'tool', '--run' } }
}
tasks.register('tool', ToolTask)
```
Keep `workingDir`, `environment` and `ignoreExitValue` as they were. See practice T10.

## Breaking changes per 8.x version, no warning shown

Source: the "Potential breaking changes" sections of the 8.x guide. Review these for every version boundary that the upgrade crosses, even if the build shows no warning. The full text is in `gradle-8x-features.md` under "Behavior changes" for each version.

- **8.0**: warnings that became errors for task validation, included-build task ordering and toolchain specs; removed archive, application, report and `org.gradle.util` APIs; abstract plugin and task classes; immutable `jvmArgs`; workers without implicit `--add-opens`; archives built with Commons Compress; toolchains used unconditionally; the Groovy DSL fallback to root configure methods removed.
- **8.1**: configuration cache properties renamed; an external process at configuration time is an error under the configuration cache; `JavaExec.getJvmArguments()` added; `CACHEDIR.TAG` written.
- **8.2**: Groovy 3.0.17, Ant 1.10.13, CodeNarc 3.2.0, PMD 6.55.0, JaCoCo 0.8.9; task configuration deferred or avoided during dependency resolution.
- **8.3**: `org.gradle.jvm.version` attribute finalizes the toolchain when read; `artifactView` no longer snapshots attributes; `TestLauncher` fails the build on test failure; Kotlin 1.9.0.
- **8.4**: secure XML processing and blocked external DTDs; Kotlin 1.9.10.
- **8.5**: `groovy-base` owns `GroovyCompile` compatibility conventions; `Provider.filter(Spec)`; Kotlin 1.9.20.
- **8.6**: JaCoCo 0.8.11; `DependencyAdder` renamed `DependencyCollector`.
- **8.7**: Commons Compress 1.25.0 changes archive checksums; TOML 1.0.0 catalog parser; SSH libraries replaced; ASM 9.6; Kotlin 1.9.22.
- **8.8**: Groovy 3.0.21, `as Action` needs a generic type; `ProblemSpec.label` replaced; `append` and `insert` removed; ASM 9.7.
- **8.9**: toolchains re-provisioned once; no implicit compile against the Gradle runtime; configuration cache classes under `org.gradle.internal`; file-system watching off on macOS 11 and earlier; JDK 8 compiler output with annotation processors uses qualified names; Kotlin 1.9.23.
- **8.10**: `JavaCompile` can fail on a JRE even with no sources; Ant 1.10.14, JaCoCo 0.8.12, Groovy 3.0.22, Kotlin 1.9.24.
- **8.11**: digits are word boundaries in abbreviated names; `UpdateDaemonJvm.jvmVersion` typed as `JavaLanguageVersion`; Kotlin 2.0.20.
- **8.12**: `tasks.create` source-level deprecated; Ant 1.10.15, Zinc 1.10.4, Kotlin 2.0.21.
- **8.13**: `JvmTestSuite.testType` removed; aggregation reports use `testSuiteName`; `Project.task` source-level deprecated; `BuildLauncher.addJvmArguments` no longer overrides `org.gradle.jvmargs`; ASM 9.7.1.
- **8.14**: executable wrapper JAR; `Settings.getDefaults()` removed; Guava 33.4.6, Groovy 3.0.24, JaCoCo 0.8.13; `EclipseClasspath.baseSourceOutputDir` is a `DirectoryProperty`.

## Cross-check against the 9.0 major guide

Anchors in this section are into `https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html`.

**Where the guides disagree or the 8.x guide names no version:**
- `is`-prefixed `Boolean` properties: 8.13 says 9.0. The 9.0 guide says that Gradle 9 still recognizes them and Gradle 10 does not. Treat the effective removal as 10.
- `org.gradle.cache.cleanup` and the Unix file mode methods: the 8.x guide names no version. 9.0.0 removed both.
- `Project.buildDir`: not mentioned in the 9.0 guide. Still deprecated, no removal version.
- `ForkOptions.javaHome`: un-deprecated in 8.14. Not mentioned in the 9.0 guide.
- Announced for 10.0 and therefore present in 9.0: `Task.getProject()` in task actions, space assignment, `StartParameter.isConfigurationCacheRequested`, string-to-enum coercion.
- About 40 items that 8.x announced for 9.0 are not listed in the 9.0 guide. The guide does not claim to be exhaustive. Treat them as removed unless the 9.x build proves otherwise. Do not skip them.

**Removed or changed in 9.0 with no 8.x deprecation entry.** These do not show as warnings on 8.x. Check them by reading the build:
- `jcenter()` is removed, deprecated since 7.0 ([jcenter](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#removal_of_deprecated_jcenter)). Replace with `mavenCentral()`.
- `WriteProperties.outputFile` is removed. Use `destinationFile` ([WriteProperties](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#removal_of_output_file_in_write_properties_task)).
- `GroovySourceSet` and `ScalaSourceSet` are removed. Use the `GroovySourceDirectorySet` extension ([source sets](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#removal_of_groovy_source_set_and_scala_source_set_interfaces)). `groovy-test`, `groovy-console` and `groovy-sql` are no longer on `localGroovy()` ([Groovy modules](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#removal_of_select_groovy_modules_from_the_gradle_distribution)).
- **Groovy 4** in build scripts: `DELEGATE_FIRST` lookup order changed, private members can be inaccessible in closures, and `super` calls from plugins compiled with Groovy 3 can fail ([Groovy 4](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#groovy-4)). Groovy DSL plugins built with 9.x need Gradle 7.0 or later at runtime.
- **Archives are reproducible by default**: fixed order, fixed timestamps, `0755` and `0644` permissions. Restore the old behavior with `reproducibleFileOrder = false`, `preserveFileTimestamps = true` and `useFileSystemPermissions()` ([reproducible archives](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#reproducible_archives_by_default)). Manual reproducibility settings are redundant now.
- **`assemble` no longer builds artifacts of custom configurations** and no longer adds them to `archives`. Add `tasks.named('assemble') { dependsOn(configurations.special.artifacts) }` where the old behavior was relied on ([assemble](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#gradle_no_longer_implicitly_builds_certain_artifacts_during_assemble)). With several packaging plugins, `assemble` builds jar, war and ear together ([war and ear](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#ear_and_war_plugins_build_all_artifacts_with_assemble)).
- Stale class files outside the build directory are no longer deleted ([stale outputs](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#stale_outputs_outside_the_build_directory_are_no_longer_deleted)).
- Classes that extend Gradle types with `@Inject` getters must be abstract ([inject](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#injection_getters_are_now_abstract)). JSpecify annotations replace JSR-305 ([JSpecify](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#jspecify)). `ConfigurationVariant.getDescription` is a `Property<String>`.
- Configuration cache: unsupported `onTaskCompletion` listener providers are cache problems, with a temporary opt-out that Gradle 10 removes ([listeners](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#unsupported_build_event_listeners_are_now_configuration_cache_problems)). The cache entry is discarded for incompatible tasks even in warning mode.
- Signing matches the OpenPGP key version ([signing](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#artifact_signing_now_matches_openpgp_key_version)).
- **Bundled tool defaults**: Checkstyle 10.24.0, CodeNarc 3.6.0, PMD 7.13.0 ([code quality](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#upgraded_default_versions_of_code_quality_tools)). PMD 7 renamed rule sets. Review `pmd { ruleSets }` and custom rule XML. With test suites: JUnit Jupiter 5.12.2, TestNG 7.11.0, Spock 2.3 ([test frameworks](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#upgraded_default_versions_of_testing_frameworks)). JGit 7.2.1.
- Minimum Kotlin Gradle Plugin 2.0.0 ([KGP](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html#lowest_supported_kotlin_gradle_plugin_version_change)). The Scala plugins no longer create `incrementalScalaAnalysisFor*` configurations.

The complete list of 9.0 removals that matter for Groovy DSL builds is in `gradle-10-deprecations.md` § "Removed in 9.0". Read both.
