# The catalog

One entry per layer. Each says what it catches *that nothing else does*, how to build the cheap
version, and how it fails — because most of these layers have a degenerate form that looks like
the real thing and finds nothing.

Read the entries for the layers you are actually considering. Do not read the whole file.

**A · Correctness you specified**
[Example tests](#example-tests) ·
[Assertions](#assertions) ·
[Reachability assertions](#reachability-assertions) ·
[Regression corpus](#regression-corpus)

**B · Correctness you did not specify**
[Properties](#properties) ·
[The second opinion](#the-second-opinion) ·
[Differential oracles](#differential-oracles)

**C · Correctness under duress**
[Fault injection](#fault-injection) ·
[Crash and restart](#crash-and-restart) ·
[Deterministic simulation](#deterministic-simulation) ·
[Adversarial corpus](#adversarial-corpus) ·
[Fuzzing](#fuzzing)

**D · Containing the damage** (not tests — often the better answer)
[Dry-run](#dry-run) ·
[Idempotency key](#idempotency-key) ·
[Blast-radius cap](#blast-radius-cap) ·
[Kill switch](#kill-switch) ·
[Audit log and undo](#audit-log-and-undo) ·
[Typed config at boot](#typed-config-at-boot) ·
[Version-skew tests](#version-skew-tests)

**E · Finding out in production**
[Invariant sweeper](#invariant-sweeper) ·
[Stored checksums](#stored-checksums) ·
[Reconciliation](#reconciliation) ·
[Restore drill](#restore-drill)

**F · Auditing the suite**
[Coverage](#coverage) ·
[Mutation testing](#mutation-testing) ·
[Determinism](#determinism) ·
[The human checklist](#the-human-checklist)

Before any of it: [the escalation ladder](#the-escalation-ladder).

---

## The escalation ladder

Check this before recommending a test, because the rungs above "test" are cheaper *and* stronger,
and an agent reaching for tests reflexively will miss them:

1. **Make it impossible.** Change the types or the structure so the bug cannot be expressed. A
   parsed-and-validated type that cannot hold an invalid value retires an entire class of test.
   TigerBeetle's static allocation retires fragmentation, OOM and use-after-free simultaneously.
2. **Make it a compile error.** Exhaustive matching, non-nullable types, `#[must_use]`, a linter
   rule with teeth.
3. **Make it an assertion.** Cheap, always on in development, covers inputs you never imagined.
4. **Make it a test.** The most specific, most maintenance, and the only one that covers exactly
   the case you thought of and nothing else.

A rung higher covers input you never enumerated. If `/analyze-illegal-states` would retire the bug
outright, say that instead of writing a test for it. "You do not need a test here, you need this
field to be a different type" is one of the most valuable outputs this skill can produce.

---

# A · Correctness you specified

## Example tests

**Catches:** that the thing works at all, for the cases someone thought of. Nothing else in the
catalog substitutes for this, and it is where almost every codebase already is.

**Build:** at the boundary of the unit, not its internals. Tests coupled to internals block the
refactor that would have eliminated the bug class.

**Fails when:** it is the *only* layer, which is the usual case. A suite of hand-written examples
encodes exactly one person's model of what could go wrong, and production bugs live in the
complement of that model. Adding the two-hundredth example test has a much lower expected value
than adding the first test of any other kind — that is the core argument this skill makes.

---

## Assertions

**Catches:** an invariant violated *at the moment it happens*, rather than as a confusing symptom
three layers away. Also the only layer that covers inputs nobody enumerated, in production, for
free.

**Build:** preconditions, postconditions, loop invariants. TigerBeetle's rule of thumb is two per
function on average, and asserting *both* directions is what makes them work — the positive space
you expect and the negative space you do not. Pair them across call boundaries: assert the
contract at the caller and again at the callee, because that catches the case where the two
disagree about what the contract is.

SQLite has 6,754 of them at roughly 3× runtime cost, compiled out unless `SQLITE_DEBUG` is set.
The compile-out is what makes the density affordable.

**Separate "I have a proof" from "I believe this."** SQLite uses four constructs for four distinct
epistemic states, and the distinction is the genuinely transferable part — most codebases collapse
all of it into one `assert`:

| Construct | The claim being made | Release build |
|---|---|---|
| `assert(X)` | X is *provably* invariant | compiled out |
| `ALWAYS(X)` | believed true, but no proof — defensive | passes X through |
| `NEVER(X)` | believed false, but no proof — defensive | passes X through |
| `testcase(X)` | X is definitely *not* invariant; force both branches | compiled out |

> "In SQLite, the presence of assert(X) means that the developers have a proof that X is always
> true." … "An assert(X) should not be seen as a safety-net or top-rope used to guard against
> mistakes."

The reason it matters operationally: a proof-backed assertion can be compiled out safely, because
if the proof is right the check is redundant. A *belief*-backed one cannot — the belief may be
wrong in production, so the branch has to stay in the shipped binary with real handling behind it.
Collapsing the two means either shipping checks you do not need or removing checks you do. SQLite's
stated purpose for keeping the defensive ones is to make the code *"self-healing" or "ductile"
rather than being "brittle" and crashing at the first hint of unplanned behavior.*

In a language without these macros, the distinction is still worth making explicitly — a
`debug_assert!` versus a real `if` with error handling, and a comment saying which one you are
claiming.

**Fails when:** they crash production. Jepsen's review of TigerBeetle names this precisely —
an interlocking set of guards converts a correctness problem into an availability problem, because
an over-conservative assertion halts a process that could have degraded gracefully. The framing
worth carrying is TigerStyle's: *assertions downgrade catastrophic correctness bugs into liveness
bugs.* That is a good trade for a database and a bad one for a video player. Decide which you are.

---

## Reachability assertions

**Catches:** code that is never exercised in a *state* that matters — which coverage structurally
cannot tell you, because coverage is location-aware and this is situation-aware.

Coverage says the line ran. `assertSometimes(buffer.isFull())` says the buffer was *actually full*
at least once during the run. The retry path can be 100% covered while never having been entered
with `retryCount > 3`.

**Build:** Antithesis's `Sometimes` assertions are the named version, but the idea ports anywhere.
A counter, incremented at the interesting state, asserted non-zero at the end of the suite. It
**fails by default until proven** — that inversion is what makes it useful, because an unreached
state is a silent gap in every other formulation.

Good candidates: the buffer filled, a retry happened, a conflict was hit, the cache missed, the
slow path ran, the error branch returned, a partial write occurred.

**Fails when:** they are assertions about lines rather than situations, at which point you have
reinvented coverage with more effort.

---

## Regression corpus

**Catches:** bugs that have already been found once. Its value compounds in a way nothing else here
does — every bug anyone ever found stays found, so the codebase gets monotonically harder to break.

**Build:** SQLite's rule is that *"that bug is not considered fixed until new test cases that would
exhibit the bug have been added."* Run `scripts/regression_gap.py` to measure how close a
repository comes to it.

Three details decide whether this is real or performative:

- **Write the test first and watch it fail.** A test written after the fix has never been observed
  to fail, so you do not know it tests the bug. This is the single most common way the discipline
  is performed without being practiced.
- **Test at the level the bug lived.** A date-parsing bug gets a test on the parser, not an
  end-to-end test on the checkout page where it surfaced.
- **Generalize it.** Ask what *class* the bug belongs to and add the assertion or property that
  covers the class, alongside the specific test. This is the difference between a suite that
  accumulates and one that merely grows.

Mike Bland's argument for why untested fixes evaporate is the concrete one: cherry-picks, merges
and rebases can undo a fix with no signal at all. Both `goto fail` and Heartbleed were trivially
unit-testable, and the Heartbleed fix itself shipped without a test.

**Fails when:** it becomes the whole strategy. Beizer's pesticide paradox — every method you use to
find bugs leaves a residue of subtler bugs it cannot find — applies with full force to a suite made
entirely of past bugs, which is by construction backward-looking. Regression tests are a floor. And
suites that only ever grow eventually dominate the cost of change, so pruning is a recurring
practice, not a one-time cleanup.

---

# B · Correctness you did not specify

## Properties

**Catches:** the cases you did not think of, by forcing you to state what must always be true
rather than what happens for input 7.

**Build:** hand off to `/property-based-testing`, which does discovery and generation properly.
This skill's job is to decide that properties are the gap, not to duplicate that one.

**Fails when:** the property is weak enough that `return []` satisfies it, or when the generator
produces inputs whose correct behaviour is not uniquely determined — see the warning under
[differential oracles](#differential-oracles), which applies equally here.

One handoff detail that matters: when a property test finds a counterexample, **promote it to a
hard-coded example in the source.** Hypothesis's example database and its equivalents are caches —
the docs are explicit that entries are dropped on version upgrades or when the test changes. The
committed example is the regression test; the cache is a convenience.

---

## The second opinion

**Catches:** bugs that are invisible to your suite because the suite and the code share an author
and therefore share a misunderstanding. This is the layer that SQLite's four-harness structure
exists to provide, and almost no ordinary codebase has any version of it.

**Build:** the expensive version is a second suite written by someone who has read the spec and not
the implementation. The affordable versions, in rough order of cost:

- Generate tests from the specification, schema, or API description rather than from the code —
  an OpenAPI schema, a protobuf definition, a state machine diagram.
- Have the tests written against the *public interface only*, by an agent or person given the
  documentation and denied the source.
- Any [differential oracle](#differential-oracles), which gets its expected answers from somewhere
  other than your own code and is usually much cheaper than a second suite.

**Fails when:** the "second" suite is derived from the first, at which point it inherits the same
blind spots and you have paid twice for one opinion.

**Be honest about what is achievable in one sitting.** SQLite's redundancy comes from four
harnesses built by different people across two decades. One agent writing a second test file in the
same session has *literally identical* blind spots — the independence is the entire mechanism, and
it is the one part that cannot be faked. So in practice this layer is rarely the right
recommendation from inside a single session. Prefer a [differential oracle](#differential-oracles),
which gets its expected answers from something that is genuinely not you, or generate the tests
from a schema or specification artifact rather than from the code.

---

## Differential oracles

**Catches:** wrong answers that look plausible. This is the class that crashes and exceptions never
reveal, and it is the hardest class to find by any other means, because there is nothing to notice.

The evidence that this is a *separate axis* from coverage rather than a subset of it: SQLite, at
100% MC/DC, still had roughly 179 logic bugs found by Manuel Rigger's oracle-based SQLancer — cases
where it computed an incorrect answer. SQLite's own docs concede that most fuzzers "only look for
assertion faults, crashes, undefined behavior… Dr. Rigger's fuzzers, on the other hand, are able to
find cases where SQLite computes an incorrect answer." Path coverage saturates; oracle strength
does not. A codebase can be exhaustively covered and still be systematically wrong.

The move is to construct a *second* thing that must agree, so you never have to state the correct
answer. Five ways to get one, cheapest first:

**1 · Two configurations of your own system.** The cheapest real oracle most codebases can build,
and the most underused. Any pair of settings that must produce identical output is a test:

- cache on vs. cache off
- index used vs. full scan
- parallel vs. serial
- incremental recompute vs. full recompute
- optimized path vs. the naive reference path
- new implementation vs. the one it replaces, during a migration

SQLite requires identical answers with query optimizations enabled and disabled — *"the answer
simply arrives quicker with the optimizations turned on."* SQLancer's NoREC generalizes it: you do
not need a second implementation, because you can build the reference engine out of the same system
by disabling its cleverness.

**2 · A reference implementation.** SQLite's SLT runs 7.2M queries against PostgreSQL, MySQL, SQL
Server and Oracle and compares answers. The generalization: any library that does what you do, any
prior version, any obviously-correct slow version you write yourself. A 1,600-line model was worth
writing to test someone else's database — Jepsen did exactly that for TigerBeetle.

**3 · Round trips.** `decode(encode(x)) == x`, `parse(print(ast)) == ast`. Cheap, and the first
thing to reach for on anything with a serialiser.

**4 · Partition and recompose.** Split the input space with a predicate, run each part separately,
require the parts to sum to the whole. SQLancer's TLP does this with SQL's three-valued logic
(`p`, `NOT p`, `p IS NULL`). It generalizes to pagination, sharding, date-range splits, streaming
vs. batch, and per-tenant vs. global aggregation — anywhere a total is computed two ways.

**5 · Construct the input so you know one fact about the output.** SQLancer's PQS picks a row
first, then synthesises a query that *must* return it. You do not need to predict the whole
result — only one thing about it. Generalizes to search (build a document that must match), access
control (build a principal that must be denied), routing, and filtering.

**Fails when — and this is the failure mode that kills differential testing:** the two sides are
permitted to disagree legitimately, so every run produces noise and the suite gets switched off.
Csmith's whole design problem was generating C programs free of undefined behaviour, because
otherwise the comparison is meaningless.

Before building one, enumerate every source of legitimate divergence and pin it: floating-point
associativity, hash and map iteration order, locale, timezone, `NaN`, unspecified sort stability,
concurrency interleaving, timestamps, and generated IDs. Either pin them or normalise them out
before comparing. Document the divergences you decide are intentional — that document turns out to
be one of the more valuable artefacts the exercise produces.

---

# C · Correctness under duress

## Fault injection

**Catches:** everything that only breaks when the environment misbehaves. This is the largest gap
in most codebases, and the one where the ratio of bugs-found to effort is highest, because the
error paths are simultaneously the least-tested code and the code that runs when things are
already bad. The USENIX finding usually cited here is that the large majority of catastrophic
failures come from incorrect handling of *non-fatal* errors.

**Build — the generalizable version of SQLite's OOM sweep, and the single highest-leverage
recommendation in this catalog:**

You usually cannot fail `malloc` in a managed language. You can apply the identical sweep to any
resource acquisition:

```
for n in 1, 2, 3, ... :
    run the operation, failing the Nth <HTTP request | DB query | file write | lock | RPC>
    assert the invariant that must hold regardless
    stop when the operation completes without reaching injection point N
```

This is exhaustive rather than random, deterministic by construction, and implementable in an
afternoon in any language. Run the sweep twice: once failing *only* the Nth call, once failing
everything from the Nth onward. The two find different bugs — the first finds bad recovery, the
second finds retry loops that never terminate.

The mechanism underneath is a **failpoint**: a named, cheap, compiled-out-in-production annotation
that a test can arm by name and count. Rust's `fail` crate, PingCAP's `failpoint` for Go, FreeBSD's
original, and FoundationDB's `BUGGIFY` are all this idea. In a language with none of them, an
injected interface at the I/O boundary plus a counter is the whole implementation.

FoundationDB's `BUGGIFY` adds one twist worth stealing: developers annotate *their own* code with
"this is an interesting place to inject a delay," because the author knows where the dangerous
interleavings are and a black-box fuzzer does not.

**Which faults, in descending order of yield:**

1. The Nth call fails (the sweep above)
2. The Nth call is *slow* rather than failing — timeouts are less tested than errors
3. Partial success: the write returns an error but happened anyway
4. Non-transitive network partitions — A reaches B, B reaches C, A cannot reach C. Naive chaos
   tooling never produces these, and they are where consensus bugs live
5. Clock jumps, forward and backward
6. Disk: `ENOSPC`, torn writes, bit flips, corrupted regions

**Fails when:** it is random rather than systematic. Random fault injection finds the shallow bugs
and then stops; the sweep over injection points is what makes it a test rather than an anecdote.

---

## Crash and restart

**Catches:** state that is only corrupt *after* a restart, which is invisible to every in-process
test. The defining Tier 2 layer.

**Build:** kill the process mid-operation and assert it either fully committed or fully rolled
back — never something in between. SQLite does this with a child process killed mid-write, and
in-memory by snapshotting the filesystem after N operations, applying the characteristic damage a
power failure causes, and checking the result is still valid.

The practical version for an ordinary service: `SIGKILL` (not `SIGTERM` — you want no cleanup) at
each of N points during a write sequence, restart, assert the invariant.

**`SIGKILL` is not power loss, and confusing the two produces a test that passes on exactly the bug
it was written to find.** Killing a process leaves unfsynced writes sitting in the OS page cache,
and the kernel flushes them afterwards regardless. So a `kill -9` test on code that never calls
`fsync` will happily report that everything committed. It tests *process* crashes — worth having,
and genuinely different from a graceful shutdown — but it says nothing about power loss, kernel
panic, or a yanked cable.

For the real thing the writes have to be intercepted below the process: `dm-flakey` or
`dm-log-writes` at the block layer, or a FUSE layer such as LazyFS or CharybdeFS. CharybdeFS can
kill the caller on `flush` or `sync`, which is the crash-consistency test in one sentence. This
distinction holds in every language — say in the report which of the two you actually built.

**Test the recovery path under fault too.** An I/O error *while recovering from a previous crash*
is the compound case, and recovery code is the least-exercised code in the system.

**Fails when:** you use a graceful shutdown, which tests the path that was already working — or
when you use `SIGKILL` and describe the result as power-loss safety.

---

## Deterministic simulation

**Catches:** concurrency and distributed-systems bugs that are otherwise irreproducible, by making
the entire run a pure function of a seed.

**Build — the cheap 80%, which is what almost every codebase should actually do:**

- Inject the clock. Ban direct `now()`.
- Inject the RNG. Ban direct `rand()`.
- Make iteration order deterministic — Rust's `HashMap` and Go's map iteration are deliberately
  randomised, and both will wreck a differential comparison.
- **Print the seed on every failure, and the exact command to reproduce it.** Resonate's CI files
  an issue containing the seed and the reproduction command; that is the standard to aim at.

The full version — a single-threaded scheduler, all I/O through a simulator, and third-party
entropy blocked at the libc level — costs an architecture. FoundationDB built and debugged the
simulator for years before writing the database. `madsim` overrides `getrandom` and `clock_gettime`
precisely because dependencies leak entropy that your own discipline cannot reach.

**Test liveness, not just safety.** A simulator that only injects transient faults cannot catch
"the cluster is permanently wedged," because the faults heal and the deadlock breaks undetected.
TigerBeetle's fix is a second phase where a quorum is made *permanently* healthy and all other
faults are frozen — only then can you assert that progress must happen.

**Fails when:** the mocks are dishonest. You have tested your system against your *beliefs* about
how the network and disk fail. Phil Eaton's caveats are the honest list: the edges stay untested,
tuning the workload generator to produce interesting behaviour is hard and labour-intensive, and
seeds stop reproducing as soon as the code changes.

**Verification trick:** run the same seed twice and diff trace-level logs byte for byte. If they
differ, your simulation is not deterministic and every result from it is suspect.

---

## Adversarial corpus

**Catches:** what happens when input is hostile rather than merely wrong. Earned the moment input
crosses a trust boundary, regardless of the code's other tier.

**Build:** a directory of malformed inputs, committed, replayed by an ordinary test. For each,
assert a *specific* error — not merely "did not crash." Truncated at every offset. Wrong magic
bytes. Valid header with corrupt body. Deeply nested structures. Enormous declared lengths with no
data behind them. Correct structure with impossible values. The empty input. One byte.

SQLite corrupts database files three ways deliberately: content bytes, unused bytes, and the
structural header bytes — and requires `SQLITE_CORRUPT` back with no buffer overflow and no NULL
dereference.

**Fails when:** the assertion is "no exception thrown." Swallowing a malformed input and returning
a zero-value struct is usually worse than crashing, and that test passes.

---

## Fuzzing

**Catches:** inputs no human would write. Earned at Tier 3, and rarely below it.

**Build:** the corpus is the valuable artefact, not the fuzzer. Split the work in two:

- **Corpus replay** — run the target over every committed input on every CI run. Fast,
  deterministic, no engine, no flake. This is a regression suite that happens to have been
  discovered by a fuzzer.
- **Actual fuzzing** — a long-running job, not a PR gate.

Every crash becomes a permanent corpus entry, named for the issue that fixed it. Go's toolchain
bakes this in: failing inputs are written to `testdata/fuzz/` and replayed as ordinary unit tests
on every `go test` afterwards. That is the discipline implemented by the tooling rather than by
willpower, and it is the model to copy in languages that do not do it for you.

**Structure-aware beats byte-level** for anything with a format. Random bit flips on a
length-prefixed or checksummed format are rejected at the first parse check, so the fuzzer never
reaches the interesting code. Mutate the parsed structure and re-serialise instead — via a typed
generator, or a custom mutator that decodes, mutates and re-encodes.

**For stateful code, fuzz the trace, not the input.** Encode a *sequence* of API calls as the
fuzzed value and replay it. This is how you fuzz a connection, a state machine, or a cache rather
than a parser, and it is the version most services need.

**Fails when:** the target only checks for crashes. A fuzz target that asserts invariants — the
round trip holds, the index agrees with the table, the sum is conserved — finds logic bugs; one
that only catches panics finds memory-safety bugs you may not even have in a managed language.
Combine with sanitizers where the language has them, so every replay is also a memory check.

**Also fails when the input space is drawn too narrowly, which is the subtler trap.** A fuzzer only
finds bugs in the space you told it existed. SQLite's Magellan RCE sat in FTS3 for years despite
continuous fuzzing, and Hipp's post-mortem is the whole lesson in one sentence: *"we never
configured a fuzzer in such a way that it might start modifying the shadow tables of FTS3, and so
we missed this one."* The structural fix was dbsqlfuzz mutating the database file and the SQL
*simultaneously*. Before trusting a fuzzing effort, write down every input the code actually reads —
including config, environment, stored state, and files it did not write — and check which ones the
fuzzer can reach. The unreached ones are where the bug is.

---

# D · Containing the damage

None of these are tests. They are changes to the code that make the failure smaller, cheaper, or
reversible when it happens anyway — and at T2 and T3 they are frequently the highest-leverage move
available. They are in this catalog because a skill that only knows how to add tests will never
propose them, and will therefore answer "this deletes customer data" with a unit test.

## Dry-run

**Catches:** nothing by itself — it moves the decision to a human before the irreversible step.

**Build:** compute the full plan, print it, act only when asked. The version that pays twice is one
where the dry-run and the real run share the *same* plan-building code, because then "the dry run's
predicted change set equals the real run's actual change set" becomes a free
[differential oracle](#differential-oracles).

**Fails when:** the dry-run path is computed separately from the real path, at which point it is a
second implementation that can be wrong on its own.

## Idempotency key

**Catches:** the duplicate. A retry on a request that actually succeeded is not an edge case — it
is what every network client, queue and load balancer does by default, and the failure is not a
wrong value but a correct value applied twice. Coverage reads 100% throughout.

**Build:** derive the key from the *request*, not from its contents. A key built from
`(customer, amount, day)` collapses two legitimate identical charges into one; `(customer, request_id)`
does not. Store it with the effect, in the same transaction.

**Fails when:** the key is derived from data that can legitimately repeat.

## Blast-radius cap

**Catches:** the unbounded version of an operation that is fine when bounded. Deleting one stale
record is routine; deleting all of them because an upstream query returned empty is an incident.

**Build:** refuse to act on more than N items, or more than some fraction of the total, without an
explicit override flag. Cheap, and it converts an irreversible surprise into a message.

**Fails when:** the cap is set above any plausible real batch, so it never fires.

## Kill switch

**Catches:** the time between noticing and being able to deploy. Worth its weight whenever the
**fan-out** modifier applies, because a config change takes effect everywhere at once and a deploy
does not.

## Audit log and undo

**Catches:** everything you did not anticipate. A soft delete with a retention window converts a T3
operation into a T1 one — which is the [demotion](#the-escalation-ladder) move in its purest form,
and usually cheaper than any test that would have prevented the deletion.

## Typed config at boot

**Catches:** the 3am discovery that a value was a string, missing, or pointing at the wrong
environment. Parse configuration and secrets into a typed structure at startup and refuse to start
if it does not validate.

**Worth special attention for anything that reads a target from the environment.** A `reset-db`
script that honours `DATABASE_URL` is one shell export away from dropping production. The tier of a
tool is the tier of the most dangerous environment it can reach, not the one it is usually pointed
at.

## Version-skew tests

**Catches:** the rolling-deploy window, which no other layer in this catalog covers. During any
rolling deploy, old and new binaries read and write the same store concurrently. Neither coverage
nor crash tests nor fuzzing finds *new writes a field, old reads it and rewrites the record without
it*.

**Build:** run the previous release's test suite against the new schema, and the new release's
suite against the old one. Both must pass. For a stored format, keep a corpus of records written by
every version still in the field and assert every version can read all of them.

---

# E · Finding out in production

Tests tell you the code was right when you wrote it. These tell you the data is right *now*, and
they are the layer most likely to be missing entirely: silent corruption is usually found by a
sweeper or by a customer, essentially never by a test. SQLite ships `PRAGMA integrity_check` for
exactly this reason — it is easy to take the harnesses from the source material and leave the
checker behind.

## Invariant sweeper

**Catches:** violations that have already happened, including ones caused by bugs you have since
fixed, by manual intervention, or by a component you do not own.

**Build:** take the invariants your assertions already state and run them over real data on a
schedule. Balances sum to zero. Every child row has a parent. No record is in two terminal states.
Counts in the index match counts in the table. Alert on a violation; do not auto-repair, because a
repair without a diagnosis destroys the evidence.

**Fails when:** it only checks rows written recently, so a historical corruption stays invisible.

## Stored checksums

**Catches:** corruption at the moment of read, rather than letting it propagate into everything
computed downstream.

**Build:** store a checksum with the record and verify on read. The point is turning a silent wrong
answer into a loud error — a T2 failure into a T1 one.

## Reconciliation

**Catches:** divergence between two things that must agree, using production data as the input.
This is a [differential oracle](#differential-oracles) pointed at live state instead of at test
input, and it is usually the single most valuable thing on this page for anything holding money or
counts.

**Build:** compute the same quantity two independent ways and compare. The ledger's sum against the
account balance. The search index against the source table. The cache against the origin. Run it
continuously and alert on drift.

## Restore drill

**Catches:** the backup that has never been restored, which is not a backup. Also the recovery
runbook nobody has executed, and the credentials that expired.

**Build:** restore to a scratch environment on a schedule and assert the restored data passes the
invariant sweeper. Time it, because recovery time is usually the number nobody knows.

---

# F · Auditing the suite

## Coverage

**Catches:** code you have never executed. That is genuinely useful, and it is the entire honest
claim. Fowler's two sentences are the whole of it: *"Test coverage is a useful tool for finding
untested parts of a codebase"* and *"Test coverage is of little use as a numeric statement of how
good your tests are."*

**Build:** branch coverage, not line. For `if (a > b && c != 25)`, statement coverage needs one
test and branch coverage needs three. Then **read the uncovered list and ask why each entry is
uncovered** — that is where the value is. The number is a byproduct.

**Check what your tool actually measures before quoting its number.** "Branch coverage" is not a
portable term and several toolchains report a flattering figure: Go has none at all (`go test
-cover` is statement coverage, so `if a && b` is one counter); Node's built-in flag and `c8` report
V8 block coverage, which counts an implicit `else` as covered; Rust's is nightly-only; JaCoCo
inflates Kotlin counts with synthetic null-checks. See `toolchain.md` for the per-language detail.
Never compare the percentage across languages.

**The mechanism is indirect, and knowing that changes how you use it.** Hipp's account of why 100%
MC/DC paid off is not that every branch got tested. It is that *"the weird tests you end up having
to write just to cause some obscure branch to go one way or another end up finding problems in
totally unrelated parts of the system."* Coverage works as a forcing function — it makes you
construct strange inputs, and the strange inputs find bugs elsewhere. Which means chasing the
number via trivial tests destroys the entire benefit while appearing to deliver it.

He is equally clear that the specific number is arbitrary: *"100% MC/DC is just an arbitrary
threshold — a high threshold and one that is easy to measure and difficult to cheat — but it is
just a threshold at which we say 'enough'."* The transferable criterion is not "100%" but **pick a
bar that is cheap to measure and hard to cheat**, then treat it as a prompt to think rather than a
score to move.

Measure **coverage on the diff**, not on the repository. "Is the code I just changed tested?" is
answerable and actionable; "is the repo at 80%?" is neither.

**Fails when:** it becomes a target. High coverage is trivially reachable with tests that assert
nothing — a test that calls a function and checks nothing scores identically to one that verifies
every postcondition. Google's own guidance stresses there is no universal ideal number and warns
against copy-pasted tests written to move it. Gains are logarithmic: moving 30% → 70% matters,
90% → 95% generally does not.

Never delete a defensive check to raise a coverage number. Mark it instead, the way SQLite's
`ALWAYS`/`NEVER` macros do — pass through in release, assert in debug, become constants when
measuring — so the branch stays in the binary and stops distorting the metric.

---

## Mutation testing

**Catches:** tests that execute code without checking it. This is the question coverage only
appears to answer.

Coverage asks *did this line run?* Mutation testing asks *would any test have failed if this line
were wrong?* Only the second is the question you care about. cargo-mutants puts the gap concretely:
a function that writes a file and returns a `Result` can be fully covered by a test that checks the
return value and never checks that the file was written.

**Build:** change the code in small ways — flip a comparison, swap a boundary, drop a statement,
replace a return value — and require that some test fails. Survivors are the output: a direct,
reviewable list of changes your suite does not notice, which is far more actionable than a coverage
report.

Deliver survivors as review comments on the diff rather than as a score to hit, which is how Google
runs it at scale. Run it on the module you are proudest of; that is where the surprise is.

**Fails when:** it is run repo-wide as a gate. It executes the suite once per mutant, so it is slow,
and equivalent mutants — changes that genuinely cannot alter behaviour — produce unavoidable false
positives. SQLite marks pure-optimization branches `/*OPTIMIZATION-IF-TRUE*/` for exactly this
reason. The cheap high-signal variant is "extreme" mutation: replace whole function bodies and find
*pseudo-tested* methods, where any return value passes.

---

## Determinism

**Catches:** undefined behaviour, uninitialised reads, order dependence, and genuine compiler bugs
— via one idea applied repeatedly: *two runs that must agree, and a disagreement is a bug.*

**Build:** find pairs of runs that must produce identical output and diff them.

- Instrumented build vs. normal build. SQLite requires the coverage run and the real run to match;
  *"any differences in output indicate either the use of undefined or indeterminate behavior in the
  SQLite code (and hence a bug), or a bug in the compiler."* They have found bugs in GCC, Clang and
  MSVC this way.
- The same seed, twice.
- Different platform, word size, or endianness.
- The same test, run 100 times.

**Treat a flaky test as a real bug until proven otherwise.** The default reaction — retry it, mark
it flaky, move on — discards a signal that something in the system is genuinely order-dependent or
timing-dependent. It is frequently a production bug that happens to have been caught in CI first.

**Fails when:** the harness itself is nondeterministic, so you chase ghosts. Pin the sources of
divergence listed under [differential oracles](#differential-oracles) before trusting any result.

---

## The human checklist

**Catches:** what no assertion expresses. SQLite runs 200+ manual items per release, explicitly
inspired by *The Checklist Manifesto*, and refuses to automate them:

> "It is important to keep a human in the loop. Sometimes problems are found while running a
> checklist item even though the test itself passed. It is important to have a human reviewing the
> test output at the highest level, and constantly asking 'Is this really right?'"

**Build:** one item per class of problem you have actually had. It grows when something escapes and
gets pruned when an item has not earned its place in a year. The list is a record of what has gone
wrong before, which makes it the cheapest institutional memory available.

**Fails when:** it is long enough to be performed without attention, at which point it costs time
and catches nothing.
