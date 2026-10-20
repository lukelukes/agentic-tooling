---
name: rewrite-migration
description: Finish an OpenRewrite Migration Run (Spring Boot 4, Jackson 3, ...) from its Worklist. Fix BLOCKERs, settle BEHAVIOUR items, verify, and record Resolutions with the rewrite CLI.
disable-model-invocation: true
allowed-tools: Bash(rewrite run show *) Bash(rewrite run verify *) Bash(rewrite run resolve *) Bash(rewrite recipe rules *)
---

# rewrite-migration

A Migration Run (`rewrite recipe run <Migration>`) writes the deterministic change into the working tree and keeps
the Run under `<repo>/.rewrite/run/<id>/`. What the Recipes could not finish is the Run's **Worklist**: Review Items,
each keyed, with a rule id, a severity and a message. You finish the Worklist: edit the code, prove it with
Verifications, and record a **Resolution** per key. The CLI never calls a model; you are the agent it hands off to.

## Contract

The CLI guarantees these and nothing else. A change to any of them is a breaking change for this skill.

| item | value |
|---|---|
| Worklist schema | `rewrite.worklist/1`. Any other `schema`: stop, and say which version you got and that this skill reads `rewrite.worklist/1` |
| Severities | `BLOCKER` (does not compile or start, or is wrong), `BEHAVIOUR` (compiles, may behave differently), `PRESERVED` (the Run kept the old behaviour with a pin; an Improvement for later) |
| Resolution statuses | `fixed`, `no-change` on `BLOCKER` and `BEHAVIOUR`; `preserved`, `adopted` only on `PRESERVED`; `deferred` on any. `no-change`, `deferred` and `adopted` need a `--note` |
| Rule ids | `area/slug`, globally unique. View-only prefix `legacy/`. Runner rows: `build/recipe-warning`, `build/recipe-error` |
| Reference key | the rule id. The item's `guide` is `rewrite-migration#<ruleId>`; its section is the heading `## <ruleId>` under `references/`, found by exact match whatever the file is called |
| Verification | `verification.status` is `passed`, `failed`, `error` or `timeout`; `verification.reason` is `dependency resolution` on an environment failure. `verification: null` means not verified yet, or a skipped repository (no Gradle or Maven build, `--build-tool none`, no changes), which has no Verification. Branch on status and reason, never on the exit code (exit `3` only says a Verification did not pass) |

Commands:

```
rewrite run show <id> --worklist --json [--path <repo>] [--rule 'jackson/*'] [--severity BLOCKER] [--open]
rewrite run verify <id> --level compile|test [--path <repo>]
rewrite run resolve [<id>] (<key>... | --rule GLOB) --as fixed|no-change|deferred|preserved|adopted --by agent
    [--path <repo>] [--note TEXT] [--file PATH]...
rewrite recipe rules --json [--rule GLOB]
rewrite run show <id> --worklist --format markdown        # the review summary, for the PR description
```

`rewrite recipe run` is not pre-approved: every Run you start asks the human first.

## Rules that hold in every step

- **The oracle is read-only.** Never edit `golden/**`, `pins.csv`, `pins.lock` or pin assertions. Make a failing pin
  pass with an old-behaviour setting or a code change. A test that cannot pass without changing what it asserts is
  reported to the human as it is.
- **Improvements are the human's.** Apply one (`adopted`) only for a rule id the human named.
- **One writer per repository.** You make every edit, run every Verification and record every Resolution.
  Subagents read: trace producers, read a reference section, draft an edit for you to apply.
- **Resolutions describe; they do not change the Run.** `fix.patch`, `report.json` and the Data Tables stay as the
  Run wrote them.
- **The reference section comes first.** Before editing for a rule, read its `## <ruleId>` section in this skill's
  `references/` directory, next to this `SKILL.md` (`grep -rn '^## <ruleId>$' <skill dir>/references/`; your working
  directory is the repository, not the skill). A rule without one: work from the catalogue `title` and `docs` (`rewrite recipe
  rules --json --rule <ruleId>`) and the item's `message`, and list it under "rules without a guide" in your summary.
- **Facts come from the build.** Resolved versions, sources and JARs of the dependency graph beat memory and blog
  posts; Boot, Framework, Jackson, OpenFeign and AWS versions move independently.

## Entry

