---
name: commit
description: Commit only this session's changes as logical, atomic conventional commits after the project's verify step passes.
argument-hint: "[single | chunks | amend] [extra instructions]"
disable-model-invocation: true
---

Commit the changes with mode $ARGUMENTS. Default mode: `chunks`.

1. Run `git status` and `git diff`. Separate this session's changes from unrelated uncommitted work. Never stage unrelated files. If ownership is unclear, list the files and ask.
2. Run the project's fast verify (`just check`, `make verify-dev`, `bun run validate`, lint + typecheck). Fix failures caused by these changes. If a pre-commit hook fails, fix the cause and retry. Never use `--no-verify`.
3. Split the commits:
   - `chunks`: one commit per logical change. Each commit builds on its own. Order: refactors, then features, then tests and docs, unless tests belong with their change.
   - `single`: one commit.
   - `amend`: amend HEAD and update its message if the scope changed.
4. Messages: conventional commits (`feat(scope): ...`), imperative, lowercase subject under 72 characters. The body says why, if it is not obvious. No plan labels, priorities, task IDs, Co-Authored-By, Claude attribution, or session links.
5. Stage with explicit paths (`git add <files>` or `git add -p`), never `git add -A`.
6. Do not push.
7. If a PRD/task file tracks this work (`.opencode/state/*/prd.json`, `tasks.md`), mark the task as passed only when I asked.

Report: `git log --oneline` of the new commits.
