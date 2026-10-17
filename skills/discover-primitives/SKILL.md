---
name: discover-primitives
description: Find the implicit primitives an existing codebase already built without naming them — what to extract, document, or just name.
argument-hint: "[paths or area to focus on]"
disable-model-invocation: true
---

Apply the reference below to this codebase. Focus: $ARGUMENTS (default: whole repo).

Process:
1. First pass: explore and list the candidate implicit primitives, with file:line evidence.
2. Second pass: spawn 2-5 opus subagents in parallel to explore further and challenge or extend the list.
3. For each primitive: extract / document / name / leave alone, with the reason.
4. Write both passes into `docs/discovered-primitives.md`. In chat, give only the top findings and the path.

---

# Discovering Primitives in Existing Code

## Philosophy

Codebases grow organically. Features get built, deadlines get met, and the code moves on. But hidden in that growth are often **implicit primitives**—mechanisms that emerged to solve one problem but quietly span a larger space than anyone noticed.

Discovery is the practice of seeing those hidden primitives: the abstraction that's already 80% there, the pattern that repeats with unnecessary variation, the configuration that's secretly a DSL, the function that everything depends on but nobody named.

**Why this matters:**
- You can't compose what you can't see
- Extracting implicit primitives turns sprawl into leverage
- Understanding a codebase's *actual* building blocks (vs. its intended architecture) tells you where it wants to go
- The best extension points are often already present—just unrecognized

**Core reframe:**
> Don't ask "what should I build?" Ask "what has this code already built without knowing it?"

---

## When to Apply

Use this pattern when:

1. **You're about to build something new** → Before writing code, ask: "Has this codebase already solved a version of this problem? Is there a hidden primitive I could surface instead of building from scratch?"

2. **You've inherited or entered an unfamiliar codebase** → The stated architecture (folders, docs, diagrams) often doesn't match the *actual* load-bearing structures. Discovery finds what the code *really* relies on.

3. **You notice repeated patterns with slight variations** → Copy-paste-modify is the fingerprint of an implicit primitive. Three implementations that do "almost the same thing" are one primitive waiting to be named.

4. **You're about to refactor or consolidate** → Before collapsing code, understand what primitive it's reaching for. Bad refactors merge things that *look* similar but vary on different axes.

5. **You want to extend something and can't find the seam** → The extension point may exist—just unnamed. Discovery surfaces where the code is already flexible, even if accidentally.

6. **Configuration has grown complex or weird** → Complex config is often a latent DSL. Discovery asks: "What language is this config file secretly speaking?"

---

## Recognition: Finding What's Already There

The hard part isn't reading code—it's seeing past what it *says* it does to what it's *actually* doing. Use these heuristics:

### Look for the load-bearing functions

Every codebase has a handful of functions/classes that everything flows through. These aren't always named as primitives—they might be called `processItem` or `handleRequest`—but they're doing primitive work.

**Signals:**
- High fan-in (many callers)
- Survives refactors (too risky to change)
- Parameters have grown over time
- Has comments like "don't touch this" or lengthy explanations

### Hunt for repeated shapes

When you see similar code in multiple places, ask: "What's the same, and what varies?" The *same* part is the implicit primitive. The *varying* part is the hidden variable it doesn't know it has.

| What you see | The implicit primitive | The hidden variable |
|--------------|------------------------|---------------------|
| Three functions that fetch-then-transform-then-cache | A pipeline executor | The transform step |
| Multiple `if (type === 'X')` switches across files | A type-based dispatcher | The type → behavior mapping |
| Copy-pasted validation with different field names | A validation rule engine | The field rules |
| Several retry loops with different backoff logic | A retry policy executor | The backoff strategy |

### Follow the flags and modes

Parameters named `mode`, `type`, `kind`, `strategy`, `options`, or boolean flags like `useNewBehavior` are markers of a primitive trying to emerge. The code is acknowledging variability but handling it through branching instead of composition.

Ask: "What if this flag were a first-class thing the caller could define, not just choose from?"

### Read the tests

Tests reveal seams. Look at:
- **What gets mocked** — Those are the code's actual dependencies, which may differ from the stated architecture
- **What fixtures exist** — These represent the "kinds of things" the system thinks it handles
- **Where tests are brittle** — Tight coupling points to primitives that aren't properly separated

### Inspect the config

Complex configuration often encodes a primitive that never got extracted into code:
- Config that's grown conditional logic (even via YAML anchors or env-var switches)
- Config that users treat as a programming language
- Config with repeated structures that only vary in a few fields

