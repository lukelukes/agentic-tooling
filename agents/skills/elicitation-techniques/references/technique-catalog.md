# Technique Catalog

Complete reference of all 45 elicitation techniques. Organized by category with descriptions and
output patterns.

## Table of Contents

1. [Reasoning Foundations (1-5)](#reasoning-foundations)
2. [Multi-Perspective (6-15)](#multi-perspective)
3. [Adversarial Stress-Test (16-20)](#adversarial-stress-test)
4. [Structured Reasoning (21-25)](#structured-reasoning)
5. [Creative Exploration (26-31)](#creative-exploration)
6. [Systematic Analysis (32-37)](#systematic-analysis)
7. [Validation & Verification (38-40)](#validation--verification)
8. [Learning & Clarification (41-42)](#learning--clarification)
9. [Reflection (43-44)](#reflection)
10. [Risk Assessment (45)](#risk-assessment)

---

## Reasoning Foundations

Techniques for stripping problems down to fundamentals and building back up.

### #1 First Principles Analysis
**What it does:** Strip away assumptions to rebuild from fundamental truths.
**Best for:** Innovation, "impossible" problems, challenging conventional wisdom.
**Output pattern:** assumptions → truths → new approach

**How to execute:**
1. State the problem or belief
2. List every assumption embedded in the current approach
3. For each assumption, ask: "Is this actually true, or inherited?"
4. Identify the fundamental truths that remain
5. Rebuild a solution from only those truths

**Example:** "We need a faster horse" → Assumption: transportation requires animals → Truth: people need to get from A to B quickly → New approach: mechanical engine

### #2 5 Whys Deep Dive
**What it does:** Drill to root causes through repeated "why" questions.
**Best for:** Debugging, incident analysis, understanding failures.
**Output pattern:** why chain → root cause → solution

**How to execute:**
1. State the problem
2. Ask "Why did this happen?" — give a specific answer
3. Take that answer and ask "Why?" again
4. Repeat until you hit something actionable (usually 3-7 levels)
5. Propose a solution that addresses the root cause, not the symptom

**Discipline:** Each "why" must be a genuine causal step. "Why did the server crash?" → "Because memory ran out" (good) vs "Because it wasn't working" (restatement, not a cause).

### #3 Socratic Questioning
**What it does:** Use targeted questions to reveal hidden assumptions and guide discovery.
**Best for:** Teaching, self-discovery, uncovering unstated beliefs.
**Output pattern:** questions → revelations → understanding

**How to execute:**
1. Start with the user's stated position or understanding
2. Ask clarifying questions that probe the foundations
3. When an assumption surfaces, ask about its basis
4. Guide toward the gap between what's believed and what's known
5. Let the insight emerge from the questioning, not from assertion

### #4 Occam's Razor Application
**What it does:** Find the simplest sufficient explanation.
**Best for:** Debugging, choosing between competing theories, cutting through over-engineering.
**Output pattern:** options → simplification → selection

**How to execute:**
1. List all candidate explanations or approaches
2. For each, identify its assumptions and complexity
3. Eliminate unnecessary complexity — what's the simplest version that still explains the facts?
4. Select the simplest sufficient explanation
5. Note what evidence would force you to accept a more complex explanation

### #5 Explain Reasoning
**What it does:** Walk through thinking step-by-step to show how conclusions were reached.
**Best for:** Transparency, catching logical errors, building trust.
**Output pattern:** steps → logic → conclusion

**How to execute:**
1. State the conclusion
2. Work backwards: what was the last logical step before the conclusion?
3. Continue backward until you reach premises the audience accepts
4. Present forward: premises → each logical step → conclusion
5. Flag any step where the logic is uncertain or the evidence is weak

---

## Multi-Perspective

Techniques for generating diverse viewpoints.

### #6 Stakeholder Round Table
**What it does:** Convene multiple personas to contribute diverse perspectives.
**Best for:** Requirements gathering, finding balanced solutions across competing interests.
**Output pattern:** perspectives → synthesis → alignment

**How to execute:**
1. Identify 3-5 stakeholders with genuinely different interests
2. For each, articulate their priorities, constraints, and concerns
3. Present the proposal to each stakeholder — capture their honest reaction
4. Map areas of agreement and disagreement
5. Synthesize: what solution addresses the most critical concerns?

### #7 Expert Panel Review
**What it does:** Assemble domain experts for deep specialized analysis.
**Best for:** Technical depth, peer review quality assessment.
**Output pattern:** expert views → consensus → recommendations

**How to execute:**
1. Define 3-4 expert roles relevant to the problem
2. Each expert analyzes from their domain perspective
3. Experts respond to each other's analyses
4. Identify consensus points and remaining disagreements
5. Produce recommendations with confidence levels

### #8 Debate Club Showdown
**What it does:** Two personas argue opposing positions while a moderator scores.
**Best for:** Controversial decisions, finding middle ground, exposing hidden trade-offs.
**Output pattern:** thesis → antithesis → synthesis

**How to execute:**
1. Frame the debate proposition clearly
2. Pro side presents strongest case (not a strawman)
3. Con side presents strongest case (not a strawman)
4. Each side rebuts
5. Moderator identifies the strongest points from each side
6. Synthesize: what position captures the best of both?

### #9 User Persona Focus Group
**What it does:** Gather product's user personas to react to proposals.
**Best for:** Feature validation, discovering unmet needs, UX feedback.
**Output pattern:** reactions → concerns → priorities

**How to execute:**
1. Define 3-5 user personas (with names, roles, tech literacy, goals)
2. Present the feature/change to each persona
3. Capture their gut reaction, then their considered feedback
4. Identify which concerns are shared vs. persona-specific
5. Prioritize based on persona importance and concern severity

### #10 Time Traveler Council
**What it does:** Past-you and future-you advise present-you on decisions.
**Best for:** Long-term perspective, escaping short-term pressure.
**Output pattern:** past wisdom → present choice → future impact

**How to execute:**
1. Define specific timeframes (e.g., 2 years ago, 5 years from now)
2. Past-you speaks from specific experiences and regrets
3. Future-you speaks from specific outcomes and priorities
4. Present-you weighs both perspectives against current constraints
5. Decision incorporates temporal wisdom without being paralyzed by it

### #11 Cross-Functional War Room
**What it does:** Product manager + engineer + designer tackle a problem together.
**Best for:** Trade-off analysis between feasibility, desirability, and viability.
**Output pattern:** constraints → trade-offs → balanced solution

**How to execute:**
1. Present the problem to all three roles simultaneously
2. Engineer identifies technical constraints and costs
3. Designer identifies user experience implications
4. PM identifies business requirements and priorities
5. Map the trade-off space and find the sweet spot

### #12 Mentor and Apprentice
**What it does:** Senior expert teaches while junior asks naive questions.
**Best for:** Surfacing hidden assumptions, knowledge transfer, documentation.
**Output pattern:** explanation → questions → deeper understanding

**How to execute:**
1. Expert explains the system/concept/decision
2. Apprentice asks "why?" and "what if?" and "what does that mean?"
3. Expert must answer without jargon or hand-waving
4. When expert struggles to explain simply, that's where complexity (or confusion) hides
5. Document the Q&A — it's often better documentation than what existed

### #13 Good Cop Bad Cop
**What it does:** Supportive and critical personas alternate.
**Best for:** Balanced assessment, finding strengths to build on AND weaknesses to fix.
**Output pattern:** encouragement → criticism → balanced view

**How to execute:**
1. Good Cop: what's working? What's strong? What should we double down on?
2. Bad Cop: what's weak? What will break? What are we fooling ourselves about?
3. Good Cop: how do we build on the strengths to address the weaknesses?
4. Synthesize into a balanced view with specific actions

### #14 Improv Yes-And
**What it does:** Multiple personas build on each other's ideas without blocking.
**Best for:** Divergent brainstorming, creative exploration, breaking out of constraints.
**Output pattern:** idea → build → build → surprising result

**How to execute:**
1. Start with any seed idea (even a mediocre one)
2. Each persona adds to it with "Yes, and..." — never "No, but..."
3. Build for 5-8 rounds, letting the idea evolve freely
4. Review the trajectory — often the final idea is unrecognizable from the start
5. Extract the valuable elements from the surprising destination

### #15 Customer Support Theater
**What it does:** Angry customer and support rep roleplay to find pain points.
**Best for:** Discovering real user frustrations, identifying service gaps.
**Output pattern:** complaint → investigation → resolution → prevention

**How to execute:**
1. Customer describes their frustration (be specific and emotional)
2. Support rep investigates: what actually went wrong?
3. Trace the issue through the system to find the root cause
4. Resolve the immediate complaint
5. Identify systemic prevention measures

---

## Adversarial Stress-Test

Techniques for finding weaknesses by trying to break things.

### #16 Red Team vs Blue Team
**What it does:** Adversarial attack-defend analysis.
**Best for:** Security testing, building robust solutions, finding exploitable weaknesses.
**Output pattern:** defense → attack → hardening

**How to execute:**
1. Blue Team presents the system/plan and its defenses
2. Red Team identifies attack vectors and attempts exploits
3. Blue Team responds to each attack
4. Document successful attacks and near-misses
5. Harden: for each vulnerability, implement specific countermeasures

### #17 Shark Tank Pitch
**What it does:** Entrepreneur pitches to skeptical investors who poke holes.
**Best for:** Business viability, forcing clarity on value proposition.
**Output pattern:** pitch → challenges → refinement

**How to execute:**
1. Pitch the idea in 2 minutes: problem, solution, market, why now
2. Investors ask hard questions: market size? Defensibility? Unit economics?
3. Entrepreneur responds honestly (no hand-waving)
4. Investors give verdict with specific concerns
5. Refine the pitch/idea based on what didn't survive scrutiny

### #18 Code Review Gauntlet
**What it does:** Senior devs with different philosophies review the same code.
**Best for:** Code quality, surfacing style debates, finding consensus on practices.
**Output pattern:** reviews → debates → standards

**How to execute:**
1. Present the code to reviewers with different priorities (performance, readability, testability, security)
2. Each reviewer gives their assessment
3. Where reviewers disagree, explore the trade-off explicitly
4. Converge on recommendations everyone can live with
5. Extract generalizable standards from the specific review

### #19 Challenge from Critical Perspective
**What it does:** Play devil's advocate to stress-test ideas.
**Best for:** Overcoming groupthink, finding weaknesses before others do.
**Output pattern:** assumptions → challenges → strengthening

**How to execute:**
1. State the idea and its supporting arguments
2. For each supporting argument, find the strongest counter-argument
3. For each assumption, ask: "What if this is wrong?"
4. Identify the weakest points in the overall case
5. Strengthen the idea by addressing the most damaging challenges

### #20 Pre-mortem Analysis
**What it does:** Imagine future failure then work backwards to prevent it.
**Best for:** Risk mitigation before launches, surfacing fears nobody is voicing.
**Output pattern:** failure scenario → causes → prevention

**How to execute:**
1. Frame: "It's [6 months/1 year] from now. This has failed completely."
2. Brainstorm: what happened? (Generate at least 5-7 specific failure scenarios)
3. For each scenario, trace the causal chain backwards
4. Rate each failure by likelihood and severity
5. For the highest-risk failures, define specific preventive actions

---

## Structured Reasoning

Techniques for organizing complex reasoning explicitly.

### #21 Tree of Thoughts
**What it does:** Explore multiple reasoning paths simultaneously, then evaluate.
**Best for:** Complex problems with multiple valid approaches.
**Output pattern:** paths → evaluation → selection

**How to execute:**
1. State the problem
2. Generate 3-5 genuinely distinct approaches (not minor variants)
3. Develop each approach 2-3 steps
4. Evaluate each based on feasibility, effectiveness, and risk
5. Select the best or synthesize elements from multiple paths

### #22 Graph of Thoughts
**What it does:** Model reasoning as an interconnected network of ideas.
**Best for:** Systems thinking, discovering emergent patterns and hidden relationships.
**Output pattern:** nodes → connections → patterns

**How to execute:**
1. Identify the key concepts, actors, and forces in the problem
2. Map connections between them (causal, correlational, enabling, blocking)
3. Look for clusters, feedback loops, and bottlenecks
4. Identify non-obvious connections and emergent patterns
5. Use the graph structure to find leverage points

### #23 Thread of Thought
**What it does:** Maintain coherent reasoning across long, complex contexts.
**Best for:** Multi-document analysis, maintaining consistency in complex arguments.
**Output pattern:** context → thread → synthesis

**How to execute:**
1. Identify the key question or thread to follow
2. Process each piece of information, explicitly connecting it to the thread
3. When new information contradicts the thread, flag and reconcile
4. Periodically summarize the thread's current state
5. Synthesize the final position from the accumulated thread

### #24 Self-Consistency Validation
**What it does:** Generate multiple independent approaches, then compare for consistency.
**Best for:** High-stakes decisions, verification, building confidence in conclusions.
**Output pattern:** approaches → comparison → consensus

**How to execute:**
1. Solve the problem using approach A (e.g., analytical)
2. Solve it again using approach B (e.g., empirical)
3. Solve it a third time using approach C (e.g., analogical)
4. Compare results: where do they agree? Disagree?
5. Agreement builds confidence; disagreement flags where more investigation is needed

### #25 Reasoning via Planning
**What it does:** Build a reasoning tree guided by world models and goal states.
**Best for:** Strategic planning, sequential decision-making, goal achievement.
**Output pattern:** model → planning → strategy

**How to execute:**
1. Define the current state and desired end state
2. Build a model of what actions are possible and their effects
3. Plan backwards from the goal: what's the last step? What enables it?
4. Plan forwards from now: what's the first step? What does it enable?
5. Reconcile the two plans into a coherent strategy

---

## Creative Exploration

Techniques for generating novel ideas and breaking out of ruts.

### #26 SCAMPER Method
**What it does:** Apply seven creativity lenses systematically.
**Best for:** Product innovation, systematic ideation, feature brainstorming.
**Output pattern:** S→C→A→M→P→E→R

**How to execute (one idea per lens minimum):**
- **S**ubstitute: What can be replaced? Different materials, people, processes?
- **C**ombine: What can be merged? Two features into one? Two products?
- **A**dapt: What can be borrowed from another domain? What's analogous?
- **M**odify: What can be enlarged, shrunk, or changed in proportion?
- **P**ut to another use: Can this solve a different problem? Serve a different audience?
- **E**liminate: What can be removed? What's not actually necessary?
- **R**everse: What if you flip the order? The roles? The direction?

### #27 Reverse Engineering
**What it does:** Work backwards from desired outcome to find the path.
**Best for:** Goal achievement, understanding what success requires.
**Output pattern:** end state → steps backward → path forward

**How to execute:**
1. Describe the desired end state in vivid, specific detail
2. Ask: "What was the last thing that happened before we reached this state?"
3. Continue stepping backward until you reach the present
4. Reverse the sequence to get a forward plan
5. Identify the first concrete step to take

### #28 What If Scenarios
**What it does:** Explore alternative realities to understand possibilities.
**Best for:** Contingency planning, understanding implications of choices.
**Output pattern:** scenarios → implications → insights

**How to execute:**
1. Identify the key variable or decision
2. Generate 3-5 "what if" scenarios by changing that variable
3. For each scenario, trace the implications forward
4. Compare: what's different? What's surprisingly similar?
5. Extract insights about what actually matters vs. what doesn't

### #29 Random Input Stimulus
**What it does:** Inject unrelated concepts to spark unexpected connections.
**Best for:** Breaking creative blocks, forced lateral thinking.
**Output pattern:** random word → associations → novel ideas

**How to execute:**
1. Pick a genuinely random word (open a dictionary, use a random word generator)
2. List 5-10 attributes or associations of that word
3. Force-connect each attribute to the problem
4. Most connections will be absurd — that's fine. A few will spark something
5. Develop the promising sparks into real ideas

### #30 Exquisite Corpse Brainstorm
**What it does:** Each persona adds to an idea seeing only the previous contribution.
**Best for:** Generating surprising combinations, breaking groupthink.
**Output pattern:** contribution → handoff → contribution → surprise

**How to execute:**
1. Person A proposes an idea (just the core concept)
2. Person B sees only A's output and builds on it
3. Person C sees only B's output and builds on that
4. Continue for 4-5 rounds
5. Reveal the full chain — the endpoint is usually surprising and often valuable

### #31 Genre Mashup
**What it does:** Combine two unrelated domains to find fresh approaches.
**Best for:** Innovation through unexpected cross-pollination.
**Output pattern:** domain A + domain B → hybrid insights

**How to execute:**
1. Name the problem domain
2. Pick a wildly different domain (biology for a software problem, music for a logistics problem)
3. List 5 principles or patterns from the unrelated domain
4. Map each principle onto the original problem
5. Develop the most promising mappings into real approaches

---

## Systematic Analysis

Techniques for rigorous evaluation of complex systems.

### #32 Architecture Decision Records
**What it does:** Multiple architects propose and debate choices with explicit trade-offs.
**Best for:** Architecture decisions, ensuring decisions are well-documented.
**Output pattern:** options → trade-offs → decision → rationale

**How to execute:**
1. State the decision to be made and the context
2. List 2-4 viable options (each must be genuinely viable)
3. For each option, list pros, cons, and risks
4. Evaluate against the project's specific constraints and priorities
5. Make the decision with explicit rationale. Document what was rejected and why.

### #33 Failure Mode Analysis
**What it does:** Systematically explore how each component could fail.
**Best for:** Reliability engineering, safety-critical systems.
**Output pattern:** components → failures → prevention

**How to execute:**
1. List every component in the system
2. For each component, brainstorm failure modes (how could this break?)
3. For each failure mode: What's the impact? How likely is it? How detectable?
4. Prioritize by risk (impact x likelihood / detectability)
5. For high-risk failures, define prevention and mitigation measures

### #34 Comparative Analysis Matrix
**What it does:** Multiple analysts evaluate options against weighted criteria.
**Best for:** Structured decision-making with explicit scoring.
**Output pattern:** options → criteria → scores → recommendation

**How to execute:**
1. Define the options being compared (2-5 works best)
2. Define evaluation criteria and assign weights (must add to 100%)
3. Score each option on each criterion (1-5 or 1-10)
4. Calculate weighted scores
5. Recommend the winner with explicit rationale. Note where scores were close.

### #35 Algorithm Olympics
**What it does:** Multiple approaches compete on the same problem with benchmarks.
**Best for:** Finding optimal implementations through direct comparison.
**Output pattern:** implementations → benchmarks → winner

**How to execute:**
1. Define the problem and success metrics clearly
2. Implement 2-4 genuinely different approaches
3. Define benchmarks: correctness, speed, memory, readability, maintainability
4. Run benchmarks and compare
5. Select winner, noting which approach wins on which dimension

### #36 Security Audit Personas
**What it does:** Hacker + defender + auditor examine from different threat models.
**Best for:** Comprehensive security review from multiple angles.
**Output pattern:** vulnerabilities → defenses → compliance

**How to execute:**
1. Hacker: what can I exploit? (Think attack paths, not theoretical vulnerabilities)
2. Defender: what's our current defense posture? Where are the gaps?
3. Auditor: does this meet compliance requirements? Industry best practices?
4. Cross-reference: vulnerabilities the hacker found that the defender missed
5. Prioritize remediation by exploitability and impact

### #37 Performance Profiler Panel
**What it does:** Database expert + frontend specialist + DevOps engineer diagnose slowness.
**Best for:** Full-stack performance debugging, identifying bottlenecks.
**Output pattern:** symptoms → analysis → optimizations

**How to execute:**
1. Describe the performance symptoms
2. Database expert: Is the query plan efficient? N+1 queries? Missing indexes?
3. Frontend specialist: Is the rendering efficient? Bundle size? Unnecessary re-renders?
4. DevOps engineer: Is the infrastructure right-sized? Caching? CDN? Connection pooling?
5. Identify the actual bottleneck (it's usually not where you think)

---

## Validation & Verification

Techniques for checking whether thinking is sound.

### #38 Meta-Prompting Analysis
**What it does:** Step back to analyze the approach itself.
**Best for:** Optimizing problem-solving methodology, improving prompts.
**Output pattern:** current → analysis → optimization

**How to execute:**
1. Describe the current approach or methodology
2. Analyze: what's working? What's not? What's the approach assuming?
3. Are there better frameworks for this type of problem?
4. Propose specific optimizations
5. Test the optimized approach against the original

### #39 Literature Review Personas
**What it does:** Optimist + skeptic + synthesizer review sources.
**Best for:** Balanced assessment of evidence quality.
**Output pattern:** sources → critiques → synthesis

**How to execute:**
1. Present the sources/evidence
2. Optimist: what does this evidence support? What's the strongest reading?
3. Skeptic: what are the methodological weaknesses? Alternative explanations?
4. Synthesizer: given both readings, what can we actually conclude?
5. Rate overall evidence quality and identify gaps

### #40 Thesis Defense Simulation
**What it does:** Student defends hypothesis against a committee with different concerns.
**Best for:** Stress-testing research methodology and conclusions.
**Output pattern:** thesis → challenges → defense → refinements

**How to execute:**
1. State the thesis/hypothesis clearly
2. Committee member 1 challenges methodology
3. Committee member 2 challenges conclusions
4. Committee member 3 challenges assumptions
5. Defend against each, noting where the defense is weakest
6. Refine the thesis based on the strongest challenges

---

## Learning & Clarification

Techniques for building and testing understanding.

### #41 Feynman Technique
**What it does:** Explain complex concepts as if teaching a child.
**Best for:** Testing understanding, finding knowledge gaps, learning.
**Output pattern:** complex → simple → gaps → mastery

**How to execute:**
1. Pick the concept to understand
2. Explain it in simple language, as if to someone with no background
3. When the explanation gets hand-wavy or uses jargon, stop — that's a gap
4. Go back to the source material and fill the gap
5. Try the simple explanation again until it flows smoothly

### #42 Rubber Duck Debugging Evolved
**What it does:** Explain code to progressively more technical ducks.
**Best for:** Debugging, finding the "it's obvious" bug you're not seeing.
**Output pattern:** simple → detailed → technical → aha

**How to execute:**
1. Explain the code to a non-technical duck: "This takes a list and returns the biggest one"
2. Explain to a junior duck: "It iterates through, comparing each element..."
3. Explain to a senior duck: "The comparison uses X algorithm with Y edge case handling..."
4. At some level of detail, you'll hit the "wait, that's not right" moment
5. That's the bug (or the misunderstanding)

---

## Reflection

Techniques for extracting wisdom from experience.

### #43 Hindsight Reflection
**What it does:** Imagine looking back from the future to gain perspective.
**Best for:** Project reviews, gaining emotional distance from recent events.
**Output pattern:** future view → insights → application

**How to execute:**
1. Imagine it's 1-2 years from now, looking back at this situation
2. What do you notice that you can't see up close?
3. What turned out to matter more (or less) than expected?
4. What would future-you tell present-you?
5. Translate those insights into actions for now

### #44 Lessons Learned Extraction
**What it does:** Systematically identify takeaways and improvements.
**Best for:** Post-project reviews, continuous improvement, retros.
**Output pattern:** experience → lessons → actions

**How to execute:**
1. Describe what happened (facts, not judgments)
2. What went well? Be specific — "communication was good" → "daily standups caught the auth bug early"
3. What went poorly? Same specificity.
4. For each item, extract a transferable lesson
5. For each lesson, define a concrete action for next time

---

## Risk Assessment

### #45 Chaos Monkey Scenarios
**What it does:** Deliberately break things to test resilience and recovery.
**Best for:** Reliability testing, discovering single points of failure.
**Output pattern:** break → observe → harden

**How to execute:**
1. List every component and dependency in the system
2. For each: "What happens if this fails right now?"
3. Trace the blast radius — what else breaks?
4. Identify components with no fallback or recovery plan
5. Design resilience measures: retries, fallbacks, circuit breakers, graceful degradation
