# TypeScript / Vitest

Targets Vitest 2 to 4 (verified on 4.1).

## Tables

```ts
import { describe, test, expect } from 'vitest'

describe('parseDuration', () => {
  test.for([
    { name: 'minutes', input: '5m', want: 300_000 },
    { name: 'mixed units', input: '1h30m', want: 5_400_000 },
  ])('$name: parses $input', ({ input, want }) => {
    expect(parseDuration(input)).toBe(want)
  })

  test.for([
    { name: 'empty input', input: '', error: EmptyInputError },
    { name: 'unknown suffix', input: '5x', error: UnknownUnitError },
  ])('rejects $name', ({ input, error }) => {
    expect(() => parseDuration(input)).toThrow(error)
  })
})
```

- **`test.for` vs `test.each`.**
  - `test.for` passes the row unspread as the first argument and the test context as the second. Prefer it in new code, since it works with `test.concurrent` and `test.extend` fixtures.
  - `test.each` spreads array rows into separate arguments.
- **Row names.** Use object rows with a `name` field and title the test `'$name'`, so the failure output names the behavior. `%s` and `%j` placeholders fit array rows.
- **Repeating a whole suite.** `describe.each` runs the same suite per backend or tenant on every supported version; `describe.for` exists only from Vitest 3.
- **Several fields of one result.** Check them with `expect.soft(...)` so every mismatch gets reported, or compare the whole object with `toEqual` / `toMatchObject` to get a diff.
- **When to split.** Split rows that need different `vi.mock` setups. A module mock applies to the whole file, not to a single row.

## Slice tests

```ts
import { beforeAll, afterAll, describe, test, expect } from 'vitest'
import { PostgreSqlContainer, type StartedPostgreSqlContainer } from '@testcontainers/postgresql'
import { buildApp } from '../src/app'          // same composition function production uses

// Optional: setup can fail part-way, and teardown must still release whatever did start.
let db: StartedPostgreSqlContainer | undefined
let app: Awaited<ReturnType<typeof buildApp>> | undefined
// The app is booted once for speed, so this spy is shared; tests never read it wholesale,
// only filtered by their own customer id (per-test data isolation), and it is never reset mid-run.
const emails = new RecordingEmailSender()
const clock = new FixedClock(new Date('2026-03-01T10:00:00Z'))

beforeAll(async () => {
  db = await new PostgreSqlContainer('postgres:16.4-alpine').start()
  app = await buildApp({ databaseUrl: db.getConnectionUri(), emailSender: emails, clock })
  await app.migrate()
}, 60_000)

afterAll(async () => {
  try {
    await app?.close()
  } finally {
    await db?.stop()
  }
})

// Narrows the optional app for test bodies (fail-fast guard, not scenario logic).
function started() {
  if (!app) throw new Error('app did not start')
  return app
}

describe('POST /orders', () => {
  test('valid order is stored and confirmed', async () => {
    const customerId = `c-${crypto.randomUUID()}`      // isolation key only: never asserted, so randomness is harmless

    const res = await started().inject({ method: 'POST', url: `/customers/${customerId}/orders`, payload: { sku: 'A1', qty: 2 } })

    expect(res.statusCode, res.body).toBe(201)
    const stored = await started().inject({ method: 'GET', url: `/customers/${customerId}/orders` })
    expect(stored.json()).toMatchObject([{ sku: 'A1', qty: 2, createdAt: '2026-03-01T10:00:00.000Z' }])
    expect(emails.subjectsTo(customerId)).toEqual(['Order confirmation'])
  })

  test.for([
    { name: 'zero quantity', body: { sku: 'A1', qty: 0 } },
    { name: 'negative quantity', body: { sku: 'A1', qty: -1 } },
    { name: 'missing sku', body: { qty: 1 } },
  ])('rejects $name with 422, stores nothing, sends nothing', async ({ body }) => {
    const customerId = `c-${crypto.randomUUID()}`

    const res = await started().inject({ method: 'POST', url: `/customers/${customerId}/orders`, payload: body })

    expect(res.statusCode, res.body).toBe(422)
    const stored = await started().inject({ method: 'GET', url: `/customers/${customerId}/orders` })
    expect(stored.json()).toEqual([])
    expect(emails.subjectsTo(customerId)).toEqual([])
  })
})
```

**Calling the app**

- Drive it through its real entry point: Fastify `app.inject`, `supertest(app)` for Express, or `fetch` against a listening server on port 0.
- Read state back through the API rather than by importing repositories. If the entry point exposes no reader, read through the real store's public methods (the same instance the app uses, or a fresh one on the same DB).
- When the app is cheap to build in-process (e.g. SQLite `:memory:`), build a fresh app, store, and spies per test instead of sharing them.

