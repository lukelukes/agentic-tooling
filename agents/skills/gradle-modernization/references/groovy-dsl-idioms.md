# Groovy DSL Idioms for Rewrites

Use these forms in each build script that a Phase 2 group edits. A rewrite keeps the same behavior in the lazy, declarative form. A rewrite does not change the Java target, the test framework, the parallelism or the compiler flags. Those are policy changes. Each policy change needs its own approval item.

Each row gives the form to write, the form that it replaces and the reason. Write the reason in the report.

## Plugins and dependencies

| Write | Do not write | Reason |
|---|---|---|
| `plugins { id 'java-library' }` | `apply plugin: 'java-library'` | The form is declarative. Gradle resolves the plugin through `pluginManagement`. The catalog alias form needs it. `apply plugin:` is valid in a precompiled convention script that applies a different convention. |
| `plugins { alias(libs.plugins.spring.boot) }` | `id 'org.springframework.boot' version '3.2.0'` | The version is in one place: `gradle/libs.versions.toml`. The alias form is not available in the `plugins {}` block of `settings.gradle` and of a precompiled plugin. |
| `implementation libs.jackson.databind` | `implementation 'com.fasterxml.jackson.core:jackson-databind:2.17.0'` | Catalog alias. Keep classifiers, excludes and attributes at the declaration: `implementation(variantOf(libs.foo) { classifier('test-fixtures') })`. |
| `implementation platform(libs.spring.bom)` | `implementation 'org.springframework:spring-framework-bom:6.2.0'` with `dependencyManagement {}` | The platform is a normal dependency. No extra plugin is necessary. |
| `api` and `implementation` in a library | `compile`, `runtime`, `testCompile` | Gradle removed the old configurations. An `api` dependency is visible to consumers. An `implementation` dependency is not. Keep the existing visibility. Do not change `api` to `implementation` in a rewrite. |

## Tasks

| Write | Do not write | Reason |
|---|---|---|
| `tasks.register('myTask', Copy) { ... }` | `task myTask(type: Copy) { ... }`, `tasks.create(...)` | Gradle configures a registered task only when it is necessary. `task x {}` and `create` realize the task on each invocation. |
| `tasks.named('test', Test) { ... }` | `test { ... }`, `tasks.getByName('test')`, `tasks.test { }` | The project-level `test { }` form realizes the task. `named` keeps the task lazy and gives the type. |
| `tasks.withType(JavaCompile).configureEach { ... }` | `tasks.withType(JavaCompile) { ... }`, `.all { }`, `.each { }` | `configureEach` is lazy. The block form of `withType` and `.all` realize each task of the type. |
| `def gen = tasks.register('gen', Gen) { outputDir = layout.buildDirectory.dir('gen') }` then `tasks.register('zipGen', Zip) { from(gen) }` | `from("$buildDir/gen")` with `dependsOn 'gen'` | The provider includes the task dependency. A `dependsOn` and a path string are not necessary. |
| `group = 'verification'; description = '...'` in `register` | A task with no group | Gradle shows the task in its group in the output of `gradle tasks`. |
| `notCompatibleWithConfigurationCache('reason')` | The cache off for the full build | The reason is visible. The other tasks stay cacheable. |

## Files and directories

| Write | Do not write | Reason |
|---|---|---|
| `layout.buildDirectory.dir('reports')` | `"$buildDir/reports"`, `new File(buildDir, 'reports')` | Gradle 9 removed `buildDir`. If the build directory changes, the provider changes with it. |
| `layout.buildDirectory.file('out.txt')` | `file("$buildDir/out.txt")` | The reason is the same. Use the `file` form for files and the `dir` form for directories. |
| `layout.projectDirectory.file('config/checkstyle.xml')` | `file('config/checkstyle.xml')` in a task configuration | The path is relative to the project directory. It is compatible with the configuration cache. |
| `destinationDirectory = layout.buildDirectory.dir('docs/javadoc')` | `destinationDir = file(...)` | Gradle 9.7 added lazy forms of the eager `File` properties. They are incubating. Write this in the report. |
| `workingDir = '../x'` on a lazy property | `workingDir = file('../x')` | Since 9.6.0, the Groovy DSL converts a `String` to a `File` on a lazy property. It also converts a single value to a `ListProperty`. The two forms are valid. |

