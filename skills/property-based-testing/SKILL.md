---
name: property-based-testing
description: >
  Analyze code to discover and generate high-quality property-based tests. Use this skill whenever
  the user asks about property-based testing, PBT, property tests, generative testing, fuzz testing
  with properties, model-based testing, stateful testing, or asks to "find good properties" for their
  code. Also use when the user mentions fast-check, Hypothesis, proptest, rapid, QuickCheck, jqwik,
  or ScalaCheck. Trigger when the user wants to go beyond example-based tests, wants to test invariants,
  wants to find edge cases automatically, or says things like "write better tests", "test this more
  thoroughly", "what properties does this code have", or "how do I know this is really correct".
---

# Property-Based Testing

Property-based testing (PBT) finds bugs that hand-written example tests miss by generating hundreds
of random inputs and checking that your code satisfies abstract properties. The power comes not from
the randomness itself, but from forcing you to articulate *what must always be true* about your code.

This skill helps you:
1. **Analyze code** to discover which properties apply
2. **Generate property-based tests** using the right framework for the language
3. **Design model-based tests** for stateful systems
4. **Avoid common pitfalls** that make property tests weak or misleading

## Workflow

```
Property-Based Testing Analysis:
- [ ] Read and understand the target code
- [ ] Classify the code (see Property Discovery below)
- [ ] Identify candidate properties from the catalog
- [ ] Validate property strength ("simplest bad implementation" check)
- [ ] Design generators (encode constraints in the generator, not in assume/filter)
- [ ] Write the tests
- [ ] Verify generator coverage
```

## Property Discovery Process

The key insight from empirical research: experienced engineers are *opportunistic* — they identify
where PBT provides high leverage rather than applying it uniformly. Start by classifying the code.

### Step 1: Classify the code

| Code type | Best property patterns |
|---|---|
| Serialization / encoding | Round-trip, invariance |
| Data structures (sort, filter, group) | Invariants + conservation (element membership) |
| Mathematical / numeric functions | Algebraic laws, commutativity, associativity |
| Stateful systems (cache, DB, queue) | Model-based / stateful testing |
| Parsers / decoders | Robustness (no crash) + round-trip if encoder exists |
| APIs / HTTP handlers | Metamorphic relations, idempotence |
| Security-critical code | Boundary values + adversarial generators |
| Algorithm with known-correct slow version | Differential / oracle testing |
| Business logic with clear rules | Business rule as property |
| Tree / graph algorithms | Structural induction |

### Step 2: Select properties from the catalog

Read `references/property-catalog.md` for the full catalog with examples. Here is the summary:

**Algebraic Properties** — when your code obeys mathematical laws:
- **Invariance**: certain outputs/measurements don't change (e.g., sort preserves length)
- **Inverse / Round-trip**: `decode(encode(x)) == x` — the most commonly useful property in practice
- **Idempotence**: `f(f(x)) == f(x)` — powerful for normalization, caching, formatting
- **Commutativity**: `f(a, b) == f(b, a)` — order shouldn't matter
- **Associativity**: `f(f(a, b), c) == f(a, f(b, c))`

**Relational Properties** — when your code establishes or preserves relationships:
- **Symmetry**: if `relates(a, b)` then `relates(b, a)`
- **Antisymmetry**: if `relates(a, b)` and `relates(b, a)` then `a == b`
- **Transitivity**: if `relates(a, b)` and `relates(b, c)` then `relates(a, c)`
- **Consistency**: related operations produce consistent results

