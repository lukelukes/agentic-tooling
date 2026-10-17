# Rust (verified against stable rustc 1.98.1, Sept 2026)

Concrete tooling per layer. Read only the entries for the layer you are actually
proposing. Verified against documentation in September 2026; check versions before
quoting a flag as current.

## What is unusual here

Unusually easy in Rust: (1) The toolchain owns most of this. `cargo test`, `#[cfg(test)]` unit tests with access to private items, `debug_assert!`, `-C instrument-coverage`, and the profile knobs are all first-party -- no framework choice to make. (2) Determinism is far more attainable than in GC'd languages: no finalizer nondeterminism, no JIT warmup, defined integer/float behaviour, and `Instant`/RNG are explicit values rather than ambient globals, so "pure function of a seed" is a realistic goal rather than an aspiration. (3) Miri has no counterpart in C/C++ -- a MIR interpreter that catches aliasing and provenance UB that AddressSanitizer structurally cannot see. (4) As of 2026, sanitizers are one `rustup target add x86_64-unknown-linux-gnuasan` away on the stable toolchain, which is better ergonomics than clang's `-fsanitize` story. (5) Property testing has a single clear winner (proptest) whose failure-persistence design -- storing the SEED, not the value, in a committed `proptest-regressions/` tree -- makes "regression test per bug" partly automatic.

Unusually hard in Rust: (1) Branch coverage is still nightly-only; stable gives region/line. (2) No monkey-patching and no runtime interception means every fault-injection seam must be designed in advance -- a trait, a generic parameter, or an explicit `fail_point!`. Retrofitting ENOSPC injection into code that calls `std::fs` directly is close to impossible without rewriting it; `cfg(test)` cannot intercept `std`. (3) `cargo-fuzz` still requires nightly and is Unix-only, which is worse than Go's built-in `go test -fuzz`. (4) Crash/power-loss consistency testing has no standard tooling whatsoever -- the two crates that claim it have under 50 downloads each, and `Child::kill()` does not actually model power loss because the page cache survives. (5) Default in-process thread parallelism lets one poisoned global leak across tests, which is why cargo-nextest's process-per-test model is effectively required rather than optional. (6) Compile time dominates: mutation testing, `--feature-powerset`, and sanitizer builds are all rebuild-bound, so sharding (`cargo mutants --shard`, `cargo nextest --partition`) matters more than raw test speed. (7) Async determinism forces you to buy into one runtime's clock abstraction (tokio's `time::pause`); there is no runtime-agnostic `Clock` trait in the ecosystem.

---

## Assertions / invariant checks stripped from production builds

**Reach for** — stdlib: `debug_assert!` / `debug_assert_eq!` / `debug_assert_ne!`, `cfg!(debug_assertions)`, `#[cfg(debug_assertions)]`. Toolchain: Cargo profile keys `debug-assertions` and `overflow-checks` (`-C debug-assertions=on`, `-C overflow-checks=on`). No third-party crate needed.

```
debug_assert!(self.len <= self.cap, "len {} > cap {}", self.len, self.cap);
# Cargo.toml -- keep invariants live in a staging/canary release build:
[profile.release]
debug-assertions = true
overflow-checks  = true
```

**Caveat** — Verified on 1.98.1: `rustc -O` strips the assert (zero cost, args type-checked but not evaluated); `rustc -O -C debug-assertions=on` panics. `overflow-checks` is a SEPARATE knob -- it defaults to following `debug-assertions` but can be set alone, and arithmetic overflow is silently wrapping in release without it. `#[core::contracts::requires/ensures]` (design-by-contract) is nightly-only behind `#![feature(contracts)]`, tracking issue #128044 -- do not build on it.

## Regression test per fixed bug + auditing git history for fix-commits with no test

**Reach for** — No Rust-specific tool exists. Use stdlib `#[test]` for the regression test and a shell/git heuristic for the audit. `cargo-mutants --in-diff` is the forward-looking enforcement in CI.

```
git log --no-merges --format='%H %s' --grep='^fix' --grep='bug' -i | while read -r sha subj; do
  git show --name-only --format= "$sha" | grep -q '\.rs$' || continue
  git show "$sha" | grep -qE '^\+.*(#\[(test|tokio::test|rstest|proptest)\]|assert_snapshot!)' \
   || git show --name-only --format= "$sha" | grep -qE '^(tests/|fuzz/corpus/|proptest-regressions/)|\.snap$' \
   || echo "NO TEST: ${sha:0:12} $subj"
done
```

