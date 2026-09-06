# Gradle 10 Readiness — Deprecations to Clear While on 9.x

Gradle 10 has not been released as of Sept 2026. Source reviewed: [Gradle 9.7.1 upgrade guide](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html). This is a triage index, not an exhaustive compatibility certificate. Before **every version transition**, read the target-pinned minor upgrade guide for each crossed boundary and, for 8.x → 9.x, the [major upgrade guide](https://docs.gradle.org/9.7.1/userguide/upgrading_major_version_9.html) plus the latest 8.x guide. Include breaking changes and changed bundled-tool defaults even when the current build emits no warning. If official sources cannot be checked, mark upgrade coverage incomplete.

Collect the real list from the CI verification workload:

```bash
./gradlew help --warning-mode=all          # deprecations + Problems report inline (9.3+)
./gradlew <verification-tasks> --warning-mode=all  # task-specific warnings too
```

Then open `build/reports/problems/problems-report.html` — from 9.7 it has source locations for up to 2050 problems.

## Announced for removal in Gradle 10 (from 9.x release notes)

| Deprecated in | What | Replacement |
|---|---|---|
| 9.1.0 (practice introduced 8.14) | **Named-argument dependency notation** `implementation group: 'g', name: 'a', version: 'v'` | `implementation 'g:a:v'` or catalog alias; preserve declaration-site semantics. |
| 9.1.0 | Antlr `-package` in `arguments` | `packageName = 'com.example'` on `AntlrTask`. |
| 9.6.0 | **Implicit lookup of properties/methods in parent projects** (Groovy DSL dynamic resolution *and* `findProperty()`/`property()`/`hasProperty()` walking up to parents) | See migration paths below. Opt into future behaviour: `enableFeaturePreview('NO_IMPLICIT_LOOKUP_IN_PARENT_PROJECTS')`. |
| 9.7.0 (preview) | Constraint edges affecting classpath ordering | `enableFeaturePreview('ENHANCED_GRAPH_ORDERING')` becomes default in 10. Test now if classpath order matters. |

### Additional Groovy/JVM and build-logic checks

Each row records **deprecated since / removal version / source anchor**. `null` means no announced removal version; do not infer 10 from the surrounding chapter. Source links below are pinned to 9.7.1. Check actual receiver types and execution context before rewriting; code patterns alone are not proof of a warning.

| Since | Removal | Check and migration | Official source |
|---|---|---|---|
| 9.1.0 | 10.0.0 | Multi-string/named dependency notation → single GAV or catalog; preserve classifiers, artifact types and closures. | [notation](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#dependency_multi_string_notation) |
| 9.1.0 | 10.0.0 | `archives` configuration → appropriate outgoing variants/publications; preserve attached artifacts and consumers. | [archives](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#archives-configuration) |
| 9.1.0 | 10.0.0 | `Configuration.visible` → remove obsolete setting after checking legacy assemble wiring. | [visible](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate-visible-property) |
| 9.1.0 | 10.0.0 | `ReportingExtension.file()` / `getApiDocTitle()`, `JavaForkOptions.setAllJvmArgs()` → use the documented replacement for the receiver; preserve JVM argument partitioning and report paths. | [report files](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#reporting_extension_file), [title](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#reporting_extension_api_doc_title), [JVM args](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#set-all-jvm-args) |
| 9.1.0 | 10.0.0 | Non-string `GradleBuild.startParameter.projectProperties` → explicit strings; toolchain configuration passed with `-P` → Gradle properties via `-D`. | [nested build properties](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated-gradle-build-non-string-properties), [toolchains](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#toolchain-project-properties) |
| 9.2.0 | 10.0.0 | `Project.container(...)` → `ObjectFactory.domainObjectContainer(...)`; RuleSource-based dependency rules → action/component-metadata APIs. Apply Java before calling `registerFeature`. | [containers](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#project_container_methods), [rules](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#dependency_management_rules), [features](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_register_feature_no_java_plugin) |
| 9.3.0 | 10.0.0 | Publishing dependencies on unpublished projects → establish intended publications; do not invent coordinates. | [publication](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#publishing_dependency_on_unpublished_project) |
| 9.3.0 | 10.0.0 | Legacy `Usage` values and self-dependencies by module GAV → current attributes/project dependencies with variant evidence. | [usage](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_legacy_usage_values), [self-dependencies](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#module_identity_for_root_component) |
| 9.3.0 | 10.0.0 | `Wrapper.getAvailableDistributionTypes()` and implicit `ModuleVersionSelector` conversion → documented public replacements; inspect custom plugin code. | [wrapper](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_wrapper_get_available_distribution_types), [selectors](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_moduleversionselector_to_modulecomponentselector) |
| 9.4.0 | 10.0.0 | `DomainObjectCollection.findAll(Closure)` → `matching { ... }`; it is lazy rather than a materialized snapshot, so preserve timing semantics. Plain Java/Groovy collection `findAll` is not this API. | [findAll](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#findAll_removal) |
| 9.4.0 | 10.0.0 | Test `beforeTest` / `afterTest` / `beforeSuite` / `afterSuite` / `onOutput` closure APIs → typed listeners; `testFramework(Closure)` → `options(Action)`. | [test APIs](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_test_methods) |
| 9.4.0 | 10.0.0 | `apply false` in precompiled script plugins, `version` in precompiled settings plugins, `Dependencies.getProject()` → correct plugin dependency/configuration APIs. | [apply false](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_apply_false_in_precompiled_script_plugins), [settings versions](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_version_in_precompiled_settings_script_plugins), [project](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#v9_deprecation_of_dependencies_get_project) |
| 9.5.0 | 10.0.0 | `CreateStartScripts.exitEnvironmentVar` → remove obsolete customization after comparing generated launchers. | [launchers](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_exit_environment_var) |
| 9.6.0 | 10.0.0 | `Project.getProperties()` / `project.properties` and script `properties` → explicit providers/maps; `providers.gradleProperty` does not include `ext` values. | [properties](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_get_properties) |
| 9.6.0 | 10.0.0 | Implicit parent lookup; Develocity plugin <4.0 relies on it → explicit values/conventions and a compatible plugin update. | [lookup](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_implicit_lookup_in_parent_projects), [Develocity](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_develocity_plugin_pre_4_0) |
| 9.6.0 | 10.0.0 | Task dependency relationships, task extensions, or injected `Project`/`Gradle` read in task actions → declared task inputs and supported services. Using a `Task` argument in `dependsOn` closures also changes. | [relationships](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#task_dependencies), [extensions](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#task_extensions), [services](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#injected_service_types_at_execution), [closures](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#task_in_task_dependency_closure) |
| 9.6.0 | 10.0.0 | Undeclared artifact transforms triggered by a task → declare the resolved artifacts as task inputs. | [transforms](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#undeclared_artifact_transform_input) |
| 9.6.0 | 10.0.0 | `Project` objects as dependency notation → `DependencyHandler.project(...)`; repository `artifactUrls` and map overloads → supported repository configuration, preserving provenance. | [projects](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#dependency_project_notation), [artifact URLs](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_maven_artifact_urls), [map overloads](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_repository_handler_map_overloads) |
| 9.6.0 | 10.0.0 | `buildNeeded` / `buildDependents` and `getTaskDependencyFromProjectDependency()` → explicit approved workload/output wiring; preserve upstream/downstream verification coverage. | [tasks](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_build_needed_build_dependents_tasks), [API](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_getTaskDependencyFromProjectDependency) |
| 9.6.0 | 10.0.0 | Remove obsolete PMD `targetJdk`; replace `ProblemSpec.severity()` with the appropriate report/throw reporting method. | [PMD](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_pmd_target_jdk), [severity](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecate_problem_spec_severity) |
| 9.6.0 | null | IDE file-generation tasks/model properties are deprecated; the cited guide does not specify a removal deadline. Do not remove still-supported IDE import model configuration. | [IDE tasks](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#ide_task_deprecation) |
| 9.7.0 | 10.0.0 | Custom collection/map subclasses serialized into configuration cache → standard collections plus explicit separate state. | [collections](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_custom_collection_types_with_cc) |
| 9.7.0 | 10.0.0 | Legacy software model / `model {}` / `RuleSource` → supported component/plugins model. Native/product migration is out of scope; flag and defer rather than rewriting it. | [software model](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_software_model) |
| 9.7.0 | null | `org.gradle.unsafe.isolated-projects*` → new names **only when the running version supports them (9.7+)**. Officially removed in a future release, not specifically 10; currently no warning is emitted. | [legacy names](https://docs.gradle.org/9.7.1/userguide/upgrading_version_9.html#deprecated_unsafe_isolated_projects_properties) |

Kotlin DSL delegate removals require a separate Kotlin audit; mixed DSL is a coverage gap, not a pass. Also review 8.x-origin warnings carried into 9.x using the pinned major/8.x guides; this index does not replace them.

Not announced Gradle-10 removals: `ResolvedArtifactResult.getVariant()` is still available and its deprecation is planned for a future release; configuration cache being preferred does not establish a release where it becomes mandatory. Keep these as advisory roadmap items, not upgrade blockers.

## Parent-project lookup: migration recipes (the big Groovy-DSL one)

The warning looks like:
```
Resolution of the property 'foo' from parent project ':' has been deprecated. This will fail with an error in Gradle 10.
```

**Pattern A — shared version/constant via `ext` in root**
```groovy
// root build.gradle (before)
ext { springVersion = '6.2.0'; javaTarget = 21 }
// child/build.gradle
implementation "org.springframework:spring-core:$springVersion"
```
→ Versions go to `libs.versions.toml`. Non-version constants go to root `gradle.properties` (`javaTarget=21`) and are read with `providers.gradleProperty('javaTarget')`, or — better — become defaults inside a convention plugin.

**Pattern B — helper method defined in root, called from children**
```groovy
// root
def configureSpringBoot(Project p) { ... }
subprojects { configureSpringBoot(it) }
```
→ The whole thing becomes a convention plugin (`spring-boot-conventions.gradle`); children apply it via `plugins {}`.

**Pattern C — `findProperty('x')` in a child expecting root `ext.x`**
→ Same as A. If the value is user-overridable, `providers.gradleProperty('x').orElse('default')` reads from `gradle.properties`, `-P`, `ORG_GRADLE_PROJECT_x`, and is CC-friendly (9.1/9.4/9.6 improved hit rates for exactly this).

**Pattern D — explicit but still cross-project: `rootProject.ext.foo` / `parent.someMethod()`**
→ Not deprecated (it's explicit), but it's cross-project mutable-state access that Isolated Projects forbids. Acceptable as a stop-gap; prefer A/B.

After clearing warnings, **offer a separate Gradle-10 experiment** (requires 9.6+) in `settings.gradle`:
```groovy
enableFeaturePreview('NO_IMPLICIT_LOOKUP_IN_PARENT_PROJECTS')
```
This changes lookup behaviour. Don't enable it as part of ordinary cleanup; compare the workload against its baseline.

## Already removed in 9.0 (relevant if migrating from 8.x)

- **Custom `Test` tasks may silently run zero tests.** `tasks.register('integrationTest', Test)` no longer inherits `testClassesDirs`/`classpath` from the `test` source set; set both explicitly (`testClassesDirs = sourceSets.integrationTest.output.classesDirs; classpath = sourceSets.integrationTest.runtimeClasspath`). A green build with a dropped test count is the symptom — compare `TEST-*.xml` counts before/after the upgrade.
- Gradle daemon requires **JDK 17+** (project toolchains may still target 8+).
- **Groovy 4**: `groovy.util.XmlSlurper`/`XmlParser` → `groovy.xml.*`; `groovy.util.slurpersupport.*` → `groovy.xml.slurpersupport.*`; `@Grab` behaviour; `Map` literal + GString edge cases; `groovy.json` unchanged.
- `Project.convention` / `getConvention()` / `Convention` type → extensions (`project.extensions`, `java {}`) .
- Selecting a variant by configuration name for **Maven** repositories (`configuration:` on external module deps).
- Much of `org.gradle.util` (`GUtil`, `ConfigureUtil`, `CollectionUtils`, `WrapUtil`, …).
- `sourceCompatibility`/`targetCompatibility` on `Project`-level Java convention (use `java { sourceCompatibility = ... }` or, better, toolchains + `options.release`).
- **Reproducible archives** are the default — builds that patched timestamps into JARs or relied on entry order need review.
- `org.gradle.api.plugins.JavaPluginConvention` and other `*Convention` classes.

## Long-standing deprecations still commonly found in old Groovy scripts

Not 9.x-specific. This table mixes removed/deprecated APIs with recommended lazy alternatives; entries such as `apply plugin:` and eager task access do not universally produce deprecation warnings. Check actual version-specific warnings before classifying a blocker.

| Old | New |
|---|---|
| `buildDir`, `"$buildDir/x"` | `layout.buildDirectory.dir('x')` / `.file('x')` |
| `tasks.create('x')`, `task x { }` | `tasks.register('x') { }` |
| `tasks.test { }` / `test { }` eager access | `tasks.named('test', Test) { }` |
| `tasks.withType(X) { }` (eager) | `tasks.withType(X).configureEach { }` |
| `compile` / `runtime` / `testCompile` configs | `implementation` / `runtimeOnly` / `testImplementation` (removed in 7.0) |
| `mainClassName = '...'` (application) | `application { mainClass = '...' }` |
| `archivesBaseName` | `base { archivesName = '...' }` |
| `jar { manifest { attributes 'Main-Class': ... } }` with `project.version` read in action | capture into local `def` or provider |
| `sourceSets.main.output.classesDir` | `sourceSets.main.output.classesDirs` |
| `configurations.compile.each` | resolve inside a task (see practice T5) |
| `project.file()` / `project.copy {}` in `doLast` | injected `FileSystemOperations`, `ProjectLayout` (practice T10) |
| `useJUnit()` with JUnit 5 deps | `useJUnitPlatform()` + `junit-platform-launcher` runtimeOnly |
| `apply plugin:` | `plugins { }` |
| `maven { url 'http://…' }` | HTTPS required since 7.0 unless `allowInsecureProtocol = true` |
| `duplicatesStrategy` unset with overlapping `from()` | Investigate duplicate contents and choose an explicit policy with approval; `EXCLUDE` can silently drop resources. |
