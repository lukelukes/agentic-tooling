---
name: elicitation-techniques
description: >
  A toolkit of 45 structured thinking techniques for deep analysis, creative exploration, and
  rigorous decision-making. Use this skill whenever the user needs to think through a hard problem,
  make a tough decision, stress-test an idea, explore creative alternatives, debug root causes,
  analyze risks, or get unstuck. Trigger on phrases like "think through", "analyze this",
  "brainstorm", "stress test", "devil's advocate", "pre-mortem", "first principles", "root cause",
  "what if", "pros and cons", "red team", "help me decide", "multiple perspectives", "SCAMPER",
  "5 whys", "failure modes", or any request for structured reasoning. Also trigger when the user
  seems stuck, is going in circles on a decision, or would clearly benefit from a different angle
  of attack even if they don't explicitly ask for a thinking technique.
---

# Elicitation Techniques

A catalog of 45 thinking techniques organized by what they're good at. Each technique has a specific
output pattern — a shape the analysis follows — that keeps the thinking structured and productive.

The value here isn't just "think harder." Each technique forces a specific *kind* of thinking that
humans naturally skip. First Principles strips assumptions you didn't know you had. Pre-mortem
leverages hindsight bias *before* failure happens. Red Team finds vulnerabilities by actually trying
to exploit them. The structure is what makes these work.

## How to Use This Skill

### Step 1: Understand the Problem

Before selecting a technique, understand what the user is actually trying to accomplish. Are they:
- **Stuck?** They need a new angle (creative-exploration or reasoning-foundations)
- **Deciding?** They need structured comparison (systematic-analysis or structured-reasoning)
- **Worried?** They need risk analysis (adversarial-stress-test or risk-assessment)
- **Exploring?** They need breadth (multi-perspective or creative-exploration)
- **Debugging?** They need depth (reasoning-foundations)
- **Validating?** They need rigor (validation-verification or adversarial-stress-test)
- **Learning?** They need clarity (learning-clarification)
- **Reviewing?** They need perspective (reflection)

### Step 2: Select Technique(s)

If the user names a specific technique, use it. Otherwise, recommend 1-2 techniques based on the
problem type. Read `references/technique-catalog.md` for the full catalog with descriptions and
output patterns for all 45 techniques.

Quick selection guide by situation:

