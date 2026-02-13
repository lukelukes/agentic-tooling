---
name: analyzing-illegal-states
description: Analyzes code for violations of "make illegal states unrepresentable". Use when reviewing code for type safety, domain modeling issues, or when asked to find places where invalid runtime states could be eliminated through better type design.
---

# Analyzing Illegal States

Identify places where the type system permits invalid runtime states that could be eliminated at compile time through better modeling.

## Workflow

```
Analysis Progress:
- [ ] Identify language and type system capabilities
- [ ] Scan for violation patterns
- [ ] Assess severity of each violation
- [ ] Generate refactored alternatives
- [ ] Summarize high-impact fixes
```

## Violation categories

### boolean-blindness
Multiple boolean flags creating impossible combinations. Type permits 2^n states but only subset valid.

```typescript
// violation: permits { isLoading: true, isError: true, data: value }
{ isLoading: boolean, isError: boolean, data: T | null }

// fix: discriminated union
type State = { status: 'loading' } | { status: 'error', error: Error } | { status: 'success', data: T }
```

### primitive-obsession
Primitives for constrained domain concepts. Permits invalid values, conflates unrelated concepts.

```typescript
// violation
userId: string; email: string; port: number;

// fix: branded/newtype wrappers
type UserId = string & { readonly __brand: 'UserId' };
type Email = string & { readonly __brand: 'Email' };
type Port = number & { readonly __brand: 'Port' }; // + smart constructor
```

### stringly-typed
Strings for known finite sets. No exhaustiveness checking, permits typos.

```typescript
// violation
status: string; // "pending" | "approved" | "rejected"

// fix
type Status = 'pending' | 'approved' | 'rejected';
```

### nullable-ambiguity
Null conflates distinct semantic states or creates invalid field combinations.

```typescript
// violation: both null or both non-null are invalid
{ error: Error | null, data: T | null }

// fix
type Result<T> = { ok: true, data: T } | { ok: false, error: Error }
```

### invalid-state-transitions
State machine permits invalid transitions. Operations available regardless of current state.

```typescript
// violation: send() callable before connect()
class Connection { connect(); send(data); disconnect(); }

// fix: typestate pattern
class Disconnected { connect(): Connected; }
class Connected { send(data): Connected; disconnect(): Disconnected; }
```

### unconstrained-collections
Collections permit invalid cardinality or composition.

```typescript
// violation: permits empty when non-empty required
recipients: string[]

// fix
type NonEmptyArray<T> = [T, ...T[]];
recipients: NonEmptyArray<Email>
```

### weakly-typed-variants
Base types requiring runtime checks instead of discriminated unions with exhaustiveness.

```typescript
// violation: requires instanceof chains
interface Shape { area(): number }

// fix: discriminated union
type Shape =
  | { kind: 'circle', radius: number }
  | { kind: 'rect', width: number, height: number }
```

### implicit-invariants
Field relationships enforced only by comments or runtime checks.

```typescript
// violation: "endDate must be after startDate"
{ startDate: Date, endDate: Date }

// fix: smart constructor returning Result, or
type DateRange = { start: Date, end: Date } & { __validated: true }
```

### partial-data-modeling
Same type for unvalidated input and validated domain objects.

```typescript
// violation: User type used for form input AND database record

// fix: separate types
type UserInput = { email: string, name: string }
type ValidatedUser = { id: UserId, email: Email, name: string }
```

### temporal-coupling
Methods must be called in specific order with nothing preventing incorrect ordering.

```typescript
// violation: build() callable before required fields set
builder.setName("x").build() // missing required email

// fix: builder with type-level tracking or separate staged types
```

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
- **CRITICAL**: Runtime crashes, data corruption, security vulnerabilities
- **HIGH**: Likely bugs, requires significant discipline to avoid
- **MEDIUM**: Suboptimal but unlikely severe issues
- **LOW**: Improvements would enhance clarity, current code defensible

## Summary format

After listing violations:

1. Counts by severity
2. Highest-ROI refactoring opportunities
3. Language-specific recommendations (compiler flags, linter rules)

## Guidelines

- Adapt to language capabilities—don't suggest Rust-level strictness for Python
- Core domain violations more severe than peripheral utilities
- Runtime checks at external boundaries are legitimate
- Don't flag legitimate flexibility—catch modeling errors, not enforce max rigidity
- If code is well-modeled, say so
