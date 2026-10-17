---
name: harden
description: >
  Decide what grade of testing a piece of code has actually earned, then prove one missing layer by
  writing it, running it, and showing it fail. Applies SQLite's testing methodology — tiering by how
  far a mistake travels before anyone notices, fault injection, differential oracles, adversarial
  corpora and a permanent regression corpus — to any codebase in any language. Use when asked to
  harden code, assess a test strategy, decide what to test next, work out why a bug escaped, or test
  something the way SQLite is tested.
argument-hint: "[path or operation to assess — a package, a command, a module]"
disable-model-invocation: true
---

# Harden

SQLite ships roughly 590 lines of test code per line of library code, across four separately
designed harnesses. Copying that ratio is almost always the wrong lesson to draw. What transfers is
the reasoning that produced it.

**Three ideas do the work here.**

*A mistake's cost is how far it travels before anyone notices.* SQLite justifies its rigour partly
on the grounds that it is "a database library which by its very nature 'remembers' past mistakes."
A wrong answer you see is an inconvenience. A wrong answer nothing notices gets recorded, and
everything downstream inherits it.

*A test suite inherits the blind spots of whoever wrote it.* SQLite maintains four harnesses instead
of one big one because they were designed independently, so they fail to think of different things.
Most codebases have one harness and therefore one set of blind spots — and the bugs that reach
production live precisely there.

*What you are actually buying is the freedom to change the code.* Hipp's retrospective on the ten
months he spent reaching 100% MC/DC does not lead with defect counts. It leads with this: *"you can
change anything, anywhere in the code, and if the tests all still pass, you have high confidence
that you didn't break anything."* Test layers are insurance against *future* edits, so code nobody
touches collects less on that policy than its risk profile alone suggests.

## The posture

Hipp is explicit that SQLite's effort level does not generalise: *"The level of effort needed to
maintain full-coverage testing is probably not cost effective for a typical application."* And he
names the precondition — *"if your developers are passionate about long term maintainability, then
having 100% MC/DC testing is a big big win. But if your developers are not interested in
maintainability, then forcing a 100% MC/DC requirement on them does not help and could make things
worse."*

So the failure mode to design against is not missing a layer. It is producing a wall of plausible
recommendations that a team learns to ignore. **"Nothing here is earned" is a valid, complete,
successful result** — it is a named terminal verdict of this skill, not a failure to find work.

## Workflow

```
- [ ] Step 1  Tier the operation, then apply every modifier explicitly
- [ ] Step 2  Inventory what already exists (run things; do not assume)
- [ ] Step 3  Hunt — probe every hazard that fired, and report every failure you reproduce
- [ ] Step 4  Demote what you can — propose the diff, do not apply it
- [ ] Step 5  Build exactly one layer, proven by a red run
- [ ] Step 6  Report, including what you rejected and what to hand off
```

---

## Step 1 — Tier the operation, then apply the modifiers


**Tier the operation, not the repository.** Any CLI with subcommands, any service with endpoints,
has several tiers inside it. `./sync.py status` prints a table; `./sync.py` prunes symlinks in your home
directory. Forcing one tier onto both either over-hardens the printer or under-hardens the deleter.
Name the entry point or the operation you are assessing. If the target spans several, say so and
break it down.

### The tier: how far does a mistake travel before anyone notices?

| Tier | Who finds out, and how long after | Typical |
|---|---|---|
| **T0 Contained** | You, immediately. The remedy is to run it again. Nothing downstream recorded it. | build scripts, formatters, local dev tooling, one-off reports |
| **T1 Correctable** | A user, within hours or days. They complain, and the data can be fixed. | most application logic, request handlers, internal services |
| **T2 Compounding** | Nobody. The wrong value is recorded — by you, or by a caller you handed it to — and every later read inherits it. | serialisers, schemas, migrations, caches treated as authoritative, ID and key derivation, anything that feeds a store |
| **T3 Unrecallable** | Nobody, or too late. It has left your control: money moved, mail sent, rows dropped, or the binary is on machines you cannot reach. | payment and ledger operations, deletion paths, outbound messaging, published libraries, firmware |

Two rules that decide most hard cases:

- **Pure code can be high tier.** The axis is where the mistake *ends up*, not whether this function
  holds state. An ID or idempotency-key derivation is stateless and T2 — a key derived from
  `(customer, amount, day)` rather than `(customer, amount, request)` collapses two legitimate
  charges into one, and every store that recorded it is now wrong forever.
