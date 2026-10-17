# Principles in depth

The snippets below are pseudocode in a Java-like style. See the language files for idiomatic forms.

## Observable behavior through the public API

Test what a client can see: return values, state readable through the API, and messages sent to external systems. Communication between your own classes is an implementation detail. Communication with unmanaged external systems is part of your contract.

```text
DON'T  assertThat(service.cache.size()).isEqualTo(1)          // private state
DON'T  verify(repo).save(any())                                // internal collaborator
DO     api.post("/users", alice); assertThat(api.get("/users/alice").status).isEqualTo(200)
```

Private methods are never tested directly. If private logic is complex enough to deserve a table, extract it into a class or function with its own public API (Khorikov: `GetPrice()` becomes `PriceCalculator`). Never widen visibility, and never add test-only methods to production code (code pollution).

## Four pillars

A test's value is the product of four scores: protection against regressions, resistance to refactoring, fast feedback, and maintainability. A zero on any one pillar makes the test worthless.

- **Resistance to refactoring** is essentially binary, so it is non-negotiable.
- **Maintainability** is also held high.
- The real trade-off is protection versus speed.

Slice tests maximize protection and resistance, and pay in speed. Hermetic engineering buys most of that speed back (see strategy.md).

A **false positive** is a red test on a behavior-preserving change. False positives teach teams to ignore red builds and to stop refactoring, which is why they are the main thing reviews hunt for.

## Output > state > communication

1. **Output-based**: feed input, check the return value. Fewest false positives. Only possible for pure code, which is one reason to push logic into a functional core.
2. **State-based**: check the state after the act, read through the public surface.
3. **Communication-based**: check calls to a collaborator. Use it only for outgoing commands to unmanaged dependencies.

## Code quadrants

| | Few collaborators | Many collaborators |
|---|---|---|
| **High complexity / domain weight** | Domain model, algorithms: Khorikov unit-tests these heavily; this skill writes unit tables only when the input space is too wide for slices (SKILL.md section 2) | Overcomplicated: split with the humble object pattern into a pure core plus a thin orchestrator |
| **Low complexity** | Trivial (getters, constructors, mapping one-liners): don't test directly | Controllers and orchestration: slice and integration tests only |

Code should either talk to the outside world or make decisions, never both. A class that needs a partial mock to be tested is overcomplicated: split it rather than mocking around it.

## Managed vs unmanaged dependencies

| Dependency | Kind | In slice/integration tests | Why |
|---|---|---|---|
| Your service's own database | Managed | Real engine (container or embedded same engine) | Only your app sees it; its interactions are implementation details |
| Your own cache (Redis) or internal queue only your service reads | Managed | Real engine | Same reasoning |
| Local file system used for your own storage | Managed | Real temp directory per test | Cheap and real |
| SMTP / email provider | Unmanaged | Spy or fake at your `EmailSender` adapter | Messages are observable to the outside world |
| Payment or third-party HTTP API | Unmanaged | Fake at your adapter, or a local fake HTTP server | The contract is externally visible; the real service is slow and costly |
| Message bus consumed by other services | Unmanaged | Spy at the last publisher type you own | Message shape is a contract |
| Database shared with other applications | Mixed | Real engine; treat the tables others read as a contract | The parts others read are unmanaged |
| Clock, random, UUID | In-process nondeterminism | Inject a fixed or controllable implementation | Determinism |