This is a DSL that didn't know it was a DSL. The config schema *is* the primitive's interface.

### Notice the workarounds

When users or developers route around the official architecture, they're showing you:
- Where the primitives are too rigid
- Where the actual extension points are (vs. the intended ones)
- What flexibility the system has that isn't surfaced

**Signals:** "Escape hatch" parameters, callback hooks that do heavy lifting, subclasses that override everything, monkey-patching, config that disables features so external tools can replace them.

---

## Excavation Method

Once you've spotted a candidate, run this process to understand it fully and assess its potential.

### 1. Name it

Implicit primitives don't have names—or have misleading ones. Giving it a name is the first act of making it real.

Ask:
- What job is this actually doing? (Not what it's called, what it *does*)
- If I extracted this into a library, what would I call it?
- What's the noun for the thing it manages or the verb for the operation it performs?

**Example:** A function called `processOrder` that actually handles validation, transformation, and conditional routing based on order type isn't a processor—it's a **pipeline with pluggable stages** or a **type-based dispatcher**.

### 2. Map its true boundaries

The code's stated interface (function signature, class API) often doesn't match its *actual* primitive boundary.

Ask:
- What does it *really* depend on? (Not imports—actual runtime dependencies)
- What does it *really* produce? (Not return type—actual effects)
- Where does its logic actually start and end? (Often bleeds into callers or callees)
- What's inside the boundary that shouldn't be? (Hardcoded policies, specific cases)
- What's outside that should be inside? (Setup code repeated by every caller)

Draw the boundary you *wish* it had, then note the gaps.

### 3. Identify the hidden variable(s)

Every implicit primitive is managing some dimension of variability—usually without exposing it cleanly.

Ask:
- What's varying across different usages of this code?
- What would *need* to vary if I wanted to use it for a new case?
- What's hardcoded that's secretly a choice?

**Catalog what you find:**

| Aspect | Currently | Hidden variable |
|--------|-----------|-----------------|
| Retry logic | Hardcoded 3 retries, exponential backoff | Retry policy |
| Validation | `if/else` chain for known fields | Validation rules per field |
| Output format | Always JSON | Serialization strategy |

### 4. Assess its current representation

How is the primitive *currently* expressed? This determines how extractable it is.

| Representation | Characteristics | Extraction difficulty |
|----------------|-----------------|----------------------|
| Implicit in control flow | Scattered `if/else`, repeated patterns | Hard—must synthesize from multiple locations |
| Concentrated in one function/class | Single location, but doing too much | Medium—needs untangling |
| Partially extracted | Has an interface, but policies baked in | Easier—widen the interface |
| Config-driven | Behavior varies by configuration | Easiest—config schema is half the primitive |

### 5. Trace composition behavior (or its absence)

Does this primitive compose with anything? How?

Ask:
- What happens when two instances of this pattern interact?
- Is there ordering/precedence? Is it defined or accidental?
- Can you combine, chain, or nest these? What breaks if you try?
- Are there implicit assumptions about "only one of these" that would block composition?

Many implicit primitives have **no composition semantics**—they were built for one use. This is the main gap you'd need to fill to make them truly reusable.

### 6. Evaluate extraction potential

Not everything should be extracted. Assess:

| Question | If yes... |
|----------|-----------|
| Are there 2+ existing usages that would benefit? | Stronger case for extraction |
| Does the hidden variable have clear, finite options? | Extract as config/data |
| Does the hidden variable need open-ended logic? | Extract as strategy/plugin interface |
| Is the boundary clean enough to extract without major refactor? | Lower cost |
| Would extraction require changing many callers? | Higher cost—may need incremental approach |
| Is the primitive's job likely to grow in scope? | Extraction prevents future sprawl |

**Output:** A judgment call—extract now, note for later, or leave alone—with reasoning.

---

## Signs You've Found a Real Primitive

Not every repeated pattern is a primitive worth extracting. Here's how to distinguish genuine primitives from incidental structure.

### It has gravity

Other code is drawn to it. You see:
- Multiple callers doing similar setup before invoking it
- Wrappers and helpers that exist just to make it easier to use
- Workarounds that exist because it doesn't *quite* do what different callers need

The gravity means it's solving a real problem—the workarounds show where its current form is too narrow.

### It has a natural boundary

When you try to draw a line around it, the line feels *right*:
- Dependencies are few and sensible
- You can explain what's "inside" and "outside" without hand-waving
- Extracting it wouldn't leave a tangle of circular references

If the boundary feels arbitrary or keeps shifting, you may be looking at entangled code, not a primitive.

### The hidden variable is real

The dimension of variability you identified actually varies in practice—or would obviously need to for reasonable future cases.

**Real variable:** "Different retry policies for different failure modes" — clearly needed, clearly varies.

**Fake variable:** "Might want to change the logging format someday" — speculative, no current pressure.

### It explains the mess

Good primitives, once named, make previously confusing code make sense:
- "Oh, these five functions are all doing *dispatch-by-type*, just inline"
- "This config file is a *rule engine* for pricing"
- "Every service has a *lifecycle manager* but they all reimplemented it"

If naming the primitive doesn't create an "aha" moment, you may be imposing structure rather than discovering it.

### It suggests its own interface

When you've found a real primitive, the API often writes itself:
- The hidden variable becomes a parameter or strategy object
- The repeated setup becomes the constructor
- The workarounds become the features list

If designing the interface requires lots of arbitrary choices, the primitive may be synthetic.

### It has siblings you didn't notice before

Discovering one primitive often reveals others nearby:
- "If *this* is a primitive, then *that* must be one too"
- Boundaries clarify: "This part is X's job, that part is Y's job"

If the primitive stands alone with no implied neighbors, it might be a one-off—useful but not part of a larger architecture.

---

## When NOT to Extract

Finding an implicit primitive doesn't mean you should extract it. Sometimes the right move is to name it, note it, and leave it alone.

### It's load-bearing but stable

Some implicit primitives are deeply embedded and *working fine*. The cost of extraction:
- Touching code that many things depend on
- Introducing new abstractions that the team must learn
- Creating bugs in previously stable paths

**Heuristic:** If it hasn't needed modification in a long time, and you don't have an immediate use case for its generalization, document your discovery and move on.

### Only one instance exists

A single implementation isn't evidence of a primitive—it's just code. You need at least 2-3 instances to:
- Confirm the pattern is real (not incidental similarity)
- Understand what actually varies
- Validate that the extracted version would serve all cases

**Exception:** If you're *about* to build a second instance, extraction before duplication is reasonable.

### The variations are incidental, not essential

Sometimes code looks similar but is doing fundamentally different jobs:
- Same shape, different domain semantics
- Similar syntax, different failure modes
- Parallel structure that happens to exist but doesn't need to stay in sync

Extracting these creates **false unification**—a primitive that fights its usages instead of serving them.

**Test:** If extracting the primitive would require immediately adding special cases or flags to handle the "exceptions," the variations are probably incidental.

### The hidden variable is speculative

You can see how the code *could* be generalized, but:
- No current caller needs that flexibility
- No concrete future case demands it
- The generalization is driven by aesthetics, not use cases

This is **premature extraction**—you'll likely guess wrong about what needs to vary.

**Heuristic:** Can you name 2-3 real scenarios (not hypothetical) that the extracted primitive would enable? If not, wait.

### Extraction cost exceeds value

Even valid primitives aren't always worth extracting. Consider:

| Factor | Raises cost |
|--------|-------------|
| Many callers to update | Coordination overhead, risk of breakage |
| Primitive boundary is fuzzy | Requires larger refactor to clean up first |
| Team unfamiliar with pattern | Learning curve, potential misuse |
| Codebase is short-lived | Investment won't pay off |

| Factor | Lowers value |
|--------|--------------|
| No new usages anticipated | Extraction serves only existing cases |
| Existing code is readable | Implicit primitive is already understandable |
| Domain is stable | Won't need the flexibility |

**Practical stance:** Sometimes the right deliverable is documentation—"here's the implicit primitive, here's how it works, here's how to add to it"—not a refactor.

### You're the only one who sees it

Primitives are most valuable when shared. If you discover a primitive but:
- The team doesn't recognize it
- It doesn't match how others think about the code
- Explaining it requires extensive context

...then extracting it may create an abstraction that only you can maintain. Consider whether evangelizing the concept should come before extracting the code.

---

## Failure Modes

### 1. Seeing primitives that aren't there

**The trap:** You impose structure from outside rather than discovering structure from within. The "primitive" exists in your mental model, not in the code.

**Smells:**
- Extraction requires fighting the code at every step
- The "instances" you identified don't actually share logic—just superficial shape
- You keep finding exceptions that don't fit the abstraction

**Remedy:** Return to concrete instances. Can you show, line-by-line, the shared mechanism? If the commonality only exists at a high level of description, it's not an extractable primitive.

### 2. Naming the wrong variable

**The trap:** You've found a real primitive, but misidentified what varies. You extract along the wrong axis.

**Example:** You notice several functions that fetch data from different APIs. You extract a "multi-API fetcher" with an `apiType` parameter. But the *real* hidden variable was the error handling strategy—now buried inside each API branch, unextractable.

**Smells:**
- After extraction, callers still need to do similar setup or post-processing
- The primitive has a "type" or "kind" parameter with a growing switch statement inside
- New cases require modifying the primitive, not just configuring it

**Remedy:** When you identify a hidden variable, ask: "Is there a *deeper* variable this one depends on?" Map the full space of variation before committing to an extraction.

### 3. Extracting the wrapper, not the primitive

**The trap:** You extract the code that *uses* the primitive, not the primitive itself. You've captured a specific policy, not a general mechanism.

**Example:** You find a "notification sender" used in several places. You extract it. But it hardcodes email as the channel, "immediate" as the timing, and a specific template structure. You've extracted *one notification policy*, not a notification primitive.

**Smells:**
- The extracted code has many hardcoded values that "could be parameters but aren't"
- It only works for the existing cases—new cases require forking, not configuring
- The name describes a specific behavior, not a capability

**Remedy:** Push extraction one level deeper. Ask: "What mechanism would let me *express* this behavior and others like it?"

### 4. Premature formalization

**The trap:** You extract a primitive after seeing only one or two instances. The abstraction calcifies around early examples and fights later ones.

**Smells:**
- Third usage requires "just one more parameter" (and then another, and another)
- You find yourself adding special cases for things that "should" fit but don't
- The primitive's interface grows faster than its capabilities

**Remedy:** Wait for three instances. Let the primitive's shape emerge from real pressure, not imagination.

### 5. Ignoring composition requirements

**The trap:** You extract a primitive that works in isolation but has no story for how multiple instances interact.

**Example:** You extract a "validation rule" primitive. Each rule works great. But when you apply multiple rules, there's no defined order, no way to short-circuit, no way to combine error messages. Every caller reinvents composition logic.

**Smells:**
- Callers wrap the primitive in their own coordination logic
- "How do I use two of these together?" has no good answer
- Ordering or precedence is implicit or accidental

**Remedy:** Composition semantics are part of the primitive, not an afterthought. Before extracting, ask: "What happens when there are two of these? Ten? Zero?"

### 6. Over-extracting stable code

**The trap:** You extract a primitive from working code to make it "cleaner," but the extraction itself introduces risk and maintenance burden with no corresponding benefit.

**Smells:**
- The code was stable and rarely modified
- No new use cases are waiting for the extraction
- The extraction creates new files, new concepts, new indirection—but the same behavior
- You're the only one who wanted this change

**Remedy:** Extraction should be pulled by demand, not pushed by aesthetics. If the implicit primitive is working fine implicitly, consider documenting it instead of extracting it.

### 7. Extracting into the wrong layer

**The trap:** You find a real primitive but place it at the wrong level of the architecture. Too low, and higher layers can't use it without reaching down. Too high, and it drags dependencies everywhere.

**Smells:**
- Using the extracted primitive requires importing unrelated modules
- It "almost" fits in multiple places but isn't quite right for any
- Circular dependencies emerge or threaten to emerge

**Remedy:** Before extraction, map where the primitive's consumers live and where its dependencies live. The primitive belongs at the lowest layer that can access its dependencies while remaining accessible to its consumers.

---

## Summary

| Instead of asking... | Ask... |
|---------------------|--------|
| "What does this code do?" | "What capability is this code providing—and to whom?" |
| "Why is this duplicated?" | "What primitive is trying to emerge from this duplication?" |
| "What's this function's purpose?" | "What's the job, what's the hidden variable, and where's the real boundary?" |
| "How do I add a new case here?" | "What's the implicit primitive I should be extending, not forking?" |
| "This config is complicated—how does it work?" | "What DSL is this config secretly encoding?" |
| "Why do all these callers do similar setup?" | "What's the primitive they wish they had?" |
| "What's the architecture of this codebase?" | "What are the *actual* load-bearing abstractions, named or not?" |

---

**The goal is recognition before construction.**

Every codebase contains primitives it doesn't know it has—mechanisms that emerged to solve specific problems but quietly generalized beyond their original scope. Discovery is the practice of seeing them.

Some you extract. Some you document. Some you simply name—so that the next person to touch the code can see what you saw.

The implicit primitive, once recognized, shapes every decision that follows: where to extend, where to refactor, where to leave alone. You can't compose what you can't see.