- **Read-only code inherits the tier of what people do with its output.** An invoice renderer is T0
  until the invoice is emailed, and T3 afterwards, because you cannot un-send it.

### The modifiers: orthogonal, and each earns its own layers

These are *not* higher tiers, and they are not cumulative with the tier. Each attaches a specific,
different set of layers, because each is a different hazard. A T1 handler that takes untrusted input
earns a corpus and nothing else from this table.

| Modifier | Trigger | What it specifically earns |
|---|---|---|
| **Untrusted** | input comes from somewhere you do not control — a user, a file you did not write, another team's API, an auto-updating tool's output | malformed-input corpus; shape validation that fails closed; fuzzing; sanitizers in memory-unsafe languages |
| **Irreversible** | the operation moves money, deletes, sends, or actuates | dry-run mode; idempotency key; blast-radius cap; kill switch; audit log or undo |
| **Concurrent** | more than one writer, a retry path, or shared mutable state | interleaving tests; idempotency under redelivery; deterministic seeded simulation |
| **Implements durability** | you are writing the commit, flush or recovery logic *yourself* | crash and restart; fault injection at the write boundary; torn-write tests |
| **Fan-out** | takes effect everywhere at once with no staged rollout, or ships to machines you cannot patch | staged rollout; version-skew tests (N-1 code against N schema); old-version corpus replay |

**The `implements durability` modifier is the one that keeps this skill honest.** Code that *calls*
`db.Save(order)` does not earn crash-consistency testing — Postgres's torn-write behaviour was
tested by people who are not you. Code that *implements* a durability guarantee does. Without this
distinction, "writes state that outlives the process" swallows every handler in every service, and
the skill becomes the wall.

**Go through the table one row at a time and record a yes or no for each, with a reason.** A
modifier never considered is a hazard never probed. In this skill's own evaluation, `Concurrent`
should plainly have fired on a tool whose every command does read-modify-write on a single shared
file — two processes, one catalog — and it was silently skipped. The concurrency bug that turned out
to matter most was then found by the run working with no modifier table at all. Silence is the
failure mode here, so put the roll-call in the report where its absence is visible.

**Weight by rate of change.** These layers are insurance against future edits, so a module untouched
in two years collects less than one being actively rewritten.
`git log --format=%ad --date=short -- <path> | head -20` answers it in a second. A hot T1 module can
easily deserve more attention than a frozen T2 one.

---

## Step 2 — Inventory what already exists


Assumptions about a test suite are usually flattering. Run things.

```bash
# What claims to be a test?
find . -path ./node_modules -prune -o \( -name '*_test.go' -o -name '*.test.*' \
  -o -name '*.spec.*' -o -name 'test_*.py' -o -name '*_test.py' \) -print | head -50

# Does the suite actually pass, and how fast?
<the project's test command>

# Which bugs were fixed without a test? (SQLite's regression rule, measured)
python3 scripts/regression_gap.py <repo>
```

`scripts/regression_gap.py` finds commits that look like bug fixes and reports which shipped without
touching a test, plus the files that recur in that list. Those files are the highest-value targets
in the repository: someone already paid to discover each of those bugs, and nothing stops them
coming back.

**When history is a bad oracle, say so rather than scoring zero.** Solo repos and squash-merge teams
amend fixes into the feature commit that introduced them, so `regression_gap.py` can report nothing
because nothing was ever labelled a fix — which reads as "this code has never had a bug." Check
whether the repo has *any* `fix:` commits before treating a zero as evidence.

Then map what you found onto the ladder. Each group catches a class the others structurally cannot.
Count what exists, including things that are not tests — a `--dry-run` flag and a `status`
subcommand are a real assurance layer, and an inventory that scores them as "nothing present" is
wrong.

**A** · Correctness you specified — example tests at the boundary; assertions on invariants;
reachability assertions; a regression test per fixed bug.

**B** · Correctness you did not specify — properties and invariants; differential oracles.

**C** · Correctness under duress — fault injection; crash and restart; deterministic simulation;
adversarial corpus; fuzzing.

**D** · Containing the damage — dry-run; idempotency; blast-radius cap; kill switch; audit and undo;
typed config at boot; version-skew tests.

**E** · Finding out in production — invariant sweeper; stored checksums; reconciliation job; restore
drill. SQLite ships `PRAGMA integrity_check` for exactly this reason. Corruption is usually found by
a sweeper or a customer, never by a test, and a skill that only proposes tests will never suggest
the thing that would actually have caught it.

