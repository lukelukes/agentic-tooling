---
name: testing-philosophy
description: Honeycomb test strategy for everyday suites in any language - big hermetic slice (e2e) tests and integration tests first, few unit tests - with classical-school mocking and table-driven cases. Use when writing a test suite for a module or feature, reviewing or refactoring brittle, mock-heavy, or copy-pasted tests (including suites that break on refactors yet let bugs through), choosing the test level, deciding what to mock, or converting similar cases into parameterized tables. Hand off invariants over large input spaces to property-based-testing, and fault injection, crash/recovery, or adversarial-oracle campaigns to sqlite-testing-philosophy.
---

# Testing philosophy

A good test fails only when observable behavior breaks and says exactly what broke. Use the project's language, test framework, and existing conventions.

## 1. Orient

Identify the mode: **write** (add tests, run them) or **review** (findings, then refactor only if asked). Read the code under test, its callers, the existing tests, and the commands that run them (build files, CI config, `Makefile`, `package.json`).

Map the system: its **entry points** (HTTP handlers, CLI commands, message consumers, the public service API), its **managed** dependencies (your own database, cache, queue, file store: only your app touches them) and its **unmanaged** dependencies (SMTP, payment provider, other teams' APIs, a bus other systems read: interactions are visible outside).

Classify each piece of code by Khorikov's quadrant (the last column is this skill's honeycomb rule, not Khorikov's; he unit-tests the domain quadrant heavily):

| Code | Complexity / domain weight | Collaborators | Test with (this skill) |
|---|---|---|---|
| Domain model, algorithms | High | Few | Unit tables, only if the input space is too wide for slices |
| Controllers, orchestration | Low | Many | Slice and integration tests only |
| Trivial code | Low | Few | Nothing directly |
| Overcomplicated | High | Many | Refactor into the two above first |

Finish with a short list: entry points, dependency classification, and which units (if any) earn unit tests.

## 2. Default portfolio: the honeycomb

This is a deliberate departure from Google's 70/20/10 unit-heavy pyramid (and from Khorikov's pyramid). See [strategy](references/strategy.md) for the reasoning and the costs it accepts.

1. **Slice tests (the bulk of feature coverage).** Enter at the real entry point, run through real wiring and real managed dependencies (a real DB engine in a container or an embedded real engine), and substitute only unmanaged systems. Cover each feature's happy path end to end and its important edge cases, varying data through tables.
2. **Integration tests.** Narrower slices around one component plus its real managed dependency (a repository against the real DB or temp directory, an adapter against a local fake server). Slices prove each feature; integration tests cover component behavior that is awkward or slow to reach from the top (query edge cases, persistence round-trips, adapter mapping, contract tests for any fake). Together the two levels are the bulk of the suite. Some overlap between levels is fine; don't write an integration test that only repeats a slice row.
3. **Unit tests: few, only where necessary.** For features, few unit tests only. Decide per unit:
   - Is it in the domain/algorithm quadrant? If no, stop: no unit test.
   - Would covering its cases through a slice be slow, obscure, or combinatorially large (parsers, pricing rules, state machines, date math)? If no, stop: the slice covers it.
   - Can the test reach it through a public API that survives refactoring? If no, extract the logic into a pure function or class first.
   - Then write one table-driven unit test for it.

Slice tests stay **hermetic**, deterministic, and parallel-safe: per-test data isolation, dynamic ports, injected clock and ID generator, no sleeps (poll with a bounded timeout), no dependence on shared environments or other teams' live services.

## 3. Rules

Each rule is explained with do/don't snippets in [principles](references/principles.md).

