# Property Catalog

A comprehensive catalog of property categories with concrete examples. When analyzing code,
walk through each category and ask: "Does this apply to the code I'm looking at?"

## Table of Contents

1. [Algebraic Properties](#algebraic-properties)
   - Invariance
   - Inverse / Round-trip
   - Idempotence
   - Commutativity
   - Associativity
2. [Relational Properties](#relational-properties)
   - Symmetry
   - Antisymmetry
   - Transitivity
   - Consistency
3. [Structural Properties](#structural-properties)
   - Conservation
   - Structural Induction
   - Completeness
4. [Testing Strategies](#testing-strategies)
   - Metamorphic Relations
   - Boundary Values
   - Equivalence Partitioning
   - Analogy / Oracle / Differential Testing
   - Model-Based Testing

---

## Algebraic Properties

### Invariance

Something measurable about the output stays the same regardless of input variation.

**When to look for it**: Any function that transforms data while preserving structure.

**Examples**:
- `sort(xs).length === xs.length` — sorting preserves length
- `map(f, xs).length === xs.length` — mapping preserves length
- `encrypt(key, plaintext).length >= plaintext.length` — encryption doesn't shrink data
- `compress(data)` decompressed equals original — compression preserves information
- A database transaction either commits all changes or none — atomicity invariant

**Strength check**: Invariance alone is usually weak. `return new Array(xs.length)` passes the
sort-length invariant. Combine with conservation or correctness properties.

**Template**:
```
For all valid inputs X:
  measure(f(X)) == measure(X)
```

### Inverse / Round-trip

Applying an operation and its inverse returns to the starting point. This is the single most
commonly useful property in production PBT.

**When to look for it**: Anywhere you have paired operations — encode/decode, serialize/deserialize,
parse/format, compress/decompress, encrypt/decrypt, write/read.

**Examples**:
- `JSON.parse(JSON.stringify(obj))` deeply equals `obj` (for JSON-safe values)
- `decode(encode(msg))` equals `msg`
- `fromDTO(toDTO(entity))` equals `entity`
- `parse(format(date))` equals `date`
- `decompress(compress(data))` equals `data`

**Real-world catch**: fast-check's round-trip property on a key-value store found a `__proto__`
prototype pollution vulnerability on the 75th generated input — missed by all hand-written tests.

**Strength check**: Round-trip is inherently strong because it constrains the implementation
heavily. The main risk is a generator that only produces "easy" inputs. Make sure generators
include special characters, empty strings, Unicode, nested structures, and boundary values.

**Template**:
```
For all valid inputs X:
  inverse(f(X)) == X
```

### Idempotence

Applying the operation twice gives the same result as applying it once.

**When to look for it**: Normalization, formatting, deduplication, caching, API retries,
data cleaning, UI rendering, database migrations.

**Examples**:
- `normalize(normalize(text)) === normalize(text)`
- `distinct(distinct(list))` equals `distinct(list)`
- `format(format(code))` equals `format(code)`
- `trim(trim(str)) === trim(str)`
- PUT requests should be idempotent — sending the same PUT twice shouldn't change the result
- `ensureDirectoryExists(path)` called twice should succeed without error

**Strength check**: Idempotence alone doesn't verify correctness — a function that returns
its input is trivially idempotent. Combine with a correctness property.

**Template**:
```
For all valid inputs X:
  f(f(X)) == f(X)
```

### Commutativity

The order of operands doesn't affect the result.

**When to look for it**: Mathematical operations, set operations, combining/merging operations,
aggregate functions, event processing where order shouldn't matter.

**Examples**:
- `merge(a, b)` equals `merge(b, a)` for symmetric merge
- `intersect(setA, setB)` equals `intersect(setB, setA)`
- `add(x, y) === add(y, x)`
- `max(a, b) === max(b, a)`
- Applying two independent filters in either order yields the same result

**Strength check**: Moderate. Catches ordering bugs but doesn't verify the operation itself is correct.

**Template**:
```
For all valid inputs A, B:
  f(A, B) == f(B, A)
```

### Associativity

Grouping of operations doesn't affect the result.

**When to look for it**: Reduction operations, fold/reduce, string concatenation, numeric
accumulation, merging operations, stream processing.

**Examples**:
- `concat(concat(a, b), c)` equals `concat(a, concat(b, c))`
- `merge(merge(a, b), c)` equals `merge(a, merge(b, c))`
- `(a + b) + c === a + (b + c)` (watch for floating-point — use approximate equality)

**Template**:
```
For all valid inputs A, B, C:
  f(f(A, B), C) == f(A, f(B, C))
```

---

## Relational Properties

### Symmetry

If A relates to B, then B relates to A.

**When to look for it**: Equality checks, similarity functions, distance metrics,
bidirectional relationships.

**Examples**:
- `equals(a, b) === equals(b, a)`
- `distance(a, b) === distance(b, a)`
- `isSimilarTo(a, b) === isSimilarTo(b, a)`
- `canCommunicateWith(a, b) === canCommunicateWith(b, a)`

**Template**:
```
For all valid inputs A, B:
  relates(A, B) implies relates(B, A)
```

### Antisymmetry

If A relates to B and B relates to A, then A equals B. (Or equivalently: if A strictly
relates to B, then B does not strictly relate to A.)

**When to look for it**: Ordering/comparison functions, ranking systems, dependency graphs,
version comparisons.

**Examples**:
- If `compare(a, b) <= 0` and `compare(b, a) <= 0` then `a === b`
- If `isSubsetOf(a, b)` and `isSubsetOf(b, a)` then `a` equals `b`
- If `dependsOn(a, b)` and `dependsOn(b, a)` then you have a cycle (which may be an error)

**Template**:
```
For all valid inputs A, B:
  if relates(A, B) and relates(B, A) then A == B
```

### Transitivity

If A relates to B and B relates to C, then A relates to C.

**When to look for it**: Sorting comparators, equivalence relations, permission hierarchies,
type hierarchies, graph reachability.

**Examples**:
- If `compare(a, b) <= 0` and `compare(b, c) <= 0` then `compare(a, c) <= 0`
- If `isAncestor(a, b)` and `isAncestor(b, c)` then `isAncestor(a, c)`
- If `hasPermission(roleA, x)` and `inheritsFrom(roleB, roleA)` then `hasPermission(roleB, x)`

**Why this matters**: A non-transitive comparator will cause sort algorithms to produce
inconsistent results or infinite loops. This is a real bug category.

**Template**:
```
For all valid inputs A, B, C:
  if relates(A, B) and relates(B, C) then relates(A, C)
```

### Consistency

Related operations or inputs produce consistent results.

**When to look for it**: Any system with multiple ways to query or compute the same
information, caches, derived state, denormalized data.

**Examples**:
- `contains(collection, item)` is consistent with `find(collection, item) !== null`
- `size(collection)` equals `toArray(collection).length`
- `isEmpty(collection)` equals `size(collection) === 0`
- After `add(set, item)`, `contains(set, item)` is true
- A cache returns the same value as computing from scratch

**Template**:
```
For all valid inputs X:
  query_a(f(X)) is consistent with query_b(f(X))
```

---

## Structural Properties

### Conservation

Certain elements or quantities are preserved through operations.

**When to look for it**: Any function that rearranges, partitions, or transforms collections.
Also: financial transactions (money in = money out), physics simulations (energy conservation).

**Examples**:
- `sort(xs)` contains exactly the same elements as `xs` (multiset equality)
- `partition(xs, predicate)` — the union of both halves equals `xs`
- `flatMap` over a list of lists — total element count is preserved
- A transfer between accounts: `balanceA + balanceB` is unchanged
- `shuffle(deck)` contains exactly the same cards as `deck`

**This is the complement to invariance**: invariance checks a measurement stays the same;
conservation checks that the actual elements/quantities are preserved.

**Template**:
```
For all valid inputs X:
  elements(f(X)) == elements(X)  (as multisets)
```

### Structural Induction

If a property holds for the base case and the inductive step preserves it, it holds for
all structures.

**When to look for it**: Recursive data structures (trees, linked lists, nested JSON),
recursive algorithms, grammars, expression evaluators.

**Examples**:
- Tree depth: `depth(leaf) == 0` and `depth(node(l, r)) == 1 + max(depth(l), depth(r))`
- BST property: base case (empty tree is valid BST) + inserting into valid BST yields valid BST
- Expression evaluation: literals evaluate correctly + compound expressions evaluate correctly
  if subexpressions do
- List reversal: `reverse([]) == []` and `reverse([x, ...xs]) == [...reverse(xs), x]`

**Generator note**: For inductive properties, you need generators that produce recursive
structures. Use `letrec` (fast-check) or `deferred`/recursive strategies to build trees,
nested lists, etc. Cap the depth to keep tests fast.

**Template**:
```
Base: property holds for atomic/empty structure
Step: if property holds for substructures, it holds for the composed structure
```

### Completeness

The function handles all possible inputs in its domain without crashing or producing
undefined behavior.

**When to look for it**: Parsers, validators, API handlers, user input processing —
anywhere that receives external input.

**Examples**:
- `parse(anyString)` either returns a valid result or a well-formed error — never throws
- `validate(anyInput)` returns true or a list of errors — never crashes
- `handleRequest(anyRequest)` returns a valid HTTP response — never hangs

**This is the "fuzz testing" property** — it's weak (doesn't check correctness) but
immediately valuable for finding crashes, panics, and unhandled edge cases.

**Template**:
```
For all inputs X in the domain:
  f(X) does not throw/panic/crash AND returns a value in the expected type
```

---

## Testing Strategies

### Metamorphic Relations

You don't know the expected output for a given input, but you know how the output must
change when the input is transformed in a specific way.

**When to look for it**: ML models, search engines, numerical computations, graphics
rendering, optimization algorithms — any function where computing the expected output
is as hard as implementing the function itself.

**Examples**:
- Search: adding a document that matches the query shouldn't decrease result count
- `sin(pi - x) == sin(x)` — you don't need the exact value of `sin(1.234)` to verify this
- Image resize: `resize(resize(img, 2x), 0.5x)` should approximate original dimensions
- Compiler optimization: `optimize(code)` must produce same outputs as `code` for all inputs
- Sort stability: sorting already-sorted data by a secondary key preserves primary ordering
- ML: `predict(louder_audio)` should equal `predict(audio)` for speech-to-text

**This is one of the most powerful patterns** because it works even when you can't compute
expected outputs. It catches bugs in the relationship between inputs and outputs.

**Template**:
```
For all valid inputs X:
  if f(X) = Y, then f(transform(X)) relates to Y in a known way
```

### Boundary Values

Test with extreme or edge case inputs. Not a "property" per se, but a generator design
strategy that makes other properties much more effective.

**Key boundaries to cover**:
- Empty collections, empty strings
- Single-element collections
- Zero, negative zero, MIN_INT, MAX_INT, NaN, Infinity
- Unicode: null bytes, emojis, RTL characters, combining characters
- Strings: `__proto__`, `constructor`, `toString` (prototype pollution vectors)
- Dates: epoch, year 2038, leap seconds, DST transitions
- Collections at capacity limits

**Generator design**: Most good PBT frameworks bias toward these automatically. But verify —
run your generator 1000 times and check that you actually see empty collections, zeros, etc.

### Equivalence Partitioning

Divide the input domain into classes where behavior should be uniform within each class,
and test representatives from each class.

**When to look for it**: Functions with conditional branches, status codes, category-based
logic, tax brackets, permission levels.

**Examples**:
- Age validation: under 0, 0-12, 13-17, 18-64, 65+, over 150
- HTTP status handling: 1xx, 2xx, 3xx, 4xx, 5xx
- File type processing: text, image, video, unknown

**Generator design**: Use `oneof` / `sampled_from` to ensure each equivalence class gets
tested, rather than hoping random generation covers them all.

### Analogy / Oracle / Differential Testing

Compare your implementation against a known-correct reference.

**When to look for it**: Optimized implementations (compare against naive version),
reimplementations (compare against original), algorithm implementations (compare against
standard library).

**Examples**:
- Custom sort vs. `Array.prototype.sort`
- Hand-rolled JSON parser vs. `JSON.parse`
- Optimized matrix multiply vs. naive triple loop
- New database query engine vs. old one
- Your SIMD implementation vs. scalar reference

**The oracle must be independently, obviously correct.** If implementing the oracle requires
as much code as the SUT, it's not an oracle — it's a second implementation with its own bugs.

**Template**:
```
For all valid inputs X:
  f_optimized(X) == f_reference(X)
```
