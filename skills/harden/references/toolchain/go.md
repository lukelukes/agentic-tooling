# Go (toolchain 1.26, Sept 2026)

Concrete tooling per layer. Read only the entries for the layer you are actually
proposing. Verified against documentation in September 2026; check versions before
quoting a flag as current.

## What is unusual here

Unusually easy in Go, because it is first-party and needs no config: (1) coverage-guided fuzzing with an automatic crash-to-seed corpus — `go test -fuzz` writes the minimized failing input into `testdata/fuzz/` and it becomes a permanent regression test that runs on every subsequent plain `go test`; no other mainstream ecosystem ships this in the default test runner. (2) The race detector, one flag. (3) `testing/synctest` (GA in Go 1.25) — a per-test virtual clock where time only advances when every goroutine in the bubble is durably blocked, so timeout and retry logic tests run instantly and deterministically; this is genuinely ahead of most ecosystems. (4) "Same code, two configurations" is a one-flag operation because build tags are first-class — the stdlib crypto packages mandate that the generic implementation build on every target precisely so it can be diffed against assembly under `-tags purego`. (5) Test binaries are self-contained static executables, so re-exec-and-SIGKILL crash tests are trivial. (6) Since Go 1.24, `go get -tool` / `go tool <name>` pins third-party test tools in go.mod, which fixes the old reproducibility mess.

Unusually hard or simply absent: (1) Branch coverage does not exist, and Go does not even have line coverage — `go test -cover` is statement coverage, so `if a && b` is a single counter. Proposal #70306 has sat open since Nov 2024. This is the single biggest gap; flag it whenever someone quotes a Go coverage percentage. (2) Assertions: no stdlib `assert`, no NDEBUG, so you hand-roll a `const` + build-tag pair and rely on unspecified (but reliable) dead-code elimination. (3) Property-based testing: `testing/quick` is explicitly frozen and has no shrinking, so you must leave the stdlib for pgregory.net/rapid. (4) Mutation testing: every option is a 0.x third-party tool, the most-cited one (zimmski/go-mutesting) is abandoned, and the maintained ones warn about multi-hour runs. (5) Full deterministic simulation: synctest covers time and goroutine blocking but not I/O and does not seed the scheduler; the one DST library (gosim) is dormant since Dec 2024, so serious users go commercial (Antithesis, as etcd did). (6) Power-loss and ENOSPC/OOM injection have no Go-level hook — you must go outside the language (LazyFS, dm-log-writes, size-capped tmpfs, cgroup limits). Note specifically that SIGKILL is not power loss: unfsynced writes survive in the page cache, so process-kill tests pass on code with a broken fsync discipline.

---

## Assertions / invariant checks compiled out of production builds

**Reach for** — No stdlib `assert`. The stdlib's own idiom: an untyped `const` guard selected by build tag, relying on SSA dead-code elimination (see $GOROOT/src/runtime/debuglog_on.go / debuglog_off.go, net/http/server.go `const debugServerConnections = false`).

```
// assert_on.go   //go:build assert
package p; const assertOn = true
// assert_off.go  //go:build !assert
package p; const assertOn = false
func assert(ok bool, m string) { if assertOn && !ok { panic(m) } }
// go test -tags assert ./...   |   go build ./...  (stripped)
```

**Caveat** — Must be `const`, not `var` — only constants get folded. Elimination is a compiler implementation detail, not a spec guarantee; confirm with `go build -gcflags=-m -tags assert`. Go has no NDEBUG equivalent, so CI must explicitly run both `-tags assert` and untagged builds or the assert path rots.

## Regression test per fixed bug + auditing git history for untested fixes

**Reach for** — No Go-specific tool exists. Two mechanisms: (a) native fuzzing does this automatically — a crash is written into `testdata/fuzz/FuzzX/<hash>` and thereafter runs on plain `go test`; (b) for hand-fixed bugs, git plumbing. Convention: name the test `TestIssue1234_ShortDesc`.

