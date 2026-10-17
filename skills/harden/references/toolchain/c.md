# C / C++

Concrete tooling per layer. Read only the entries for the layer you are actually
proposing. Verified against documentation in September 2026; check versions before
quoting a flag as current.

## What is unusual here

What is unusually EASY here: compiler-native instrumentation. Sanitizers (ASan/UBSan/TSan/LSan/MSan), coverage (including MC/DC), and coverage-guided fuzzing are all single compiler flags shipped by GCC and Clang — no third-party runtime, no agent, no rewriting. Fuzzing in particular is more mature in C/C++ than anywhere else (libFuzzer, AFL++, OSS-Fuzz, FuzzTest), and record/replay debugging (rr) has no equivalent in most ecosystems. Syscall-level fault injection via strace --inject needs no code change at all.

What is unusually HARD: (1) Deterministic seeded simulation. There is no library. Rust has madsim/turmoil, Go has testing/synctest; C++ has FoundationDB's Flow, which is a bespoke actor-compiler nobody reuses. You own the clock, the scheduler and the I/O seams or you get nothing. (2) "Same code, two build configurations, in one process" differential testing is blocked by ODR — you need two processes, dlopen, or -D-driven inline namespaces. (3) Mutation testing is Clang-only (Mull) with an exact-version plugin coupling; GCC and MSVC users have nothing. (4) Snapshot testing has no framework-native support; ApprovalTests.cpp is the only real answer and is slow-moving. (5) Unspecified behaviour (evaluation order, unordered-container iteration order) is invisible to every sanitizer and is the number-one source of C++ test flakes.

Two toolchain facts worth carrying: libFuzzer is maintenance-only since late 2022 and google/centipede's standalone repo is archived (folded into google/fuzztest) — google/fuzztest is now the single best entry point because it covers property-based testing, differential/oracle testing, persistent corpus and crash-to-seed regression in one API. And C++26 contracts are real but not portable: GCC 16 implements P2900R14 behind -std=c++26 -fcontracts; mainline Clang 22 does not.

COULD NOT FULLY VERIFY: exact LLVM release that introduced the four libc++ hardening modes (secondary sources consistently say LLVM 18, when _LIBCPP_ENABLE_HARDENED_MODE was split into NONE/FAST/EXTENSIVE/DEBUG and _LIBCPP_ENABLE_ASSERTIONS was deprecated; the current Hardening.html carries no version history). Sources also conflict on Clang C++26 contracts — one 2026 post says "no mainline GCC or Clang", but the GCC 16 changes page explicitly lists P2900R14, so I trust GCC 16 = yes, Clang mainline = no. AFL++ afl-cmin/afl-tmin exact invocations were not confirmed from primary docs and are omitted.

---

## Assertions / invariant checks stripped from production builds

**Reach for** — stdlib: <cassert> assert() gated by -DNDEBUG. Stdlib hardening: libstdc++ -D_GLIBCXX_ASSERTIONS, libc++ -D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_FAST (LLVM 18+), glibc -D_FORTIFY_SOURCE=3. Language-level: C++26 contracts (pre/post/contract_assert), GCC 16 only.

```
# debug: assertions live
c++ -O0 -g -D_GLIBCXX_ASSERTIONS -D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_DEBUG ...
# release: assert() gone, cheap stdlib checks kept
c++ -O2 -DNDEBUG -D_FORTIFY_SOURCE=3 -D_GLIBCXX_ASSERTIONS \
   -D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_FAST ...
# C++26 contracts (GCC 16 only, experimental):
g++ -std=c++26 -fcontracts -fcontract-evaluation-semantic=enforce -lstdc++exp
```

**Caveat** — NDEBUG is the only portable switch and assert() gives you abort() with no custom handler. _GLIBCXX_DEBUG (not _GLIBCXX_ASSERTIONS) is ABI-breaking — every TU and every prebuilt library must agree. libc++ fast/extensive modes trap (__builtin_trap) rather than print, by design. C++26 contracts: GCC 16 implements P2900R14 behind -fcontracts; mainline Clang 22 does NOT (only experimental forks); treat as not-yet-portable.

