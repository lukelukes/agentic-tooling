# Research and provenance

Primary sources checked on 2026-09-19. The workflow and examples in this skill are adaptations for general software projects, not a claim that every technique below is part of SQLite.

## SQLite foundation

- [How SQLite Is Tested](https://www.sqlite.org/testing.html): independent harnesses, systematic anomaly testing, fuzzing, regression preservation, coverage, and delivered-build checks. Read sections 3–4 for failure/input exploration and 7–9 for evidence about the tests. Borrow the principles rather than historical test counts or tool-status claims.
- [Atomic Commit in SQLite](https://www.sqlite.org/atomiccommit.html): crash recovery depends on an explicit storage model, synchronization, and commit boundaries. Consult this when designing persistence experiments; process termination alone does not model power loss.
- [TH3](https://www.sqlite.org/th3.html): configuration-specific coverage and branch mutation testing. TH3 is proprietary; this skill does not require access to it. SQLite's coverage claims should not be generalized to every extension, platform, and build combination.
- [The Use Of assert() In SQLite](https://www.sqlite.org/assert.html): runtime assertions expose assumptions and invariants, while defensive conditions remain meaningful. Use this distinction when a coverage target creates pressure to remove protection.

## Complementary techniques

- [SQLancer project documentation](https://github.com/sqlancer/sqlancer/blob/main/README.md): separates generated workloads from test oracles, including methods that detect incorrect answers rather than crashes. Its target is database implementations; application-level adaptations need their own justified invariants.
- [NoREC: Detecting Optimization Bugs in Database Engines via Non-Optimizing Reference Engine Construction](https://arxiv.org/abs/2007.08292), Rigger and Su, 2020: compares optimized queries with equivalent forms that avoid the relevant optimization. Generalize to simple reference paths only when semantic equivalence is established.
- [FoundationDB testing](https://apple.github.io/foundationdb/testing.html): deterministic simulation explores failures alongside real-system tests. A simulator only covers modeled behavior; a complete cluster simulator is not a prerequisite for useful local fault injection.
- [FoundationDB client testing](https://apple.github.io/foundationdb/client-testing.html): repeatability requires controlling workload nondeterminism, not just choosing a seed. Save event histories and configuration when scheduler or environment behavior matters.
- [TigerBeetle: Simulation Testing for Liveness](https://tigerbeetle.com/blog/2023-07-06-simulation-testing-for-liveness/): random restarts can conceal progress failures. Check safety during disruption, then completion under explicit healthy conditions without harness resets that accidentally rescue the system.
- [LLVM libFuzzer documentation](https://llvm.org/docs/LibFuzzer.html): coverage-guided mutation, seed corpora, minimized inputs, and bounded campaigns. Follow the installed tool's interface; these mechanics are examples, not a language requirement.
- [Hypothesis stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html): generate sequences of interacting operations and compare with a model. Useful when isolated input cases miss history-dependent bugs; other ecosystems can implement the same approach.

## Boundaries of the synthesis

The evidence map, risk ranking, test-selection rules, output format, and non-database examples are this skill's design. They are intended to make the sources actionable without importing the cost of a database project's entire testing organization. Full coverage, mutation scores, and successful finite campaigns remain evidence with limitations, not proofs of the absence of defects.