```
git log --no-merges -i --grep='fix\|bug' --format='%H%x09%s' |
while IFS=$'\t' read -r h s; do f=$(git show --name-only --format= "$h");
  echo "$f" | grep -q '\.go$' || continue
  echo "$f" | grep -qE '(_test\.go|^testdata/)' || echo "NO-TEST $h $s"; done
```

**Caveat** — Verified working on a real Go repo. Noisy: doc typos and pure refactors match `-i --grep=fix`; tighten to `--grep='^fix(\(|:)'` if you use Conventional Commits. Squash-merge repos collapse the fix+test into one commit (good); merge-commit repos need `--first-parent`. Cannot detect a fix whose test is a new case added to an existing table-driven test's `testdata/` — that still shows as touched, which is the desired signal.

## Property-based testing

**Reach for** — pgregory.net/rapid v1.3.0 (883 stars, released Apr 2026, actively maintained). Stdlib `testing/quick` exists but its own doc says "The testing/quick package is frozen and is not accepting new features" — it has no shrinking. leanovate/gopter's last release was 2020.

```
func TestRoundTrip(t *testing.T) {
  rapid.Check(t, func(t *rapid.T) {
    b := rapid.SliceOf(rapid.Byte()).Draw(t, "b")
    if got := Decode(Encode(b)); !bytes.Equal(got, b) { t.Fatal(got) }
  })
}
// go test -rapid.checks=100000 -rapid.seed=42 -rapid.shrinktime=30s ./...
```

**Caveat** — Needs Go 1.23+. Failures are persisted to `testdata/rapid/<TestName>/<TestName>-<ts>-<pid>.fail` and auto-replayed on the next run — commit these. A fail file is silently ignored if the rapid version changed (logs "[rapid] ignoring fail file"). Stateful testing is `t.Repeat(map[string]func(*rapid.T){...})` / `rapid.StateMachineActions`; `-rapid.steps` controls sequence length. Default is only 100 checks — raise it in CI.

## Differential / oracle testing (same code, two configs)

**Reach for** — No framework needed; this is a build-flag exercise plus google/go-cmp for the comparison. Go-specific config axes: the `purego` build tag (stdlib crypto policy — generic Go must build everywhere so it can be diffed against assembly), `-gcflags=all='-N -l'` (optimizer off vs on), `-tags`, `GOARCH`, and `-race` (changes covermode + scheduling).

```
go test ./... && go test -tags purego ./...        # asm vs generic
go test -gcflags=all='-N -l' ./...                  # opt off vs on
GOARCH=386 go test -c ./...                         # cross-arch build check
// in-test oracle:
if d := cmp.Diff(slowRef(x), fastImpl(x)); d != "" { t.Fatalf("%v: %s", x, d) }
// wrap in f.Fuzz(...) or rapid.Check to generate x
```

**Caveat** — go-cmp panics on unexported fields unless given `cmp.AllowUnexported`/`cmpopts.IgnoreUnexported`, and its doc states it is intended for tests only — do not import it in production code. `GOARCH=386 go test` only *runs* if the host can execute that binary; otherwise use `go test -c` for a compile check or qemu-user. `-gcflags=all=` recompiles the stdlib, so the first run is slow and it busts the build cache.

## Fault injection: I/O errors, OOM, ENOSPC, timeouts, partial writes, network faults

**Reach for** — Stdlib covers reader/writer faults: `testing/iotest` (ErrReader, TimeoutReader, HalfReader, OneByteReader, TruncateWriter for partial writes), `testing/fstest.MapFS`, `net.Pipe`, `net/http/httptest`, `golang.org/x/net/nettest`. For faults deep inside unexported code: `go.etcd.io/gofail` (etcd, 426 stars, active). Network chaos: Shopify/toxiproxy (12.3k stars, active). No Go-level hook for OOM or ENOSPC.