## Regression test per fixed bug + AUDIT git history for fix-commits with no test

**Reach for** — No standard tool in this ecosystem. Plain git + shell. Enforcement side: git bisect run, plus a CI gate on the same script.

```
git log --no-merges -i --grep='^fix' --format='%H%x09%s' | while IFS=$'\t' read -r sha subj; do
  git show --format= --name-only "$sha" \
    | grep -qiE '(^|/)(tests?|spec)/|_test\.(c|cc|cpp|cxx)$|test_.*\.(c|cc|cpp)$' \
    || echo "NO-TEST $(git show -s --format=%as $sha) ${sha:0:9} $subj"
done
# confirm a test actually pins the bug:
git bisect start HEAD <good> && git bisect run ctest --test-dir build -R MyRegressionTest
```

**Caveat** — Pure heuristic: depends on your commit-message convention and on tests living in a greppable path. Header-only/inline-test layouts (doctest TEST_CASE next to the code) defeat the path regex — switch to `git show -U0 | grep -c 'TEST_CASE\|TEST(' `. SZZ-style bug-introducing-commit tools (pyszz etc.) are research-grade, not production tooling. Verified: script run successfully in a live repo.

## Property-based testing

**Reach for** — google/fuzztest — the de-facto 2026 choice; property-based testing and coverage-guided fuzzing in one macro, GoogleTest-integrated, actively developed (commits Sept 2026). emil-e/rapidcheck is the classic QuickCheck clone, still alive but low-velocity (~2 commits in 2026). Nothing in the stdlib.

```
void SortIsIdempotent(std::vector<int> v) {
  auto a = Sorted(v); auto b = Sorted(a);
  EXPECT_EQ(a, b);
}
FUZZ_TEST(SortTest, SortIsIdempotent)
    .WithDomains(fuzztest::VectorOf(fuzztest::InRange(-100, 100)));
# runs a short randomized budget under plain `ctest`; full fuzz: ./t --fuzz=SortTest.SortIsIdempotent
```

**Caveat** — FuzzTest's fuzzing mode needs Clang (-fsanitize-coverage=inline-8bit-counters,trace-cmp) and is Linux-first; MSVC is unsupported. CMake path needs cmake>=3.19 plus fuzztest_setup_fuzzing_flags()/link_fuzztest(). In non-fuzzing (normal unit-test) builds it still runs each property for a short randomized budget, so it works as an ordinary ctest target. RapidCheck has no releases/tags — you vendor a commit.

## Differential / oracle testing (same code, two configurations)

**Reach for** — No dedicated framework. Standard practice is a FuzzTest/libFuzzer harness asserting equality of two implementations — Google documents this as "Differential Fuzzing with an Oracle" in fuzztest/doc/use-cases.md.

```
void FastMatchesNaive(std::string_view in) {
  EXPECT_EQ(ParseFast(in), ParseNaive(in));   // optimized vs reference
}
FUZZ_TEST(ParserDiff, FastMatchesNaive);
# two *build configs* of the same code: build twice, diff outputs
for cfg in on off; do ./build-$cfg/tool --cache=$cfg < in > out.$cfg; done; diff out.on out.off
```

**Caveat** — The awkward part in C/C++ is genuinely the "same code, two build configurations" variant: you cannot link two differently-configured builds of the same TU into one process without ODR violations. Options are (a) two processes + diff of stdout/artifacts, (b) wrap each build in a distinct inline namespace driven by -D, (c) dlopen two .so's built with -fvisibility=hidden. (a) is what everyone actually does.

## Fault injection: I/O errors, OOM, ENOSPC, timeouts, partial writes, network faults

**Reach for** — strace --inject= (syscall-level, no rebuild, Linux, strace 4.15+) is the lowest-friction. LD_PRELOAD: albertito/libfiu (fiu-run/fiu-ctrl, POSIX failpoints), ralight/mallocfail (per-stacktrace malloc failure, active 2026). Network: tc qdisc netem. ENOSPC: tiny tmpfs. Highest fidelity is in-code injection behind a VFS/allocator seam (the SQLite model).

