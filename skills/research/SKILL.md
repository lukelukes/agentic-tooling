---
name: research
description: Fan out parallel web-search-researcher subagents on a topic, cover the well-known solutions first, and write one markdown report with every source.
argument-hint: "<topic> [-> output.md] [N agents]"
disable-model-invocation: true
---

Research $ARGUMENTS.

## Before searching
- If the goal or scope is unclear, ask up to 3 numbered questions first, each with a recommended answer.
- Check local material first: `docs/`, sibling repos (`../`), added dirs. Local code beats web results.
- Write the angle list: the standard, boring, widely-used solutions FIRST, then advanced and niche ones. Missing an obvious approach (e.g. tmux send-keys for TUI testing) is the worst failure here.

## Fan out
- Spawn 3-5 `web-search-researcher` subagents in parallel (or the N given), one angle each. Typical angles: idiomatic patterns, architecture/scalability (folder structure, composition), performance, pitfalls and antipatterns, prior art in real repos, current versions and release notes.
- Each agent returns claims with a source URL per claim, the source date, and a confidence note. Prefer primary sources (official docs, maintainers, source code). Use context7 for library docs.
- After the first wave, read what came back and list the gaps. Run a second wave for the gaps.

## Output
Write the report to the path given, else `docs/<topic-kebab>.md`:
1. TL;DR: 5-10 terse, actionable bullets for this project.
2. Findings by angle: dense, technical, no filler.
3. Recommendations for this repo, numbered, with tradeoffs.
4. Not covered / open questions: say plainly what was not researched.
5. Sources: EVERY source visited, sorted by date (newest first): `- [title](url) (date) — one line on what it supports`.

In chat, reply only with the TL;DR and the file path.