**Caveat** — I ran this against github.com/mitsuhiko/insta: 11 of 57 fix-commits in 2 years added no test. It is a heuristic -- doc fixes, clippy fixes and dependency bumps are false positives; filter by `--` pathspec to your real source dirs. Rust has no equivalent of a coverage-diff gate out of the box; the closest enforcement is `git diff origin/main.. | cargo mutants --in-diff -` in CI, which fails when changed lines can be mutated without any test noticing.

## Property-based testing

**Reach for** — `proptest` 1.11.0 (Mar 2026) -- the de-facto standard; `proptest-derive` 0.8 or `test-strategy` 0.4.5 for attribute syntax; `proptest-state-machine` 0.8 for model-based/stateful testing. `quickcheck` 1.1.0 exists (BurntSushi shipped 1.1.0 in Feb 2026 after 5 dormant years) but has markedly weaker shrinking.

```
// [dev-dependencies] proptest = "1.11"
proptest::proptest! {
    #[test]
    fn roundtrip(s in "\\PC*") { prop_assert_eq!(decode(&encode(&s))?, s); }
}
// PROPTEST_CASES=10000 cargo test     (default is 256 cases)
```

**Caveat** — Failing cases are auto-persisted as SEEDS (not values) into `proptest-regressions/<path/to/file>.txt`; commit that directory -- it IS your regression suite and is replayed before new cases on every run. Inside `proptest!` use `prop_assert*!` not `assert*!` so shrinking works. `prop_assume!` for filtering silently burns the case budget if overused.

## Differential / oracle testing (two configurations, identical output)

**Reach for** — No dedicated crate; this is an idiom, not a tool. Driver = `proptest` or `cargo fuzz`; config matrix = `cargo-hack` 0.6.45 (`--feature-powerset`); readable diffs = `similar-asserts` 2.0.

```
proptest! { #[test] fn fast_matches_naive(xs in prop::collection::vec(any::<i64>(), 0..512)) {
    prop_assert_eq!(sum_fast(&xs), xs.iter().sum::<i64>());          // fast path vs oracle
}}
// cache on/off in ONE process (runtime flag, not cfg):
// prop_assert_eq!(run(Cfg{cache:true}, &input), run(Cfg{cache:false}, &input));
cargo hack test --feature-powerset --depth 2   # same code, every feature config
```

**Caveat** — Prefer a runtime config struct over `#[cfg(feature)]` for the on/off axis -- `cfg` variants cannot both exist in one process, so you cannot assert_eq across them. For new-impl-vs-old-impl, pull the old version in as a second dev-dependency under a rename (`old_thing = { package = "thing", version = "0.4" }`) or a `git worktree` path dep. Under `cargo fuzz` your crate is compiled with `--cfg fuzzing` automatically: use it to silence nondeterminism (timestamps, randomness), never to change the algorithm being compared.

## Fault injection: I/O errors, ENOSPC, timeouts, partial writes, network faults

**Reach for** — `fail` 0.5.1 (tikv/fail-rs; repo still active Sep 2026 despite no release since 2022) or the maintained fork `fail-parallel` 0.6.0 (slatedb, Jul 2026) which fixes the parallel-test problem. Network faults: `turmoil` 0.7.2. Error values: stdlib `std::io::ErrorKind` -- the errno-ish variants are now stable. `partial-io` is unmaintained (last release 2022).

```
fail::fail_point!("before-fsync", |_| Err(io::Error::from(io::ErrorKind::StorageFull)));
// macro compiles to NOTHING unless the feature is on:
FAILPOINTS='before-fsync=90%return' cargo test --features fail/failpoints
// partial write / EINTR without any crate: wrap the writer
impl Write for Flaky<W> { fn write(&mut self, b:&[u8])->io::Result<usize>{
    if self.n==0 { Err(io::ErrorKind::Interrupted.into()) } else { self.inner.write(&b[..1]) } } }
```

**Caveat** — Verified on 1.98.1 that `StorageFull`, `QuotaExceeded`, `ResourceBusy`, `FileTooLarge`, `ReadOnlyFilesystem`, `NetworkDown`, `HostUnreachable`, `StaleNetworkFileHandle`, `WriteZero`, `CrossesDevices` are all STABLE `ErrorKind` variants -- hand-rolled injection no longer needs nightly or a crate. The `FAILPOINTS` registry is process-global, so put failpoint tests in a dedicated test binary or use `fail-parallel`. Action grammar: `off|return|panic|sleep(ms)|pause|delay(ms)|print`, prefixed by `N%` probability and/or `N*` count. Crucially, Rust has no monkey-patching: you must design the seam (trait object, generic over a `FileSystem`/`Clock` trait, or an explicit `fail_point!`) BEFORE you need it.