```
strace -f -e inject=write:error=ENOSPC:when=3 ./myprog          # 3rd write fails
strace -f -e inject=read:error=EIO:when=5+ ./myprog             # every read from 5th on
strace -f -e inject=recvmsg:delay_exit=200000 ./myprog          # 200ms timeout injection
fiu-run -x -c 'enable_random name=posix/io/rw/read,probability=0.05' ./myprog
LD_PRELOAD=libmallocfail.so MALLOCFAIL_FILE=... ./myprog        # OOM per unique stack
sudo tc qdisc add dev eth0 root netem loss 10% delay 100ms 20ms
```

**Caveat** — strace injection is Linux-only and ~100x slowdown; `when=N+` / `when=N+M` syntax is the repeating form. libfiu is maintained but slow-moving (last push Sept 2025) and its POSIX preload only covers the functions in preload/posix/function_list. mallocfail and libfiu both use LD_PRELOAD on malloc and therefore conflict with Valgrind and with ASan's allocator. None of these can inject a *partial* write — for torn writes use LazyFS (next row) or an injectable write() seam in your own code.

## Crash / kill / restart / recovery testing, incl. power-loss simulation of a file write

**Reach for** — In-process: GoogleTest death tests (EXPECT_DEATH / EXPECT_EXIT / ASSERT_DEATH). Real power-loss: kernel dm-log-writes target + josefbacik/log-writes `replay-log` (this is what xfstests uses), or dsrhaslab/lazyfs — a FUSE fs with torn-seq / torn-op / clear-cache faults (active 2026). utsaslab/crashmonkey is ABANDONED (last commit 2022).

```
EXPECT_EXIT(Server().HandleCorruptFrame(buf), ::testing::KilledBySignal(SIGABRT), "bad frame");
# power-loss replay (root, spare device):
sudo dmsetup create logwrites --table "0 $(blockdev --getsz /dev/sdb) log-writes /dev/sdb /dev/sdc"
mkfs.ext4 /dev/mapper/logwrites && mount /dev/mapper/logwrites /mnt && ./workload
sudo replay-log --log /dev/sdc --replay /dev/sdb --end-mark fsync   # then fsck + verify
# userspace alternative:
./scripts/mount-lazyfs.sh -c config/torn-op.toml -m /tmp/lazyfs.mnt -r /tmp/lazyfs.root
```

**Caveat** — dm-log-writes needs root, two block devices, and the out-of-tree `replay-log` userspace tool; it is a filesystem-developer workflow, heavy for app CI. LazyFS is FUSE over ext4, Linux-only, and its torn-op/torn-seq configs are TOML + a named-pipe command protocol (steep setup). GoogleTest death tests fork and are unreliable in multithreaded programs — always set --gtest_death_test_style=threadsafe, and they do not work on Windows the same way. They also interact badly with sanitizers (ASan reports leaks in the forked child unless detect_leaks=0).

## Deterministic seeded simulation (clock, scheduler, randomness, I/O as a function of one seed)

**Reach for** — Genuinely unsupported: there is no C++ equivalent of Rust's madsim/turmoil or Go's testing/synctest. The reference implementation is FoundationDB's Flow (an actor-compiler extension to C++ with a single-threaded simulator and deterministicRandom()) — not reusable as a library. Practical building blocks: template the Clock (std::chrono Clock concept), inject std::mt19937_64 seeded once, own the run loop (C++20 coroutines, single-threaded). Adjacent: rr (record/replay, actively developed), libfaketime (clock only), facebookexperimental/hermit (deterministic Linux container — experimental).

```
struct Sim { std::mt19937_64 rng; std::chrono::steady_clock::time_point now; };
int main(int argc, char** argv) {
  uint64_t seed = argc > 1 ? std::stoull(argv[1]) : std::random_device{}();
  std::fprintf(stderr, "SEED=%llu\n", (unsigned long long)seed);   // print it, always
  Sim s{std::mt19937_64{seed}, {}};
  return RunScenario(s) ? 0 : 1;   // ./sim 12345 must reproduce byte-for-byte
}
rr record --chaos ./flaky_test && rr replay   # capture + replay a real nondeterministic run
```

