---
name: composable-architecture
description: >
  Provides guidance for high quality architecture and feature development.
  Use this when: User requests a specific feature, You're designing a new
  system or module, You see the same shape of problem appearing repeatedly,
  User explicitly asks for extensible or composable design, You're tempted
  to add a flag or parameter to an existing function
---

# Primitives Over Features

## Philosophy

When asked to add a feature, don't build the feature. Build the smallest mechanism that makes the feature—and many others like it—expressible.

**Alternate framings (same idea):**

- Mechanism vs. Policy: The system provides _what's possible_; configuration/callers decide _what happens_
- Find the generative core: The smallest set of orthogonal primitives whose compositions span the space of behaviors
- Build the language, not the script: Don't write the solution; write the thing that lets solutions be written

## When to Apply

Use this pattern when:

1. **User requests a specific feature** → Ask: "Is this an instance of something more general?"
2. **You're designing a new system or module** → Ask: "What's the space of behaviors this should support?"
3. **You see the same shape of problem appearing repeatedly** → Multiple requests that feel similar are signaling a missing primitive
4. **User explicitly asks for extensible or composable design**
5. **You're tempted to add a flag or parameter to an existing function** → Often indicates a policy being baked into mechanism

## Recognition: Finding the Hidden Space

The hard part is seeing that specific requests are instances of a general space. Use these heuristics:

### Ask "What varies?"

Every feature request encodes an assumption about what's fixed and what's variable. Challenge the fixed parts.

| Request                     | Surface variable | Hidden variable                |
| --------------------------- | ---------------- | ------------------------------ |
| "Add vim mode"              | Key bindings     | Input meaning depends on state |
| "Add Black Friday discount" | Discount amount  | Price modification rules       |
| "Email when task is due"    | Email content    | Event → condition → action     |

### Collect before abstracting

Don't extract primitives from one example. Wait until you have 2-3 concrete instances, then ask: "What's the smallest thing that would make all of these expressible?"

### Look for hardcoded conditionals

`if (user.role == 'admin')`, `if (vendor == 'VendorA')`, `if (mode == 'vim')` — these are policies masquerading as mechanism. The conditional's subject hints at the missing primitive.

### Notice the escape hatches

When users request "just let me override X" or "add a hook for Y," they're telling you where your mechanism is too rigid or where policy leaked in.

## Extraction Method

When you've identified a candidate space, run this loop:

### 1. Name the hidden variable

What dimension of variability is the request really asking for?

### 2. Extract the minimal mechanism

What is the smallest general machine that can express many instances of that variability?

Good primitives are:

- **Orthogonal**: Each does one job
- **Composable**: They combine predictably
- **Deep**: Small interface, large capability space (Ousterhout's "deep modules")

### 3. Choose the least-powerful representation

| Power level              | Use when                                           | Watch out for                          |
| ------------------------ | -------------------------------------------------- | -------------------------------------- |
| Data/config (JSON, YAML) | Finite, enumerable options                         | Walls when users need logic            |
| Constrained DSL          | Need conditions/expressions but want analyzability | Language creep over time               |
| Scripting/plugins        | Genuinely open-ended extension                     | Unpredictable behavior, harder tooling |

**Default stance:** Start with the least powerful option that works. Require explicit opt-in to escalate. The W3C "Rule of Least Power" applies: constrained languages improve reuse and tooling.

**The tradeoff:** Too constrained → users hit walls, demand escape hatches. Too powerful → unpredictable behavior, no static analysis. There's no universal answer; evaluate per-domain.

### 4. Define composition laws

Primitives without composition semantics create chaos. Specify:

- **Precedence/override rules**: What wins when primitives conflict?
- **Scoping rules**: What's the boundary of each primitive's effect?
- **Defaults + escape hatches**: What happens when nothing matches?

Example (Ghostty key tables): Stack of tables, inner-to-outer lookup, explicit `catch_all`, one-shot variant. You can predict behavior from these rules alone.

### 5. Ship recipes, not features

Validate by expressing 1-2 concrete use cases as compositions of your primitives. These become documentation, not baked-in behaviors.

## Worked Example

**Request:** "Add a Black Friday discount—20% off everything"

**Step 1: Name the hidden variable**
This isn't about Black Friday. It's about _price modifications_. Other instances: loyalty discounts, bulk pricing, promo codes, regional pricing.

**Step 2: Extract mechanism**
A price modification has:

- **Conditions**: When does it apply? (date range, user segment, cart contents, promo code)
- **Effect**: What does it do? (percentage off, fixed amount, set price)
- **Priority**: What wins when multiple apply?

Mechanism: A rules engine that evaluates conditions and applies effects.

**Step 3: Choose representation**
Conditions are combinatorial but finite. Start with declarative rules:

```yaml
- name: black-friday-2024
  conditions:
    date: { after: "2024-11-29", before: "2024-11-30" }
  effect: { percent_off: 20 }
  priority: 100
```

If users need custom logic (e.g., "10% off if cart contains items from 3+ categories"), provide a constrained expression language—not arbitrary code.

**Step 4: Composition laws**

- Rules evaluated in priority order
- First matching rule wins (or: all matching rules stack—choose one)
- No match → base price

**Step 5: Ship recipes**
"Black Friday" is now a row in the rules table. Document it as an example, not a feature.

**Result:** Next request ("add promo codes") is a config change, not a code change.

## Signs You've Found Good Primitives

1. **Unanticipated compositions work**: Users do things you never imagined, and they just work
2. **Features become configurations**: What would have been a PR becomes a config example
3. **Primitives explain each other**: Higher-level concepts decompose cleanly into lower-level ones
4. **Removal is possible**: "Don't do X" is expressible by not composing something, rather than adding a flag

## When NOT to Use This Pattern

**Don't over-engineer when:**

- **It's a one-off**: Prototypes, scripts, exploratory code. The overhead of extraction isn't worth it.
- **The space has exactly one point**: If you're confident there will never be a second instance, just build the feature.
- **You're guessing at the space**: Premature abstraction is worse than no abstraction. Wait for concrete instances.
- **The domain is genuinely simple**: Not everything needs a rules engine. Sometimes `if/else` is the right answer.

**Heuristic:** If you can't name 2-3 other instances that your primitive would support, you're probably abstracting too early.

## Failure Modes

### 1. "Primitives" that are secretly policy

The primitive bakes in today's workflow and blocks tomorrow's.

_Smell:_ The primitive has parameters like `isBlackFriday` or `vendorType`.

### 2. Too-powerful extension too early

You ship a scripting language because you can't predict needs. Now behavior is unpredictable and tooling is impossible.

_Smell:_ "Users can write arbitrary code to handle this."

### 3. No composition semantics

Hooks and events everywhere, but unclear ordering, conflicts, or precedence.

_Smell:_ "It depends on registration order" or "we're not sure what happens if both fire."

### 4. Shallow primitives

Tons of tiny knobs that don't combine into real leverage. Configuration explosion without expressive power.

_Smell:_ Adding a new use case requires adding new primitives rather than composing existing ones.

### 5. Refusing to escalate

Sticking with a constrained representation when users genuinely need more power, forcing workarounds.

_Smell:_ Users encoding programs in your config format, or requesting the same escape hatch repeatedly.

## Summary

| Instead of...                   | Ask...                                                              |
| ------------------------------- | ------------------------------------------------------------------- |
| "How do I add this feature?"    | "What's the capability that makes this feature possible?"           |
| "How do I implement this rule?" | "What's the structure of rules in this domain?"                     |
| "How do I handle this case?"    | "What's the space of cases, and how do I let callers specify them?" |

The goal is **inversion of control**: don't write the script; write the language in which scripts are written.