## Crash / kill / restart / recovery, incl. power-loss simulation of a file write

**Reach for** — Genuinely no de-facto standard in Rust -- say so plainly. Practice: stdlib `std::process::Command` + `Child::kill()` (SIGKILL) against `env!("CARGO_BIN_EXE_<name>")`; `fail` points with the `panic`/`exit` action to crash at an exact line; `turmoil`'s `sim.crash("host")` / `sim.bounce("host")` for the distributed case. True power-loss needs an in-memory FS model you write yourself, or non-Rust tooling (dm-log-writes, CrashMonkey/ACE).

```
let mut c = Command::new(env!("CARGO_BIN_EXE_mydb")).arg(&dir).spawn()?;
wait_for_ack(&dir)?;                 // write has been acknowledged to the client
c.kill()?; c.wait()?;                // SIGKILL: no Drop, no flush, no fsync
assert_recovered(&dir)?;             // reopen and assert the durability invariant
// crash at a precise internal point instead:
// FAILPOINTS='after-wal-append=panic' cargo test --features fail/failpoints
```

**Caveat** — `Child::kill()` is SIGKILL so destructors and buffered writes are lost -- that is the point -- but it does NOT model power loss: the OS page cache survives, so a written-but-unsynced block still lands on disk and your test will pass a bug it should catch. Modelling lost/reordered unsynced writes requires a fake filesystem in front of your storage layer, `dm-log-writes` under the test, or a commercial DST platform (Antithesis). The crates.io hits `powercut` and `fstx` have <50 total downloads each -- do not recommend them.

## Deterministic seeded simulation (clock, scheduler, randomness, I/O from one seed)

**Reach for** — `turmoil` 0.7.2 (tokio-rs; hosts+network+time, `rng_seed`), `madsim` 0.2.34 (full deterministic runtime, shims libc), `shuttle` 0.9.3 (awslabs; randomized scheduler + replay string -- actively developed), `loom` 0.7.2 (exhaustive interleavings). Clock: `tokio::time::pause` / `#[tokio::test(start_paused = true)]` (features `time`,`test-util`). Entropy: `rand` 0.10 `StdRng::seed_from_u64(seed)`.

```
let mut sim = turmoil::Builder::new().rng_seed(seed).fail_rate(0.01).build();
sim.host("srv", || async { serve().await });   // must use turmoil::net::TcpStream
sim.client("c",  async { /* asserts */ Ok(()) });
sim.run()?;                                     // same seed => byte-identical run
// shuttle: on failure it prints a schedule string -> shuttle::replay(f, "9101...")
for s in $(seq 1 1000); do SEED=$s cargo test --test sim || break; done
```

**Caveat** — Rust gives you no determinism for free -- you must (a) thread the seed into every RNG, (b) use `tokio::time::Instant` not `std::time::Instant`, (c) use the `current_thread` runtime flavor, (d) route all I/O through the sim types. Any call reaching real libc (`clock_gettime`, `getrandom`) silently breaks reproducibility; madsim and S2's `mad-turmoil` 0.2.1 override those symbols to fix it. loom = sound but state-space explodes (cap with `LOOM_MAX_PREEMPTIONS=3`, and it has had no release since Apr 2024); shuttle = unsound but scales to real code. Guard the whole thing with a CI meta-test that reruns one seed twice and diffs trace logs byte-for-byte.

## Branch (not line) coverage

**Reach for** — `cargo-llvm-cov` 0.9.1 driving rustc's `-C instrument-coverage`. Branch coverage = `--branch`; MC/DC = `--mcdc`. Both NIGHTLY-ONLY. `cargo-tarpaulin` 0.37.3 explicitly documents `-b, --branch  Branch coverage: NOT IMPLEMENTED`.

```
cargo install cargo-llvm-cov
cargo +nightly llvm-cov --branch --html            # branch coverage (unstable)
cargo +nightly llvm-cov --mcdc --lcov --output-path lcov.info
cargo llvm-cov nextest --lcov --output-path lcov.info   # stable: region/line only
```

**Caveat** — Verified on rustc 1.98.1: `-Zcoverage-options=branch` is rejected with "the option `Z` is only accepted on the nightly compiler", while `-C instrument-coverage` compiles fine. So on stable Rust in Sept 2026 you get region/line coverage only -- branch coverage is still a nightly feature (unstable book: `coverage-options` = `block|branch|condition`). `--doctests` also needs nightly. This is a genuine weak spot versus JVM/JS ecosystems.

