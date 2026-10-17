# The primary source, condensed

[How SQLite Is Tested](https://www.sqlite.org/testing.html), reduced to the parts that carry
reasoning rather than SQLite-specific mechanics. Read this when a recommendation needs justifying,
when someone pushes back on why a layer matters, or when you want the original argument instead of
this skill's generalisation of it.

Contents: [Scale](#scale) · [Why it actually paid off](#why-it-actually-paid-off) ·
[Why four harnesses](#why-four-harnesses) · [Coverage](#coverage) ·
[Anomaly testing](#anomaly-testing) · [Fuzzing](#fuzzing) · [The tension](#the-tension) ·
[Regression rule](#the-regression-rule) · [Determinism](#determinism-as-a-bug-detector) ·
[Test what you fly](#test-what-you-fly) ·
[Assertions](#assertions) · [Humans](#the-human-in-the-loop) · [Proportionality](#proportionality) ·
[What did not work](#what-did-not-work) · [Honest limits](#honest-limits)

---

## Scale

155.8 KSLOC of library code. 92,053.1 KSLOC of test code. A ratio of roughly **590:1**.

Quote these numbers to establish that SQLite is an outlier, not a model to copy wholesale. The
interesting question is never "how do we get to 590:1" — it is "which of the things they bought
with that effort would pay for themselves here."

One number that cuts the other way, and is worth knowing before anyone objects on speed: the
minimum set of tests giving 100% branch coverage runs in about **three minutes**. The exhaustive
cross-platform sweep takes days, but the rigorous suite is not the slow suite. Thoroughness and
fast feedback were not traded against each other here.

---

## Why it actually paid off

The reason SQLite reached 100% MC/DC is a failed business plan. Hipp had been consulting for
Rockwell Collins, learned DO-178B, and spent roughly ten months (2008-09-25 to 2009-07-25) building
TH3 intending to sell it to avionics manufacturers. Nobody ever bought it.

What he reports as the actual return is not defect count:

> "That plan didn't work out — I've never sold the tests to any aviation manufacturer; not one. But
> the TH3 test harness has had side benefits that I did not anticipate, not the least of which is
> that it allows us to maintain a complex code base that is run on billions of devices with just a
> few developers."

> "Another big advantage of 100% MC/DC is that once they are in place, you can change anything,
> anywhere in the code, and if the tests all still pass, you have high confidence that you didn't
> break anything. This enables us to evolve the SQLite code much faster than we could otherwise,
> using relatively few eyeballs."

**This is the most transferable framing in the whole corpus.** The justification that held up was
maintainability leverage for a small team, and it was an unanticipated side effect of an effort
undertaken for a different reason entirely. It is also the reason to weight recommendations toward
code that is actively changing.

Two second-order effects worth knowing, because they explain *how* coverage works rather than
asserting that it does:

**It is a forcing function, and the benefit is indirect.**

> "My experience is that the weird tests you end up having to write just to cause some obscure
> branch to go one way or another end up finding problems in totally unrelated parts of the system.
> One of the chief benefits of 100% MC/DC is not so much that every branch is tested, but rather
> that you have to write so many tests, and such strange, weird, convoluted, and stressful tests,
> that you randomly stumble across (and fix) lots of problems you would have never thought about
> otherwise."

The corollary matters for anyone tempted to chase the number: trivial tests written to move the
percentage destroy the entire mechanism while appearing to deliver it.

**It removes cruft.** The coverage requirement forces unreachable code either to be deleted or
converted into an assertion, so the codebase cannot accumulate branches nobody can justify.

---

## Why four harnesses

SQLite maintains four independently designed and separately maintained test harnesses:

| Harness | What it is | Scale |
|---|---|---|
| **TCL tests** | The original suite, used during development | 51,445 test cases, 1,390 files |
| **TH3** | Proprietary; exists to reach 100% branch and MC/DC coverage on embedded targets | 50,362 cases, ~2.4M instances per coverage run; 248.5M instances in the pre-release soak |
| **SLT** | SQL Logic Test — runs the same queries against PostgreSQL, MySQL, SQL Server and Oracle and compares answers | 7.2M queries, 1.12 GB |
| **dbsqlfuzz** | Structure-aware fuzzer that mutates the SQL *and* the database file at once | ~500M cases/day across 16 cores |

**The transferable point is the independence, not the count.** TH3 uses only published interfaces
and was written separately from the TCL suite; SLT derives its expected answers from four other
database engines rather than from SQLite's own behaviour. Each harness was built by a different
process, so each fails to imagine different things.

A single suite — however large — encodes one team's model of what could go wrong, and its gaps are
exactly the bugs that reach production. The cheap version of this idea for an ordinary codebase is
a second set of tests derived from the specification by someone who has not read the
implementation, or a differential oracle that gets its expected answers from somewhere other than
your own code.

---

## Coverage

SQLite requires **100% branch coverage** and **100% MC/DC**, measured with `gcov`.

Branch, not statement. Given `if( a>b && c!=25 ){ d++; }`:
- statement coverage needs **one** test
- branch coverage needs **three**: `a<=b`, `a>b && c==25`, `a>b && c!=25`

MC/DC additionally requires that each condition independently affect the outcome — so every
sub-condition must be shown to matter on its own, not just as part of a combination.

**Mutation testing is how they check the coverage is honest.** SQLite compiles to assembly,
changes each branch instruction to an unconditional jump or a no-op, and requires that some test
notices. Branches that legitimately do not affect output — pure optimisations — are marked
`/*OPTIMIZATION-IF-TRUE*/` so the false positives can be filtered rather than papered over.

> "Because every single branch instruction in SQLite core code is covered by test cases, the
> developers can be confident that changes made in one part of the code do not have unintended
> consequences in other parts of the code."

That sentence is the real benefit, and it is about *change safety*, not about correctness today.

---

## Anomaly testing

The largest transferable idea on the page, and the one most codebases have nothing of. SQLite
tests systematically for failures of the machine rather than failures of the logic.

**Out-of-memory.** A pluggable allocator is instrumented to fail on the Nth allocation. Run the
operation, fail at N=1, increment, repeat until the operation completes without hitting the
injection point. Both "fail once" and "fail from now on" modes.

> "On embedded devices, OOM errors are frighteningly common and since SQLite is frequently used on
> embedded devices, it is important that SQLite be able to gracefully handle OOM errors."

**I/O errors.** The same sweep, through a custom VFS that fails the Nth I/O operation — simulating
full disks, network outages, permission changes. After each run, injection is disabled and
`PRAGMA integrity_check` must pass.

**Crashes and power loss.** A child process is killed mid-write and the parent verifies the
database either fully committed or fully rolled back — never something in between. TH3 does it
in-memory: snapshot the filesystem after N operations, apply the characteristic damage a power
failure causes, verify the database is still valid and the transaction was atomic, repeat with
different random damage.

**Compound failures.** An I/O error *while recovering from a previous crash*. Real incidents are
rarely one failure at a time, and recovery paths are the least-tested code in most systems while
being the code that runs when things are already bad.

The generalisable pattern in all four: **pick a failure the environment can produce, make it
happen deterministically at every point it could happen, and assert the invariant that must hold
regardless.** The sweep over injection points is what makes it a test rather than an anecdote.

---

## Fuzzing

- **dbsqlfuzz** mutates two inputs simultaneously — the SQL text and the database file. Fuzzing
  one input at a time misses bugs that need both to be strange at once.
- **Fuzzcheck** keeps every historically interesting case any fuzzer ever produced — thousands,
  distilled from billions examined — and reruns them under `make test`. "Interesting" means it
  showed previously unseen behaviour or was a real bug.
- **OSS-Fuzz** runs continuously on Google infrastructure against every check-in.

> "Since dbsqlfuzz has been added to the SQLite internal test suite, bug reports from external
> fuzzers such as OSSFuzz have all but stopped."

That outcome is the argument for the permanent corpus. A fuzzer with no corpus rediscovers the same
shallow bugs forever; a fuzzer whose corpus accumulates gets steadily deeper, and the corpus itself
becomes the most valuable artefact the effort produces.

Malformed-database testing is separate and deliberate: bytes are corrupted in the content, in
unused space, and in the structural headers, and SQLite must return `SQLITE_CORRUPT` without
overflowing a buffer or dereferencing NULL.

---

## The tension

Stated outright on the page, and worth carrying because it is a trade most teams make
accidentally:

> "Fuzz testing and 100% MC/DC testing are in tension with one another."

MC/DC pressure pushes you to *remove* defensive code, because an unreachable branch is a branch you
cannot cover. Fuzzing pressure pushes you to *add* it, because hostile input will find the case you
thought was impossible.

SQLite's resolution is `ALWAYS(X)` and `NEVER(X)`: macros that pass through in release builds,
assert in debug builds, and become the constants `1` and `0` when measuring coverage. The suite is
run three times, once under each definition, and all three must agree. The branch stays in the
binary and stops distorting the metric.

SQLite has since shifted emphasis — it still holds 100% MC/DC on core code, but *"most testing CPU
cycles are now devoted to fuzzing."* The lesson is not that coverage was a mistake; it is that the
right allocation changed as the threat model changed.

---

## The regression rule

> "Whenever a bug is reported against SQLite, that bug is not considered fixed until new test cases
> that would exhibit the bug have been added to either the TCL or TH3 test suites."

The cheapest high-value policy on the whole page, and the easiest to audit after the fact —
`scripts/regression_gap.py` measures how close a repository comes to it.

Its value compounds in a way nothing else here does: every bug anyone ever found stays found. A
codebase with this rule gets monotonically harder to break; one without it re-breaks the same
things on a multi-year cycle.

---

## Determinism as a bug detector

Three separate applications of one idea — *two runs that must agree, and a disagreement is a bug*:

- **Coverage run vs. normal run.** Output must be identical. *"Any differences in output indicate
  either the use of undefined or indeterminate behavior in the SQLite code (and hence a bug), or a
  bug in the compiler."* SQLite has found bugs in GCC, Clang and MSVC this way.
- **Optimisations on vs. off.** `SQLITE_TESTCTRL_OPTIMIZATIONS` disables query optimisations at
  runtime; the full suite runs both ways and must produce identical answers. *"SQLite should always
  generate exactly the same answer with optimizations enabled and with optimizations disabled; the
  answer simply arrives quicker."*
- **Portability sweeps.** 32-bit and 64-bit, big- and little-endian, signed and unsigned `char`,
  `-ftrapv`, `-fsanitize=undefined`.

The second one generalises further than it first appears, and is the cheapest differential oracle
most codebases can build: *any* pair of configurations that must agree is a test. Cache on versus
cache off. Parallel versus serial. Fast path versus reference path. The new implementation versus
the one it replaces. You need no external oracle, because the system is its own.

---

## Test what you fly

SQLite runs its suite three times per release, in three different build configurations, and all
three must agree. Hipp's statement of it:

> "'Test what you fly and fly what you test' is what we live by at SQLite. Testing is done three
> times:
> (1) One test uses compiler and preprocessor options set up to measure coverage. This is not so
> much a test of SQLite itself as it is a test of the test logic, to verify that the testing
> provides 100% MC/DC.
> (2) The second test runs with assert(), ALWAYS(), and NEVER() enabled. This is like a unit test.
> It verifies internal assumptions and state, at the expense of running 3x slower.
> (3) Finally, we build as for delivery and test once again. This is the string test, where we
> 'test what we fly'.
> All three test runs must give the same answer (modulo performance) before a release."

And the rule he draws from it, which is the transferable part:

> "you should not do all your testing using one configuration and then deliver a different build.
> But that does not mean you can't have extra logic in your code that helps do unit testing and
> debugging during development and which is excluded from release builds. You just need to make
> sure that you rerun all tests in the release configuration."

Nearly every codebase violates this without noticing: the suite runs with debug assertions on, test
doubles wired in, and a development config, guarding a binary that has none of those. The fix is
not to remove the debug-only logic — it is to run the suite once more against what actually ships.

This is arguably more transferable than MC/DC itself, since it costs one CI job and applies to
every language.

---

## Assertions

**6,754 `assert()` statements** check preconditions, postconditions and loop invariants. They cost
about 3× runtime, so they are compiled out unless `SQLITE_DEBUG` is set.

Assertions catch a class nothing else does: an invariant violated *at the moment it happens*,
rather than as a confusing symptom several layers away. They also serve as executable documentation
of what the code believes — which is why they are worth writing even in a codebase with few tests.

Mutex assertions (`sqlite3_mutex_held()`, `sqlite3_mutex_notheld()`) apply the same idea to
threading invariants, which are otherwise close to untestable.

---

## The human in the loop

A release checklist of **200+ manual items**, explicitly inspired by *The Checklist Manifesto*,
ranging from seconds to hours each. Deliberately not automated:

> "It is important to keep a human in the loop. Sometimes problems are found while running a
> checklist item even though the test itself passed. It is important to have a human reviewing the
> test output at the highest level, and constantly asking 'Is this really right?'"

The checklist grows; every newly discovered class of problem adds an item.

---

## Proportionality

The quote that should govern every recommendation this skill makes:

> "Maintaining 100% MC/DC is laborious and time-consuming. The level of effort needed to maintain
> full-coverage testing is probably not cost effective for a typical application. However, we think
> that full-coverage testing is justified for a very widely deployed infrastructure library like
> SQLite, and especially for a database library which by its very nature 'remembers' past mistakes."

Two justifications, both about blast radius, neither about code quality in the abstract: **very
widely deployed** (you cannot recall the mistake) and **remembers past mistakes** (the mistake
outlives the run). Those are the two axes the tier table in `SKILL.md` is built from.

Hipp goes further elsewhere and names a precondition that is about the team rather than the code:

> "if your developers are passionate about long term maintainability, then having 100% MC/DC
> testing is a big big win. But if your developers are not interested in maintainability, then
> forcing a 100% MC/DC requirement on them does not help and could make things worse."

The practice is downstream of a value. Imposed as a mandate on a team that does not hold that
value, he predicts it backfires — which is a useful thing to say out loud when someone asks for a
coverage gate.

---

## What did not work

Worth knowing so the skill does not recommend it reflexively:

> "Static analysis has not been helpful in finding bugs in SQLite. Static analysis has found a few
> bugs in SQLite, but those are the exceptions. More bugs have been introduced into SQLite while
> trying to get it to compile without warnings than have been found by static analysis."

This is a finding about *mature, heavily tested C*, not a general claim — static analysis and type
checking earn their keep in most codebases, and in memory-unsafe languages sanitizers remain
essential. But it is a useful corrective to the assumption that adding another linter is progress.

---

## Honest limits

This page is a primary source written by the project about itself. Four caveats worth carrying, so
the skill argues from evidence rather than reputation.

**Coverage saturates; oracle strength does not.** SQLite sat at 100% MC/DC and Manuel Rigger's
SQLancer still found on the order of 179 logic bugs in it — cases where it returned a wrong answer.
SQLite's own docs concede the point: most fuzzers "only look for assertion faults, crashes,
undefined behavior… Dr. Rigger's fuzzers, on the other hand, are able to find cases where SQLite
computes an incorrect answer." Path coverage and oracle quality are *orthogonal axes*. SQLite was
exceptional on the first and had to have the second supplied by an outsider. A codebase can be
exhaustively covered and systematically wrong.

**The metric is partly constructed by the people it evaluates.** Reaching "100% MC/DC" is not a
fully automated measurement: `testcase()` and `ALWAYS`/`NEVER` are hand-placed macros, and where a
developer puts them shapes the denominator. Hipp's defence — that the threshold is "easy to measure
and difficult to cheat" — holds relative to line coverage, not absolutely. Treat any coverage
figure, including SQLite's, as a claim about process rather than a measurement of correctness.

**The scale may itself be a liability.** Pekka Enberg, who is rewriting SQLite in Rust, put the
objection directly: "SQLite's verification is legendary! I am unsure if 92 million lines of closed
source code for the test suite is a good long term strategy, though." Two problems bundled there —
a test corpus 590× the size of the code is a maintenance burden in its own right, and TH3 is
proprietary, so the artefact that makes SQLite trustworthy cannot be audited by the people relying
on it. The modern counter-bet is deterministic simulation testing, which trades an enormous
enumerated corpus for a seeded generator. Both bets are live; this skill treats them as
complementary layers rather than rivals.

**The aviation association is weaker than usually implied.** SQLite is *inspired by* DO-178B, not
compliant with it — Hipp: "The SQLite project is not 100% DO-178B compliant. We have gotten slack
on some of the more mundane paperwork aspects." And the frequently cited Airbus A350 deployment is
maintenance logging, not safety-of-flight: "I don't think it's in safety-critical applications. I
think they use it to log maintenance activities." Do not lean on "aviation-grade" as an argument;
lean on the mechanisms, which stand on their own.