**Caveat** — Say this plainly: you must build it yourself, and the hard parts (scheduler, socket, filesystem shims) are exactly the parts no library gives you. Hidden nondeterminism sources that bite in C++: pointer-value-dependent ordering (std::unordered_map iteration, std::sort on equal keys), ASLR, uninitialised reads, and std::random_device. Pin ASLR with `setarch -R`. rr is Linux-only, x86-64 or Apple-M1-class ARM, emulates a single core (parallel workloads slow badly), and cannot record processes sharing memory with untraced ones. Hermit gets mostly dependency bumps — treat as research.

## Branch (not line) coverage measurement

**Reach for** — Clang source-based: -fprofile-instr-generate -fcoverage-mapping + llvm-cov show --show-branches=count (cleanest branch data). GCC: --coverage + gcovr (--txt-metric branch) or lcov 2.x (--rc branch_coverage=1). MC/DC: Clang -fcoverage-mcdc (18+) with llvm-cov --show-mcdc, or GCC -fcondition-coverage (14+) with gcov --conditions / gcovr --decisions.

```
clang++ -O0 -g -fprofile-instr-generate -fcoverage-mapping -fcoverage-mcdc t.cc -o t
LLVM_PROFILE_FILE=t.profraw ./t && llvm-profdata merge -sparse t.profraw -o t.profdata
llvm-cov show ./t -instr-profile=t.profdata --show-branches=count --show-mcdc
llvm-cov report ./t -instr-profile=t.profdata   # Branch% column
# GCC side:
g++ --coverage -fprofile-abs-path -fcondition-coverage -O0 t.cc -o t && ./t
gcovr --txt-metric branch --decisions --fail-under-branch 80
```

**Caveat** — gcov branch counts in C++ are noisy: they include compiler-generated exception-unwind edges, so "branch coverage" is systematically depressed and not comparable to other languages. Clang source-based coverage counts only source-level branches and is what you want for a meaningful number. gcovr's -b/--branches is deprecated → use --txt-metric branch. Clang MC/DC handles at most six conditions per boolean expression (larger ones are skipped). lcov MC/DC requires GCC >= 14.2 or LLVM >= 18.1 plus --rc mcdc_coverage=1 / --mcdc-coverage on both lcov and genhtml.

## Mutation testing

**Reach for** — mull-project/mull — LLVM-IR-level, the only maintained general-purpose option (active Sept 2026, v0.34.x). joakim-brannstrom/dextool mutate is source-level and alive but niche (written in D, ~112 stars). No GCC or MSVC option exists.

```
clang++ -fpass-plugin=/usr/lib/mull-ir-frontend-18 -g -grecord-command-line \
        -O0 test.cc -o test_bin
mull-runner-18 ./test_bin -ide-reporter-show-killed
# multi-file: drop -grecord-command-line, use mull.yml with `mutators:` and compile_commands.json
```

**Caveat** — Clang-only, and the plugin/runner must match your Clang major version exactly (mull-ir-frontend-N / mull-runner-N). -grecord-command-line only works when compiling a single file per invocation. Runtime is roughly (number of mutants) x (test-suite time) — budget it per-module, not repo-wide. Template-heavy and header-only code produces large mutant counts with a lot of equivalent mutants, so the raw score is misleading.

## Fuzzing with a persistent corpus + crash-to-seed regression discipline

**Reach for** — google/fuzztest has this built in via a corpus database (--corpus_database, default ~/.cache/fuzztest) that stores the corpus AND every crashing input, and replays crashes as regression tests. Lower level: libFuzzer (-fsanitize=fuzzer, Clang-only) and AFLplusplus (multi-core). OSS-Fuzz for open-source projects.