## Mutation testing

**Reach for** — `cargo-mutants` 27.1.0 (2 Jun 2026), MSRV 1.88. The only serious option. `mutagen` is abandoned (last release 2018, ~360 recent downloads).

```
cargo install --locked cargo-mutants
cargo mutants -j4 --timeout 60                     # full run -> mutants.out/
git diff origin/main.. | cargo mutants --in-diff -  # PR-scoped, fits a CI budget
cargo mutants --shard 1/8                          # fan out across CI runners
```

**Caveat** — Requires an already-green, genuinely non-flaky suite -- it reruns the whole suite once per mutant, so a single flaky test poisons the report. No cross-compilation support. `--in-diff` is documented as "not a substitute for a full test run" (a change in one file can break coverage elsewhere). Suppress unmutatable code with `#[mutants::skip]`. Breaking change in 27.0.0: `--file/--exclude/--examine-re/--exclude-re` now COMBINE with config-file values instead of replacing them.

## Fuzzing with a persistent corpus + crash-to-seed regression discipline

**Reach for** — `cargo-fuzz` 0.13.2 + `libfuzzer-sys` (default), `afl` 0.18.2 (afl.rs), `bolero` 0.13.4 (one `check!` body runs as a unit test, a libfuzzer/AFL/honggfuzz target, and under Kani). Structured inputs: `arbitrary` 1.4.2 with `#[derive(Arbitrary)]`.

```
cargo install cargo-fuzz && cargo fuzz init && cargo fuzz add parse
cargo +nightly fuzz run parse -- -max_total_time=600 -jobs=8  # corpus: fuzz/corpus/parse/
cargo fuzz run  parse fuzz/artifacts/parse/crash-<sha1>       # reproduce
cargo fuzz tmin parse fuzz/artifacts/parse/crash-<sha1>       # minimize the input
cargo fuzz cmin parse                                         # minimize the corpus
// fuzz_target!(|input: MyStruct| { let _ = handle(input); });
```

**Caveat** — cargo-fuzz REQUIRES nightly (it passes unstable rustc flags) and only supports x86-64/aarch64 Unix -- no Windows. This is worse than Go's built-in `go test -fuzz`. Discipline: commit `fuzz/corpus/<target>/`, and for every crash copy the artifact bytes into a committed file AND write a plain `#[test]` that feeds them, so `cargo test` (stable, no nightly) catches the regression forever. Upstream libFuzzer has been maintenance-only since late 2022 (authors moved to Centipede); `libafl_libfuzzer` is a documented drop-in replacement for the `libfuzzer-sys` dependency. Fuzz builds get `--cfg fuzzing` automatically -- use it to disable checksums/timestamps, not logic.

## Sanitizers and undefined/unspecified behaviour detection

