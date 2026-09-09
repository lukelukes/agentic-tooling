# Gradle 10 Readiness: Deprecations to Clear on 9.x

Gradle 10 is not released as of September 2026. Source: [Gradle 9.7.1 upgrade guide](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html). This file is a triage index. It is not a complete compatibility certificate.

Before **every version transition**:
1. Read the minor upgrade guide, pinned to the target version, for each version boundary that you cross.
2. For 8.x to 9.x, also read the [major upgrade guide](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html) and the latest 8.x guide.
3. Include breaking changes and changed bundled-tool defaults, even if the current build shows no warning.
4. If you cannot read the official sources, mark the upgrade coverage as incomplete.

Collect the real list from the CI verification workload:

```bash
./gradlew help --warning-mode=all          # deprecations and Problems report inline (9.3 and later)
./gradlew <verification-tasks> --warning-mode=all  # task-specific warnings
```

Then open `build/reports/problems/problems-report.html`. From 9.7 it has source locations for up to 2050 problems.

## Announced for removal in Gradle 10

Source: 9.x release notes.

| Deprecated in | Item | Replacement |
|---|---|---|
| 9.1.0 (practice from 8.14) | **Named-argument dependency notation** `implementation group: 'g', name: 'a', version: 'v'` | `implementation 'g:a:v'` or a catalog alias. Keep the declaration-site semantics. |
| 9.1.0 | Antlr `-package` in `arguments` | `packageName = 'com.example'` on `AntlrTask`. |
| 9.6.0 | **Implicit lookup of properties and methods in parent projects.** This covers Groovy DSL dynamic resolution and `findProperty()`, `property()` and `hasProperty()` that walk up to parents | See the migration recipes below. To opt into the future behavior: `enableFeaturePreview('NO_IMPLICIT_LOOKUP_IN_PARENT_PROJECTS')`. |
| 9.7.0 (preview) | Constraint edges that affect classpath order | `enableFeaturePreview('ENHANCED_GRAPH_ORDERING')` becomes the default in 10. Test now if classpath order matters. |

### Groovy, JVM and build-logic checks

Each row records the version that deprecated the item, the removal version and the source anchor. `null` means that no removal version is announced. Do not infer 10 from the chapter. The source links are pinned to 9.7.1. Check the actual receiver types and the execution context before you rewrite. A code pattern alone is not proof of a warning.

