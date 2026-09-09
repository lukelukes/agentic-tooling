## Maintenance

`LATEST_GRADLE` and `LAST_VERIFIED` in `scripts/audit_gradle_project.py` record the documentation review date. Use version-pinned official sources for API claims.

After you change rules or scripts, run:

```sh
python -B scripts/test_audit.py
python -B -m unittest discover -s scripts -p 'test_*.py'
```

`test_gather_facts.py` drives the orchestrator with a fake launcher. `scripts/test_recipes.py --gradle <launcher>` runs the recipes against a real Gradle. See `references/verification.md`. `evals/` holds the agent-level scenarios.
