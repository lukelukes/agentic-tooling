# Explanation (Understanding-oriented)

Discursive treatment of a subject that permits reflection. Deepens comprehension by providing context, history, rationale, and connections. The only documentation type that can be read away from the product.

## Constraints

- **Do not describe machinery.** That belongs in reference.
- **Do not instruct.** That belongs in tutorials and how-to guides.
- **Keep boundaries tight.** Explanation naturally absorbs other content — frame it deliberately.

## Requirements

- **Make connections.** Link concepts to related topics, even external ones.
- **Provide context.** Why things are the way they are: design decisions, historical reasons, technical constraints, trade-offs.
- **Discuss the subject.** The bigger picture, alternatives considered, reasons for choices.
- **Admit opinion and perspective.** Consider alternatives, counter-examples, multiple approaches. All practice is invested with opinion.

## Language

- "The reason for X is because historically, Y..."
- "W is better than Z, because..."
- "An X in this system is analogous to a Y in that system. However..."
- "Some users prefer W (because Z). This can work, but..."

Titles should allow an implicit "About" prefix: "About dependency resolution", "About the manifest format".

## Structure

Flexible. Explanation does not have a rigid format — it is prose, discussion, narrative. Common patterns:

```
# [Topic]

[Opening that establishes what this explains and why it matters]

## Context
[Historical or technical background]

## How it works (conceptually)
[High-level mental model — NOT reference-level description]

## Design decisions
[Why this approach was chosen over alternatives]

## Trade-offs
[What was gained and lost]

## Related concepts
[Connections to other parts of the system]
```

## Example: Good explanation

```
# About dependency resolution

Booster resolves dependencies using a SAT solver rather than the more
common topological sort. This was a deliberate choice: topological
sorting fails silently on diamond dependencies, while SAT solving
surfaces conflicts explicitly.

The trade-off is speed. Resolution takes ~200ms longer on large
manifests. In practice, this matters only during initial bootstrap —
incremental updates resolve in <50ms regardless of approach.
```

## Example: Bad explanation (describes machinery instead of discussing)

```
# Dependency resolution

The `resolve` command takes a manifest file and produces a lock file.
It accepts the following flags: --strict, --allow-prerelease...
```

## Why explanation is neglected

- Less urgent than the other three types
- Unclear scope (no natural boundaries like "one command = one reference entry")
- Often scattered in small pieces across other documents rather than standing alone
- Yet foundational: no practitioner can afford to be without understanding of their craft

## Common failure: Explanation that creeps into reference

If you find yourself listing flags, parameters, or exact syntax — you have drifted into reference. Pull back to the conceptual level.