```
# stdlib partial-write / read-error injection
r := iotest.TimeoutReader(iotest.HalfReader(src)); w := iotest.TruncateWriter(dst, 10)
# gofail: add `// gofail: var BeforeCommit struct{}` in source, then
gofail enable ./... && go get go.etcd.io/gofail/runtime && go build ./...
GOFAIL_FAILPOINTS='BeforeCommit=return(1);slowDisk=sleep(500)' go test ./...
# or in-test: gofail.Enable("BeforeCommit", `return(1)`); defer gofail.Disable(...)
```

**Caveat** — gofail rewrites your source in place (`gofail enable` / `gofail disable`) and generates `*.fail.go` files — wire it into a Makefile target, never commit half-enabled trees. Disabled failpoints compile to a no-op and inline away, so there is no production cost. ENOSPC has no Go API: use a size-capped tmpfs (`mount -t tmpfs -o size=1M`), a wrapping `io.Writer` that returns `syscall.ENOSPC`, or a FUSE FS via hanwen/go-fuse. OOM likewise: `debug.SetMemoryLimit`/`GOMEMLIMIT` is a *soft* limit that makes the GC thrash, it does not produce an allocation failure or an OOM kill — use a cgroup memory limit for the real thing.

## Crash / kill / restart / recovery testing (incl. power-loss of a file write)

**Reach for** — Stdlib idiom: re-exec the test binary as a subprocess (`os.Args[0]` + `-test.run=^TestHelper$` + env guard), the pattern used throughout $GOROOT/src/os/exec/exec_test.go. Verify recovery with anishathalye/porcupine (linearizability checker, 1.2k stars, active). True power-loss needs out-of-process help: LazyFS (FUSE, C++) drops unfsynced pages on simulated crash — this is what etcd's `tests/robustness` suite uses alongside gofail; dm-log-writes/dm-flakey are the kernel-level alternative.

```
func TestCrashRecover(t *testing.T) {
  if os.Getenv("CRASH_CHILD") == "1" { writeUntilKilled(t); return }
  cmd := exec.Command(os.Args[0], "-test.run=^TestCrashRecover$")
  cmd.Env = append(os.Environ(), "CRASH_CHILD=1", "GOCOVERDIR="+t.TempDir())
  cmd.Start(); time.Sleep(50*time.Millisecond); cmd.Process.Signal(syscall.SIGKILL)
  cmd.Wait(); assertRecovers(t, dir) // reopen and check invariants
}
```

**Caveat** — SIGKILL is NOT power loss: unfsynced writes survive in the page cache, so a process-kill test will pass on code that would lose data on real power loss. You need LazyFS or dm-log-writes to actually test the fsync discipline. Build the child with `go build -cover` and set `GOCOVERDIR` or you lose coverage on every killed subprocess. `defer` does not run on SIGKILL or `os.Exit`, so cleanup must be in the parent (`t.TempDir()` handles this). Porcupine can blow up combinatorially on long histories — keep operation counts small.

## Deterministic seeded simulation (clock, scheduler, randomness, I/O)

**Reach for** — Stdlib covers time and goroutine blocking but NOT I/O or a seeded scheduler: `testing/synctest` (GA in Go 1.25) gives each bubble a virtual clock starting at 2000-01-01 UTC that advances only when every goroutine is durably blocked. Randomness: `math/rand/v2` with an explicit `rand.NewPCG(s1,s2)`, `GODEBUG=randautoseed=0` for the v1 global, and `testing/cryptotest.SetGlobalRandom(t, seed)` (NEW in Go 1.26) for crypto/rand. Whole-run-is-a-function-of-seed is not achievable with stdlib alone.

```
synctest.Test(t, func(t *testing.T) {
  r := rand.New(rand.NewPCG(seed, seed))  // math/rand/v2
  go worker(r)
  time.Sleep(time.Hour)   // virtual: returns instantly
  synctest.Wait()         // all other bubble goroutines durably blocked
})
// Go 1.26: testing/cryptotest.SetGlobalRandom(t, seed) for crypto/rand
```

**Caveat** — synctest does NOT virtualize I/O or seed the scheduler: `sync.Mutex.Lock` and real network I/O are explicitly *not* durable blocking, and a bubble that touches the network will hang or fail. The Go 1.24 `GOEXPERIMENT=synctest` API (different shape) was removed in Go 1.26. `synctest.Sleep` only lands in Go 1.27. `cryptotest.SetGlobalRandom` is process-global so it forbids `t.Parallel()`. The only full-DST library, jellevandenhooff/gosim (`go run github.com/jellevandenhooff/gosim/cmd/gosim test -seeds=1-100`), has 81 stars and no commits since Dec 2024 and calls itself experimental — treat as dormant. Antithesis (commercial, used by etcd) is the production answer if you need real seeded whole-system determinism.

## Branch (not line) coverage measurement

**Reach for** — Go does not have branch coverage, and does not have line coverage either — `go test -cover` measures STATEMENT coverage (`-covermode=set|count|atomic`). Proposal golang/go#70306 ("cmd/cover: support branch coverage") has been open since Nov 2024 with no decision; the older #28888 likewise. Closest third-party: rillig/gobco (condition coverage, 86 stars, last push May 2026).

```
go test -covermode=count -coverprofile=c.out ./... && go tool cover -html=c.out
# integration/binary coverage (Go 1.20+):
go build -cover -o app ./cmd/app
GOCOVERDIR=/tmp/cov ./app ... && go tool covdata percent -i=/tmp/cov
# condition coverage:
go install github.com/rillig/gobco@latest && gobco ./...
```

**Caveat** — Say this plainly to users: a 100% Go coverage number says nothing about branch coverage, because `if a && b { x() }` is one statement. `-covermode=count` on a one-line `if` still reports a single counter. gobco's README states it does not detect entirely unused functions and "doesn't cover `select` statements", so it is a supplement to `go test -cover`, not a replacement. `go build -cover` + `go tool covdata` is the only officially blessed way to get coverage out of a real binary run.

## Mutation testing

**Reach for** — No official tool; all options are 0.x third-party. go-gremlins/gremlins is the most-used maintained one (420 stars, v0.6.0 Dec 2025, pushed Jun 2026). The widely-cited zimmski/go-mutesting (673 stars) is effectively ABANDONED — last release v1.2 in 2021, last push Jul 2024. Live forks: avito-tech/go-mutesting v2.3.1 (Dec 2025) and jonbaldie/go-mutesting/v2 (very active, but only 5 stars — unproven). gtramontina/ooze (288 stars) is also alive.

```
go install github.com/go-gremlins/gremlins/cmd/gremlins@latest
gremlins unleash ./...            # flags verified from cmd/unleash.go:
#  -d dry-run  -t tags  -D <ref> diff-only  -o out.json  -i integration  -S statuses
# alternative fork with MSI gates:
go install github.com/jonbaldie/go-mutesting/v2/cmd/go-mutesting@latest
go-mutesting --coverage --min-msi 70 --git-diff-lines --git-diff-base master ./...
```

**Caveat** — gremlins is pre-1.0 and its README warns "configuration flags and/or configuration files can change among minor releases" and that it "doesn't work very well on very big Go modules, mainly because a run can take hours". Always run `-D <base-ref>` (diff mode) in CI, never the whole module. gremlins has no MSI quality-gate/baseline file; the jonbaldie fork does but is barely adopted. Nothing mutates Go assembly — Filippo Valsorda prototyped `cmd/asm` mutation (`-mut`/`-mutlist` asmflags, Jul 2025) but it is unreleased. Pin the tool with Go 1.24+ `go get -tool` so CI is reproducible.

## Fuzzing with a persistent corpus + crash-to-seed regression discipline

**Reach for** — Stdlib, since Go 1.18. `go test -fuzz` with coverage-guided libFuzzer-style mutation. The crash-to-seed loop is built in and requires zero configuration. dvyukov/go-fuzz predates this and is in maintenance (last push Sep 2024) — do not use it for new work. google/gofuzz is ARCHIVED (Nov 2022); its successor is sigs.k8s.io/randfill. For struct-shaped inputs use github.com/AdaLogics/go-fuzz-headers.

```
func FuzzParse(f *testing.F) {
  f.Add([]byte("{}"))                       // seed; testdata/fuzz/FuzzParse/* also loaded
  f.Fuzz(func(t *testing.T, b []byte) { _, _ = Parse(b) })
}
go test -fuzz=FuzzParse -fuzztime=10m -parallel=8 ./pkg
# on failure Go writes testdata/fuzz/FuzzParse/<hash> — git add it.
# it then runs on every plain `go test`, forever. That is the discipline.
```

**Caveat** — Generated corpus lives in `$GOCACHE/fuzz` and is NOT shared across machines or CI runs — you must upload/restore it yourself (or use OSS-Fuzz / ClusterFuzzLite) or every CI job restarts from the seed corpus. Fuzz args are limited to 14 types (string, []byte, the int/uint family, float32/64, bool) — no structs, no slices of structs. Coverage instrumentation only works on amd64 and arm64. There is a hard 1s-per-input timeout. `-fuzz` must match exactly one fuzz target in exactly one package in the main module. `-count` does not apply to `-fuzz`.

## Sanitizers and undefined/unspecified behaviour detection

**Reach for** — `-race` (ThreadSanitizer) is the one that matters and is first-party. Also `-asan`, `-msan` (cgo/C side, need clang or gcc), `GOEXPERIMENT=cgocheck2` (slow, complete cgo pointer checking), `-gcflags=all=-d=checkptr=2` (unsafe.Pointer validity; auto-on under -race/-msan), `GODEBUG=checkfinalizers=1` (Go 1.25+, finalizer/cleanup misuse), and `go vet` which `go test` runs automatically (unsafeptr, copylocks, loopclosure, testinggoroutine, waitgroup, ...).

```
GORACE='halt_on_error=1 history_size=7' go test -race -count=5 -shuffle=on ./...
CC=clang go test -asan ./...     # leak-detects at exit by default since Go 1.25
CC=clang go test -msan ./...
GOEXPERIMENT=cgocheck2 go test ./...
GODEBUG=checkfinalizers=1 go test ./...
```

**Caveat** — The race detector only reports races that actually execute — it is a dynamic tool, so you must pair it with `-count=N`, `-shuffle=on` and varied `-cpu=1,2,4` to shake schedules loose. Costs ~2-20x CPU and 5-10x memory. linux/riscv64 support only landed in Go 1.26. `-asan`/`-msan` instrument the C side of cgo, not pure Go — they are near-useless for a cgo-free module. Since Go 1.25 `-asan` leak-detects at exit by default; silence with `ASAN_OPTIONS=detect_leaks=0`. Go has very little true UB, and the unspecified behaviours (map iteration order, `select` case choice, `sort.Slice` instability, goroutine interleaving) are already randomized by the runtime, so there is nothing extra to turn on — that randomization is the detector.

## Golden/snapshot testing + a corpus of malformed inputs

**Reach for** — No stdlib golden helper. De-facto standard is a hand-rolled `-update` flag plus google/go-cmp (4.7k stars) for the diff — this is what cmd/go and most of the stdlib do. Libraries: gotest.tools/v3/golden (`-update`, active), hexops/autogold (`-update`, inline snapshots, 294 stars). bradleyjkemp/cupaloy is stale (last push May 2023). For CLI / multi-file fixtures: github.com/rogpeppe/go-internal/testscript + txtar (991 stars, v1.15.0 May 2026), the exact machinery cmd/go tests itself with.

```
var update = flag.Bool("update", false, "rewrite golden files")
got := render(in); gp := filepath.Join("testdata", t.Name()+".golden")
if *update { os.WriteFile(gp, got, 0o644); return }
want, _ := os.ReadFile(gp)
if d := cmp.Diff(string(want), string(got)); d != "" { t.Fatal(d) }
// go test ./... -update    |  testscript: testscript.Params{Dir:"testdata", UpdateScripts:true}
```

**Caveat** — Reuse `testdata/fuzz/FuzzX/` as the malformed-input corpus — the fuzzer already populates it and `go test` already replays it, so you get one corpus instead of two. Golden files containing timestamps, map iteration order, pointer addresses or `%v` of structs are the single biggest source of Go test flakes — normalize before writing. `cmp.Diff` panics on unexported fields without `cmpopts.IgnoreUnexported`/`cmp.AllowUnexported`, and go-cmp documents itself as test-only. `-update` must be a non-default flag and CI must never set it; a blanket `-update` silently blesses regressions.

## Flake elimination / enforcing run-to-run determinism

**Reach for** — Mostly first-party flags: `-shuffle=on` (Go 1.17+, prints the seed), `-count=N`, `-race`, `-cpu=1,2,4`, `-timeout`, `-failfast`. Plus `testing/synctest` (Go 1.25) which eliminates the biggest single flake source — real sleeps and wall-clock timeouts. go.uber.org/goleak (5.3k stars, pushed Sep 2026) for leaked goroutines. gotestsum (2.7k stars) `--rerun-fails` to *identify* flakes. Determinism knobs: `GODEBUG=randautoseed=0`, `t.TempDir()`, `t.Setenv`, `t.Chdir` (Go 1.24+).

```
go test -race -shuffle=on -count=10 -cpu=1,4 -timeout=10m ./...
// package-wide leak check:
func TestMain(m *testing.M) { goleak.VerifyTestMain(m) }
// flake hunt in CI:
gotestsum --rerun-fails=2 --rerun-fails-max-failures=10 --packages=./... --junitfile=r.xml
```

**Caveat** — `-shuffle` only randomizes top-level test/benchmark order *within one binary* — it does not shuffle subtests or package order, so ordering bugs across packages stay hidden. `-count=N` disables the test result cache (that is the point, but it makes CI slow). `goleak.VerifyNone(t)` is documented as incompatible with `t.Parallel()` — use `VerifyTestMain` or `IgnoreCurrent()`. `t.Setenv` panics in a parallel test by design. Since Go 1.25 `testing.AllocsPerRun` panics if parallel tests are running, which catches a whole class of flaky benchmarks. Treat `--rerun-fails` as a detector, not a remedy — using it to make CI green is how flakes become permanent.

---

## Sources

- https://go.dev/doc/go1.26
- https://go.dev/doc/go1.25
- https://pkg.go.dev/testing/synctest
- https://pkg.go.dev/testing/cryptotest#SetGlobalRandom
- https://go.dev/doc/security/fuzz/
- https://go.dev/doc/build-cover
- https://github.com/golang/go/issues/70306
- https://github.com/golang/go/issues/28888
- https://pkg.go.dev/testing/quick
- https://pkg.go.dev/testing/iotest
- https://pkg.go.dev/pgregory.net/rapid
- https://github.com/flyingmutant/rapid/blob/master/persist.go
- https://github.com/go-gremlins/gremlins
- https://github.com/go-gremlins/gremlins/blob/main/cmd/unleash.go
- https://github.com/jonbaldie/go-mutesting
- https://github.com/zimmski/go-mutesting
- https://github.com/rillig/gobco
- https://github.com/etcd-io/gofail
- https://github.com/etcd-io/etcd/tree/main/tests/robustness
- https://github.com/etcd-io/etcd/issues/16597
- https://etcd.io/blog/2025/autonomus_testing_with_antithesis/
- https://github.com/anishathalye/porcupine
- https://github.com/Shopify/toxiproxy
- https://pkg.go.dev/go.uber.org/goleak
- https://github.com/gotestyourself/gotestsum
