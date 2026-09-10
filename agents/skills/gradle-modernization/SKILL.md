---
name: gradle-modernization
description: Modernize a Java projects Gradle build configuration to use modern features and best practices.
disable-model-invocation: true
---

# Gradle modernization

## Scope
- Gradle Groovy DSL (`.gradle` files)
- Kotlin DSL and Android/AGP are out of scope

## Phases
1. **Audit and report.**
2. **Apply changes, one approved group at a time.** After each group, make sure that build behavior did not change.

## Reference files

| File | Use |
|---|---|
| `references/gradle-8x-features.md` | Builds that start on 8.x. |
| `references/gradle-9x-features.md` | Full audit, or a question about one 9.x version or feature. One section per version 9.0 to 9.7. Only changes to act on and behavior changes that can break the build. |
| `references/best-practices.md` | Full audit, or a question about one practice. 44 official practices plus companions C1 (dependency locking) and C2 (consistent resolution). Each has Detect, Fix and Risk. |
| `references/gradle-9-deprecations.md` | 8.x to 9.x transition |
| `references/gradle-10-deprecations.md` | Preparation for future 10.x release |
| `references/report-template.md` | Structure of the audit report. |
| `references/groovy-dsl-idioms.md` | Groovy DSL idioms |

## Phase 1: Audit

Run a subagent to gather facts for the other stages, output into `facts.json` file.
For each command, using `jq` command, add additional facts into the file.

### Step 0. Gather facts
- java -v
- ./gradlew --version
- ./gradlew tasks --all
- ./gradlew dependencies

### Step 1. Must apply changes
- Mockito agent:
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
- `gradle.properties`:
```
org.gradle.caching=true
org.gradle.parallel=true
org.gradle.configuration-cache=true
org.gradle.configuration-cache.entries-per-key=5
org.gradle.jvmargs=-Xmx2g -XX:MaxMetaspaceSize=1g
```

### Step 2. Walk the references

1. Read `best-practices.md` from top to bottom. Mark each practice: ✅ followed, ❌ violated, ➖ N/A, ❓ not checked, ⚠ suspected (scanner lead, not verified).
2. Read `gradle-9x-features.md` for every version between the current version and the target version. If the current version is 8.x, start with `gradle-8x-features.md` from the current version to 8.14, then continue with `gradle-9x-features.md` §9.0.0.
3. For **every version transition**, also read `gradle-10-deprecations.md` and the official upgrade guide pinned to the target version. For 8.x to 9.x, also read `gradle-9-deprecations.md`, the major upgrade guide and the latest 8.x guide.
4. Review breaking changes and changed bundled-tool defaults, even if the build shows no warnings.
5. Do not infer a removal deadline from a chapter title.

### Step 3. Plugin compatibility inventory

This step is mandatory when the target version differs from the current version.

- List every plugin with its version and the Gradle and JDK ranges it supports. Sources: the plugin portal page and the plugin release notes.
- Keep four JDK concerns separate: daemon JVM, compilation toolchain, bytecode target (`options.release`) and test runtime.
- A plugin that does not support the target Gradle blocks the wrapper upgrade. Update or replace the plugin first.

### Step 4. Write the report

Use `report-template.md`. For each finding, give: rule ID, location, evidence, confidence, consequence, verification method and risk.

- Put build blockers and measurable benefits before naming preferences.
- Measure representative timings before you propose a performance-driven restructuring.
- Order the candidate groups by prerequisites first, then by risk.
- "No changes recommended" is a valid result. Do not add speculative violations to raise a best-practice score.

### Step 6. Stop

Ask the user which groups to apply.

## Phase 2: Apply approved groups

Apply one group at a time. For each group:

### Isolate the change

- Start from a clean tree. Commit or stash pending work first, or record which files were already dirty.
- Make only the edits of this group. `git diff` must show only this group.
- Rollback: `git checkout -- <files>` and remove the new files that the group created.
- Do not stage or commit unless the user asks.

## Group-specific rules

### Wrapper upgrades

Do the steps in this order:

