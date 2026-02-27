# Framework Reference

Detailed API patterns for each major PBT framework. Read the section for your project's
language when generating tests.

## Table of Contents

1. [TypeScript / JavaScript — fast-check](#typescript--javascript--fast-check)
2. [Python — Hypothesis](#python--hypothesis)
3. [Rust — proptest](#rust--proptest)
4. [Go — rapid](#go--rapid)
5. [Other Languages](#other-languages)
6. [Generator Design Patterns](#generator-design-patterns)

---

## TypeScript / JavaScript — fast-check

**Package**: `fast-check` (v4.x)
**Install**: `npm install --save-dev fast-check`

### Basic Property Test

```typescript
import fc from "fast-check";

// With a test runner (jest/vitest)
test("sort is idempotent", () => {
  fc.assert(
    fc.property(fc.array(fc.integer()), (arr) => {
      const sorted = arr.slice().sort((a, b) => a - b);
      const sortedTwice = sorted.slice().sort((a, b) => a - b);
      expect(sorted).toEqual(sortedTwice);
    })
  );
});

// Standalone (no test runner)
fc.assert(
  fc.property(fc.array(fc.integer()), (arr) => {
    const sorted = arr.slice().sort((a, b) => a - b);
    return sorted.length === arr.length; // return boolean
  })
);
```

### Key Arbitraries

```typescript
// Primitives
fc.integer()                        // any safe integer
fc.integer({ min: 0, max: 100 })    // bounded
fc.nat()                            // non-negative integer
fc.float()                          // including NaN, Infinity, -0
fc.float({ noNaN: true })           // exclude special values
fc.boolean()
fc.string()                         // includes unicode, special chars
fc.string({ minLength: 1 })
fc.fullUnicodeString()              // includes surrogates, combining chars

// Collections
fc.array(fc.integer())
fc.array(fc.integer(), { minLength: 1, maxLength: 100 })
fc.uniqueArray(fc.integer())
fc.set(fc.integer())                // v4: returns Set<number>

// Objects
fc.record({ name: fc.string(), age: fc.nat() })
fc.object()                         // arbitrary nested object
fc.jsonValue()                      // JSON-safe values

// Combinators
fc.oneof(fc.string(), fc.integer()) // one of several types
fc.option(fc.string())              // string | null
fc.tuple(fc.string(), fc.integer()) // [string, number]
fc.constant("fixed-value")

// Dependent generation
fc.integer({ min: 1, max: 10 }).chain((size) =>
  fc.array(fc.integer(), { minLength: size, maxLength: size })
)
```

### Composing Custom Arbitraries

```typescript
// Use .map() for transforms (preserves shrinking)
const positiveEven = fc.nat().map((n) => (n + 1) * 2);

// Use .filter() sparingly (high discard = bad)
const nonEmpty = fc.string().filter((s) => s.length > 0);
// Better: fc.string({ minLength: 1 })

// Use .chain() for dependent generation
const arrayWithElement = fc.array(fc.integer(), { minLength: 1 }).chain((arr) =>
  fc.tuple(fc.constant(arr), fc.nat({ max: arr.length - 1 }))
);

// Recursive structures via fc.letrec
const jsonArb = fc.letrec((tie) => ({
  value: fc.oneof(
    fc.string(),
    fc.double({ noNaN: true }),
    fc.boolean(),
    fc.constant(null),
    tie("array"),
    tie("object")
  ),
  array: fc.array(tie("value"), { maxLength: 3 }),
  object: fc.dictionary(fc.string(), tie("value"), { maxKeys: 3 }),
})).value;
```

### Race Condition Detection

```typescript
// Unique to fast-check — shuffles promise resolution order
test("no race conditions in cache", () => {
  fc.assert(
    fc.asyncProperty(fc.scheduler(), async (s) => {
      const cache = new AsyncCache();

      // Schedule concurrent operations
      const p1 = s.schedule(Promise.resolve("a")).then(() => cache.get("key"));
      const p2 = s.schedule(Promise.resolve("b")).then(() => cache.set("key", 42));

      // Let scheduler pick execution order
      await s.waitAll();

      // Assert consistency regardless of order
      const value = cache.get("key");
      expect(value).toBeDefined();
    })
  );
});
```

### Configuration

```typescript
fc.assert(
  fc.property(fc.string(), (s) => { /* ... */ }),
  {
    numRuns: 1000,           // default: 100
    seed: 42,                // for reproducibility
    endOnFailure: true,      // stop at first failure
    verbose: fc.VerbosityLevel.VeryVerbose,  // log all values
  }
);
```

---

## Python — Hypothesis

**Package**: `hypothesis`
**Install**: `pip install hypothesis`

### Basic Property Test

```python
from hypothesis import given, settings, example, assume
import hypothesis.strategies as st

@given(st.lists(st.integers()))
def test_sort_preserves_length(xs):
    assert len(sorted(xs)) == len(xs)

# Add known-important examples alongside random generation
@given(st.lists(st.integers()))
@example([])           # always test empty
@example([1])          # always test singleton
@example([2, 1])       # always test minimal unsorted
def test_sort_is_idempotent(xs):
    once = sorted(xs)
    twice = sorted(once)
    assert once == twice
```

### Key Strategies

```python
# Primitives
st.integers()
st.integers(min_value=0, max_value=100)
st.floats(allow_nan=False, allow_infinity=False)
st.booleans()
st.text()
st.text(min_size=1, max_size=100)
st.binary()

# Collections
st.lists(st.integers())
st.lists(st.integers(), min_size=1, max_size=50)
st.sets(st.integers())
st.frozensets(st.text())
st.dictionaries(st.text(), st.integers())

# Objects / structured data
st.fixed_dictionaries({"name": st.text(), "age": st.integers(min_value=0)})
st.builds(User, name=st.text(), age=st.integers(min_value=0))

# Combinators
st.one_of(st.text(), st.integers())
st.none() | st.text()                    # Optional[str]
st.tuples(st.text(), st.integers())
st.just("constant")
st.sampled_from(["red", "green", "blue"])

# Dependent generation
@st.composite
def sorted_pair(draw):
    a = draw(st.integers())
    b = draw(st.integers(min_value=a))
    return (a, b)
```

### Targeted Property-Based Testing

```python
from hypothesis import target

@given(st.lists(st.integers()))
def test_no_quadratic_sort(xs):
    import time
    start = time.perf_counter()
    result = my_sort(xs)
    elapsed = time.perf_counter() - start

    # Guide Hypothesis toward inputs that maximize runtime
    target(elapsed, label="sort_runtime")

    assert result == sorted(xs)
```

This uses simulated annealing to search for inputs that maximize the target metric — great
for finding worst-case performance.

### Settings and Configuration

```python
from hypothesis import settings, HealthCheck, Phase

@settings(
    max_examples=500,            # default: 100
    deadline=None,               # disable per-test timeout
    suppress_health_check=[HealthCheck.too_slow],
    database=None,               # disable example database
    phases=[Phase.generate],     # skip shrinking (rarely useful)
)
@given(st.text())
def test_with_custom_settings(s):
    ...
```

### Verifying Generator Coverage

```python
from hypothesis import event

@given(st.lists(st.integers()))
def test_with_coverage(xs):
    event(f"list_size={len(xs)}")
    if len(xs) == 0:
        event("empty_list")
    # Run with --hypothesis-show-statistics to see distribution
    result = process(xs)
    assert is_valid(result)
```

---

## Rust — proptest

**Crate**: `proptest`
**Cargo.toml**: `proptest = "1"`

### Basic Property Test

```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn sort_preserves_length(ref v in prop::collection::vec(any::<i32>(), 0..100)) {
        let mut sorted = v.clone();
        sorted.sort();
        prop_assert_eq!(sorted.len(), v.len());
    }

    #[test]
    fn sort_is_idempotent(ref v in prop::collection::vec(any::<i32>(), 0..100)) {
        let mut once = v.clone();
        once.sort();
        let mut twice = once.clone();
        twice.sort();
        prop_assert_eq!(once, twice);
    }
}
```

### Key Strategies

```rust
// Primitives
any::<i32>()
0..100i32                          // range as strategy
prop::bool::ANY
"[a-z]{1,10}"                     // regex-based string strategy
prop::string::string_regex("[0-9]+").unwrap()

// Collections
prop::collection::vec(any::<i32>(), 0..50)
prop::collection::hash_set(any::<String>(), 0..20)
prop::collection::hash_map(any::<String>(), any::<i64>(), 0..20)

// Combinators
prop_oneof![Just(0), 1..100i32]
prop::option::of(any::<String>())
(any::<i32>(), any::<String>())    // tuple strategy
```

### Composing Strategies

```rust
// prop_compose! macro — the primary way to build custom strategies
prop_compose! {
    fn user_strategy()(
        name in "[a-z]{3,10}",
        age in 0..150u32,
        active in any::<bool>(),
    ) -> User {
        User { name, age, active }
    }
}

// Dependent generation with prop_flat_map
fn non_empty_with_element() -> impl Strategy<Value = (Vec<i32>, usize)> {
    prop::collection::vec(any::<i32>(), 1..50)
        .prop_flat_map(|vec| {
            let len = vec.len();
            (Just(vec), 0..len)
        })
}

// Recursive strategies
fn json_value() -> impl Strategy<Value = JsonValue> {
    let leaf = prop_oneof![
        any::<i64>().prop_map(JsonValue::Number),
        "[a-z]{0,10}".prop_map(JsonValue::String),
        any::<bool>().prop_map(JsonValue::Bool),
        Just(JsonValue::Null),
    ];
    leaf.prop_recursive(4, 64, 10, |inner| {
        prop_oneof![
            prop::collection::vec(inner.clone(), 0..5).prop_map(JsonValue::Array),
            prop::collection::hash_map("[a-z]{1,5}", inner, 0..5).prop_map(JsonValue::Object),
        ]
    })
}
```

### Configuration

```rust
proptest! {
    #![proptest_config(ProptestConfig::with_cases(1000))]

    #[test]
    fn my_test(x in any::<i32>()) {
        // runs 1000 cases instead of default 256
    }
}
```

---

## Go — rapid

**Package**: `pgregory.net/rapid`
**Install**: `go get pgregory.net/rapid`

### Basic Property Test

```go
import (
    "sort"
    "testing"
    "pgregory.net/rapid"
)

func TestSortPreservesLength(t *testing.T) {
    rapid.Check(t, func(t *rapid.T) {
        xs := rapid.SliceOf(rapid.Int()).Draw(t, "xs")
        original := len(xs)
        sort.Ints(xs)
        if len(xs) != original {
            t.Fatalf("sort changed length from %d to %d", original, len(xs))
        }
    })
}
```

### Key Generators

```go
// Primitives
rapid.Int()
rapid.IntRange(0, 100)
rapid.Float64()
rapid.Bool()
rapid.String()
rapid.StringN(1, 100, -1)      // min_len, max_len, max_codepoint

// Collections
rapid.SliceOf(rapid.Int())
rapid.SliceOfN(rapid.Int(), 1, 50)  // min, max length
rapid.MapOf(rapid.String(), rapid.Int())

// Combinators
rapid.OneOf(rapid.Int(), rapid.Float64())
rapid.Just(42)
rapid.SampledFrom([]string{"a", "b", "c"})
rapid.Ptr(rapid.Int(), true)    // *int, allow nil

// Custom
rapid.Custom(func(t *rapid.T) MyStruct {
    return MyStruct{
        Name: rapid.String().Draw(t, "name"),
        Age:  rapid.IntRange(0, 150).Draw(t, "age"),
    }
})
```

---

## Other Languages

### Java — jqwik

```java
@Property
void sortPreservesLength(@ForAll List<Integer> list) {
    List<Integer> sorted = new ArrayList<>(list);
    Collections.sort(sorted);
    assertThat(sorted).hasSize(list.size());
}

@Provide
Arbitrary<User> users() {
    return Combinators.combine(
        Arbitraries.strings().alpha().ofMinLength(1),
        Arbitraries.integers().between(0, 150)
    ).as(User::new);
}
```

### Haskell — QuickCheck

```haskell
prop_sortPreservesLength :: [Int] -> Bool
prop_sortPreservesLength xs = length (sort xs) == length xs

prop_sortIdempotent :: [Int] -> Bool
prop_sortIdempotent xs = sort (sort xs) == sort xs
```

---

## Generator Design Patterns

These patterns apply across all frameworks.

### Encode Validity in the Generator

```python
# BAD: generate then filter (high discard rate)
@given(st.integers())
def test_positive(n):
    assume(n > 0)
    ...

# GOOD: generate valid inputs directly
@given(st.integers(min_value=1))
def test_positive(n):
    ...
```

### Generate Structured Data Near the Domain

```typescript
// BAD: completely random strings for URL testing
fc.string()

// GOOD: structured URLs with intentional variations
const urlArb = fc.record({
  protocol: fc.constantFrom("http", "https", "ftp"),
  host: fc.domain(),
  port: fc.option(fc.integer({ min: 1, max: 65535 })),
  path: fc.array(fc.webSegment(), { maxLength: 5 }).map((ps) => "/" + ps.join("/")),
  query: fc.option(
    fc.dictionary(fc.webSegment(), fc.webSegment(), { maxKeys: 3 })
  ),
}).map(({ protocol, host, port, path, query }) => {
  let url = `${protocol}://${host}`;
  if (port !== null) url += `:${port}`;
  url += path;
  if (query !== null) {
    url += "?" + Object.entries(query).map(([k, v]) => `${k}=${v}`).join("&");
  }
  return url;
});
```

### Verify Generator Distribution

Always spot-check that your generator produces the inputs you expect:

```python
# Python: run with --hypothesis-show-statistics
from hypothesis import event

@given(my_strategy())
def test_check_distribution(value):
    event(f"type={type(value).__name__}")
    event(f"size={'empty' if len(value) == 0 else 'small' if len(value) < 5 else 'large'}")
```

```typescript
// TypeScript: sample from your arbitrary
const samples = fc.sample(myArbitrary, 1000);
const emptyCounts = samples.filter((s) => s.length === 0).length;
console.log(`Empty inputs: ${emptyCounts}/1000`);
// Verify this matches your expectations
```