```
# FuzzTest: fuzz, corpus + crashes persist automatically
./my_test --fuzz=MySuite.MyProp --corpus_database=./fuzz_corpus --jobs=8 --fuzz_for=10m
./my_test --reproduce_findings_as_separate_tests --corpus_database=./fuzz_corpus  # CI gate
FUZZTEST_REPLAY=./fuzz_corpus/.../crash-abc ./my_test   # single reproducer
# libFuzzer
clang++ -g -O2 -fsanitize=fuzzer,address,undefined h.cc -o fuzz
./fuzz corpus/ -jobs=8 -fork=1 -max_total_time=600 && ./fuzz -merge=1 corpus_min/ corpus/
# AFL++
AFL_USE_ASAN=1 afl-clang-lto++ -O2 -fsanitize=fuzzer h.cc -o fuzz
afl-fuzz -M p -i seeds -o out -x dict.dict -- ./fuzz   # crashes land in out/p/crashes/
```

**Caveat** — libFuzzer has been in maintenance-only mode since late 2022 (upstream says the original authors stopped active work and moved to Centipede); it still ships in Clang and is fine, but expect no new features. google/centipede as a standalone repo is ARCHIVED — it now lives inside google/fuzztest. libFuzzer is Clang-only (GCC has no -fsanitize=fuzzer); AFL++ covers GCC via afl-g++-fast and is the right choice for multi-core campaigns. The discipline that matters: commit the minimized corpus dir to the repo and run it as a fixed-time replay in CI (libFuzzer: pass file paths as args; FuzzTest: --replay_corpus).

## Sanitizers and undefined/unspecified behaviour detection

**Reach for** — Compiler-native, both GCC and Clang: -fsanitize=address, undefined, thread, leak. Clang-only: memory (MSan), type (TySan, Clang 21+), realtime (RTSan, Clang 20+). GCC 16 adds -fsanitize=memtag (AArch64 MTE stack tagging). Valgrind memcheck/helgrind as a no-rebuild fallback.

```
c++ -O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined \
    -fno-sanitize-recover=all -fsanitize-address-use-after-scope app.cc -o app
ASAN_OPTIONS=detect_leaks=1:strict_string_checks=1:detect_stack_use_after_return=1 \
UBSAN_OPTIONS=print_stacktrace=1 ./app
c++ -O1 -g -fsanitize=thread app.cc -o app && TSAN_OPTIONS=second_deadlock_stack=1 ./app
clang++ -O1 -g -fsanitize=memory -fsanitize-memory-track-origins=2 -stdlib=libc++ app.cc
```

**Caveat** — ASan and TSan are mutually exclusive — separate CI jobs. UBSan by default *recovers* and keeps going; without -fno-sanitize-recover=all your CI will be green on real UB. MSan requires EVERY dependency including libc++ to be MSan-instrumented, which in practice means building libc++ yourself — Clang-only, no GCC equivalent, and the usual reason teams skip it. Unspecified (as opposed to undefined) behaviour — evaluation order, unordered container iteration order, signed-shift-adjacent implementation-defined choices — is largely NOT detected by any sanitizer; -fstrict-aliasing violations need the newer TySan (-fsanitize=type, Clang 21+, still young). Add -D_GLIBCXX_ASSERTIONS / libc++ hardening alongside; sanitizers do not check STL preconditions.

## Golden/snapshot testing + corpus of malformed inputs

**Reach for** — approvals/ApprovalTests.cpp — header-only approval/golden-master testing, plugs into GoogleTest, Catch2, doctest, Boost.Test, CppUTest, [Boost].ut. For CLI/compiler-shaped tools, LLVM's lit + FileCheck is the de-facto standard and works out-of-tree (pip install lit). Malformed-input corpus = the fuzzer corpus directory, committed and replayed.

```
// ApprovalTests + gtest
#define APPROVALS_GOOGLETEST
#include "ApprovalTests.hpp"
TEST(Render, Golden) { ApprovalTests::Approvals::verify(Render(doc)); }
// first run writes *.received.txt; you `mv` it to *.approved.txt to bless it
# lit/FileCheck style (out-of-tree)
# RUN: %tool %s | FileCheck %s
# CHECK: error: unterminated string at 3:12
pip install lit && lit -v test/ && ./fuzz corpus_malformed/*   # replay bad-input corpus
```