**F** · Auditing the suite — branch coverage as a probe; mutation testing; run-to-run determinism; a
human checklist.

Most real codebases have a thick A, a thin B, and nothing in C, D, E or F. That shape is the finding.

`references/techniques.md` describes each layer — what it catches that nothing else does, how to
build it, and how it fails. `references/toolchain.md` maps every layer to concrete tooling per
language. Read the relevant entries before proposing anything, so the recommendation names real
tools and real invocations.

---

## Step 3 — Hunt

This is the step that decides whether the report is worth reading, and the easiest one to skip.
The tier and the modifiers are a **search plan, not a conclusion**. Each modifier that fired names
a hazard, and each hazard deserves a genuine attempt to produce a failure *before* you commit to a
single layer.

Skipping breadth here has a measured cost. In this skill's own evaluation, a run that tiered
correctly and went straight to one hazard found one real bug. An unstructured run over the same
repository found five — including the worst of them: two concurrent processes doing
read-modify-write on one file, silently losing entries in 9 of 30 trials. The narrow run missed it
because it had already chosen its layer and stopped looking.

So for every modifier that fired, spend a real attempt trying to break the code.

| Modifier | The cheapest probe that actually produces failures |
|---|---|
| **Untrusted** | feed it shapes nobody writes by hand: truncated at every offset, wrong types, the empty input, valid header with corrupt body, a renamed field |
| **Irreversible** | run the operation twice; run it against an empty or unexpected upstream answer; interrupt it midway |
| **Concurrent** | run two of it at once, in a loop, and diff the result against either one alone — thirty trials is usually enough to separate "fine" from "loses data" |
| **Implements durability** | kill it mid-write at each of N points and restart; say whether you tested process death or power loss, because they are not the same thing |
| **Fan-out** | run the previous version against the new state, and the new version against the old |

**Report every failure that reproduces**, each with the command and the file holding its output.
That list is a bug report, and it is usually the most valuable thing on the page. It is not the
backlog the one-layer rule exists to prevent — the cap in Step 5 governs what you ask someone to
*maintain forever*, not what you found along the way.

If nothing reproduces, say so plainly. That is a real result, and it is the strongest evidence
available that the honest answer is "this already has the testing it has earned."

## Step 4 — Demote what you can


Before considering any test layer, answer one question: **is there a change to the code that makes
this failure impossible, for less than the test would cost?** If yes, that is the whole
recommendation. Do not also build the test.

**Propose the change as a diff; do not apply it.** A request to assess testing is not consent to
rewrite the code, and a skill that quietly edits source while answering a question is one people
stop pointing at their repositories. The report carries the patch; the working tree stays as you
found it.

You can still prove the change works, and should. Apply it in a scratch copy — `git worktree add`,
or a copy under your scratch directory — run the failing test against it there, and show red → green
from that copy. Then hand over the diff and leave the original alone. The evidence survives; the
user decides whether to apply it.

This step exists because at T2 and T3 the highest-leverage move is usually a design change rather
than a test, and a skill that only knows how to add tests will never say so:

| Instead of testing for… | Demote it with… |
|---|---|
| a torn write | write-temp-then-rename, plus fsync on the parent directory |
| a duplicate charge on retry | an idempotency key |
| an impossible state | a type that cannot represent it — see `/analyze-illegal-states` |
| a bad config discovered at 3am | parsing config and secrets into a typed struct at boot, failing to start |
| an unbounded delete | a blast-radius cap that refuses and asks |
| a force-push to the wrong branch | `--force-with-lease` and a branch allowlist |
| a permanent deletion | a soft delete and an undo window |

**Green tests do not prove the fix is right.** A demotion that turns your red run green can still
be wrong in ways that run cannot see — a lock unreachable from one of the writers, a struct tag that
interacts badly with an existing one, a validation that also rejects something legitimate. Say what
you checked and what you did not. The diff is a proposal for a human to review, and calling it
verified because the suite went green is the same overreach as claiming an impact you only measured
one layer down.

The full ordering, cheapest and strongest first: **make it impossible → make it a compile error →
make it an assertion → make it a test.** Each rung up covers input you never enumerated. *"You do
not need a test here, you need this field to be a different type"* is one of the most valuable
things this skill can say, and it is invisible to anything that starts from the assumption that the
answer is a test.

---

## Step 5 — Build exactly one layer


> **A layer is earned by demonstrating it, not by describing it.** Write the failing test or the
> fault injection, run it against the code as it stands, and capture the output to a file you cite.
> No red run, no recommendation.

