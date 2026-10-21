# Wrapping wayfinder from a companion skill

Research for the map-view ticket "Wrapping wayfinder" (`.scratch/map-view/issues/01-wrapping-wayfinder.md`).

**Question.** How can a skill authored in this repo (`skills/<name>/`) invoke the upstream `mattpocock-skills:wayfinder` skill, and grilling and domain-modeling beneath it, while it adds its own behaviour, for example starting a local server and writing each grilling round to a file? What does wayfinder charting write to disk today? Do upstream skills already persist a design tree or rounds that we could reuse?

Sources: the installed plugin `mattpocock-skills` 1.3.1 (commit `49dd158`), cached at `~/.claude/plugins/cache/luke/mattpocock-skills/1.3.1/` (shortened to `<mps>` below); the Claude Code docs at <https://code.claude.com/docs/en/skills> and <https://code.claude.com/docs/en/hooks>; this repo's `README.md` and `sync.py`.

## Summary

- **A companion skill cannot call wayfinder through the Skill tool.** Wayfinder sets `disable-model-invocation: true`. Claude Code blocks Skill tool calls to such a skill and tells the model not to recreate it another way. Upstream's own invocation rules say the same thing: a user-invoked skill can never be reached from another skill.
- **grilling and domain-modeling can be called.** Both are model-invoked, so the companion can call the Skill tool for them, the same way wayfinder does.
- **There are two workable ways to compose with wayfinder:**
  1. The user stacks both skills in one message: `/map-view /mattpocock-skills:wayfinder <idea>`. This works only at the terminal prompt.
  2. The companion inlines the live upstream text at load time with `` !`cat …/wayfinder/SKILL.md` ``. This bypasses the Skill tool, depends on a cache path that changes with each version, and works against the reason the flag exists.
- **Hooks are the best way to persist rounds.** Hooks declared in a skill's frontmatter register when the skill is invoked and stay registered for the rest of the session. A `Stop` hook receives `last_assistant_message`, which is the text of the round. A `UserPromptSubmit` hook receives `prompt`, which is the answer. Neither depends on the model remembering to write a file.
- **On disk today, charting writes only the end products:** `map.md` and `issues/NN-<slug>.md` under `.scratch/<effort>/`, any `GLOSSARY.md` and ADR edits that domain-modeling makes, and the `research/<name>` branches. The grilling rounds themselves exist only in the chat and in the session transcript JSONL.
- **No upstream skill persists a design tree or rounds.** grilling keeps the tree in context only. grill-with-docs and to-spec write a glossary, ADRs, or a final spec. to-questionnaire writes a file of questions with answer stubs, which is the nearest shape, but it is user-invoked and built for a different purpose.

## 1. Can a repo skill invoke `mattpocock-skills:wayfinder`?

### The flag that blocks it