**Caveat** — ApprovalTests.cpp is maintained but slow-moving: last tagged release v.10.13.0 (March 2024) despite commits into Aug 2026 — pin the header, don't expect frequent releases. It needs a configured diff tool for interactive blessing, and its "accept by renaming .received to .approved" workflow is easy to rubber-stamp in review. lit/FileCheck bring a Python dependency and are only ergonomic when your unit of test is "run a binary, match its text output". There is no stdlib or framework-native snapshot facility in Catch2/GoogleTest/doctest.

## Flake elimination / enforcing run-to-run determinism

**Reach for** — CTest: --repeat until-fail:N, --schedule-random (+ --schedule-random-seed, CMake 4.1+), --rerun-failed. GoogleTest: --gtest_shuffle --gtest_random_seed=N --gtest_repeat=N. Catch2 v3: --order rand --rng-seed <n>, --shard-count/--shard-index. TSan for the underlying races. rr record --chaos to capture a flake you cannot reproduce. setarch -R to pin ASLR.

```
ctest --test-dir build -j8 --output-on-failure --repeat until-fail:50 --schedule-random
ctest --schedule-random-seed 4242 --rerun-failed      # reproduce an ordering-dependent failure
./tests --gtest_shuffle --gtest_random_seed=4242 --gtest_repeat=100 --gtest_break_on_failure
./tests --order rand --rng-seed 4242                  # Catch2 v3
setarch -R ./tests                                    # kill ASLR-dependent flakes
rr record --chaos ./tests && rr replay                # then debug the exact failing run
```

**Caveat** — ctest --repeat <mode>:<n> requires CMake 3.17+ (--repeat-until-fail alone goes back to 3.2); --schedule-random-seed only landed in CMake 4.1, so before that random scheduling was not reproducible. Catch2 v3 randomizes order BY DEFAULT with a random_device seed — CI must log and be able to pin --rng-seed or you cannot reproduce. GoogleTest --gtest_random_seed=0 means time-based (non-reproducible). The dominant C++-specific flake source is iteration order of std::unordered_* (pointer/hash dependent, varies with ASLR and allocator) — grep for range-for over unordered containers before blaming the scheduler.

---

## Sources

- https://llvm.org/docs/LibFuzzer.html
- https://appsec.guide/docs/fuzzing/c-cpp/libfuzzer/
- https://appsec.guide/docs/fuzzing/c-cpp/aflpp/
- https://github.com/google/fuzztest
- https://github.com/google/fuzztest/blob/main/doc/use-cases.md
- https://github.com/google/fuzztest/blob/main/doc/flags-reference.md
- https://github.com/google/fuzztest/blob/main/doc/quickstart-cmake.md
- https://github.com/google/fuzztest/blob/main/fuzztest/init_fuzztest.cc
- https://libcxx.llvm.org/Hardening.html
- https://gcc.gnu.org/gcc-16/changes.html
- https://fkoehler.me/posts/2026/05/test-driving-cpp26-contracts-with-gcc-16-1/
- https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2025/p2899r1.pdf
- https://clang.llvm.org/docs/SourceBasedCodeCoverage.html
- https://llvm.org/docs/CommandGuide/llvm-cov.html
- https://gcc.gnu.org/onlinedocs/gcc/Invoking-Gcov.html
- https://gcovr.com/en/stable/manpage.html
- https://man.archlinux.org/man/lcov.1.en
- https://maskray.me/blog/2024-01-28-mc-dc-and-compiler-implementations
- https://mull.readthedocs.io/en/latest/tutorials/HelloWorld.html
- https://github.com/mull-project/mull
- https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html
- https://clang.llvm.org/docs/RealtimeSanitizer.html
- https://clang.llvm.org/docs/TypeSanitizer.html
- https://man7.org/linux/man-pages/man1/strace.1.html
- https://blitiri.com.ar/p/libfiu/doc/posix.html
