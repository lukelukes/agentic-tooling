## Maintenance

`LATEST_GRADLE` / `LAST_VERIFIED` record the documentation review date. Use version-pinned official sources for API claims. When updating rules or scripts, run `python -B scripts/test_audit.py` and `python -B -m unittest discover -s scripts -p 'test_*.py'` (`test_gather_facts.py` drives the orchestrator with a fake launcher). `scripts/test_recipes.py --gradle <launcher>` runs the recipes against a real Gradle (see `references/verification.md`). `evals/` holds agent-level scenarios.
