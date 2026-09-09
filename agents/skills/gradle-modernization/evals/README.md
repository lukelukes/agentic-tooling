# Evals

`evals.json` lists the agent-level scenarios. Each `fixture` is a directory under `evals/fixtures/`. To run a scenario:

1. Copy the fixture to a scratch location.
2. Give the agent the copy, the scenario `prompt` and this skill.
3. Judge the transcript and the resulting tree against the `assertions`.

The fixtures contain no wrapper JAR and no real plugins. They are static-audit cases unless the scenario says otherwise. For a runnable scenario, add a real wrapper to the copy first.

`trigger-evals.json` is a proposed set of should-trigger and should-not-trigger queries for the skill description. It covers Java and Groovy modernization, narrow advice, entry points older than the supported range, and near-misses such as Kotlin DSL, Android/AGP and product-test migrations. Review it before you run description optimization.

For recipe coverage with a real Gradle, run `scripts/test_recipes.py` against each Gradle version of interest: the latest 8.x, an early 9.x and the current 9.x. See `references/verification.md`.
