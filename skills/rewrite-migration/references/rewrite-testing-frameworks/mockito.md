# rewrite-testing-frameworks: PowerMock to Mockito

Rules of `org.openrewrite.java.testing.mockito.ReplacePowerMockito` and its steps. Mockito does not mock private
methods, constructors of classes it does not create, or suppress static initializers, and it does so on purpose. A
test that needs these needs a change to the code under test or to the test design, not a different mocking call.
Read the resolved `mockito-core` version first: static and construction mocking need `mockito-inline` before 5.0.

## testing/powermock-usage-not-migrated

A PowerMock feature with no Mockito equivalent (`MemberModifier.suppress`, `PowerMockito.verifyNew`, `Whitebox`,
stubbing a private method, ...). The source is not changed, and the migration removes PowerMock, so this does not
compile after the Run.

- Static methods: `Mockito.mockStatic(..)` in a try-with-resources block.
- `whenNew(..)` and `verifyNew(..)`: `Mockito.mockConstruction(..)`, or inject a factory into the class under test.
- Private members and `suppress(..)`: change the code under test (package-private method, extracted collaborator,
  injected dependency), then test through it.

## testing/powermock-private-method-stubbing

`doNothing().when(instance, "method", args..)` (or `doReturn`, `doThrow`) on a private method was left as it was.

- Make the method package-private and stub it on a spy with `doNothing().when(spy).method(args..)`, or extract it to
  a collaborator that the test mocks.
- When the stubbing only kept a side effect out of the test, consider whether the test should cover that side
  effect instead.

## testing/powermock-test-disabled

The Recipe disabled the test (`@Disabled`, `@Ignore` or TestNG `@Ignore`) and commented out its body, or the whole
class when the use was outside a test method. The test does not run, so the build passes without it.

- Rework the test not to depend on private members (see `testing/powermock-usage-not-migrated`), uncomment the body,
  and remove the disabling annotation.
- When the test cannot be reworked now, resolve as `deferred` with a note that names the test, so the human sees
  that coverage is missing.

Check: the re-enabled test runs and passes; the count of tests that ran goes up by the tests you re-enabled.