1. Clear the deprecation warnings on the current version.
2. Update or replace the plugins that do not support the target version.
3. For 8.x to 9.x: move to the latest 8.x first, 8.14.5, and clear its warnings with `gradle-9-deprecations.md`. The upgrade guide recommends this. 8.14.4 fixed two security advisories, so 8.14.3 and earlier are not acceptable intermediate versions.
4. Run `./gradlew wrapper --gradle-version=<target> --gradle-distribution-sha256-sum=<sha>`. Get the checksum from https://gradle.org/release-checksums/. Run the command a second time so that the new Gradle regenerates the wrapper jar and scripts.
5. Run `help --warning-mode=all` on the new version.

Select the latest version that every plugin supports. Report the gap to the newest release.

### Version catalog migration

- Keep the existing catalog architecture: imported, published, programmatic and multiple catalogs.
- Move external library and plugin versions as defined in D3. Do not move unrelated strings.
- The `plugins {}` blocks of settings plugins and precompiled plugins cannot use project catalog `alias()`.
- Catalog TOML supports rich versions such as `strictly` and `prefer`. It does **not** support classifiers, artifact types, excludes, attributes or capability requirements. Keep those at the dependency declaration site. Example: `implementation(variantOf(libs.foo) { classifier('test-fixtures') })`. Keep existing closures and constraints.
- Defer everything that the catalog cannot express identically.
- Success means equal dependency and artifact evidence, not zero GAV strings. An incremental migration is valid.

### Dependency locking

- Locking does not require a catalog or convention-plugin migration.
- Before you propose anything, read the current state per project from `facts.build_facts.<build>.locking`. A declaration that does not activate locking, or an activated project without a lock file, is a defect to fix. It is not existing coverage to keep.
- Keep existing per-configuration locking and custom lock locations.
- Enable locking and generate the lock state in the same group, per project (C1). Use `DEFAULT` mode while bootstrapping. Switch to `STRICT` when each locked configuration has state.
- Include the generated lock files in the diff.
- Resolved versions must not change when you only enable locking.
- A selective update can change other modules through resolution rules. Review the whole lock diff.
- Settings plugin versions and dependency verification are separate concerns.

### Convention plugins

Convention plugin extraction preserves behavior. It is not a policy change.

- Logic moved from `subprojects {}` into `build-logic/src/main/groovy/*-conventions.gradle` must reproduce the existing configuration exactly: same Java target, same compiler arguments, same test framework, same parallelism.
- `best-practices.md` § "Convention plugin skeleton" separates the behavior-preserving base from optional policy upgrades. Each policy upgrade is its own approval item with its own verification. Examples: toolchain bump, `-Werror`, JUnit Platform, `maxParallelForks`, sources jar.
- Use `groovy-gradle-plugin` in `build-logic/build.gradle`.
- Migrate one subproject at a time.
- `tasks --provenance` before and after must show the same task set.

### Configuration cache

- Enable the configuration cache only after store-then-reuse succeeds on the verification task set.
- Mark incompatible tasks with `notCompatibleWithConfigurationCache('reason')`.
- List the blocking plugins in the report. Do not keep the cache off without a statement.

### Product source and test files

Do not edit application source files or test files. Source moves (S1, S2), removal of Cucumber runners and test migrations are proposals, not executions. Build-logic extraction can create or edit `build-logic/src/**` and `buildSrc/src/**`. These are build tooling, not product sources.

### Behavior-affecting groups

These groups are medium or high risk: exclusion narrowing (D8), redundant dependencies (D6), `consistentResolution` (C2), `sourceCompatibility` to toolchain, and test framework changes. Explain the observable effect. Run the full test and dependency comparison above.

## Groovy DSL idioms for rewrites

Read `references/groovy-dsl-idioms.md` before you edit a build script. Each rewrite must use the lazy, declarative forms in that file.

## Do not recommend

- Kotlin DSL. This is official practice G1, but it is out of scope by user decision. Mention it once as "not applied".
- Feature previews or incubating features, for example Isolated Projects. If the user asks for one, tell the user that it is incubating. Make it a separate decision.
- Java target bumps, `-Werror`, test framework changes or higher parallelism as part of "modernization". These are policy changes. Offer them separately.
