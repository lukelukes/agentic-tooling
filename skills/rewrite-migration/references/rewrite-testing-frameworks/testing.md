# rewrite-testing-frameworks: testing

Rules that the JUnit 6 migration (`JUnit5to6Migration`, chained from Spring Framework 7) reports, where the anchor is
the `group:artifact` of the dependency in the build file, and the Testcontainers 2 rule.

## testing/junit-migrationsupport-kept

The module's code uses `org.junit.jupiter.migrationsupport` (JUnit 4 rules in Jupiter tests), so the migration kept
`junit-jupiter-migrationsupport`, which JUnit 6 deprecates; it moves to JUnit 6 with the other Jupiter artifacts. The
`setting` names the kept dependency.

- Leave the item unresolved. Rewriting the tests to Jupiter extensions and dropping the dependency is an Improvement:
  set `adopted` only when the human asks for it, after the tests no longer use the migration support.

Check: the tests that use the rules still run (`--verify=test`), and their count did not drop.

Source: [JUnit 6.0 release notes](https://docs.junit.org/6.0.0/release-notes/).

## testing/junit-version-differs-from-bom

The module declares a JUnit artifact with an explicit version that differs from the one the Spring Boot BOM manages:
in Maven the BOM of the parent or an import, in Gradle the BOM of `io.spring.dependency-management` or a
`platform(..)` the build file declares. The migration removes explicit versions equal to the BOM's and keeps this one
unchanged (it does not raise it to JUnit 6) as the user's choice; the `setting` names the kept dependency.

- Leave the item unresolved when the version is a deliberate hold. Dropping the version, so the Spring Boot 4 BOM
  brings the JUnit 6 version it manages, is an Improvement: set `adopted` only when the human asks for it.
- If verify fails because the kept JUnit version and the JUnit platform of Spring Boot 4 do not match, report it: the
  hold has to be revisited with the team.

Check: `mvn dependency:tree` (or `gradle dependencies --configuration testRuntimeClasspath`) shows one JUnit version
line, and `--verify=test` runs the tests.

Source: [Spring Boot dependency versions](https://docs.spring.io/spring-boot/appendix/dependency-versions/coordinates.html).

## testing/testcontainers-junit4-container-rule

Testcontainers 2 containers are no longer JUnit 4 `TestRule`s. `AddTestcontainersAnnotations` turns a container
`@Rule`/`@ClassRule` into `@Container` with `@Testcontainers` on classes that the JUnit 4 to 5 migration left on
JUnit Jupiter. A class still on JUnit 4 (`@RunWith`, or JUnit 4 test or lifecycle annotations) is left unchanged, and
so is one whose superclass or subclass stays on JUnit 4. When the Run contains the JUnit 4 to 5 migration (a Spring
Boot migration does), only a JUnit 4 runner that migration does not replace keeps another class of the hierarchy on
JUnit 4; when it does not (the Testcontainers 2 migration on its own), every JUnit 4 class does. Each container field
left unchanged is reported, anchored on the field. The test class does not compile, or the container never starts.

- Move the class, and the classes of its hierarchy, to JUnit Jupiter, then use `@Testcontainers` and `@Container`
  (or let Spring Boot's `@ServiceConnection` manage the container).
- If the class has to stay on JUnit 4 (a custom runner), start and stop the container yourself: `container.start()`
  in a `@BeforeClass` method, and `stop()` in `@AfterClass`.

Check: the test class runs (`--verify=test`), its test count did not drop, and the container starts.

Source: [Testcontainers JUnit 4 integration](https://java.testcontainers.org/test_framework_integration/junit_4/).
