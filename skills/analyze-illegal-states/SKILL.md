---
name: analyze-illegal-states
description: Analyzes code for violations of "make illegal states unrepresentable". Use when reviewing code for type safety, domain modeling issues, or when asked to find places where invalid runtime states could be eliminated through better type design. Also use this skill when the user asks to "improve types", "tighten types", "make types stricter", review code for "impossible states" or "invalid states", or when you notice boolean-flag soup, stringly-typed enums, nullable ambiguity, or other modeling smells during a code review or refactoring task. Trigger on mentions of sum types, discriminated unions, algebraic data types, or typestate patterns.
---

# Analyzing Illegal States

Identify places where the type system permits invalid runtime states that could be eliminated at compile time through better modeling.

## Scanning strategy

Violations cluster in predictable places. Start here:

1. **Config and options objects** — boolean flags, string-typed enums, nullable fields with implicit dependencies
2. **API response / request types** — data/error/loading combinations, partial vs validated data
3. **State machines** — order status, connection lifecycle, workflow stages where operations should only be available in certain states
4. **DTOs and boundary types** — same type used for unvalidated input and validated domain objects
5. **Core domain models** — these carry the highest severity because they propagate through the entire system

Look for these signals: multiple booleans on the same type, `| null` chains, `string` where only a few values are valid, comments describing field relationships or call ordering.

## Violation categories

### boolean-blindness
Multiple boolean flags creating impossible combinations. Type permits 2^n states but only a subset are valid.

```typescript
// violation: permits { isLoading: true, isError: true, data: value }
{ isLoading: boolean, isError: boolean, data: T | null }

// fix: discriminated union
type State = { status: 'loading' } | { status: 'error', error: Error } | { status: 'success', data: T }
```

### primitive-obsession
Primitives for constrained domain concepts. Permits invalid values, conflates unrelated concepts.

```typescript
// violation: userId and email are interchangeable strings, port allows negatives/floats
userId: string; email: string; port: number; currency: string;

// fix: branded/newtype wrappers
type UserId = string & { readonly __brand: 'UserId' };
type Email = string & { readonly __brand: 'Email' };
type Port = number & { readonly __brand: 'Port' }; // + smart constructor validating 0-65535
type Currency = 'USD' | 'EUR' | 'GBP'; // finite set of ISO codes
```

### stringly-typed
Strings for known finite sets. No exhaustiveness checking, permits typos.

```typescript
// violation: typo compiles fine — if (status === "pendng")
status: string; // "pending" | "approved" | "rejected"

// fix
type Status = 'pending' | 'approved' | 'rejected';
```

### nullable-ambiguity
Null conflates distinct semantic states or creates invalid field combinations.

```typescript
// violation 1: both null or both non-null are invalid
{ error: Error | null, data: T | null }

// violation 2: null conflates "not deleted" with "deletion date unknown"
{ deletedAt: Date | null }

// violation 3: fields that must be present together or not at all
{ shippedAt: Date | null, trackingNumber: string | null }

// fix: sum types for mutually exclusive states, nested structs for co-dependent fields
type Result<T> = { ok: true, data: T } | { ok: false, error: Error }
type Deletion = { deleted: false } | { deleted: true, deletedAt: Date }
type Shipping = { shipped: false } | { shipped: true, shippedAt: Date, trackingNumber: string }
```

### invalid-state-transitions
State machine permits invalid transitions. Operations available regardless of current state.

```typescript
// violation: send() callable before connect()
class Connection { connect(); send(data); disconnect(); }

// fix: typestate pattern — each state is a separate type
class Disconnected { connect(): Connected; }
class Connected { send(data): Connected; disconnect(): Disconnected; }
```

### unconstrained-collections
Collections permit invalid cardinality or composition.

```typescript
// violation 1: permits empty when non-empty required
recipients: string[]

// violation 2: loses structural meaning
coordinates: number[] // is it [x, y]? [lat, lng, alt]?

// violation 3: erases all type information
config: Map<string, any>

// fix
type NonEmptyArray<T> = [T, ...T[]];
recipients: NonEmptyArray<Email>
type Point2D = { x: number, y: number }
```

### weakly-typed-variants
Base types requiring runtime checks instead of discriminated unions with exhaustiveness.