| Situation | Go-to techniques |
|---|---|
| "Why does this keep failing?" | 5 Whys (#2), Rubber Duck Debugging (#42) |
| "Should we build X or Y?" | Comparative Analysis Matrix (#34), Debate Club (#8) |
| "Is this idea any good?" | Shark Tank Pitch (#17), Pre-mortem (#20) |
| "How do we innovate here?" | First Principles (#1), SCAMPER (#26), Genre Mashup (#31) |
| "What could go wrong?" | Pre-mortem (#20), Failure Mode Analysis (#33), Chaos Monkey (#45) |
| "Is this secure enough?" | Red Team vs Blue Team (#16), Security Audit Personas (#36) |
| "Help me understand this" | Feynman Technique (#41), Socratic Questioning (#3) |
| "We need buy-in from stakeholders" | Stakeholder Round Table (#6), User Persona Focus Group (#9) |
| "This architecture decision is hard" | Architecture Decision Records (#32), Tree of Thoughts (#21) |
| "We're going in circles" | First Principles (#1), Challenge from Critical Perspective (#19) |
| "What did we learn from this?" | Lessons Learned (#44), Hindsight Reflection (#43) |
| "Make this code better" | Code Review Gauntlet (#18), Performance Profiler Panel (#37) |
| "I need fresh ideas" | Random Input Stimulus (#29), Improv Yes-And (#14), Exquisite Corpse (#30) |

When in doubt, default to **First Principles Analysis** for analytical problems or **Stakeholder
Round Table** for people/product problems. These are the most broadly applicable.

### Step 3: Execute the Technique

Each technique has an **output pattern** that defines its flow. Follow the pattern — it's the
skeleton that keeps the analysis productive. But adapt the depth and tone to the problem. A
pre-mortem for a weekend project should be lighter than one for a production launch.

General execution principles:
- **Be specific to the user's actual problem.** Generic analysis is useless. Name their code,
  their users, their constraints.
- **Follow the output pattern as structure, not as a straitjacket.** The pattern tells you what
  sections to produce, but use judgment on depth.
- **Surface genuine insights, not obvious ones.** The technique should reveal something the user
  hadn't considered. If every point is something they'd have thought of anyway, push harder.
- **End with actionable output.** Every technique should conclude with something the user can
  *do* — a decision, a list of next steps, a revised approach, or a specific thing to investigate.

## Technique Execution Guide

Below are execution instructions for each category. For the full list of techniques with
descriptions and output patterns, see `references/technique-catalog.md`.

### Reasoning Foundations (Techniques 1-5)

These techniques strip problems down to fundamentals. Use them when the problem feels tangled or
when existing approaches aren't working.

**Execution pattern:**
1. State the problem clearly
2. Apply the technique's specific lens (assumptions for First Principles, "why" chains for 5 Whys,
   questions for Socratic, simplification for Occam's, step-by-step for Explain Reasoning)
3. Identify what was hidden or assumed
4. Rebuild from what you found

**First Principles Analysis** is the star here. The key move is *listing every assumption*, then
asking "do I actually know this is true, or did I inherit it?" Most breakthroughs come from
challenging inherited assumptions that everyone treats as given.

**5 Whys** seems simple but requires discipline. Each "why" must be a genuine causal step, not a
restatement. Stop when you hit something actionable, not when you've asked exactly five times.

### Multi-Perspective (Techniques 6-15)

These techniques generate diverse viewpoints. They're powerful because a single person naturally
thinks from one angle. Use them when a decision affects multiple people or when you suspect blind
spots.

**Execution pattern:**
1. Define the scenario or proposal being examined
2. Establish the personas (stakeholders, experts, users, etc.)
3. Have each persona react authentically — with their own concerns, values, and priorities
4. Identify where personas agree (signal) and disagree (the interesting part)
5. Synthesize across perspectives

**The personas must be genuinely different.** A Stakeholder Round Table where every stakeholder
agrees is a failure — either the personas aren't distinct enough or the proposal is more
controversial than you're making it. Lean into disagreement; that's where the insights are.

For **Debate Club Showdown**, commit fully to each side. A weak steelman followed by a strong
argument isn't a debate — it's confirmation bias wearing a costume.

For **Time Traveler Council**, be concrete about timeframes. "Past-you from 2 years ago" has
specific regrets; "future-you in 5 years" has specific priorities. Vague time travelers give
vague advice.

### Adversarial Stress-Test (Techniques 16-20)

These techniques try to break things on purpose. Use them before launches, before committing to
a decision, or whenever something feels too good to be true.

**Execution pattern:**
1. Present the thing being stress-tested (idea, system, plan)
2. Attack it systematically from the technique's angle
3. Document every weakness found
4. For each weakness, propose a specific hardening measure
5. Reassess: is the thing viable after hardening?

**Pre-mortem Analysis** is especially powerful because it exploits hindsight bias. Instead of asking
"what could go wrong?" (which triggers optimism bias), ask "it's 6 months from now and this has
failed spectacularly — what happened?" People are much better at explaining past failures than
predicting future ones, even when the "past" is imaginary.

**Red Team vs Blue Team** requires genuine adversarial thinking. The red team should try to
*actually* find exploits, not just list theoretical vulnerabilities. If you're red-teaming code,
trace actual attack paths. If you're red-teaming a business plan, identify specific competitors
or market shifts that would kill it.

### Structured Reasoning (Techniques 21-25)

These techniques organize complex reasoning into explicit structures. Use them when a problem has
many moving parts or when you need to compare multiple approaches rigorously.

**Execution pattern:**
1. Define the problem space
2. Generate multiple distinct reasoning paths or approaches
3. Make the structure explicit (tree, graph, thread, or parallel tracks)
4. Evaluate each path against the problem
5. Select or synthesize the best approach with clear rationale

**Tree of Thoughts** is best when you have 3-5 genuinely different approaches and need to
evaluate them. Don't generate near-identical variants — each branch should represent a
fundamentally different strategy.

**Self-Consistency Validation** is critical for high-stakes decisions. If three independent
approaches reach the same conclusion, confidence is high. If they diverge, the disagreement
itself is the most important finding — investigate why.

### Creative Exploration (Techniques 26-31)

These techniques generate novel ideas. Use them when the problem space feels exhausted or when
incremental thinking isn't enough.

**Execution pattern:**
1. State the current situation or constraint
2. Apply the technique's specific creative mechanism
3. Generate ideas without filtering (divergent thinking)
4. Then filter and evaluate (convergent thinking)
5. Select the most promising ideas for development

**SCAMPER** is systematic creativity. Go through each letter and force at least one idea per lens,
even if it seems absurd. The "absurd" ideas often contain a kernel of insight that leads somewhere
useful when refined.

**Random Input Stimulus** works by forcing lateral connections. Pick a genuinely random word (don't
cherry-pick one that conveniently relates to the problem) and find connections. The more forced the
connection feels initially, the more likely it produces a genuinely novel idea.

### Systematic Analysis (Techniques 32-37)

These techniques structure evaluation of complex systems. Use them for architecture decisions,
performance problems, security reviews, or any situation where rigor matters more than speed.

**Execution pattern:**
1. Define the system or options being analyzed
2. Establish evaluation criteria or areas of concern
3. Analyze systematically (each option against each criterion, or each component for each failure mode)
4. Produce structured output (matrix, scorecard, or annotated diagram)
5. Make a clear recommendation with explicit rationale

**Architecture Decision Records** should capture not just what was decided, but *why* — including
what was rejected and why. Future-you reading this ADR should understand the tradeoffs without
additional context.

**Comparative Analysis Matrix** needs honest scoring. If everything scores 8/10 on everything,
the criteria aren't discriminating enough. Good criteria create separation between options.

### Validation & Verification (Techniques 38-40)

These techniques check whether thinking is sound. Use them after analysis to verify conclusions,
or when you suspect motivated reasoning.

**Execution pattern:**
1. State the conclusion or methodology being validated
2. Apply the technique's validation lens
3. Identify weaknesses, gaps, or inconsistencies
4. Strengthen or revise based on findings

### Learning & Clarification (Techniques 41-42)

These techniques build understanding. Use them when something is confusing, when you need to
explain something to others, or when debugging.

**Feynman Technique** is the gold standard: if you can't explain it simply, you don't understand
it well enough. When you hit a point where the simple explanation breaks down, that's exactly where
your understanding is weakest — and exactly where the bug or misunderstanding likely lives.

### Reflection (Techniques 43-44)

These techniques extract wisdom from experience. Use them after projects, incidents, or any
significant experience worth learning from.

**Execution pattern:**
1. Describe the experience or project
2. Identify what went well and what didn't (with specifics, not generalities)
3. Extract transferable lessons
4. Define concrete actions for next time

### Risk Assessment (Technique 45)

**Chaos Monkey Scenarios** systematically break things to test resilience. For each component,
ask: "What happens if this fails right now?" Then: "Do we have a plan for that?" The value is
in discovering the gaps *before* production discovers them for you.

## Combining Techniques

Some problems benefit from a sequence of techniques:

- **Explore then stress-test:** SCAMPER (#26) to generate options, then Pre-mortem (#20) to
  stress-test the best one
- **Understand then decide:** First Principles (#1) to understand the space, then Comparative
  Analysis Matrix (#34) to choose
- **Debate then validate:** Debate Club (#8) to surface tensions, then Self-Consistency
  Validation (#24) to verify the resolution
- **Perspective then action:** Stakeholder Round Table (#6) to understand concerns, then
  Architecture Decision Records (#32) to formalize the decision

When combining techniques, keep each one focused. Better to do two techniques well than four
techniques superficially.
