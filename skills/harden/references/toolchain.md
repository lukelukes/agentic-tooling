# Toolchain index

Per-language detail lives in one file each. Read only the one you need:

[`toolchain/go.md`](toolchain/go.md) ·
[`toolchain/rust.md`](toolchain/rust.md) ·
[`toolchain/python.md`](toolchain/python.md) ·
[`toolchain/typescript.md`](toolchain/typescript.md) ·
[`toolchain/jvm.md`](toolchain/jvm.md) ·
[`toolchain/c.md`](toolchain/c.md)

Each covers the same thirteen layers with the concrete tool, the real invocation, and the caveat.
Verified September 2026.

---

## What is cheap where

Use this to pick the layer with the best effort-to-value ratio *in this language*, which is often
not the layer that is most valuable in the abstract.

| | Cheapest high-value layer | Genuinely hard here |
|---|---|---|
| **Go** | `go test -fuzz` — crash-to-seed corpus is automatic and replays on every later `go test`. `testing/synctest` gives a virtual clock free. | No branch coverage *at all*. Mutation testing options are 0.x or abandoned. No I/O-level fault-injection hook. |
| **Rust** | `cargo-mutants` (zero config) and proptest, which commits the *seed* to `proptest-regressions/` so regressions persist automatically. Miri catches UB nothing else sees. | Every fault-injection seam must be designed in advance — you cannot intercept `std` from `cfg(test)`. `cargo-fuzz` is still nightly and Unix-only. |
| **Python** | Hypothesis — arguably the strongest PBT library anywhere. `unittest.mock.patch` makes fault injection a three-line job. | No virtual clock, no deterministic scheduler, no per-module assertion stripping (`python -O` is global, so most production Python ships with asserts on). |
| **TypeScript** | `node:test` covers snapshots, fake timers, mocking and coverage with zero dependencies. fast-check is best-in-class, with `fc.scheduler()` for async interleavings. StrykerJS `--since` gives a sub-2-minute mutation gate. | Assertion stripping has no standard. Deterministic simulation is the weakest of any ecosystem here — libuv's threadpool is not controllable. |
| **JVM** | Bytecode instrumentation means JaCoCo and PIT just work with no source changes. Byteman throws an exception from any call site in the JDK. jcstress and Lincheck for concurrency have no real equivalent elsewhere. | Whole-program determinism is essentially unsolved. Kotlin degrades several tools, and free Kotlin mutation testing is effectively dead. |
| **C/C++** | Everything is a compiler flag: sanitizers, MC/DC coverage, and coverage-guided fuzzing. `google/fuzztest` now covers PBT, differential testing and the persistent corpus in one API. `strace --inject` needs no code change at all. | No deterministic simulation library exists. Two build configs in one process is blocked by ODR. Mutation testing is Clang-only. |

---

## Three cross-language traps

These caught out more than one of the language surveys, and each one invalidates a layer that looks
like it is working.

**SIGKILL is not power loss.** Killing the process leaves unfsynced writes in the OS page cache,
where they are written out afterwards anyway. A crash test built on `kill -9` therefore *passes* on
code with a broken fsync discipline — the exact bug it was written to find. Real power-loss testing
needs the writes intercepted below the process: `dm-flakey`, `dm-log-writes`, LazyFS or CharybdeFS.
This is true in every language here; Go, Rust and the JVM surveys each flagged it independently. If
you build a crash test, say in the report which of the two things it actually tests.

**"Branch coverage" frequently is not.** The number means different things per toolchain, and
several report a flattering one:

- Go has no branch coverage at all — `go test -cover` is *statement* coverage, so `if a && b` is a
  single counter.
- Node's `--test-coverage-branches` and `c8` report raw V8 block coverage, which counts an implicit
  `else` as covered. One measurement: 66.67% from c8 against 25% from istanbul, same function.
- Rust's branch coverage is nightly-only; stable gives region and line.
- JaCoCo inflates Kotlin branch counts with synthetic null-checks and default-argument masks.

Check what the tool actually measures before quoting a percentage, and never compare the number
across languages.

**Abandoned but still widely recommended.** Search results and model priors both lag. Currently
dead or maintenance-only: `zimmski/go-mutesting`, `unassert` (JS), `junit-quickcheck`,
`QuickTheories`, `pitest-kotlin`, and libFuzzer (maintenance-only since late 2022; prefer
`google/fuzztest`). Check the last commit date before recommending a tool.

---

## One note specific to agents

jqwik's release notes state that the project "is not meant to be used by any 'AI' coding agents at
all." That is a notice rather than a licence term, but it is the maintainer's stated wish. On
Kotlin, prefer Kotest's property testing; on Java, expect friction and consider raising it with the
user rather than proceeding silently.