| Since | Removal | Check and migration | Official source |
|---|---|---|---|
| 9.1.0 | 10.0.0 | Multi-string or named dependency notation. Replace with a single GAV string or a catalog alias. Keep classifiers, artifact types and closures. | [notation](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#dependency_multi_string_notation) |
| 9.1.0 | 10.0.0 | `archives` configuration. Replace with the applicable outgoing variants or publications. Keep attached artifacts and consumers. | [archives](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#archives-configuration) |
| 9.1.0 | 10.0.0 | `Configuration.visible`. Remove the obsolete setting after you check the legacy assemble wiring. | [visible](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate-visible-property) |
| 9.1.0 | 10.0.0 | `ReportingExtension.file()`, `getApiDocTitle()`, `JavaForkOptions.setAllJvmArgs()`. Use the documented replacement for the receiver. Keep the JVM argument partitioning and the report paths. | [report files](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#reporting_extension_file), [title](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#reporting_extension_api_doc_title), [JVM args](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#set-all-jvm-args) |
| 9.1.0 | 10.0.0 | Non-string `GradleBuild.startParameter.projectProperties`. Use explicit strings. Toolchain configuration passed with `-P`: use Gradle properties through `-D`. | [nested build properties](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated-gradle-build-non-string-properties), [toolchains](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#toolchain-project-properties) |
| 9.2.0 | 10.0.0 | `Project.container(...)`: use `ObjectFactory.domainObjectContainer(...)`. RuleSource-based dependency rules: use the action or component-metadata APIs. Apply Java before you call `registerFeature`. | [containers](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#project_container_methods), [rules](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#dependency_management_rules), [features](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_register_feature_no_java_plugin) |
| 9.3.0 | 10.0.0 | Publishing dependencies on unpublished projects. Define the intended publications. Do not invent coordinates. | [publication](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#publishing_dependency_on_unpublished_project) |
| 9.3.0 | 10.0.0 | Legacy `Usage` values and self-dependencies by module GAV. Use current attributes and project dependencies, with variant evidence. | [usage](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_legacy_usage_values), [self-dependencies](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#module_identity_for_root_component) |
| 9.3.0 | 10.0.0 | `Wrapper.getAvailableDistributionTypes()` and implicit `ModuleVersionSelector` conversion. Use the documented public replacements. Inspect custom plugin code. | [wrapper](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_wrapper_get_available_distribution_types), [selectors](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_moduleversionselector_to_modulecomponentselector) |
| 9.4.0 | 10.0.0 | `DomainObjectCollection.findAll(Closure)`: use `matching { ... }`. `matching` is lazy, not a snapshot. Keep the timing semantics. Plain Java or Groovy collection `findAll` is not this API. | [findAll](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#findAll_removal) |
| 9.4.0 | 10.0.0 | Test `beforeTest`, `afterTest`, `beforeSuite`, `afterSuite` and `onOutput` closure APIs: use typed listeners. `testFramework(Closure)`: use `options(Action)`. | [test APIs](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_test_methods) |
| 9.4.0 | 10.0.0 | `apply false` in precompiled script plugins, `version` in precompiled settings plugins, `Dependencies.getProject()`. Use the correct plugin dependency and configuration APIs. | [apply false](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_apply_false_in_precompiled_script_plugins), [settings versions](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_version_in_precompiled_settings_script_plugins), [project](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#v9_deprecation_of_dependencies_get_project) |
| 9.5.0 | 10.0.0 | `CreateStartScripts.exitEnvironmentVar`. Remove the obsolete customization after you compare the generated launchers. | [launchers](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_exit_environment_var) |
| 9.6.0 | 10.0.0 | `Project.getProperties()`, `project.properties` and script `properties`. Use explicit providers or maps. `providers.gradleProperty` does not include `ext` values. | [properties](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_get_properties) |
| 9.6.0 | 10.0.0 | Implicit parent lookup. Develocity plugin before 4.0 depends on it. Use explicit values or conventions, and update to a compatible plugin. | [lookup](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_implicit_lookup_in_parent_projects), [Develocity](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_develocity_plugin_pre_4_0) |
| 9.6.0 | 10.0.0 | Task dependency relationships, task extensions, or injected `Project` or `Gradle` read in task actions. Use declared task inputs and supported services. A `Task` argument in a `dependsOn` closure also changes. | [relationships](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#task_dependencies), [extensions](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#task_extensions), [services](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#injected_service_types_at_execution), [closures](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#task_in_task_dependency_closure) |
| 9.6.0 | 10.0.0 | Undeclared artifact transforms that a task triggers. Declare the resolved artifacts as task inputs. | [transforms](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#undeclared_artifact_transform_input) |
| 9.6.0 | 10.0.0 | `Project` objects as dependency notation: use `DependencyHandler.project(...)`. Repository `artifactUrls` and map overloads: use the supported repository configuration and keep the provenance. | [projects](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#dependency_project_notation), [artifact URLs](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_maven_artifact_urls), [map overloads](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_repository_handler_map_overloads) |
| 9.6.0 | 10.0.0 | `buildNeeded`, `buildDependents` and `getTaskDependencyFromProjectDependency()`. Use explicit, approved workload and output wiring. Keep the upstream and downstream verification coverage. | [tasks](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_build_needed_build_dependents_tasks), [API](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_getTaskDependencyFromProjectDependency) |
| 9.6.0 | 10.0.0 | Remove obsolete PMD `targetJdk`. Replace `ProblemSpec.severity()` with the applicable report or throw method. | [PMD](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_pmd_target_jdk), [severity](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_problem_spec_severity) |
| 9.6.0 | null | IDE file-generation tasks and model properties are deprecated. The guide gives no removal version. Do not remove IDE import model configuration that is still supported. | [IDE tasks](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#ide_task_deprecation) |
| 9.7.0 | 10.0.0 | Custom collection or map subclasses serialized into the configuration cache. Use standard collections and explicit separate state. | [collections](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_custom_collection_types_with_cc) |
| 9.7.0 | 10.0.0 | Legacy software model, `model {}` and `RuleSource`. Use the supported component and plugin model. Native and product migration is out of scope. Report and defer it. Do not rewrite it. | [software model](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_software_model) |
| 9.7.0 | null | `org.gradle.unsafe.isolated-projects*`. Use the new names **only if the running version supports them (9.7 and later)**. Removal is announced for a future release, not for 10. No warning is shown at present. | [legacy names](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_unsafe_isolated_projects_properties) |

Kotlin DSL delegate removals need a separate Kotlin audit. A mixed DSL is a coverage gap, not a pass. Also review warnings from 8.x that the build carries into 9.x. Use the pinned major and 8.x guides. This index does not replace them.

Not announced for removal in Gradle 10:
- `ResolvedArtifactResult.getVariant()` is still available. Its deprecation is planned for a future release.
- The configuration cache is the preferred mode. No release makes it mandatory.

Keep these as advisory roadmap items, not as upgrade blockers.

## Parent-project lookup: migration recipes

This is the most common Groovy DSL deprecation in multi-project builds. The warning is:

```
Resolution of the property 'foo' from parent project ':' has been deprecated. This will fail with an error in Gradle 10.
```

**Pattern A: shared version or constant in root `ext`**
```groovy
// root build.gradle (before)
ext { springVersion = '6.2.0'; javaTarget = 21 }
// child/build.gradle
implementation "org.springframework:spring-core:$springVersion"
```
Migration: Move versions to `libs.versions.toml`. Move other constants to the root `gradle.properties`, for example `javaTarget=21`, and read them with `providers.gradleProperty('javaTarget')`. The preferred option is a default inside a convention plugin.

**Pattern B: helper method in root, called from children**
```groovy
// root
def configureSpringBoot(Project p) { ... }
subprojects { configureSpringBoot(it) }
```
Migration: Move the whole helper into a convention plugin, for example `spring-boot-conventions.gradle`. Children apply it with `plugins {}`.

**Pattern C: `findProperty('x')` in a child that expects root `ext.x`**
Migration: Same as Pattern A. If the user can override the value, use `providers.gradleProperty('x').orElse('default')`. It reads `gradle.properties`, `-P` and `ORG_GRADLE_PROJECT_x`, and it is compatible with the configuration cache. Versions 9.1, 9.4 and 9.6 improved the cache hit rate for this case.

**Pattern D: explicit cross-project access, `rootProject.ext.foo` or `parent.someMethod()`**
This is not deprecated because it is explicit. It is cross-project access to mutable state, which Isolated Projects forbids. It is acceptable as a stop-gap. Prefer Pattern A or B.

After you clear the warnings, **offer a separate Gradle 10 experiment**. It requires 9.6 or later. In `settings.gradle`:
```groovy
enableFeaturePreview('NO_IMPLICIT_LOOKUP_IN_PARENT_PROJECTS')
```
This changes the lookup behavior. Do not enable it as part of ordinary cleanup. Compare the workload with its baseline.

## Removed in 9.0

These items apply to migrations from 8.x.

- **Custom `Test` tasks can run zero tests without an error.** `tasks.register('integrationTest', Test)` no longer inherits `testClassesDirs` and `classpath` from the `test` source set. Set both explicitly: `testClassesDirs = sourceSets.integrationTest.output.classesDirs; classpath = sourceSets.integrationTest.runtimeClasspath`. The symptom is a green build with a lower test count. Compare the `TEST-*.xml` counts before and after the upgrade.
- The Gradle daemon requires **JDK 17 or later**. Project toolchains can still target Java 8 and later.
- **Groovy 4**: `groovy.util.XmlSlurper` and `XmlParser` moved to `groovy.xml.*`. `groovy.util.slurpersupport.*` moved to `groovy.xml.slurpersupport.*`. `@Grab` behavior changed. `Map` literal and GString edge cases changed. `groovy.json` did not change.
- `Project.convention`, `getConvention()` and the `Convention` type. Use extensions: `project.extensions`, `java {}`.
- Variant selection by configuration name for **Maven** repositories, `configuration:` on external module dependencies.
- Most of `org.gradle.util`: `GUtil`, `ConfigureUtil`, `CollectionUtils`, `WrapUtil` and others.
- `sourceCompatibility` and `targetCompatibility` on the `Project`-level Java convention. Use `java { sourceCompatibility = ... }`, or the preferred option, toolchains with `options.release`.
- **Reproducible archives** are the default. Review builds that wrote timestamps into JARs or that depended on entry order.
- `org.gradle.api.plugins.JavaPluginConvention` and the other `*Convention` classes.

## Long-standing deprecations in old Groovy scripts

These are not specific to 9.x. The table mixes removed APIs, deprecated APIs and recommended lazy alternatives. Entries such as `apply plugin:` and eager task access do not always show a deprecation warning. Check the actual version-specific warnings before you classify a blocker.

| Old | New |
|---|---|
| `buildDir`, `"$buildDir/x"` | `layout.buildDirectory.dir('x')` or `.file('x')` |
| `tasks.create('x')`, `task x { }` | `tasks.register('x') { }` |
| `tasks.test { }`, `test { }` (eager access) | `tasks.named('test', Test) { }` |
| `tasks.withType(X) { }` (eager) | `tasks.withType(X).configureEach { }` |
| `compile`, `runtime`, `testCompile` configurations | `implementation`, `runtimeOnly`, `testImplementation`. The old names were removed in 7.0 |
| `mainClassName = '...'` (application) | `application { mainClass = '...' }` |
| `archivesBaseName` | `base { archivesName = '...' }` |
| `jar { manifest { attributes 'Main-Class': ... } }` with `project.version` read in the action | Capture the value into a local `def` or a provider |
| `sourceSets.main.output.classesDir` | `sourceSets.main.output.classesDirs` |
| `configurations.compile.each` | Resolve inside a task. See practice T5 |
| `project.file()`, `project.copy {}` in `doLast` | Injected `FileSystemOperations`, `ProjectLayout`. See practice T10 |
| `useJUnit()` with JUnit 5 dependencies | `useJUnitPlatform()` and `junit-platform-launcher` as `runtimeOnly` |
| `apply plugin:` | `plugins { }` |
| `maven { url 'http://…' }` | HTTPS is required since 7.0, unless `allowInsecureProtocol = true` |
| `duplicatesStrategy` not set, with overlapping `from()` | Investigate the duplicate contents. Select an explicit policy with approval. `EXCLUDE` can drop resources without an error |