This is the whole gate, and it replaces the obvious alternative — demanding a specific,
concrete-sounding failure scenario — because that alternative does not work. Describing plausible
failures fluently is the thing a language model is best at, so a prose gate tests the wrong
faculty: it filters vagueness, not irrelevance. A red run is adjudicated by the shell instead of by
you.

If the test passes on the first run, that is a real and useful result: the code already handles that
case. Record it in the rejected list and move on.

**Three ways this gate gets defeated. Recognise them in your own output:**

- **Specificity laundering** — bolting real file names and function names onto a textbook failure
  mode. Concreteness is free once you have read the file; it is not evidence.
- **Hypothetical-tense smuggling** — "if the process were killed between these two calls…". Nothing
  in that sentence claims the failure is reachable, and it always passes a prose gate.
- **Consequence inflation** — ending every scenario with customer harm, while reasoning locally
  about one file and not noticing the transaction, retry, queue or CDN wrapped around it.

**Two cheap checks that cost more to fake than to satisfy:**

- **Name the observer.** Who finds out, and how long after? "The test we are about to write" means
  theater. "The customer, within five minutes, and they retry" means T1 and cheap. "Nobody, until
  the Q4 audit" is the expensive case, and the one worth buying.
- **Check the history.** Has a bug of this class ever been fixed in this file? SQLite's own ladder is
  bug-derived — dbsqlfuzz exists because fuzz bugs kept being found. Past defect class is the best
  free predictor in the repo. Treat a clean history as evidence against, not as a veto, per the
  caveat in Step 2.

**When a red run is genuinely impossible** — the failure needs hardware you do not have, a
production-shaped dataset, or a multi-day soak — fall back to a **quoted citation**: `path:line`
plus the verbatim lines that create the failure, so a reader can `grep` for them. A paraphrase is
not a citation.

### Evidence hygiene

The red run protects the headline finding. It does not protect the prose around it, and that is
where this skill was measured to leak: in its own evaluation, **every run — with the skill and
without it — made at least one claim its evidence did not support.** This matters more than it
sounds, because verified parts lend their credibility to unverified ones sitting in the same report.

Four rules, each closing one observed leak:

**Never retype output.** Redirect the failing run to a file and cite that file —
`<test command> 2>&1 | tee red-run.txt`. Retyping is reconstruction, and reconstruction drifts: one
observed report pasted a code block from an earlier run under a heading claiming it was the later
one, and silently dropped two cases while reporting the total. If you inline output, copy it from
the file rather than from memory.

**Verify your own citations.** `path:line` references are mechanically checkable, so check them:

```bash
python3 scripts/verify_citations.py <report.md> <repo-root>
```

It greps every citation and reports any where the quoted text is not at that line. Observed drift
was 8–18 lines *with verbatim-correct quoted text* — exactly the shape that survives a human skim.

**Claim it at the layer you measured it.** A failing library-level test proves a library-level bug.
It does not prove the user-visible symptom you can picture downstream. One observed report verified
index corruption through the Go API, then asserted a CLI behaviour that does not reproduce, because
an earlier code path returns first. To claim an end-to-end impact, run the thing end to end.

**Counts and superlatives come from commands.** "The only", "the highest", "every", and every number
are claims. Get them from `grep -c`, `find … | wc -l`, `git log --oneline -- <path> | wc -l`, or do
not make them. Observed failures: a wrong "highest-churn package" that was never measured, a wrong
"the only `os.RemoveAll`" contradicted by the same report two sections earlier, and test counts off
by 5 and by 14.

**Then build it properly.** A working test the project's existing test command picks up, in the
project's existing framework. Four things decide whether it is worth anything:

- **Prefer a self-enforcing red state.** A one-shot red run proves the layer worked at one moment.
  A strict expected-failure marker re-proves it on every run forever, and goes red the moment
  somebody fixes the bug — which is the notification you actually want. Use `test.failing` (bun,
  jest), `pytest.mark.xfail(strict=True)`, `#[should_panic]`, or the language's equivalent. It also
  catches a test that is *accidentally already passing*, which a manual red run cannot.
- **Make the failure legible.** These layers fail on inputs no human wrote — seed `0x8f3a`, injection
  point 41, a 400-byte mutated blob. Print the seed, make it settable from the environment, and
  write the failing input to a file the test names in its output. A failure nobody can reproduce is
  a flaky test that gets deleted in three months.