- Wayfinder's frontmatter has `disable-model-invocation: true` (`<mps>/skills/engineering/wayfinder/SKILL.md`, line 4). Its Codex metadata has the matching `policy.allow_implicit_invocation: false` (`<mps>/skills/engineering/wayfinder/agents/openai.yaml`).
- The Claude Code docs describe the flag: "Claude can invoke any skill that doesn't have `disable-model-invocation: true` set." For a skill that has the flag, the invocation table says "Claude can invoke: Not on its own". They also say: "If Claude tries anyway, Claude Code blocks the call and instructs it not to reproduce the deploy steps another way, so expect Claude to suggest running `/deploy` yourself." ([skills: Control who invokes a skill](https://code.claude.com/docs/en/skills))
- The docs do not say explicitly whether skill A can invoke skill B. The only path they document is the Skill tool, and that path is gated by the flag above ([skills](https://code.claude.com/docs/en/skills)).
- Upstream states the rule as an invariant: "Each harness excludes a user-invoked skill from the model's reach in its own way, so nothing but the human can fire it: no other skill can. A user-invoked skill may invoke model-invoked skills, but it can never reach another user-invoked skill." (`<mps>/.agents/invocation.md`)
- Every skill authored in this repo also sets `disable-model-invocation: true` (`README.md`, "Invocation posture"). So the companion will be user-invoked too. That is fine, because it only needs to call model-invoked skills.

### Skills beneath wayfinder that can be called

- `grilling` has no `disable-model-invocation` flag (`<mps>/skills/productivity/grilling/SKILL.md`), and neither does `domain-modeling` (`<mps>/skills/engineering/domain-modeling/SKILL.md`). Both are model-invoked.
- Wayfinder itself reaches them with the operative wording that upstream's convention requires: "Call the Skill tool twice, for "grilling" and "domain-modeling"" (wayfinder `SKILL.md` line 111; convention in `<mps>/.agents/invocation.md`, "Dependencies between them"). A companion can use the same sentence.
- Name resolution: plugin skills are namespaced as `/plugin-name:skill-name`, and "The bare `/fancy` also invokes the skill unless another command already uses that name" ([skills](https://code.claude.com/docs/en/skills)). `sync.py` does not link third-party plugin skills into `~/.claude/skills`. It links them only into `~/.agents/skills` and `~/.cursor/skills` (`sync.py` `cache_link_plan`, roots `AGENTS_SKILLS` and `CURSOR_SKILLS`). In Claude Code, the companion therefore reaches the upstream skills only by their plugin names, `mattpocock-skills:grilling` and the others, or by the bare names when nothing else uses them.

### Option A: stack the skills in one message (recommended)

- "At the terminal prompt, typing `/write-tests /fix-issue 123` loads both skills and passes the trailing text `123` as `$ARGUMENTS` to each of them. Claude Code expands the first skill plus up to five more stacked after it. Expansion stops at the first token that isn't an inline user-invocable skill." ([skills: Stack several skills in one message](https://code.claude.com/docs/en/skills))
- `/map-view /mattpocock-skills:wayfinder <idea>` loads both skills in one user message. Wayfinder runs unchanged and the companion adds its standing instructions and hooks. The user types the wayfinder name, so the upstream invariant holds.
- Limits:
  - "Through the Agent SDK or `claude -p`, Claude Code loads only the first skill, with the rest of the line as its arguments." This is acceptable, because the map's Notes say agent sessions run in the terminal.
  - Both skills receive the same `$ARGUMENTS`.
- An alternative with the same effect: invoke `/map-view` first, which installs its hooks and starts the server, and have it end by telling the user to run `/mattpocock-skills:wayfinder <idea>`. This follows upstream's documented pattern of telling the user to run a user-invoked skill (`<mps>/.agents/invocation.md`). Skill content stays in the conversation across later turns ([skills: Skill content lifecycle](https://code.claude.com/docs/en/skills)), so the companion's instructions are still active when wayfinder runs.

### Option B: inline wayfinder's text at load time (not recommended)

- `` !`<command>` `` "runs shell commands before the skill content is sent to Claude. The command output replaces the placeholder." ([skills: dynamic context injection](https://code.claude.com/docs/en/skills)) So `` !`cat <installPath>/skills/engineering/wayfinder/SKILL.md` `` would paste the live upstream text into the companion without a Skill tool call and without a fork.
- Reasons against it:
  - The cache path includes the version. Two versions sit side by side right now, `1.2.3` and `1.3.1`. The current path is only known from `~/.claude/plugins/installed_plugins.json` (`installPath`).
  - "A failed command aborts the entire skill invocation."
  - It works around the explicit block that Claude Code puts on model invocation of a flagged skill.
  - Wayfinder links to sibling skills by Skill tool name, and those calls still work. Any relative links in the text, however, would resolve against the wrong directory.

## 2. Adding behaviour: server start and round persistence

### Hooks in skill frontmatter

- "Skill hooks: Claude Code registers them when you or Claude invoke the skill and keeps running them for the rest of the session, on turns after the skill's own turn as well." `once: true` removes a hook after its first successful run. Frontmatter hooks in a *project* skill follow workspace trust. ([hooks: Hooks in skills and agents](https://code.claude.com/docs/en/hooks)) Skills in this repo are symlinked into `~/.claude/skills` (`README.md`), so they load as personal skills, not project skills.
- **Stop hook**: it receives `last_assistant_message`, which "contains the text content of Claude's final response". The docs advise using this field rather than `transcript_path`, because "the transcript file isn't guaranteed to include the final message at Stop time". It also receives `stop_hook_active`. ([hooks: Stop](https://code.claude.com/docs/en/hooks))
- **UserPromptSubmit hook**: it receives `prompt`, the text the user submitted. It can add `additionalContext` but cannot replace the prompt. ([hooks: UserPromptSubmit](https://code.claude.com/docs/en/hooks))
- **UserPromptExpansion hook**: it fires when the user types a skill as a slash command. It receives `command_name`, `command_args` and `command_source` ("plugin"). This is how to detect `/mattpocock-skills:wayfinder`. A `PreToolUse` hook on `Skill` does not fire on that typed path. ([hooks: UserPromptExpansion](https://code.claude.com/docs/en/hooks)) A frontmatter hook registers only after its own skill is invoked. A UserPromptExpansion hook on the companion therefore sees a wayfinder invocation only if the companion ran first.
- Every hook also receives `transcript_path` and `session_id`, the common input fields ([hooks](https://code.claude.com/docs/en/hooks)).

### Recognising a round

grilling fixes the shape of a round. Each question is `❓ **Q<n>** - **<title>**: <body>`, followed by `➡️ <recommended answer>`, and questions are separated by `---`. "Word each question so "yes" accepts your recommended answer." (`<mps>/skills/productivity/grilling/SKILL.md`, lines 10-24). A Stop hook can match `❓ **Q` in `last_assistant_message` to recognise a round and parse its questions and recommendations. The next UserPromptSubmit carries the answers.

Two things grilling does not give us, which the companion would have to add:

- Question numbering restarts every round. Stable ids across rounds are not specified.
- grilling does not write down which answer opened which question. "Each round the user answers reshapes the tree" (grilling `SKILL.md` line 26), but those edges stay implicit.

The hook approach captures the raw rounds reliably. The design-tree edges need either a companion instruction for the model to emit them, or inference after the fact. This feeds the ticket "Charting file format".

### Starting the server

- A `` !`…` `` injection runs before the skill loads, uses "the Bash tool's default 2-minute timeout", and aborts the skill if it fails ([skills](https://code.claude.com/docs/en/skills)). A server start placed here must detach and return at once.
- The alternative is a plain instruction for Claude to run the server with Bash in the background. Pre-approve it with `allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/… *)`. The grant lasts only for the turn that invokes the skill ([skills: allowed-tools and `${CLAUDE_SKILL_DIR}`](https://code.claude.com/docs/en/skills)).
- `${CLAUDE_SKILL_DIR}` resolves to the skill's own folder, so a contained toolchain under `skills/<name>/` can be addressed without hard-coded paths ([skills](https://code.claude.com/docs/en/skills)). This fits the map's note that the companion may bring its own toolchain inside its folder.

### Packaging: loose skill or plugin

`sync.py` supports both `skills/<name>/` and `plugins/<name>/.claude-plugin/plugin.json`. A plugin directory is linked into `~/.claude/skills`, "which is what makes it a skills-dir plugin and gives it a /namespace:command prefix" (`sync.py`, `own_link_plan`). Claude Code plugins can ship always-on hooks in `hooks/hooks.json` ([hooks: plugin hooks](https://code.claude.com/docs/en/hooks)). With those, a UserPromptExpansion hook could see `/mattpocock-skills:wayfinder` even when the companion was never invoked. Not verified: whether a skills-dir plugin linked this way loads `hooks/hooks.json` in the same way as a marketplace-installed plugin. A loose skill with frontmatter hooks needs no such check.

## 3. What charting writes to disk today

With the local-markdown tracker, which this effort uses:

| Output | Path | Source |
|---|---|---|
| Map | `.scratch/<effort>/map.md`, with Destination, Notes, empty Decisions so far, Not yet specified, Out of scope | wayfinder `SKILL.md` steps 3 and 27-53; `<mps>/skills/engineering/setup-matt-pocock-skills/issue-tracker-local.md` line 25 |
| Tickets | `.scratch/<effort>/issues/NN-<slug>.md`, with `Type:`, `Status:` and `Blocked by:` lines and `## Question` | wayfinder step 4; issue-tracker-local.md lines 26-28 |
| Glossary and ADRs | `GLOSSARY.md` and `docs/adr/NNNN-*.md`, written inline as terms settle | domain-modeling `SKILL.md` lines 40, 62, 66-74 |
| Research findings | a pushed `research/<name>` branch, with no PR | wayfinder step 5 |

Nothing is written for the rounds, the questions, the recommendations or the answers. Charting "hand-resolves nothing" (wayfinder step 6), and the rounds survive only in the conversation. Claude Code's session transcript JSONL (`transcript_path`) is the only place they persist today ([hooks: common input fields](https://code.claude.com/docs/en/hooks)). `.scratch/map-view/` in this repo shows the result: `map.md` plus eight files in `issues/`, and no record of the grilling that produced them.

The Decisions-so-far line of a resolved ticket is written only when the ticket is resolved (issue-tracker-local.md line 30). During charting that section stays empty (wayfinder step 3).

## 4. Does any upstream skill persist a design tree or rounds?

None does.

- **grilling**: "Map this as a **design tree**" and "Work the tree in **rounds**". The tree is held in context, and the skill has no file output (`<mps>/skills/productivity/grilling/SKILL.md`). It already uses the glossary terms *design tree*, *round* and *frontier*, which matches `GLOSSARY.md` → Map view.
- **grill-with-docs** consists only of "Call the Skill tool twice, for "grilling" and "domain-modeling"" (`<mps>/skills/engineering/grill-with-docs/SKILL.md`). The "docs" in its name are the glossary and ADRs from domain-modeling, not a record of the rounds. **grill-me** is only grilling.
- **to-spec** turns the conversation into one spec on the tracker (`.scratch/<feature>/spec.md` locally) using a fixed template. It writes the outcome, not the tree (`<mps>/skills/engineering/to-spec/SKILL.md`).
- **to-questionnaire** writes `to-questionnaire-<slug>.md`, with questions grouped by theme and a `>` answer stub under each (`<mps>/skills/productivity/to-questionnaire/SKILL.md`). It is the closest upstream precedent for "questions in a markdown file, answered in place". It is user-invoked and aimed at an async human recipient, so it can only be borrowed as a format idea.
- **handoff** writes a summary to `$TMPDIR`, outside the repo (`<mps>/skills/productivity/handoff/SKILL.md`).

### Upstream's position on structured question UIs

Upstream has ruled out routing grilling through a harness question tool or "experimental HTML questionnaire mode for batch grilling" (#1152). Its reasons are harness neutrality, and the concern that structured pickers push grilling towards pre-baked multiple choice. Its suggestion is a per-user preference in your own `CLAUDE.md` (`<mps>/.out-of-scope/native-question-tool.md`). This supports the map's decision to wrap wayfinder rather than change it. It also suggests that a browser answer box should stay free text.
