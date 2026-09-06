# Evals

`evals.json` lists agent-level scenarios. Each `fixture` is a plain directory under `evals/fixtures/`; copy it somewhere scratch, give the agent that copy, the scenario `prompt` and this skill, then judge the transcript and resulting tree against the `assertions`. Fixtures contain no wrapper JAR or real plugins, so they are static-audit cases unless the scenario says otherwise; for a runnable scenario, add a real wrapper to the copy first.

`trigger-evals.json` is a proposed set of should-trigger / should-not-trigger queries for the skill description (Java/Groovy modernization, narrow advice, older-than-supported entry points, and near-misses such as Kotlin DSL, Android/AGP and product-test migrations). Review it before running description optimization.

For real-Gradle recipe coverage, run `scripts/test_recipes.py` (see `references/verification.md`) against each Gradle version you care about: latest 8.x, an early 9.x, and the current 9.x.