- **Observable behavior through the public API.** Assert what a caller or external system can see: responses, persisted state, messages emitted to unmanaged systems. Read persisted state through the entry point's API; if it exposes no reader, read through the public methods of the real managed store (a fresh instance on the same DB/directory is fine), never through mocks or private fields. Seed state the same way when no feature API creates it. Private methods and internal call order are implementation details, unless the documented contract promises an order (e.g. "persisted before the e-mail"); then check it through observable state, such as a spy that reads the store when called.
- **Resistance to refactoring is non-negotiable** (Khorikov's four pillars: regression protection, resistance to refactoring, fast feedback, maintainability). A test whose *assertions* turn red on a behavior-preserving refactor has zero value; rewrite it, or delete it once replacement coverage of the same behavior exists. Updating construction, wiring, or harness setup after a refactor (e.g. a new constructor dependency) is normal maintenance, not brittleness.
- **Assertion style: output > state > communication.** Prefer return values, then resulting state; verify interactions only for outgoing calls to unmanaged dependencies.
- **Mock policy (strict classical school).** Real in-process collaborators always; the one exception is nondeterminism controls (clock, randomness, ID source, scheduler), which get fixed or controllable implementations. Managed dependencies (own DB, cache, file store) use the real engine in slice and integration tests; fake one only when no real engine can run hermetically on one machine, and then the fake must pass the same contract tests as the real adapter. Otherwise fakes, stubs, spies, or mocks **only** for unmanaged out-of-process dependencies, at the last type your code owns before the wire. Stubs supply input; never assert that a stub was called (asserting on output that carries stub-supplied data, such as a stored payment id, is fine).
- **DAMP over DRY.** Each test reads alone: relevant values visible in the test body, irrelevant ones hidden behind builders with defaults. Share builders and harnesses, never mutable fixtures.
- **Straight-line tests.** No loops or branches that pick the scenario or compute the expected value; write expected values as literals obtained independently from the code. A table runner (section 4) is the one allowed loop. Conditions that only fail the test are fine: Go's `if got != want { t.Errorf }` and `if err != nil { t.Fatal }`, prerequisite guards, and TypeScript narrowing that throws or fails (`if (r.kind !== "ok") throw ...`) instead of an `as` cast.
- **One behavior per test, arrange/act/assert.** The act is usually one line; several acts mean several tests (slow slice tests may chain steps of one scenario).
- **Behavior names.** Name the scenario and outcome in domain language (`rejects_order_when_stock_is_insufficient`), not the method.
- **Clear failure messages.** Show the input, got, and want; use diffing assertions for structures.
- **Control nondeterminism by injection.** Clock, randomness, IDs, and concurrency come in as dependencies; domain code takes `now` as a value. Random test-data isolation keys that are never asserted on need no injection.
- **Coverage is a negative indicator only.** Use it to find untested behavior, never as a target.

## 4. Tables when the shape matches

Default to a table (Go `t.Run` over a slice or map, JUnit `@ParameterizedTest`, Vitest `test.for`/`test.each`) when cases share one arrange/act/assert shape and differ only in data. At slice level, boot the harness once and vary requests per row; give each row fresh data (or a fresh cheap in-process harness) when rows change state. "Few unit tests" counts unit-tested units and test methods, not rows: one dense boundary table for one algorithm is fine.

Every row carries a behavior name that appears in failure output (if the runner or reporter hides display names, put the name in the assertion message too), and holds data only. Split into separate tests or separate tables when rows need per-row setup or mock behavior, function-valued fields, `if`/`switch` in the runner beyond one early return for error rows (fail-the-test assertion checks don't count), different assertions, or a runner you must read to understand a row. Valid and invalid inputs usually get separate tables.

Language idioms: [Java/JUnit](references/java-junit.md), [Go](references/go.md), [TypeScript/Vitest](references/typescript-vitest.md).

## 5. Write mode

1. Run the existing suite first and record the command and result.
2. Pick the largest practical entry point and build or reuse a slice harness (real wiring, real managed deps, fakes/spies for unmanaged deps, injected clock).
3. Write slice tests per feature: happy path, then edge cases and error paths that callers can observe, as table rows where the shape matches.
4. Add unit tables only for units that passed the decision in section 2.
5. Run the tests. Then prove at least one important test **goes red** for a plausible defect: copy the module (or use a git worktree), apply one mutation to the copy (flip a boundary, drop a write), run the suite against the copy, confirm the intended test fails with a readable message, and discard the copy. Never edit the original production files. Pick mutations that change observable behavior.
6. Report: tests added per level and why, commands run and outcomes, the demonstrated red, and any gaps left. Put all of it in one report. If the task names a report file, that file is a requested deliverable: write it. If your environment forbids writing it, say so and give the complete report inline.

If production code blocks testing (hidden `new` of an unmanaged client, static clock, logic fused with I/O), make the smallest seam that injects the dependency; production behavior must stay on the real path.

## 6. Review mode

Read the suite against the rules. Report each finding as:

`severity | file:line or test name | principle violated | concrete fix`

Assign severities only from the review checklist in [principles](references/principles.md#review-checklist); it is the single rubric. Where you can, prove findings: apply a behavior-preserving refactor in a disposable copy and show the brittle tests go red (false positive), and apply a real defect and show the old suite stays green (false negative).

When asked to refactor, keep the suite green at every step:

1. Run the suite; record baseline.
2. Add the replacement slice or integration test first and see it pass.
3. Show it goes red for the defect the old test was meant to catch (mutating a disposable copy, as in write mode). This step is required: report the mutation diff, the command run against the copy, and the named test that failed. "The new suite would catch it" without a run does not count.
4. Delete or collapse the brittle tests (mock-heavy unit tests of orchestration, copy-pasted cases into a table).
5. Re-run; report tests removed, added, behavior still protected, and the demonstrated red from step 3.

## 7. Handoffs

- Invariants over large or structured input spaces (round-trips, idempotence, model-based stateful tests): read `../property-based-testing/SKILL.md` (relative to this skill's directory; that skill is not auto-invoked).
- Dependency fault schedules, crash/recovery, persistence atomicity, adversarial or differential oracles: use the `sqlite-testing-philosophy` skill.

Keep this skill's tests as the everyday suite; those skills add targeted campaigns on top.

## References

- [strategy.md](references/strategy.md): honeycomb in depth, slice selection, hermetic and fast slice tests, departure from the pyramid.
- [principles.md](references/principles.md): rules with snippets, quadrant, managed vs unmanaged table, test-double taxonomy, review checklist.
- [sources.md](references/sources.md): provenance and where sources disagree.