- The human names a Migration ("migrate this to Boot 4.1"): you may start it, `rewrite recipe run <Migration>
  --verify` on a clean tree, after reading `references/migrations/` for that Migration. The human approves the prompt.
- Otherwise start from the existing Run (`run show` defaults to the newest). Start no Run, Improvement or second Run
  the human did not ask for.
- Ask once, now: may you commit? Without a yes, leave every change uncommitted and say so at the end.

With a ROOT of several repositories, run one agent per repository (`--path <repo>`).

## The loop, per repository

1. **Read.** `rewrite run show <id> --worklist --json --path <repo>`. Stop if `schema` is not `rewrite.worklist/1`,
   or if the repository's `state` is not `written`. Done when you hold the open items grouped by rule id.
2. **Baseline.** If `verification` is `null`, run `rewrite run verify <id> --level compile`. Status `error` or
   `timeout`, or `failed` with reason `dependency resolution`: stop and report. That is the environment or the
   coordinates, not code. Still `null` after that one `run verify`: the repository was skipped; stop and report it as
   not verifiable. Done when a compile Verification exists.
3. **BLOCKERs, one rule group at a time.** First the rules whose items carry joined diagnostics, then the other
   `BLOCKER` rules. Per group: read the section, edit, `rewrite run verify <id> --level compile`, then
   `rewrite run resolve <keys> --as fixed --by agent --file <edited files>` for the keys the group fixed. Done when
   no `BLOCKER` of the group is open and its diagnostics are gone from the newest Verification.
4. **Unattributed diagnostics** (`verification.unattributed`): fix them as part of the Migration. They have no key,
   so nothing is resolved; list each in the summary as a Recipe candidate.
5. **BEHAVIOUR items**, once compile passes. Each gets `fixed`, `no-change` or `deferred`, always with a `--note`
   saying what you checked. Add the focused test a section asks for. Done when no `BEHAVIOUR` item is open.
6. **Tests.** `rewrite run verify <id> --level test`, once. Fix the failures joined to items. A failure you cannot
   tie to the Migration is reported, with the test left as it is.
7. **PRESERVED items** stay unresolved; they are not open and never block. Set `adopted` only for a rule id the human
   asked for: remove the pin together with its provenance comment ("Keeps the default from before ... (rule <id>)
   ..."), both or neither, then record one adoption for the whole rule id:
   `rewrite run resolve <id> --rule <ruleId> --as adopted --by agent --note "<who asked, what changed>"`.

### Stop rules

Stop when any of these holds, and write the summary:

- the newest Verification `passed` at compile (and at test, if step 6 ran) and no `BLOCKER` is open;
- a Verification is `error` or `timeout`, or `failed` with reason `dependency resolution`;
- `verification` is still `null` after one `run verify` (a skipped repository: report it as not verifiable);
- 3 Verifications in a row that resolved no new key.

The error count is never a convergence test: javac reports by phase, so 37, then 5, then 12 errors can be progress.

## Commits and the summary

- Commit 1 is the Run's change exactly as written, message `Run <id>: <Migration>`, so the human reviews the Recipe
  output apart from your edits.
- Then one commit per rule group or area. The message names the rule ids and the keys resolved.
- The PR description, or your final message without a PR, is `rewrite run show <id> --worklist --format markdown`,
  plus the behaviour you could not verify, the Recipe candidates (unattributed diagnostics) and the rules without
  a guide.
- The human owns what you leave: `deferred` items, `PRESERVED` items, Recipe candidates.

## Two Runs instead of one

Some compile errors only go away once the new version's type hierarchy is on the class path. Propose two Runs only
for those, and only run them when the human agrees; `references/migrations/spring-boot4.md` has the procedure.

## References

- `references/<module>/<area>.md`: one `## <ruleId>` section per rule, by the module whose catalogue owns it
  (the rule's `module`: `rewrite-spring`, `rewrite-jackson`, `rewrite-apache`, `rewrite-testing-frameworks`,
  `rewrite-cucumber-jvm`, `rewrite-gradle`, `rewrite-migrate-java`, `rewrite-core`).
- `references/migrations/<name>.md`: notes that cut across one Migration, one `## <Recipe FQN>` heading each.
- `scripts/check-references`: fails when the references drift from `rewrite recipe rules --json --all`. Run it after
  changing either the references or a rewrite catalogue. Its tests: `python3 -m unittest discover -s
  skills/rewrite-migration/tests`.
