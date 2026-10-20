# rewrite-testing-frameworks: JUnit 4 to JUnit Jupiter

Rules of the JUnit 4 to 5 steps (`org.openrewrite.java.testing.junit5.*`). Each item is a test or a rule field that
the Recipe left as it was. Until it is migrated, the class still needs JUnit 4 (or the Vintage engine) on the test
class path, and a mix of JUnit 4 and Jupiter annotations in one class runs only one kind of them. Read the resolved
`junit-jupiter`, `junit-vintage-engine` and `system-stubs-jupiter` versions first.

Check, for every rule here: run the migrated test class alone and compare the number of tests that ran with the
number before the Migration. A test that silently stopped running is the usual failure.

## testing/junitparams-conversion-not-supported

A JUnitParams `@Parameters` test whose arguments or parameter converters have no Jupiter form the Recipe can write
(for example `@Parameters(source = ..)` with a provider class, `@TypeConverter`, or a `parametersFor..` method that
does not return `Object[]`). The method keeps its JUnitParams annotations.

- Rewrite it as `@ParameterizedTest` with the matching source: `@CsvSource` for inline strings, `@MethodSource` for
  a static factory that returns `Stream<Arguments>`, `@ArgumentsSource` for a provider class.
- A `@TypeConverter` becomes an `ArgumentConverter` with `@ConvertWith` on the parameter.
- Remove `@RunWith(JUnitParamsRunner.class)` only when no method in the class still uses JUnitParams.

## testing/testcase-set-name-commented-out

`setName(..)` of `junit.framework.TestCase` was commented out, as Jupiter has no test name to set.

- When the name only labelled the test in reports, use `@DisplayName` and delete the comment.
- When code read the name back (`getName()`), inject `TestInfo` and use `testInfo.getDisplayName()` or
  `getTestMethod()`.
- When nothing used it, delete the comment and resolve as `fixed`.

## testing/expected-exception-not-migrated

An `ExpectedException` rule was kept, because a test that uses it reads a local variable that is reassigned, which
an `assertThrows(..)` lambda cannot capture.

- In each such test, copy the reassigned variable into an effectively final local before the call, or move the
  throwing call into a helper method, then wrap the call in `assertThrows(Expected.class, () -> ..)`.
- Move `expectMessage(..)` and `expectCause(..)` to assertions on the exception that `assertThrows` returns.
- Delete the rule field when no test uses it.

## testing/expected-system-exit-not-migrated

A System Rules `ExpectedSystemExit` rule was kept: other classes (subclasses) may use it, an expectation is set
outside a test method body, or the code after it cannot move into a lambda.

- In each test, wrap the code that exits in System Stubs' `int status = catchSystemExit(() -> ..)` and assert
  `assertEquals(expected, status)`.
- An assertion registered with `checkAssertionAfterwards(..)` runs after the `catchSystemExit(..)` call.
- A subclass that uses the rule: migrate the subclass tests in the same change, then delete the field.

## testing/system-rule-not-migrated

A System Rules rule (`ProvideSystemProperty`, `SystemOutRule`, `TextFromStandardInputStream`, ...) was kept, because
other classes may use it or a use has no direct System Stubs equivalent.

- Replace the field with the System Stubs equivalent annotated `@SystemStub` (`SystemProperties`, `SystemOut`,
  `SystemErr`, `SystemIn`), and add `@ExtendWith(SystemStubsExtension.class)` to the class.
- Migrate a use without a direct equivalent by hand: for example set properties in `@BeforeEach` with
  `systemProperties.set(..)`, or read output with `systemOut.getLinesNormalized()`.
- A subclass that uses the rule: migrate it in the same change.