Mock at the edge: the last type in the chain that your code owns, such as an adapter over the vendor SDK (Khorikov's book and "Unit Testing Dependencies"). Mock that adapter, not the vendor SDK itself. "Only mock types you own" comes from Freeman and Pryce (GOOS); Khorikov treats it as a non-strict guideline and prefers "only mock types you understand". Check the adapter against the real service or a recorded contract in a separate, slower lane.

## Test-double taxonomy

| Double | What it does | Allowed where |
|---|---|---|
| **Dummy** | Fills a parameter and is never used | Anywhere; prefer a builder default |
| **Stub** | Returns canned input for incoming queries | For unmanaged inputs (a third-party rate API). Never assert on stub calls |
| **Fake** | A working lightweight implementation (in-memory repository, local fake HTTP server) | Unmanaged dependencies; a managed one only when no real engine can run hermetically on one machine. The fake must pass the same contract tests as the real implementation, and its owner maintains it |
| **Spy** | Records outgoing calls for later assertions | Preferred form for verifying outgoing messages to unmanaged dependencies; hand-written spies read well |
| **Mock** (framework, pre-programmed expectations) | Verifies interactions | Only for outgoing commands to unmanaged dependencies, at the edge |

Order of preference: real, then fake, then stub or spy at the edge, then mock. **Never** replace managed dependencies or in-process collaborators with mocks.

```text
DON'T  stub.getUserCount() returns 10; ...; verify(stub).getUserCount()      // asserting on a stub
DO     emailSpy = new RecordingEmailSender(); ...; assertThat(emailSpy.sent).containsExactly(welcome("a@x.io"))
```

## DAMP, builders, cause and effect

- The inputs that matter, and the effect they produce, are visible in the test body.
- Boilerplate goes into builders or harness helpers that take parameters.
- Don't share mutable fixtures through fields or `beforeAll`.

```text
DON'T  @BeforeEach setUp() { order = fixtures.standardOrder(); }   // which fields matter?
DO     var order = anOrder().withQuantity(0).build();              // the one field that matters, visible
```

DRY applies to domain knowledge, not to test lines. Duplicated literals across tests are fine.

## No logic in tests; independent expectations

```text
DON'T  expected = baseUrl + "/u/0/photos"; assertEquals(expected, nav.url())  // hides a double-slash bug
DON'T  expected = price * qty * (1 - discount)                               // re-implements the SUT
DO     assertEquals("http://photos.google.com/u/0/photos", nav.url())
DO     assertEquals(Money.of("90.00"), total)                                // hand-computed
```

Test helpers that contain real logic need their own tests.

## One behavior per test; AAA; names

- Arrange, act, assert, separated by blank lines. The act is usually one line. If a behavior needs two calls to stay consistent, that suggests the API is missing an operation.
- Test behaviors, not methods: `processTransaction_sendsEmailWhenBalanceIsLow` and `processTransaction_updatesBalance` are separate tests.
- Names read as facts in domain language: `delivery_with_a_past_date_is_invalid`, not `isDeliveryValid_InvalidDate_ReturnsFalse`.
- Slice tests of one scenario may chain several steps (create, then pay, then ship) when setting up each step separately would be slower and no clearer. Assert after each step.

## Failure messages

A good failure message states the call, the actual value, and the expected value, e.g. `ParseDuration("5x") error = nil, want ErrUnit`. For structures, use diffing assertions (`cmp.Diff`, AssertJ recursive comparison, Vitest `toEqual`). A bare "expected true" message is a finding.

## Determinism

- Inject the clock as a service at the application boundary, and pass `now` as a value into domain methods.
- Don't read a static or ambient clock in new code: it is shared state that blocks parallel runs.
- Exception: when production code must stay unchanged and already reads the ambient clock (`new Date()`, `Date.now()`), scoped fake timers (`vi.useFakeTimers()` + `vi.setSystemTime`) are acceptable. Restore real timers in `afterEach`, and run tests that share that timer environment sequentially (no `test.concurrent`). Name the clock seam as the follow-up fix.
- Treat random sources, UUIDs, and goroutine or thread scheduling the same way when they affect behavior or expected values. Exception: a random value used only as a uniqueness key for test-data isolation (e.g. `c-${randomUUID()}` as a customer id) and never asserted on is fine, as is an uninjected ID generator whose output no assertion depends on.
- A test is flaky if it both passes and fails on the same code. Fix it or quarantine it with a deadline; never add retries to it silently.

## Coverage

Coverage measures reach, not checking. Use uncovered lines to find behavior that has no test, then test that behavior through the slice. Never write tests that exist only to execute lines.

## Review checklist

This is the single severity rubric; SKILL.md review mode uses it. When one test matches several items, report the highest.

- [ ] Assertions on stubs: verifying that a query stub was called, how often, or with which arguments (high). Asserting SUT output that carries stub-supplied data is not this smell: it still checks the SUT's selection, propagation, or mapping, even as the only assertion (Khorikov's own example asserts stubbed data in the returned report: https://enterprisecraftsmanship.com/posts/when-to-mock/). When the stub replaces an in-process or managed collaborator (e.g. a stubbed pricing class whose canned total the test asserts), report it as inappropriate substitution under the next item: the propagation check is real, but the collaborator's own logic is never exercised. Keep that propagation assertion in the replacement test, now against the real collaborator.
- [ ] Inappropriate substitution: managed dependencies (own DB, own cache, own store) are mocked, or an in-process collaborator is stubbed and the test asserts values it supplies, so query, mapping, pricing, or duplicate-detection bugs pass unnoticed (high)
- [ ] Expected values computed with production logic or a copy of it (high)
- [ ] Features with no slice test through a real entry point (high if the feature matters)
- [ ] Interaction verification (call counts, call order, `verify`) on in-process or managed collaborators (medium: breaks on behavior-preserving refactors)
- [ ] Unit tests of controllers or orchestration made of mocks (medium): replace with a slice test
- [ ] Partial mocks or spies on the system under test (medium): split the class
- [ ] Tests of private methods, reflection, widened visibility, or test-only production code (medium)
- [ ] Sleeps, real clock, real randomness that affects behavior or expected values, order-dependent or shared mutable state (medium). Random uniqueness-only isolation keys that are never asserted on are not a finding (see Determinism)
- [ ] Several behaviors or acts in one unit test; `if`/loops in test bodies that select scenarios or compute expected values (medium); assertion checks, fail-fast guards, and type narrowing that fails the test are fine
- [ ] Copy-pasted tests differing only in data (low): collapse into a table
- [ ] Tables with per-row mock setup, function fields, or branching runners (low/medium): split
- [ ] Method-named tests (`test1`, `testProcess`); vague failure messages (low)
- [ ] Trivial code tested directly (low): delete