- **Give it a permanent corpus.** Whatever it discovers — a crashing input, a bad seed, a deadlocking
  schedule — gets committed as a fixture and replayed forever. SQLite's fuzzers stopped finding new
  things because every interesting input any fuzzer ever found is still in the corpus.
- **Run it against the build you ship.** SQLite runs its suite three times per release — instrumented
  for coverage, with assertions on, and as delivered — and all three must agree. *"Test what you fly
  and fly what you test."* Debug-only logic is fine; shipping without re-running the suite in the
  release configuration is not.

**One layer — but report every failure you actually reproduced.** The cap governs what you propose
*building and maintaining*, not what you found. If the red run surfaces five real bugs, five real
bugs belong in the report: that is a bug report, and it is the most valuable thing on the page. What
has to stay singular is the layer you are asking someone to own forever. Name at most three runners
up, ranked against each other, and let the rest go.

Do not let the tier table veto a layer that is nearly free because the seam already exists. If the
code already has a `--dry-run` flag or a cache that can be switched off, the differential oracle
costs an afternoon and you should take it regardless of tier.

---

## Step 6 — Report


```markdown
## Harden: <operation assessed>

### Tier
<T0-T3> — who finds out, and how long after

### Modifiers
Untrusted           yes/no — <why>
Irreversible        yes/no — <why>
Concurrent          yes/no — <why>
Implements durability  yes/no — <why>
Fan-out             yes/no — <why>

### What exists
A/B/C/D/E/F — <what is present, with evidence: counts from commands, the test command, pass state>
Regression discipline: <N>% of fix commits shipped with a test — or "history is a bad oracle here"

### Bugs reproduced
<every failure that reproduced, from every modifier probed in Step 3 — each with the command
 and the file holding its output. This is the bug report, and it is not capped.>
<if nothing reproduced, say so: it is the main evidence for "already has what it has earned">

### Demotion
<the design change that would remove the hazard, as a diff, NOT applied — or why none exists>
<if you verified it in a scratch copy, say so and give the red → green result from there>

### The layer, demonstrated
<what you wrote, where it lives, and the file holding the red run — not retyped output>

### Considered and rejected
- <layer> — <why not, specifically about this code>

### Hand off
<what belongs to another skill>

### Evidence check
<the verify_citations.py result, and anything you could not verify, named as unverified>
```

The rejected section is what makes the recommendation trustworthy, so it has to cost something.
List the layers a reader would *most expect* given the tier and modifiers — not layers nobody was
going to suggest. "Rejected formal verification" is decoration. *"Rejected fuzzing: every input to
this module is a typed struct built by our own call sites, so a byte fuzzer tests the serialiser,
not this code"* is informative.

---

## Scope, and what to hand off

This skill owns **triage** — the tier decision, the demotion check, the rejected list — and builds
only what no other skill here covers: fault injection, crash and restart, adversarial corpora,
fuzzing, self-differential toggles, determinism harnesses, and the mutation audit.

Two explicit non-goals, because the overlap is otherwise not just duplicative but contradictory:

- **This skill does not write property tests.** `/property-based-testing` owns property discovery,
  generator design and model-based testing of stateful systems, at much higher fidelity. When ladder
  group B is the gap, say so and print the handoff.
- **This skill does not audit existing tests.** `/10x-check` judges the tests you have against
  regression protection, refactoring resistance, speed and maintainability.

Everything in this repo sets `disable-model-invocation`, so you cannot call those skills — print the
next command for the user to run (`/property-based-testing src/ledger.rs`) rather than pretending to
invoke it.

Note the real tension: `/10x-check`'s refactoring-resistance pillar will flag exactly the
internals-coupled artifacts that fault injection and differential oracles produce. That coupling is
usually the price of the layer rather than a defect in it — say so in the handoff so the two skills
do not argue through the user.

## What this skill will not do

- Recommend a layer it has not demonstrated failing.
- Modify your source. Demotions arrive as a diff for you to apply.
- State a number, a superlative, or a user-visible impact it did not measure.
- Produce a ranked backlog instead of a decision.
- Treat a coverage percentage as a goal, or recommend raising one.
- Recommend crash or fault-injection testing for code that merely *calls* a database.
- Add tests to code whose honest assessment is that it already has enough.

## Source

Derived from [How SQLite Is Tested](https://www.sqlite.org/testing.html). `references/sqlite.md`
condenses the primary source with the quotes, plus the honest limits of the approach — including
where SQLite's own methodology has been shown to fall short.
