# rewrite-spring: build

Rules that the build Recipes of the Spring Boot 4.0 and 4.1 Migrations report, then general notes. The anchor of a
dependency row is `group:artifact`, of a plugin row `plugin:<id>`; a module-wide row anchors on `<file>`, the build
file.

## build/held-back-version-pin

The Maven build pinned a dependency or plugin below the version the Spring Boot BOM managed before the Run (for
example `com.h2database:h2` 2.1.214 under Boot 3.5, which managed 2.3.232). Such a pin is a deliberate hold, so the
Migration keeps it, also through the parent upgrade, with a `PRESERVED` row; the `setting` names the kept pin
(`pom.xml:com.h2database:h2`). Pins at or above the old managed version are removed when the Boot 4 BOM overtakes
them, and get no row: the patch shows them. Kotlin and REST Assured pins are never held back: the Migration raises
them (Kotlin with its compiler). If the Boot BOM of before the Run could not be downloaded, every pin of the POM stays
and the POM has a `build/recipe-warning` item instead.

- Leave the item unresolved. Dropping the pin (adopting the Boot 4 managed version) is an Improvement: set `adopted`
  only when the human asks for it, after removing the `<version>` (and the version property, if nothing else uses it).
- If verify fails on the kept pin (the old version does not work with Boot 4), report it: the hold has to be
  revisited with the team, not silently dropped.

Check: `mvn dependency:tree` shows the kept version.

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## build/boot-starter-not-added-to-library

The module has no Spring Boot dependency, so the Migration treats it as a library and does not add the Boot 4 starter
that its code or dependencies imply (`spring-boot-starter-restclient` for `org.springframework.web.client` types,
`spring-boot-starter-webmvc-test` for `MockMvc`, `spring-boot-starter-flyway` for a Flyway dependency,
`spring-boot-starter-liquibase` for `liquibase-core`). In a Spring Boot module the Migration replaces `flyway-core`
and `liquibase-core` by their starters; a library keeps them. The anchor names the starter.

- If the module is a library used by Boot applications, resolve `no-change`: the applications bring the starter.
- If the module runs as a Spring Boot application (a Boot parent or plugin, but no Boot dependency), add the starter
  without a version (the Boot BOM manages it), in place of `flyway-core` or `liquibase-core` where the row is about
  them, and resolve `fixed`.

Check: the module compiles and its tests pass; for an application, the context starts.

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## build/jooq-requires-java21

The module uses the `nu.studer.jooq` Gradle plugin, but its Java sources target a release below 21. The 4.1
Migration raises the plugin to 10.2.1 and jOOQ to 3.21.7 (the version Spring Boot 4.1 manages) only on Java 21, so
it changed nothing here. Spring Boot 4.1 still manages jOOQ 3.21 at runtime, which needs Java 21.

- Move the module to Java 21 (toolchain or `sourceCompatibility`/`targetCompatibility`), then raise the plugin and the
  `jooq { version = ... }` value by hand, or rerun the Migration.
- If the module must stay on Java 17, keep it on Spring Boot 4.0 (jOOQ 3.19) and say so in the summary.

Check: code generation runs and the module compiles and tests pass on Java 21.

Source: [Spring Boot 4.1 release notes](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.1-Release-Notes).

## build/jooq-pinned-version-kept

The `jooq { version = ... }` value of the `nu.studer.jooq` configuration, or the version of the `nu.studer.jooq`
plugin itself, is an expression (a variable or a `gradle.properties` property), so the 4.1 Migration kept it: it
never overwrites a version expression. The `setting` names the kept pin: `build.gradle:org.jooq:jooq` for the jOOQ
version (anchor `org.jooq:jooq`), `build.gradle:nu.studer.jooq` for the plugin (anchor `plugin:nu.studer.jooq`).

- Leave the item unresolved. Raising the version to the 3.21.x that Spring Boot 4.1 manages, or the plugin to 10.2.1,
  is an Improvement: set `adopted` only when the human asks for it, after changing the expression's value.
- If verify fails because generated code and the runtime jOOQ differ, align the expression with the runtime version.

Check: code generation runs with the intended jOOQ version (`./gradlew generateJooq --info`).

Source: [Spring Boot 4.1 release notes](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.1-Release-Notes).

## build/kotlin-k2-crossing

The module was on Kotlin 1.x before the Run. Spring Boot 4 needs Kotlin 2.2, so the Migration raises it, and the
module now compiles with the K2 compiler, which can reject code that Kotlin 1.x accepted (smart casts, resolution
changes, deprecations that became errors). `languageVersion=1.9` is no way back: Kotlin 2.4 no longer supports it.

