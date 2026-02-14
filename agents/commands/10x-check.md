Review our production code and test strategy as a 10x senior engineer (10+ years).

Evaluate tests against the four pillars:

1. Protection against regressions - do tests catch bugs when code breaks?
2. Resistance to refactoring - do tests survive internal changes without false failures?
3. Fast feedback - quick enough for tight dev loops?
4. Maintainability - easy to read, modify, and extend?

For each test file:

- Rate each pillar (strong/weak/missing)
- Flag the biggest concern a staff engineer would raise
- Suggest one concrete fix

Be direct and critical. Reject anything you wouldn't approve in PR review.
