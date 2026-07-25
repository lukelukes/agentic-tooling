# Tutorials (Learning-oriented)

An experience under the guidance of a tutor. The learner acquires skill by doing something meaningful toward an achievable goal. What they *do* is not necessarily what they *learn*.

## Constraints

- **Do not try to teach.** Provide learning experiences; trust that understanding emerges from doing.
- **Do not explain.** Link to explanation documents. A learner focused on execution cannot absorb theory simultaneously.
- **Do not offer choices or alternatives.** Stay on a single path to the conclusion.
- **Stay concrete.** Move from one concrete action and result to the next. Never abstract.

## Requirements

- **Early, frequent visible results.** Each step produces a comprehensible outcome.
- **Maintain an expectations narrative.** Continuous feedback: "You will notice that...", "The output should look like..."
- **Direct observation.** Point out environmental cues the learner will miss: "Notice that the server responded with..."
- **Aspire to perfect reliability.** The tutorial must work for every user, every time.
- **Embrace repetition.** Permit step repetition so learners confirm results.

## Responsibilities

The teacher bears nearly complete responsibility for success. Exercises must be:
- Meaningful (learner experiences achievement)
- Successful (learner can complete them)
- Logical (pathway makes sense)
- Usefully complete (encounters all necessary actions, concepts, and tools)

The learner's only responsibility: attentiveness and following directions.

## Language

- First-person plural: "We will now...", "Let's create..."
- Imperative: "First, do x. Now, do y."
- Set expectations: "The output should look something like..."
- Acknowledge progress: "You have built a..."

## Example: Good tutorial step

```
Create a new configuration file:

    booster init --config default

You should see output like:

    Created config at ~/.config/booster/config.toml

Open the file. Notice that it contains default values for all settings.
Now let's add our first managed package.
```

## Example: Bad tutorial step (explains instead of doing)

```
Configuration files in booster use TOML format because TOML provides
better readability than JSON and is more standardized than YAML. The
configuration system supports inheritance, where local configs override
global ones. Let's create a config file...
```

## Common failure: Tutorial that is actually a how-to guide

If you find yourself writing "If you want X, do Y; if you want Z, do W" — that is a how-to guide. Tutorials have one path, no branches.