- Compile the module and fix the K2 errors by hand, following the K2 migration guide.
- Resolve `fixed` when it compiles and the tests pass.

Check: `--verify=compile`, then the module's tests.

Source: [K2 compiler migration guide](https://kotlinlang.org/docs/k2-compiler-migration-guide.html).

## build/kotlin-options-dsl

The Gradle build of a module that crossed to Kotlin 2.2 uses the `kotlinOptions` DSL, which is an error in the Kotlin
Gradle plugin 2.2.

- Move each `kotlinOptions { ... }` setting to `compilerOptions { ... }` (`jvmTarget` becomes
  `JvmTarget.fromTarget(...)`, `freeCompilerArgs` becomes `freeCompilerArgs.addAll(...)`).

Check: the build script configures (`./gradlew help`) and the module compiles.

Source: [Kotlin Gradle compiler options](https://kotlinlang.org/docs/gradle-compiler-options.html).

## build/kotlin-xjsr305

The module passes `-Xjsr305` to the Kotlin compiler. Spring Framework 7 annotates its APIs with JSpecify instead of
JSR-305, and Kotlin 2 reads JSpecify as strict, so the flag no longer decides the nullness of Spring APIs: platform
types become nullable or non-null, and calls can change meaning or stop compiling.

- Compile and fix the nullness errors; review calls whose result Kotlin now treats as nullable.
- Remove `-Xjsr305` when no other JSR-305 annotated library still needs it.

Check: the module compiles without new nullness warnings in Spring API calls, and its tests pass.

Source: [Spring Framework 7.0 release notes](https://github.com/spring-projects/spring-framework/wiki/Spring-Framework-7.0-Release-Notes).

## General notes

These notes apply when a Boot 4 Run leaves a dependency without a version, or when an active version
override decides what resolves. Work from the resolved graph (`dependencyInsight --configuration <name>` in Gradle,
`dependency:tree` in Maven), and the pre-migration build or lockfile when the graph has changed.

## REST Assured

Boot 4 no longer manages REST Assured.

- For each REST Assured artifact the project uses, keep the version it resolved before the upgrade, or import the
  matching REST Assured BOM. Recover that version from the pre-migration build or lockfile.
- Leave projects that do not use REST Assured alone, and leave a version that another BOM still manages to that BOM.
- Resolving the dependency fixes the missing version; the affected tests prove compatibility.

## Version overrides

AssertJ, Jackson and jOOQ version properties (`jackson.version`, `jackson-bom.version`, `assertj.version`,
`jooq.version`, ...) can pin what the Boot BOM would choose.

- Commented-out declarations stay as they are.
- For an active override, find the property, the BOM that honours it, and the reason for the pin. Remove or update an
  override only when it is shown to be obsolete or incompatible, then check the resulting graph. A newer explicit
  version may be intentional.
- Check jOOQ runtime and code generation versions together where the build generates code.
- Check whether a Jackson override controls Jackson 2 or Jackson 3: `jackson.version` and `jackson-bom.version` are
  different properties.

Check: resolve the test runtime class path and run the affected tests.

## build/maven-skiptests-aot

The POM binds the `process-test-aot` goal of `spring-boot-maven-plugin`. On Spring Boot 4.1 `-DskipTests` no longer skips it. CI files are not scanned.

Inspect: the builds (CI, release) that skip tests.

Decide: use `-Dmaven.test.skip=true`, or the plugin's `skip`, in the builds that skip tests.

Prove: a CI build with tests skipped succeeds.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## build/libraries-without-boot4-path

The module depends on a library that has no Spring Boot 4 version: Camunda 7, Axon Framework 4, problem-spring-web, or the net.devh gRPC starters. The message names the replacement.

Inspect: what the module uses the library for.

Decide: port to the replacement, or keep the module on Spring Boot 3.5.

Prove: the module's tests pass under `rewrite run verify --level test`.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## build/maven-optional-deps-uber-jar

Spring Boot 4's `repackage` leaves optional dependencies out of the uber jar unless `<includeOptional>true</includeOptional>` is set; the jar then fails only when it starts. Reported per compile or runtime dependency with `<optional>true</optional>` (also through a property; not Lombok, the configuration processor or DevTools), in modules whose effective build runs `spring-boot-maven-plugin`'s `repackage` goal: an execution of the module or a parent POM, or the one `spring-boot-starter-parent` manages.

Inspect: whether the application needs the dependency at runtime.

Decide: per dependency: drop `<optional>`, set the plugin's `includeOptional`, or leave it out on purpose.

Prove: the packaged jar starts; on the fixture, pin 51 (`PackagedJarPinTest`, failsafe).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).