**Unmanaged HTTP dependencies**

- Pass fakes in through the composition function, as above.
- Alternatively, intercept at the network layer with MSW (`setupServer` from `msw/node`). `onUnhandledRequest: 'error'` only makes the unmatched request throw; if application code catches that error (e.g. a best-effort email call), the test still passes. Record unmatched requests and assert none in teardown. This harness shares one server, handler list and `unhandled` array per file, so use it only where tests in that file run sequentially (no `test.concurrent` / `describe.concurrent`); for concurrent tests, inject per-test fakes through the composition function instead:

```ts
const unhandled: string[] = []
const server = setupServer(...handlers)
beforeAll(() => server.listen({
  onUnhandledRequest(request, print) { unhandled.push(`${request.method} ${request.url}`); print.error() },
}))
afterEach(() => { server.resetHandlers(); expect(unhandled.splice(0)).toEqual([]) })
afterAll(() => server.close())
```

**Database containers**

- `beforeAll` runs once per test file (suite), not per worker, so a container started there is started again for every file. To share one, start it once for the whole run in `globalSetup` and pass the connection string through `provide`/`inject`.
- Isolate data per test with unique IDs or per-test schemas. Vitest runs files in parallel, so shared rows leak between files.

## Fakes and spies over `vi.mock`

- Pass dependencies explicitly as parameters or constructor arguments. Implement fakes as small classes that satisfy the port type.
- Avoid `vi.mock('./repository')` and other mocks of your own modules. They couple the test to the file layout and hide real bugs.
- If a third-party SDK is imported directly with no seam, introduce a thin adapter (the last type you own) and fake that, as SKILL.md requires. Only when production code must stay unchanged, `vi.mock` the SDK module as a declared exception and report it as a gap to fix.
- `vi.mock` is hoisted above imports, so any variables its factory uses must come from `vi.hoisted(() => ({ ... }))`.
- Use `vi.fn()` / `vi.spyOn` only on unmanaged edges. Create `vi.fn()` doubles fresh in each test; that works on every Vitest version. Add `afterEach(() => vi.restoreAllMocks())` to undo `vi.spyOn`. On Vitest 4+ it restores only `vi.spyOn` spies and leaves `vi.fn()` state alone; on Vitest 2/3 it also clears `vi.fn()` call history and resets their implementations.
- Never assert `toHaveBeenCalled` on a stub that only feeds data in.

```ts
class RecordingEmailSender implements EmailSender {
  readonly sent: Email[] = []
  async send(email: Email) { this.sent.push(email) }
  subjectsTo(customerId: string) { return this.sent.filter(e => e.customerId === customerId).map(e => e.subject) }
}
```

## Time

- Inject a `Clock` (`{ now(): Date }`) into the app. Domain functions take `now: Date` as a parameter.
- For timer-driven code (debounce, retry backoff), use fake timers:
  - Call `vi.useFakeTimers()` in `beforeEach` and `vi.useRealTimers()` in `afterEach`.
  - Advance time with `await vi.advanceTimersByTimeAsync(ms)`.
  - `vi.setSystemTime(date)` pins `Date.now()`.
  - Put timing values in the table rows and timer setup in hooks.
- To wait for async effects, use `await vi.waitFor(() => expect(...).toBe(...), { timeout: 2000 })`, never `setTimeout` sleeps.

## Naming and assertions

- Nest `describe` blocks by subject or context. Test titles state behavior: `'rejects an expired token'`.
- Use `toEqual` / `toStrictEqual` for structures so failures show a diff.
- Add a custom message as the second argument to `expect(value, message)`. Passing the response body there makes failed slice tests easy to diagnose.

## Pitfalls

- A module-level `let` fixture mutated by tests is shared state. Build fresh values per test with builders.
- Snapshot tests of whole responses are change detectors. Assert the fields that matter.
- `test.concurrent` with shared app state needs data isolation per row. Use `test.concurrent.for(...)`, and use the test context's `expect` for snapshots and `expect.assertions(n)`/`expect.hasAssertions()`, which the global `expect` cannot attribute to the right concurrent test.
- Unawaited promises in tests pass silently. Always `await`, and use `expect.assertions(n)` only when a callback-style assertion might never run.
- Vitest strips types without checking them, so a test that reads `r.order` without narrowing a discriminated union runs green yet does not compile. Narrow with a guard that fails the test (`if (!r.ok) throw new Error(...)`, or `expect(r.ok).toBe(true)` followed by the guard), not an `as` cast. Run `tsc --noEmit` (the project's `typecheck` script) over the test files as well as `vitest run`.