```typescript
// violation 1: requires instanceof chains
interface Shape { area(): number }

// violation 2: overlapping unions without discriminant
type Result = Success | Failure; // how do you tell which is which?

// fix: discriminated union with literal tag
type Shape =
  | { kind: 'circle', radius: number }
  | { kind: 'rect', width: number, height: number }
```

### implicit-invariants
Field relationships enforced only by comments or runtime checks.

```typescript
// violation: "endDate must be after startDate", "denominator must not be zero"
{ startDate: Date, endDate: Date }
{ numerator: number, denominator: number }
{ min: number, max: number } // implicit min <= max

// fix: smart constructor returning Result, or validated wrapper type
type DateRange = { start: Date, end: Date } & { __validated: true }
function createDateRange(start: Date, end: Date): DateRange | Error { ... }
```

### partial-data-modeling
Same type for unvalidated input and validated domain objects.

```typescript
// violation: User type used for form input AND database record
interface User { id: string, email: string, name: string }

// fix: separate types per lifecycle stage
type UserInput = { email: string, name: string }
type ValidatedUser = { id: UserId, email: Email, name: string, createdAt: Date }
```

### temporal-coupling
Methods must be called in specific order with nothing preventing incorrect ordering.

```typescript
// violation: build() callable before required fields set
builder.setName("x").build() // missing required email

// fix: builder with type-level tracking or separate staged types
type BuilderWithName = { setEmail(e: Email): BuilderReady }
type BuilderReady = { build(): User }
```

## Language adaptation

The examples above are TypeScript, but the patterns apply across languages. Adapt your suggestions to what the target language actually supports — suggesting phantom types in Python or branded types in Go wastes everyone's time.

| Language | Sum types / unions | Branded primitives | Exhaustiveness | Notes |
|---|---|---|---|---|
| **TypeScript** | Discriminated unions | Branded types (`& { __brand }`) | `never` default in switch | Enable `strictNullChecks`, `noUncheckedIndexedAccess` |
| **Rust** | `enum` (native sum types) | Newtype pattern (`struct Email(String)`) | Compiler-enforced match | `#[non_exhaustive]` for extensible enums |
| **Go** | Interface + unexported method, or separate structs per state | Defined types (`type UserId string`) | No compiler support — use linters | No generics until 1.18; prefer concrete types |
| **Python** | `Union` + `Literal` from `typing` | No real support — use `NewType` for docs | mypy/pyright check `match` | Pydantic for runtime validation; type checker is optional |
| **Java 17+** | Sealed interfaces/classes | Record types for value objects | Pattern matching in switch (preview) | Consider records + sealed hierarchies |
| **C#** | Abstract records / OneOf library | Record structs | Switch expressions with discard | Native discriminated unions not yet available |

For languages without sum types (Go, older Java), focus on the patterns that *are* expressible: separate types per state, smart constructors, making invalid construction impossible even if invalid values technically compile.

## Output format

For each violation:

```
[SEVERITY] category — location
Description of illegal states permitted.

Current:
<code snippet>

Suggested:
<refactored code>

Tradeoffs: (if any)
```

**Severity criteria:**
- **CRITICAL**: Runtime crashes, data corruption, security vulnerabilities. High likelihood of hitting production.
- **HIGH**: Likely bugs, requires significant discipline to avoid. Common defect source.
- **MEDIUM**: Suboptimal but unlikely to cause severe issues.
- **LOW**: Improvements would enhance clarity, current code defensible.

**Prioritization**: When reporting multiple violations, group by module or domain layer. Flag violations in types that cross module boundaries or appear in public APIs first — fixing these has the highest ROI because they propagate constraints to all consumers.

## Summary format

After listing violations:

1. Counts by severity
2. Highest-ROI refactoring opportunities (which fixes eliminate the most invalid states)
3. Language-specific recommendations (compiler flags, linter rules, libraries)

## Guidelines

- Adapt to language capabilities — suggest only what the language can actually express
- Core domain violations are more severe than peripheral utilities
- Runtime checks at external boundaries are legitimate — API handlers, file parsers, and user input should validate at runtime, not through types alone
- Don't flag legitimate flexibility — catch modeling errors, not enforce maximum rigidity
- Back off when appropriate: rapid prototyping, scripts, performance-critical hot paths where wrapper types add overhead, or interop with untyped libraries
- If code is well-modeled, say so — don't manufacture violations
