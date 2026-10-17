---
name: review-loop
description: Orchestrate parallel reviewer subagents (plus Codex) over a change, fix must-fix findings with fixer subagents, and repeat until every reviewer approves.
argument-hint: "[uncommitted | staged | last-commit | <sha> | <branch> | pr <n>] [personas] [--gate] [--opus|--sonnet]"
disable-model-invocation: true
---

You are the orchestrator. You do not review or implement. Subagents review, subagents fix, you re-run the reviewers.

Algorithm: `UNTIL_APPROVED(review -> triage -> fix -> verify)`. You HAVE to loop until all reviewers return APPROVED. Do not stop after one round to ask, unless `--gate` is set.

## Setup
1. Resolve the target from $ARGUMENTS. Default: uncommitted changes; if clean, the last commit. Print the exact diff command you use (`git diff`, `git diff --staged`, `git show <sha>`, `git diff origin/main...HEAD`, `gh pr diff <n>`).
2. Detect the stack from the repo. Personas default to "10x <stack> engineer" (e.g. "10x react + tauri rust engineer"); use the personas in $ARGUMENTS when given.
3. Exit plan mode if active, or workers will inherit it and write nothing.
4. Detect the verify command (`just check`, `make verify`, `bun run validate`, ...) and the run command if the change is user-visible.

## Each round
1. Spawn reviewers in parallel, one per persona, on opus unless told otherwise. Each uses the `thermo-nuclear-code-review` skill lens. Also run Codex: `codex exec --sandbox read-only -c model_reasoning_effort="high" "\$thermo-nuclear-code-review review <diff command>. End with VERDICT: APPROVED or CHANGES_REQUESTED."`
2. Each reviewer returns numbered findings tagged MUST-FIX or NIT, with file:line and the reason, then a verdict.
3. Dedupe across reviewers. Present one table: `# | finding | reviewer(s) | severity | action`.
4. `--gate`: stop and let me decide per row (I answer like "1 fix, 2 skip, 3 follow-up"). Record decisions in `docs/review-decisions.md` and pass them to the next round's reviewers so rejected items are not re-raised.
5. Spawn fixer subagents for MUST-FIX items. Group by file to avoid conflicts. Fix root causes, not the flagged symptom. Stay inside the scope of the target change.
6. NITs go to `docs/REVIEW_NITS.md` (append, numbered), not into code.
7. Run the verify command. If the change is user-visible, start the app and confirm it works. A broken app is a MUST-FIX for the next round.

## Convergence
- Give reviewers in round N the findings and decisions of rounds 1..N-1. Ask them to confirm earlier fixes held.
- If the same finding comes back twice, stop patching: find the root cause and say what it is.
- After 5 rounds without approval, stop and report what blocks approval.

## Finish
- All reviewers APPROVED + verify green.
- If the target was a commit: amend it and update the message/body if the scope changed. Otherwise leave changes uncommitted unless I asked to commit.
- Report: rounds run, table of what was fixed, path to the nits file, final verify output summary.