**Structural Properties** — when your code operates on structured data:
- **Conservation**: elements are preserved (sort doesn't lose or duplicate items)
- **Structural induction**: property holds for base case and extends to recursive structures
- **Completeness**: handles all possible inputs in its domain without error

**Testing Strategies** — approaches rather than specific properties:
- **Metamorphic relations**: if `f(x) = y`, then `f(transform(x))` must relate to `y` in a known way
- **Boundary values**: extreme/edge inputs (empty, max, zero, negative)
- **Equivalence partitioning**: divide inputs into classes, test representatives from each
- **Analogy / Oracle**: compare against a known-correct reference implementation
- **Model-based testing**: compare a simple model against the real system (see below)

### Step 3: Validate property strength

For each property, ask: **"What is the simplest broken implementation that passes this property?"**

- If `return []` passes it → too weak (add a conservation/membership property)
- If `return input` passes it → too weak (add a transformation/correctness property)
- If only subtle bugs pass it → good property

Combine multiple properties. A single property is almost always too weak on its own. The conjunction
of 2-3 complementary properties is where PBT becomes powerful.

### Step 4: Design generators

The quality of your generators determines the quality of your tests. Key principles:

1. **Encode validity in the generator, not in `assume`/`filter`**. High discard rates waste test
   budget and can break shrinking.
2. **Use `map`/`chain` (not raw generators)** to preserve integrated shrinking.
3. **Bias toward interesting inputs**: empty collections, boundary values, near-valid inputs.
   The most interesting bugs live in "almost valid" inputs, not completely random noise.
4. **Verify your generator**: run it 1000 times and check the distribution. Generator bugs
   are common and silent.

## Model-Based Testing

For stateful systems (caches, databases, queues, state machines), model-based testing is the
most powerful approach. The pattern:

```
Real system  ←→  Simplified model (e.g., a HashMap or list)
    ↓                    ↓
Execute command     Update model state
    ↓                    ↓
    └── Assert states match ──┘
```

The model must be **embarrassingly simple** — simple enough that you trust it by inspection.
If implementing the model requires as much code as the real system, you've gained nothing.

Read `references/model-based-testing.md` for framework-specific APIs and patterns.

### When to use model-based testing

Use it when the system has more *non-functional complexity* (caching, batching, concurrency,
persistence) than inherent domain complexity. The model captures the domain logic; the test
verifies that the non-functional concerns don't corrupt it.

## Framework Reference

Read `references/frameworks.md` for detailed API patterns per language. Quick guide:

| Language | Framework | Key feature |
|---|---|---|
| TypeScript/JS | fast-check | Async race detection via `fc.scheduler()` |
| Python | Hypothesis | Targeted PBT via `hypothesis.target()`, example database |
| Rust | proptest | `prop_compose!` macro, `proptest-state-machine` crate |
| Go | rapid | Zero deps, `t.Repeat()` for stateful testing |
| Java | jqwik | `@ForAll`, `@Provide`, lifecycle annotations |
| Haskell | QuickCheck | The original — type-class based `Arbitrary` |

## Common Anti-Patterns

Avoid these — they're the difference between PBT that catches real bugs and PBT that gives
false confidence:

1. **Trivially weak properties** — passes for broken implementations. Always do the
   "simplest bad implementation" check.

2. **Reimplementing the SUT** — writing `assert f(x) == my_copy_of_f(x)`. The model
   must be independently, obviously correct.

3. **Overusing `assume`/`filter`** — generates inputs then throws most away. Encode
   constraints in the generator instead.

4. **No coverage verification** — a generator that never produces empty collections
   or zero gives false confidence. Check distributions.

5. **Generator too broad, property too narrow** — random noise tests robustness but
   not correctness. Generate structured inputs near your domain.

6. **Ignoring shrinking** — use frameworks with integrated shrinking (Hypothesis,
   fast-check, proptest). Type-based shrinking can produce invalid counterexamples.

## Output Format

When analyzing code and generating property-based tests, produce:

```
## Property Analysis: [module/function name]

**Code classification**: [from the table above]

### Identified Properties

1. **[Property name]** ([category])
   - Statement: "For all valid [inputs], [what must be true]"
   - Strength: [what broken implementations does this catch?]
   - Generator notes: [any special generator requirements]

2. ...

### Generated Tests

[Tests in the appropriate framework for the project's language]

### Generator Verification

[A brief note on what edge cases the generators cover and any
distribution checks worth adding]
```

When the analysis is complete, state which properties you consider highest-value (most
likely to catch real bugs) and why. Prioritize properties that:
- Catch bugs that unit tests typically miss
- Exercise edge cases and boundary conditions
- Verify the interaction between operations (not just individual operations)
