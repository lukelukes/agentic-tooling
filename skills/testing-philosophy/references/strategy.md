# Test strategy: the honeycomb

## Terms

These words have different meanings in different sources, so this skill fixes them:

- **Slice test**: enters at a real entry point (HTTP handler, CLI command, message consumer, public service API), runs the application's real wiring, and uses real managed dependencies. Only unmanaged external systems are substituted. The user calls these "big e2e tests over huge slices". Spotify calls the same thing an *integration test*. Fowler argues that what honeycomb advocates call integration tests are largely what he calls sociable unit tests.
- **Integration test**: a narrower slice. One component plus its real managed dependency, or one adapter against a local fake of an external system.
- **Unit test**: exercises a pure domain or algorithm unit in-process. It may span several real classes (classical school). Spotify calls these *implementation detail tests*.
- **Integrated test** (Spotify's term): passes or fails depending on another system's correctness, such as a shared staging environment or another team's live service. Keep these out of the normal suite. At most a handful of smoke checks run post-deploy.

## Portfolio

| Level | Share of effort | Real | Substituted |
|---|---|---|---|
| Slice | Most feature coverage | Entry point, routing, serialization, DI wiring, config, domain, persistence, own DB/cache/queue | Unmanaged systems: email, payments, third-party and other-team APIs, externally consumed buses |
| Integration | Together with slices, the bulk; component behavior slices reach awkwardly or slowly | Component under test, managed dependency | Unmanaged out-of-process dependencies only. In-process collaborators stay real; a managed dependency is faked only when no real engine runs hermetically, and then the fake passes the same contract tests as the real adapter |
| Unit | Few; domain and algorithm code only | The pure unit and its in-process collaborators | Nothing, because pure code has no out-of-process dependencies |

For a feature, acceptance is proven at slice level. Unit tests in a feature are the exception. They are reserved for logic whose case table would be slow or unreadable through the slice.

## Choosing slices

1. List the features and user-visible promises in scope.
2. For each one, pick the **widest entry point that can still run hermetically on one machine**. Prefer an in-process server or handler invocation (`httptest`, `MockMvc`/`WebTestClient` or a random-port server, `supertest`/`app.inject`) over a deployed environment.
3. Pick the **longest happy path**, the one that touches every managed and unmanaged dependency the feature uses. That test proves the wiring.
4. Add rows or tests for edge and error cases a caller can observe: validation failures, conflicts, not-found, authorization, idempotent retries. Leave out fail-fast guards that are obvious from one row.
5. Push a case down to a unit table only when it passes the decision in SKILL.md section 2.
6. When a slice test finds a bug, reproduce the bug at the lowest level permitted by SKILL.md section 2 where it still shows up. That is a unit row only for logic that already qualifies for a unit table; orchestration and wiring bugs stay as slice or integration regressions. Keep that reproduction as a regression test.

## What gets asserted in a slice test

- The response (status, body, error shape) at the entry point.
- Persisted state, read back **through the public API** where possible. When no API exposes it, read through the real managed store's public methods (a fresh store instance on the same DB or directory proves it was really persisted). Never read it through a direct query against internal tables or columns.
- Outgoing messages to unmanaged systems, captured by a spy or fake at the edge: the last adapter your code owns (e.g. `EmailSender`, `PaymentGateway`), or a local fake HTTP server. Also assert the call count, and that no unexpected calls were made.

Never assert on internal calls between your own components.

## Keeping slice tests hermetic, fast, and parallel

**Managed dependencies: use the real engine.**
- Run the production engine and version with Testcontainers (Java, Go, Node), or with an embedded real engine when production uses the same one (SQLite in-process).
- Pin image tags; never use `latest`.
- Start one container per test process (singleton), and never share mutable data between tests.
- Wait for readiness with wait strategies, not sleeps.
- Use mapped ports and hosts; never hard-code them.
- Replace an in-memory engine with a substitute only if it behaves the same (an H2 "compatibility mode" does not).

**Per-test data isolation.** Options, from fastest to most faithful:

| Technique | Speed | Caveats |
|---|---|---|
| Unique IDs or tenant per test in a shared DB | Fastest, parallel | Assert only on your own rows; avoid global counts |
| Template-cloned DB per test (Postgres `CREATE DATABASE ... TEMPLATE`, pgtestdb, IntegreSQL) | Tens of ms, parallel | Postgres-specific; keep failed DBs for debugging |
| Transaction rolled back per test | Fast | Misses work on other threads or connections, `REQUIRES_NEW`, and commit-time constraints; ORM needs an explicit flush |
| Truncate or clean at the **start** of each test | Simple | Serializes tests that share tables |

Prefer the first two options. Only use rollback when the code under test runs on the test's own connection.

**Test data.**
- Create state through the public API or domain factories so fixtures obey real invariants. If no feature API creates the state (e.g. products, coupons), seed it through the real store's public methods.
- Use builders with safe defaults. Each test overrides only the fields it depends on.
- Avoid raw SQL fixtures, which drift from the schema's rules.

**Nondeterminism.**
- Inject the clock, ID or UUID generator, and random source at the composition root; domain code takes `now` as a value.
- For async work, poll with a bounded timeout and a clear timeout message, or wait on an event.
- Advance time with a fake clock instead of sleeping.

**Speed budget.**
- Boot the app and containers once per process. Reuse the harness across tests and table rows.
- Keep test connection pools small but sized for real demand: at least the number of concurrent operations per app instance times the connections each can hold at once (an outer transaction plus a `REQUIRES_NEW` inner one needs 2). A pool below that deadlocks correct code. Catch leaks with a short acquisition timeout and the pool's leak detection (e.g. HikariCP `connectionTimeout`, `leakDetectionThreshold`), not with an artificially tiny pool.
- Run tests in parallel once data isolation holds.
- A suite that takes seconds is fine. A suite that takes minutes needs profiling before more tests are added.

**Diagnosability.** The classic criticism of big tests is that failures are hard to localize. Counter it with:
- Failure messages that name the scenario, the request, the got/want values, and a diff.
- On failure, dump the response body, the relevant rows, and the captured outgoing messages (`t.Cleanup` with `t.Failed()`, a JUnit `TestWatcher`, Vitest `onTestFailed`).
- A test ID tagged into logs.
- Retained per-test databases (template-DB approach).

## Departure from Google's pyramid (deliberate)

Google suggests roughly 70% unit, 20% integration, and 10% E2E as a first guess ("Just Say No to More End-to-End Tests"), adding: "The exact mix will be different for each team, but in general, it should retain that pyramid shape." SWE at Google ch. 11 says about 80/15/5, allows a blend "appropriate to the local architectural and organizational realities", and in the same passage names an E2E-heavy suite the "ice cream cone" anti-pattern. Google's flexibility covers ratios within a pyramid, not a different shape. Khorikov also keeps a pyramid and unit tests the domain heavily.

This skill departs from both on purpose, because the user chose the honeycomb. The reasoning:

- This skill's premise (not a sourced statistic): in typical application code, many defects live in wiring, configuration, serialization, queries, and orchestration, which unit tests with doubles cannot see. Google ch. 14 lists five gaps in unit testing (unfaithful doubles, configuration issues, issues under load, unanticipated inputs and side effects, emergent behavior); the first two matter most here, and the chapter notes that "configuration changes are the number one reason for our major outages".
- Unit tests of orchestration are coupled to structure and break on refactors (Spotify, Khorikov's controller quadrant).
- Google's objections to E2E tests are of two kinds. The first is *flaky, slow, poorly isolated* tests against shared environments; the mitigations in this file (hermetic single-machine setups, real engines in containers, fakes for other systems, no sleeps, clear messages) address it directly, match Google's own advice for large tests, and fit Google's "medium" size budget. The second is broad failure scope and building and running more code than the change needs; the mitigations only reduce it (one feature slice, not the whole system), and the rest is the cost accepted below.
- Spotify's honeycomb and Kent C. Dodds's testing trophy put integration-level tests at the center. Fowler notes that the shape debate is mostly about definitions. Google does not endorse this shape; the departure rests on the user's decision and these sources.

The cost accepted: suites take seconds rather than milliseconds, and each failure covers more code. If slice tests become flaky or slow, fix hermeticity first. Do not add more unit tests of orchestration to compensate.
