# rewrite-gradle: build

Rules of the Gradle build steps of a Migration (`org.openrewrite.gradle.*`). Facts come from the build: run
`./gradlew -q javaToolchains` and read the resolved toolchain before choosing a version.

## build/java-compatibility-not-updated

`sourceCompatibility`, `targetCompatibility` (or `setSourceCompatibility(..)`, `setTargetCompatibility(..)`) was not
set to the new Java version, because its argument is not a version literal: a variable, a property, or an expression.
The build may still compile for the old version.

- Find where the value comes from (`gradle.properties`, an `ext` property, a version catalog, a convention plugin)
  and set it there, so that every project that reads it gets the new version.
- Prefer one `java { toolchain { languageVersion = JavaLanguageVersion.of(N) } }` when the build has no reason for a
  separate compatibility setting.

Check: `./gradlew -q properties` shows the new `sourceCompatibility` and `targetCompatibility`, or the compiled
classes have the new major version (`javap -v` shows `major version`).
