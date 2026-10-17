# Go (stdlib `testing`)

This guide targets modules whose `go.mod` `go` directive is 1.22 or later, where each loop iteration gets its own variable, so the `tc := tc` copy is unnecessary. The semantics follow the module's (or a file's `//go:build go1.N` constraint's) language version, not the toolchain: check the `go` directive before removing captures, and keep `tc := tc` in parallel table subtests when it is below 1.22 ([loopvar](https://go.dev/blog/loopvar-preview)). For structural comparison it uses `github.com/google/go-cmp/cmp` only if the module already requires it. Do not add go-cmp (or any assertion library) to a module that does not already require it; use the stdlib forms under **Stdlib comparison** below.

## Tables

```go
func TestParseDuration(t *testing.T) {
	t.Parallel()
	tests := map[string]struct {
		in   string
		want time.Duration
	}{
		"minutes":     {in: "5m", want: 5 * time.Minute},
		"mixed units": {in: "1h30m", want: 90 * time.Minute},
	}
	for name, tc := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()
			got, err := ParseDuration(tc.in)
			if err != nil {
				t.Fatalf("ParseDuration(%q) error = %v, want nil", tc.in, err)
			}
			if got != tc.want {
				t.Errorf("ParseDuration(%q) = %v, want %v", tc.in, got, tc.want)
			}
		})
	}
}

func TestParseDuration_Errors(t *testing.T) {
	t.Parallel()
	tests := map[string]struct {
		in      string
		wantErr error
	}{
		"empty input":    {in: "", wantErr: ErrEmpty},
		"unknown suffix": {in: "5x", wantErr: ErrUnit},
	}
	for name, tc := range tests {
		t.Run(name, func(t *testing.T) {
			t.Parallel()
			_, err := ParseDuration(tc.in)
			if !errors.Is(err, tc.wantErr) {
				t.Errorf("ParseDuration(%q) error = %v, want %v", tc.in, err, tc.wantErr)
			}
		})
	}
}
```

- **One subtest per row.** Wrap each row in `t.Run(name, ...)`. The name shows up in the failure output, and you can run a single row with `go test -run 'TestParseDuration/empty_input'`.
- **Map or slice.** A map gives randomized iteration order, which flushes out tests that depend on order. Use a slice when output order matters.
- **Parallel subtests.** Call `t.Parallel()` in both the parent and each subtest, but only once the rows share no mutable state.
- **Failure messages.** Use the form `Func(input) = got, want want`. Call `t.Fatalf` only when the checks after it would be meaningless. Otherwise call `t.Errorf` so every mismatch gets reported.
- **Errors.** Match expected errors with `errors.Is` against sentinel errors, or with `errors.As` for typed errors. Don't compare error strings.
- **Structs.** With go-cmp already in go.mod, compare with `cmp.Diff(want, got)` and print `mismatch (-want +got):\n%s`. Assert IDs and timestamps exactly when they come from an injected ID source or clock; a zero or offset `CreatedAt` is a real bug. Leave a field out (`cmpopts.IgnoreFields(Order{}, "ID")`) only when it is uncontrolled and irrelevant to the behavior under test.
- **Stdlib comparison** (no go-cmp): `got != want` for comparable structs; `slices.Equal(got, want)` / `maps.Equal` for slices and maps of comparable values; `reflect.DeepEqual(got, want)` otherwise. Always print both sides: `t.Errorf("Checkout(...) =\n%+v\nwant\n%+v", got, want)`. Put injected-clock timestamps and controlled IDs in `want`. `!=` and `reflect.DeepEqual` compare `time.Time` by location and monotonic reading, so a timestamp read back from storage can differ from an equal instant: assert it with `got.CreatedAt.Equal(want.CreatedAt)` against the exact expected instant (or normalize copies with `.UTC().Round(0)` before the struct comparison; with go-cmp, `cmp.Diff` already uses `Time.Equal`). Zero a field on a copy of `got` only when it is uncontrolled and irrelevant to that test.
- **Helpers.** Any helper that asserts or builds values starts with `t.Helper()`, so failures point at the caller's line.
- **Split signals** (also why the example above keeps error rows in their own table).
  - Struct fields such as `setup func(...)`, `mockX`, or `expectEmail bool`.
  - A `switch` inside the runner.
  - Error rows that need assertions different from the success rows. Give these a separate `TestXxx_Errors` table.

## Slice tests

