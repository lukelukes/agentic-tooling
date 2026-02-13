# How-to Guides (Goal-oriented)

Directions that guide a competent user through a real-world problem toward a specific result. The user already knows what they want to achieve.

## Constraints

- **Do not teach.** The user has competence; they need direction, not education.
- **Do not explain.** Link to explanation documents for background and theory.
- **Practical usability over completeness.** Serve the specific task, do not attempt to be comprehensive.

## Requirements

- **Focus on real problems, not tools.** Write from the user's perspective. Address meaningful outcomes.
- **Logical sequencing.** Steps follow meaningful order — either because prior completion is necessary or because it benefits workflow.
- **Seek flow.** Anticipate user needs. Avoid context-switching between tools or concepts.
- **Clear titling.** State what the guide achieves: "How to configure monitoring alerts" not "Monitoring".
- **Handle real-world messiness.** Unlike tutorials, how-to guides must acknowledge alternatives and prepare for the unexpected: "If X fails, try Y."

## Language

- Imperative, direct: "Configure the...", "Set the value to..."
- Conditional when needed: "If you're using PostgreSQL, add..."
- Titled with "How to..." prefix

## Structure

```
# How to [achieve specific goal]

## Prerequisites
[What the user needs before starting]

## Steps
1. [First action]
2. [Second action]
   - If [condition], then [alternative]
3. [Third action]

## Troubleshooting
[Common issues and solutions]
```

## Example: Good how-to guide

```
# How to rotate managed package versions

Ensure you have at least two package versions tracked.

1. List current versions:

       booster pkg versions nginx

2. Pin the target version:

       booster pkg pin nginx 1.24.0

3. If the pin fails with a dependency conflict, resolve it first:

       booster pkg deps resolve nginx

4. Verify the rotation:

       booster pkg versions nginx --active
```

## Example: Bad how-to guide (teaches instead of directing)

```
# How to rotate managed package versions

Package rotation is important because it ensures you can roll back
to known-good states. Booster tracks versions using a DAG structure
that allows...
```

## Common failure: How-to guide that is actually a tutorial

If your user has no prior competence and you're building it step by step in a safe environment — that is a tutorial. How-to guides assume the user already works with the system.
