# Test recipes

These are original, language-agnostic application recipes informed by the sources in [sources.md](sources.md). Select only recipes that address the contract under test.

## Failure schedules and recovery

First identify the effect boundary. An error before commit may promise no change; an error while returning a reply may leave a committed change. Encode the actual contract rather than assuming every exception implies rollback.

Wrap the dependency boundary with a deterministic controller. Record operation names, ordinal positions, whether failure was delivered, and any resources opened. The system under test must still execute its real business logic.

For a bounded, deterministic operation, enumerate failure positions from a fresh starting state. Use both a transient failure and sustained unavailability when meaningful. Continue until a successful run finishes without reaching the scheduled fault. A fault-free success following a retry is not evidence that all positions were exhausted. If a budget is reached first, report incomplete exploration.

Illustrative harness logic; adapt exception types, resource accounting, and promises to the project:

```text
for mode in [fail_once, fail_from_here_on]:
    completed = false
    for n in 1..budget:
        fixture = fresh_fixture()
        controller = instrument(fixture.dependency, n, mode)
        try:
            outcome = capture_expected_result_or_dependency_error(run_real_operation)
            trace = controller.trace
        finally:
            disable_injection()
        verify_outcome_and_state_against_contract(outcome, fixture, trace)
        verify_resources_are_released(fixture)
        verify_next_valid_operation_works(fixture)
        if not controller.fired and outcome.is_success:
            completed = true
            break
    assert completed, "failure schedule exploration exceeded budget"
```

In actual code, preserve unexpected exceptions as failures while still restoring hooks and fixtures. Capture a resource baseline before the operation; compare after cleanup. Fresh processes, file handles, leases, locks, temporary files, and background tasks can matter more than heap usage in managed runtimes.

Example: a bulk import promises that rejected batches leave the previous dataset usable. Fail acquisition, individual writes, and commit separately; read all records afterward, then attempt a valid import. An assertion that only checks an exception misses partial writes and poisoned state.

For recovery code, start from a genuine interrupted fixture. Interrupt recovery itself at a chosen boundary, restore availability, recover again, and check the promised stable state. Choose a few consequential combinations before attempting a large cross-product.

For crash tests, define what survives. Killing a child process tests process death, while OS buffers may remain intact. A power-loss model needs explicit assumptions about persistence barriers, loss, ordering, and partial writes. State the permitted recovered states at each acknowledgement boundary. Never extrapolate a simple mocked exception into a durability guarantee.

## Independent correctness checks

Use an oracle with a different route to the answer: hand-calculated examples, a deliberately simple model, another implementation, or a relation between equivalent operations. Computing expectations with the same production helper carries its defect into the test.

Examples:

- For a fast interval-overlap index, compare generated small sets against an exhaustive pair scan.
- For an integer-money allocation routine, check exact hand-worked examples, conservation of the total, and permitted per-recipient bounds. Conservation alone would miss assigning everything to one recipient.
- For a cache, compare cold and warm calls with the reference result, then update underlying state and exercise invalidation.
- For a query transformation, compare equivalent formulations only within a declared semantic subset.

Establish equivalence before differential comparison: ordering, duplicate multiplicity, NULL handling, collations, numeric precision, nondeterministic functions, and error semantics may differ. Sorting outputs can hide an ordering bug; converting to a set can hide duplicate loss.

For metamorphic tests, state the relation and its preconditions. A format round trip checks consistency, but two mutually wrong encoder/decoder functions can still agree. Add known external examples or a second oracle.

Separate result equivalence from optimization effectiveness. A correct slow implementation can satisfy all semantic tests; use stable work counters or an appropriate benchmark when reduced work is itself the requirement.

## Generated inputs and sequences

Choose a representation that reaches meaningful behavior. Include valid structured examples, minimally invalid neighbors, and limit-1/limit/limit+1 cases. Vary existing state alongside the next input where interactions matter.

For a parser, bound input size, execution time, and memory; define permitted rejection behavior and check successful parses against semantic rules. For a stateful API, generate operation sequences and compare state after each transition with a small model. Model-based stateful tests complement raw-byte fuzzing.

Make replay reliable: reset global state, control randomness and clocks where practical, record the complete operation history, and avoid real network dependencies in the inner loop. If concurrency matters, preserve the schedule or enough history to reconstruct it; the same seed with uncontrolled scheduling is not deterministic replay.

A useful campaign reports its budget, executed cases, oracle, retained failures, and reproduction commands. Zero crashes is only the result of a crash oracle over those cases. Use semantic assertions to detect wrong answers and resource accounting to detect leaks.

Retain minimized bug cases as fast regressions. Keep a bounded corpus of structurally useful inputs for subsequent campaigns. Derive tool commands from the installed version; the skill does not require a particular fuzzing library.

## Challenge the tests themselves

Coverage asks whether code ran. To inspect assertion strength, introduce a plausible defect in a disposable copy: skip rollback, reverse a boundary comparison, bypass invalidation, drop a duplicate, or suppress cleanup. Run the relevant tests and inspect why they failed.

Classify outcomes: detected semantic defect; survived and needs investigation; equivalent under the contract; performance-only change; invalid mutation or tool failure. Compilation errors do not demonstrate behavioral detection. Avoid treating every survivor as an application bug or chasing a universal mutation score.

For a critical decision involving A and B, choose pairs of examples in which changing A alone changes the outcome, then B alone. Account for short-circuit evaluation and the coverage tool's actual definition. Source branch coverage and MC/DC are distinct criteria, not interchangeable labels.

Retain defensive checks and exercise their assumptions with debug/runtime assertions or a targeted seam when appropriate. Disabling protective code solely to improve a report defeats the purpose of reliability testing.

Record the tested build/runtime options. Run meaningful checks with deployment settings as well as instrumentation; debug assertions or different optimizations can change behavior. Keep the matrix targeted to supported environments and actual risks.