```go
func TestPlaceOrder(t *testing.T) {
	app := newTestApp(t) // real router + real DB (container or template clone) + spies; cleanup via t.Cleanup

	tests := []struct {
		name       string
		body       string
		wantStatus int
		wantOrders []OrderView
		wantEmails []string
	}{
		{
			name:       "valid order is stored and confirmed",
			body:       `{"sku":"A1","qty":2}`,
			wantStatus: http.StatusCreated,
			wantOrders: []OrderView{{SKU: "A1", Qty: 2, Status: "pending"}},
			wantEmails: []string{"Order confirmation"},
		},
		{name: "zero quantity is rejected, nothing stored or sent", body: `{"sku":"A1","qty":0}`, wantStatus: http.StatusUnprocessableEntity},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			customer := app.newCustomer(t) // unique per row: data isolation

			resp := app.post(t, "/customers/"+customer+"/orders", tc.body) // returns {StatusCode, Body string}

			if resp.StatusCode != tc.wantStatus {
				t.Fatalf("POST orders %s: status = %d, want %d; body: %s", tc.body, resp.StatusCode, tc.wantStatus, resp.Body)
			}
			if diff := cmp.Diff(tc.wantEmails, app.emails.SubjectsTo(customer), cmpopts.EquateEmpty()); diff != "" {
				t.Errorf("emails mismatch (-want +got):\n%s", diff)
			}
			got := app.listOrders(t, customer) // GET /customers/{id}/orders; empty rows assert nothing was stored
			if diff := cmp.Diff(tc.wantOrders, got, cmpopts.IgnoreFields(OrderView{}, "ID"), cmpopts.EquateEmpty()); diff != "" {
				t.Errorf("stored orders mismatch (-want +got):\n%s", diff)
			}
		})
	}
}
```

**Building the harness (`newTestApp`)**

- Construct the real `http.Handler` through the same composition function that `main` uses. Pass in the test DB, spies for unmanaged adapters, and a controllable clock.
- Call the handler through `httptest.NewServer(handler)`. For pure handler checks, use `httptest.NewRecorder()` instead.

**Database**

- The simplest option is `testcontainers-go` with the production image, started once in `TestMain`.
- For isolation that is safe under parallel tests, use a template-cloned database per test (for example `pgtestdb`).
- SQLite belongs in these tests only when production also runs SQLite.

**Cleanup and diagnostics**

- Register teardown with `t.Cleanup`. Inside it, check `t.Failed()` to dump rows and captured messages when the test failed.

**Scope**

- Use build tags or `testing.Short()` to split the slow lane only when the suite genuinely needs it. The slice tests are the main suite, not an optional extra.

## Fakes and spies

```go
type recordingMailer struct {
	mu   sync.Mutex
	sent []Email
}

func (m *recordingMailer) Send(_ context.Context, e Email) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.sent = append(m.sent, e)
	return nil
}
```

- Keep interfaces small and define them on the consumer side, as ports. Hand-written fakes and spies are idiomatic Go, so don't reach for mock generators for your own components.
- Run the same contract test against both the fake and the real adapter. A convenient shape is `func testStore(t *testing.T, newStore func(t *testing.T) Store)`, called once per implementation.
- For outgoing HTTP to a third party, use `httptest.NewServer` as a local fake of that API. Point the adapter's base URL at it.

## Time

- Inject the clock with a `now func() time.Time` field or a small `Clock` interface. Domain functions take `now time.Time` as a parameter.
- For timeouts, tickers, and retry backoff, use `testing/synctest` (stable in Go 1.25). Inside `synctest.Test(t, func(t *testing.T) { ... })`, the fake clock advances instantly only when every goroutine in the bubble is *durably* blocked (channel ops on bubble channels, `time.Sleep`, `select`, `sync.WaitGroup`/`sync.Cond` waits), and `synctest.Wait()` waits for that state. Socket or file I/O, syscalls, and `sync.Mutex` acquisition are not durable blocks, so the clock never advances past them.
  - Use it only for self-contained bubbles: in-process code plus in-memory fakes, `net.Pipe`, or bubble-created channels. Keep slice tests that talk to a real listener, `httptest.NewServer`, or a real database outside `synctest`; wrapped, they can hang instead of timing out. Control time there with the injected clock.
- Never call `time.Sleep` to wait for async work. Poll with a deadline, or wait on a channel.

## Naming

- Name test functions `TestSubject` or `TestSubject_Behavior`. Subtest names describe the behavior, for example `"expired token is rejected"`; spaces become underscores in `-run` patterns.

## Pitfalls

- Using `reflect.DeepEqual` without printing both values. Print got and want with `%+v`, or use `cmp.Diff` if the module already requires go-cmp.
- Global state in package-level variables (clocks, registries). It breaks `t.Parallel()`, so inject it instead.
- Calling `t.Fatal` from a goroutine the test started. It must be called from the test goroutine; report errors back through a channel instead.
- Skipping `-race`. Run slice tests with `go test -race ./...`.
