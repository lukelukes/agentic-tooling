---
name: sqlite-testing-philosophy
description: Review test effectiveness and implement stronger tests using SQLite-inspired fault injection, independent correctness oracles, and adversarial testing. Use for test-strategy reviews, coverage that misses bugs, persistence or recovery reliability, and explicit SQLite-style testing in any language. Ordinary SQLite queries or configuration alone do not trigger this skill.
---

# SQLite testing philosophy

Build evidence that consequential defects would be detected. Use the project's language and existing test framework; scale the work to the consequences of failure.

## 1. Establish what must remain true

Read the relevant implementation, tests, project instructions, and test commands. Identify the requested mode: a review produces findings; implementation changes and runs tests. Preserve the user's scope.

Choose the few observable promises whose violation matters most. Identify inputs, existing state, external dependencies, failure boundaries, and the deployed configuration. State the oracle: the rule or independent mechanism that determines the correct result.

If a promise is unclear, look for its specification or callers. Ask only when the missing decision changes correctness; continue work on independent, established promises. Existing behavior is evidence, not automatically the contract.

Finish this step with a compact evidence map:

| Promise | Plausible defect | Existing evidence | Missing experiment and oracle |
|---|---|---|---|
| Retrying an accepted request has one effect | Reply lost after commit causes duplicate work | Success-only test | Lose reply, retry same key, inspect durable effects |

## 2. Select discriminating experiments

SQLite's transferable lessons: independently designed harnesses reduce shared blind spots; failure handling deserves deliberate tests; generated inputs need correctness checks; regression cases preserve discoveries; coverage measures reach rather than sufficient assertions; instrumented and delivered builds both matter. Its scale is a consequence of its role, not a universal test-count target. See [research sources](references/sources.md) for provenance and limitations.

Rank gaps by consequence, likelihood, and current uncertainty. Start with the smallest experiment that would distinguish a realistic defect from correct behavior. Each selected test should connect:

`promise → defect → stimulus → observable assertion → replay command`

Choose the relevant recipe in [test recipes](references/test-recipes.md):

- **Dependency failures, cleanup, persistence, or recovery:** read “Failure schedules and recovery.”
- **Wrong results, caching, optimized paths, or complex transformations:** read “Independent correctness checks.”
- **Parsers, protocols, input limits, or state machines:** read “Generated inputs and sequences.”
- **High coverage with weak confidence:** read “Challenge the tests themselves.”

A pure calculation may need a handful of boundary examples and a simple reference calculation. A storage component may warrant controlled failure schedules. Recommend new infrastructure only when its expected benefit justifies setup and maintenance.

## 3. Run trustworthy experiments

For a review, cite the inspected files and distinguish verified defects from missing evidence. Describe the highest-value tests precisely enough to implement, including their expected outcomes and cost. Do not modify application files during a review.

For implementation, add focused tests using existing seams. Introduce a narrow test seam only if necessary; keep the tested behavior on the real production path. Tests of a mock's own invented algorithm establish little about the application.

Use fresh disposable fixtures for each experiment and restore injected behavior in cleanup. Prove the intended stimulus occurred with a recorded event or counter. Check observable state as well as the return value. If the behavior is durable, inspect it through a fresh reader or restart where relevant.

Define a case or time budget before generated campaigns. Preserve the failing input or operation sequence, seed, configuration, and exact replay command; a seed alone may become unusable after generator changes. Minimize discoveries into small regression cases.

Use resource checks and runtime instrumentation appropriate to the stack. Separate process-crash evidence from a model of lost, reordered, or torn persistent writes. Limit reliability claims to the environment and failures actually tested.

## 4. Verify detection, then report

Run the targeted tests and appropriate project checks. For a discovered defect, demonstrate the regression failing on the original code and passing after the fix when feasible. If tests already pass, challenge a valuable assertion with one controlled, plausible defect in a disposable copy; confirm the failure is the intended assertion, then discard the mutation.

For complex decisions, examine individual conditions and boundary cases. Keep useful defensive checks; record justified exclusions and investigate surviving mutants. Neither a percentage nor the absence of fuzz crashes proves correctness.

Keep fast deterministic regressions in the normal feedback loop. Put costly randomized, configuration, or stress campaigns in an explicit follow-up or existing scheduled lane. Do not start an unbounded campaign.

Finish with:

- **Protected behavior:** the promise and the defect the test detects.
- **Evidence:** files, commands, observed outcomes, and any failing-before/passing-after demonstration.
- **Limits:** untested failure modes, uncertain contracts, unavailable tools, and the next most valuable experiment.

Clearly label proposals and checks that were not run. Stop when the scoped evidence is complete.