**Reach for** — NEW IN 2026 AND THE HEADLINE ANSWER: stable sanitizer targets `x86_64-unknown-linux-gnuasan` / `gnumsan` / `gnutsan` (Tier 2; PR #149644 merged 2026-01-20, PR #152757 merged 2026-03-26). Plus Miri (`rustup +nightly component add miri`) for UB/aliasing/data races in `unsafe` code, and `cargo-careful` 0.4.10 for std-internal debug assertions.

```
rustup target add x86_64-unknown-linux-gnuasan   # STABLE: no nightly, no -Zbuild-std
cargo test --target x86_64-unknown-linux-gnuasan
cargo +nightly miri test            # MIRIFLAGS="-Zmiri-many-seeds -Zmiri-tree-borrows"
cargo +nightly careful test
RUSTFLAGS=-Zsanitizer=thread cargo +nightly test -Zbuild-std --target x86_64-unknown-linux-gnu
```

**Caveat** — I verified this end-to-end on rustc 1.98.1: `rustup target list` contains gnuasan/gnumsan/gnutsan, and `rustc --target x86_64-unknown-linux-gnuasan` produced a binary that reported `AddressSanitizer: heap-buffer-overflow` -- no nightly, no build-std. Caveats: these targets are cross-compile-only (no host tools), so proc-macro-heavy workspaces may need extra `--target` plumbing. The `-Zsanitizer=` FLAG itself is still unstable -- stabilization PR #123617 was still open in Sept 2026 -- so the targets are the stable path, not the flag. Miri is an interpreter: 50-500x slower, no FFI or inline asm, and explores one nondeterministic path per run (hence `-Zmiri-many-seeds`); it catches aliasing/provenance UB that ASan structurally cannot.

## Golden/snapshot testing and a corpus of malformed inputs

**Reach for** — `insta` 1.48.0 + `cargo-insta` -- the de-facto standard. `insta::glob!` (feature `glob`) for corpus-driven snapshots. `trycmd` 1.2.1 / `snapbox` 1.2.2 (assert-rs) for CLI golden files. `expect-test` 1.5.1 (rust-analyzer) if you want inline-only with near-zero deps -- stable/finished rather than abandoned, but last released Dec 2024. `datatest-stable` 0.3.3 for one-test-per-corpus-file reporting.

```
// [dev-dependencies] insta = { version = "1.48", features = ["glob"] }
insta::glob!("corpus/malformed/*.bin", |p| {
    insta::assert_debug_snapshot!(parse(&std::fs::read(p).unwrap()));
});
cargo test && cargo insta review        # interactive accept/reject of .snap.new
// INSTA_UPDATE=always cargo test   (force-write; INSTA_UPDATE defaults to `no` under CI)
```

**Caveat** — Snapshots live in `snapshots/*.snap` beside the test; unreviewed ones are `.snap.new` (or `.pending-snap` for inline `@"..."` snapshots). `INSTA_UPDATE=auto` resolves to `no` when the `CI` env var is set, so CI fails instead of silently rewriting -- assert that in your pipeline rather than trusting it. The natural corpus pipeline is fuzzer -> `fuzz/artifacts/` -> committed `corpus/malformed/` -> `insta::glob!`, which gives you one stable-toolchain test over every historical crash input. `glob!` panics on zero matches, which is the behaviour you want.

## Flake elimination / enforcing run-to-run determinism in the suite

**Reach for** — `cargo-nextest` 0.9.145 (Sep 2026): process-per-test isolation by default, `--retries` + `flaky-result = "fail"`, `slow-timeout`/`terminate-after`, `leak-timeout`, `--partition`. Effectively mandatory for a serious Rust suite.

```
cargo nextest run --retries 2 --flaky-result fail  # pass-on-retry is now a FAILURE
cargo nextest run --test-threads 1                 # contrast with default: order/parallelism deps
# .config/nextest.toml
[profile.ci]
retries = 2
flaky-result = "fail"
slow-timeout = { period = "30s", terminate-after = 4 }
```

**Caveat** — `--flaky-result` / `NEXTEST_FLAKY_RESULT` landed in nextest 0.9.131 (2026-03-18) -- older nextest silently treats pass-on-retry as a pass. nextest does NOT run doctests: keep a separate `cargo test --doc` in CI. Rust-specific flake sources to hunt: `HashMap`/`HashSet` iteration order (`RandomState` reseeds per process, so nextest's process-per-test amplifies ordering bugs -- a feature, not a bug), wall-clock sleeps (replace with `tokio::time::pause`), `std::env::set_var` (process-global and `unsafe` since edition 2024), and `static mut`/`OnceLock` state shared across in-process tests. Also pin `PROPTEST_CASES` and commit `proptest-regressions/` so property tests don't themselves become the flake.

---

## Sources

- https://doc.rust-lang.org/nightly/unstable-book/compiler-flags/coverage-options.html
- https://doc.rust-lang.org/beta/unstable-book/compiler-flags/sanitizer.html
- https://doc.rust-lang.org/nightly/rustc/platform-support/x86_64-unknown-linux-gnuasan.html
- https://doc.rust-lang.org/nightly/core/contracts/index.html
- https://github.com/rust-lang/rust/issues/123615
- https://github.com/rust-lang/rust/pull/149644
- https://github.com/rust-lang/rust/pull/152757
- https://github.com/rust-lang/rust/pull/123617
- https://github.com/taiki-e/cargo-llvm-cov
- https://github.com/taiki-e/cargo-llvm-cov/issues/8
- https://github.com/xd009642/tarpaulin
- https://mutants.rs/
- https://mutants.rs/in-diff.html
- https://mutants.rs/changelog.html
- https://proptest-rs.github.io/proptest/proptest/failure-persistence.html
- https://proptest-rs.github.io/proptest/proptest/state-machine.html
- https://rust-fuzz.github.io/book/cargo-fuzz.html
- https://rust-fuzz.github.io/book/cargo-fuzz/tutorial.html
- https://rust-fuzz.github.io/book/cargo-fuzz/guide.html
- https://github.com/rust-fuzz/cargo-fuzz
- https://github.com/AFLplusplus/LibAFL/pull/981
- https://llvm.org/docs/LibFuzzer.html
- https://github.com/rust-lang/miri
- https://github.com/RalfJung/cargo-careful
- https://docs.rs/loom/latest/loom/