## Properties and providers

| Write | Do not write | Reason |
|---|---|---|
| `providers.gradleProperty('release')` | `project.findProperty('release')`, `hasProperty('release')` at configuration time | The provider is a recorded input. Gradle reuses the configuration cache when a `-P` value changes, if no script reads the value at configuration time. |
| `providers.environmentVariable('API_TOKEN')` | `System.getenv('API_TOKEN')` at configuration time | The reason is the same. If a script reads the value at configuration time, Gradle cannot reuse the cache entry. |
| `providers.systemProperty('user.home')` | `System.getProperty('user.home')` at configuration time | The reason is the same. |
| `archiveFileName = 'app.jar'` | `archiveFileName.set('app.jar')`, `archiveName = 'app.jar'` | In the Groovy DSL, `=` sets a value or a provider on a `Property`. Gradle removed the old eager setters. |
| `mainClass = 'com.example.Main'` in `application {}` | `mainClassName = '...'` | Gradle 9 removed `mainClassName`. |
| `providers.of(GitHash) {}` for a value from a process | `'git rev-parse HEAD'.execute().text` at configuration time | A `ValueSource` runs one time. It is a recorded input. See `best-practices.md` P4 for the class. |
| `providers.gradleProperty(...)` for a value from the root `gradle.properties` | `ext.foo` in the root, read as `foo` in a subproject | Gradle 9.6 deprecated the implicit lookup in parent projects. Gradle 10 removes it. A convention plugin extension is a different fix. |

## In task actions

| Write | Do not write | Reason |
|---|---|---|
| Get the values at configuration time: `def dir = layout.buildDirectory.dir('x')`. Use `dir.get()` in `doLast`. | `project.buildDir`, `project.version`, `project.file(...)` in `doLast` or `doFirst` | With the configuration cache, `project` is not available at execution time. |
| `logger.lifecycle('...')` | `project.logger`, `println` | `logger` is a task-level service. |
| A task class with `@Inject abstract ExecOperations getExecOperations()` and `execOperations.exec { }` | `project.exec { }` in `doLast` | `project.exec` and `project.copy` fail with the configuration cache. `FileSystemOperations` replaces `project.copy`. For a value, `providers.exec { }` is sufficient. |

## Configuration-time rules

| Write | Do not write | Reason |
|---|---|---|
| `from(configurations.runtimeClasspath)` as a task input | `configurations.runtimeClasspath.files`, `.resolve()`, `.asPath` at configuration time | Resolution at configuration time runs on each invocation. It prevents the configuration cache. See `best-practices.md` T7. |
| `tasks.withType(Test).configureEach { ... }` | `afterEvaluate { tasks.test { ... } }` | `configureEach` runs when Gradle realizes the task. `afterEvaluate` is practice G8. Its result changes with the evaluation order. |
| A convention plugin in `build-logic/src/main/groovy/*-conventions.gradle` | `subprojects { apply plugin: 'java'; ... }` | Each project declares the plugins that it applies. Cross-project configuration is practice S4. Keep the exact configuration when you move it. |
| `java { toolchain { languageVersion = JavaLanguageVersion.of(17) } }` | `sourceCompatibility = '17'` at the top level | Gradle compiles with a JDK 17 that it downloads. Keep the existing target. A bump is a policy change. `foojay-resolver-convention` in settings enables auto-provisioning. |
| `dependencyLocking { lockAllConfigurations() }` | `dependencyLocking { lockMode = LockMode.STRICT }` alone | A `lockMode` without activation does not lock a configuration. See C1. |

## Checks after a rewrite

- `git diff` shows only the files of the group.
- `tasks --provenance` before and after shows the same task set.
- The dependency reports per configuration are equal. A difference is correct only if it is the purpose of the group.
- The strict configuration-cache pair stores and reuses.
