# Model-Based Testing

Model-based testing is the most powerful property-based testing technique for stateful systems.
The core idea: build an embarrassingly simple model of your system and verify that the real
implementation stays synchronized with it under random operation sequences.

## Table of Contents

1. [The Pattern](#the-pattern)
2. [When To Use It](#when-to-use-it)
3. [Designing the Model](#designing-the-model)
4. [Framework-Specific APIs](#framework-specific-apis)
5. [Stateful Testing Patterns](#stateful-testing-patterns)
6. [Common Mistakes](#common-mistakes)

---

## The Pattern

```
┌─────────────┐     generate random     ┌─────────────┐
│   Command    │ ←── command sequence ── │  Framework   │
│  Sequence    │                         │  (shrinks    │
│              │                         │   on fail)   │
└──────┬───────┘                         └──────────────┘
       │
       │  for each command:
       ▼
┌──────────────────────────────────────────┐
│  1. Check precondition against model     │
│  2. Execute command on real system       │
│  3. Execute command on model             │
│  4. Assert postconditions                │
│  5. Assert invariants                    │
└──────────────────────────────────────────┘
```

When the test fails, the framework shrinks the command sequence to a minimal reproduction.
A 50-step failure might shrink to 3 steps.

## When To Use It

Model-based testing shines when the system has **non-functional complexity** layered on top of
simple domain logic:

- **Caches**: Simple map as model, verify cache returns same values as direct computation
- **Databases**: In-memory map as model, verify CRUD operations match
- **Queues/buffers**: Python list as model, verify ordering and capacity
- **Connection pools**: Counter as model, verify allocation/release semantics
- **State machines**: Enum + transition map as model, verify valid transitions
- **File systems**: Nested dict as model, verify directory operations
- **Concurrent data structures**: Sequential reference as model, verify linearizability

It's less useful when the domain logic itself is complex — if the model needs to be nearly
as complex as the real implementation, you're just writing the code twice.

## Designing the Model

The model must be:

1. **Obviously correct** — simple enough that bugs in it are immediately visible
2. **Much simpler than the real system** — typically 10-50 lines
3. **State-equivalent** — tracks the same logical state, just without the non-functional concerns

Example for a key-value cache with TTL:

```
Real system: Redis-backed cache with LRU eviction, TTL, connection pooling, retry logic
Model: a Python dict with timestamps — {key: (value, expire_time)}
```

The model ignores LRU eviction, connection pooling, and retry logic. It only models the
core semantics: "keys map to values and expire after TTL."

## Framework-Specific APIs

### TypeScript / fast-check

fast-check uses a command pattern with `fc.commands()`:

```typescript
import fc from "fast-check";

// 1. Define your model type
type Model = { items: Map<string, number> };

// 2. Define commands
class SetCommand implements fc.Command<Model, RealCache> {
  constructor(readonly key: string, readonly value: number) {}

  check(m: Readonly<Model>) {
    return true; // precondition: always valid
  }

  run(m: Model, real: RealCache) {
    // Update model
    m.items.set(this.key, this.value);
    // Execute on real system
    real.set(this.key, this.value);
    // Assert postcondition
    expect(real.get(this.key)).toBe(this.value);
  }

  toString() {
    return `set(${this.key}, ${this.value})`;
  }
}

class GetCommand implements fc.Command<Model, RealCache> {
  constructor(readonly key: string) {}

  check(m: Readonly<Model>) {
    return m.items.has(this.key); // precondition: key exists
  }

  run(m: Model, real: RealCache) {
    const expected = m.items.get(this.key);
    const actual = real.get(this.key);
    expect(actual).toBe(expected);
  }

  toString() {
    return `get(${this.key})`;
  }
}

class DeleteCommand implements fc.Command<Model, RealCache> {
  constructor(readonly key: string) {}

  check(m: Readonly<Model>) {
    return true;
  }

  run(m: Model, real: RealCache) {
    m.items.delete(this.key);
    real.delete(this.key);
    expect(real.has(this.key)).toBe(false);
  }

  toString() {
    return `delete(${this.key})`;
  }
}

// 3. Build the command arbitrary
const allCommands = [
  fc.tuple(fc.string(), fc.integer()).map(([k, v]) => new SetCommand(k, v)),
  fc.string().map((k) => new GetCommand(k)),
  fc.string().map((k) => new DeleteCommand(k)),
];

// 4. Run the model-based test
test("cache behaves like a simple map", () => {
  fc.assert(
    fc.property(fc.commands(allCommands, { size: "+1" }), (cmds) => {
      const model: Model = { items: new Map() };
      const real = new RealCache();
      fc.modelRun(() => ({ model, real }), cmds);
    })
  );
});
```

Key points:
- `check()` is the precondition — return `false` to skip commands that are invalid in the current state
- `run()` executes on both systems and asserts postconditions
- `toString()` is critical for readable failure output — shrunk sequences need to be understandable
- `fc.commands()` generates and shrinks command sequences as a unit

For async systems, use `fc.asyncModelRun()`. For race condition detection, use
`fc.scheduledModelRun()` — this is unique to fast-check and systematically shuffles promise
resolution order to find concurrency bugs.

### Python / Hypothesis

Hypothesis uses `RuleBasedStateMachine`:

```python
from hypothesis import given, settings
from hypothesis.stateful import (
    RuleBasedStateMachine,
    rule,
    invariant,
    precondition,
    initialize,
    Bundle,
)
import hypothesis.strategies as st

class CacheStateMachine(RuleBasedStateMachine):
    """Model-based test: real cache vs. dict model."""

    def __init__(self):
        super().__init__()
        self.model = {}
        self.real = RealCache()

    keys = Bundle("keys")

    @initialize(target=keys)
    def init_key(self):
        """Seed the key bundle with an initial key."""
        return "init"

    @rule(target=keys, key=st.text(min_size=1, max_size=10), value=st.integers())
    def set_item(self, key, value):
        self.model[key] = value
        self.real.set(key, value)
        assert self.real.get(key) == value
        return key

    @rule(key=keys)
    def get_item(self, key):
        expected = self.model.get(key)
        actual = self.real.get(key)
        assert actual == expected, f"get({key}): expected {expected}, got {actual}"

    @rule(key=keys)
    def delete_item(self, key):
        self.model.pop(key, None)
        self.real.delete(key)
        assert self.real.get(key) is None

    @invariant()
    def size_matches(self):
        assert len(self.real) == len(self.model)

# Run the test
TestCache = CacheStateMachine.TestCase
```

Key points:
- `Bundle` lets data flow between rules — `set_item` produces keys that `get_item` consumes
- `@invariant()` is checked after every rule execution
- `@precondition(lambda self: ...)` guards rules that are only valid in certain states
- `@initialize` runs once at the start to set up initial state
- Hypothesis handles shrinking of rule sequences automatically

### Rust / proptest

proptest uses the `proptest-state-machine` crate:

```rust
use proptest::prelude::*;
use proptest_state_machine::{
    prop_state_machine, ReferenceStateMachine, StateMachineTest,
};
use std::collections::HashMap;

// 1. Define transitions
#[derive(Clone, Debug)]
enum Transition {
    Set(String, i64),
    Get(String),
    Delete(String),
}

// 2. Define the reference (model) state machine
#[derive(Clone, Debug, Default)]
struct CacheModel {
    items: HashMap<String, i64>,
}

impl ReferenceStateMachine for CacheModel {
    type State = Self;
    type Transition = Transition;

    fn init_state() -> BoxedStrategy<Self::State> {
        Just(Self::default()).boxed()
    }

    fn transitions(state: &Self::State) -> BoxedStrategy<Transition> {
        let keys: Vec<String> = state.items.keys().cloned().collect();
        let mut strategies: Vec<BoxedStrategy<Transition>> = vec![
            ("[a-z]{1,5}", any::<i64>())
                .prop_map(|(k, v)| Transition::Set(k, v))
                .boxed(),
        ];
        if !keys.is_empty() {
            let keys_clone = keys.clone();
            strategies.push(
                proptest::sample::select(keys_clone)
                    .prop_map(Transition::Get)
                    .boxed(),
            );
            strategies.push(
                proptest::sample::select(keys)
                    .prop_map(Transition::Delete)
                    .boxed(),
            );
        }
        proptest::strategy::Union::new(strategies).boxed()
    }

    fn apply(mut state: Self::State, transition: &Transition) -> Self::State {
        match transition {
            Transition::Set(k, v) => { state.items.insert(k.clone(), *v); }
            Transition::Get(_) => {}
            Transition::Delete(k) => { state.items.remove(k); }
        }
        state
    }

    fn preconditions(state: &Self::State, transition: &Transition) -> bool {
        match transition {
            Transition::Get(k) | Transition::Delete(k) => state.items.contains_key(k),
            _ => true,
        }
    }
}

// 3. Define the test against the real system
struct CacheTest;

impl StateMachineTest for CacheTest {
    type SystemUnderTest = RealCache;
    type Reference = CacheModel;

    fn init_test(_ref_state: &<Self::Reference as ReferenceStateMachine>::State) -> Self::SystemUnderTest {
        RealCache::new()
    }

    fn apply(
        state: Self::SystemUnderTest,
        ref_state: &<Self::Reference as ReferenceStateMachine>::State,
        transition: Transition,
    ) -> Self::SystemUnderTest {
        match &transition {
            Transition::Set(k, v) => {
                state.set(k, *v);
                assert_eq!(state.get(k), Some(*v));
            }
            Transition::Get(k) => {
                let expected = ref_state.items.get(k);
                assert_eq!(state.get(k).as_ref(), expected);
            }
            Transition::Delete(k) => {
                state.delete(k);
                assert_eq!(state.get(k), None);
            }
        }
        state
    }
}

// 4. Run it
prop_state_machine! {
    #[test]
    fn cache_model_test(sequential 1..50 => CacheTest);
}
```

### Go / rapid

rapid uses `t.Repeat()` for stateful testing:

```go
func TestCacheModel(t *testing.T) {
    rapid.Check(t, func(t *rapid.T) {
        model := make(map[string]int)
        real := NewCache()

        t.Repeat(map[string]func(*rapid.T){
            "set": func(t *rapid.T) {
                key := rapid.String().Draw(t, "key")
                val := rapid.Int().Draw(t, "val")
                model[key] = val
                real.Set(key, val)
                if got := real.Get(key); got != val {
                    t.Fatalf("after set(%q, %d): got %d", key, val, got)
                }
            },
            "get": func(t *rapid.T) {
                if len(model) == 0 {
                    return // precondition: need at least one key
                }
                keys := make([]string, 0, len(model))
                for k := range model {
                    keys = append(keys, k)
                }
                key := rapid.SampledFrom(keys).Draw(t, "key")
                expected := model[key]
                got := real.Get(key)
                if got != expected {
                    t.Fatalf("get(%q): expected %d, got %d", key, expected, got)
                }
            },
            "delete": func(t *rapid.T) {
                key := rapid.String().Draw(t, "key")
                delete(model, key)
                real.Delete(key)
                if real.Has(key) {
                    t.Fatalf("key %q still exists after delete", key)
                }
            },
        })
    })
}
```

---

## Stateful Testing Patterns

### Invariants Between Steps

Check properties that must hold after every single operation, not just at the end:

- **Size consistency**: model size always matches real system size
- **No phantom entries**: every key in the real system exists in the model
- **Ordering**: if it's an ordered collection, ordering is maintained after every insert/delete
- **Resource limits**: pool never has more than N active connections

### Precondition Design

Preconditions prevent generating invalid command sequences. Get them right:

- **Too loose**: generates `delete` on empty collections → tests fail for wrong reasons
- **Too tight**: never generates interesting sequences → low coverage
- **Just right**: generates valid sequences that explore edge cases

The precondition must also be checked during shrinking — otherwise the shrinker may produce
an invalid sequence that appears to be a minimal reproduction but isn't actually reachable.

### Data Flow Between Commands

Operations often produce values needed by later operations. Use Bundles (Hypothesis),
constrained generators (fast-check), or shared state (proptest/rapid) to pass data forward:

```python
# Hypothesis: Bundle pattern
keys = Bundle("keys")

@rule(target=keys, key=st.text())
def create(self, key):
    self.real.create(key)
    return key  # Goes into the bundle

@rule(key=keys)  # Draws from the bundle
def read(self, key):
    self.real.read(key)
```

This ensures `read` only receives keys that were actually created — without using `assume`.

---

## Common Mistakes

1. **Model too complex**: If the model is >50 lines, you're probably modeling too much.
   Strip it down to the essential state.

2. **Missing `toString()` / `Debug`**: When a 50-step sequence shrinks to 3 steps, you need
   to be able to read those 3 steps. Always implement readable string representations.

3. **No invariant checks**: Only checking postconditions per-command misses bugs that
   corrupt state without immediately visible effects. Add invariants.

4. **Preconditions checked only during generation**: Preconditions must be re-evaluated
   during shrinking. Frameworks with integrated shrinking handle this automatically.

5. **Not verifying state at the end**: After the command sequence completes, do a full
   comparison of model state vs. real system state — not just per-command checks.
