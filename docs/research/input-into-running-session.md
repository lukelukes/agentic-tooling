# Getting browser input into a running Claude Code session

Question: how can an answer typed in a local browser page (the map view) reach a Claude Code session that is already running in a terminal, so the agent picks it up and asks the next round?

Checked against the official Claude Code docs on 2026-10-21 and the installed Claude Code, `2.1.306 (Claude Code)` (`claude --version`).

## Short answer

There are five mechanisms that work in a terminal session today:

1. A background waiter: Bash with `run_in_background`, or the Monitor tool.
2. Hooks, mainly an `asyncRewake` hook.
3. Channels, MCP servers that push events into the session.
4. The session's cross-session inbox socket.
5. The user's own typed or queued messages.

Remote Control, `--resume` and the Agent SDK do not apply here.

**Recommendation:** after the agent posts a round, it starts a background waiter that exits when the map view writes the answer file, then ends its turn. The terminal goes back to an idle prompt, so the user can answer either in the browser or in the terminal. The waiter's exit wakes the session. This needs no flags, plugins, settings or research-preview features. Channels give the cleanest push semantics, but every launch needs a development flag and a warning dialog, so keep them as an upgrade path.

## Comparison

| Mechanism | Mid-turn | Session idle at prompt | What the terminal shows | User can still answer in terminal | Limits |
|---|---|---|---|---|---|
| Background Bash waiter (`run_in_background`) | n/a: the agent itself starts it | Wakes Claude when the command exits [1][2] | Background task indicator, then Claude resumes | Yes; the prompt is free | No time limit in a local interactive session [3]; disabled by `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` or bare mode [4] |
| Monitor tool (`until` loop or `tail -F`) | Events interject [5] | Events interject [5] | Monitor event notifications | Yes | Watch deadline: 5 min default, 30 min max [5]; not on Bedrock, Vertex or Foundry, or with `DISABLE_TELEMETRY` / `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` [5] |
| Plugin monitor (`monitors/monitors.json`) | Notifications | Notifications | Same | Yes | Runs for the whole session, interactive only, same availability limits as Monitor [6] |
| Foreground Bash wait | Blocks the turn | n/a | A running tool | Only by queueing [7] or pressing Esc | Timeout 2 min default, 10 min max; after that the command moves to the background [8] |
| Stop hook, synchronous, `decision: "block"` | Holds the end of the turn | n/a | Stop hook running | Not cleanly | 600 s hook timeout; at most 8 consecutive continuations [9][10] |
| `asyncRewake` hook | Output arrives next turn | Exit code 2 wakes Claude immediately [11] | System reminder for Claude; async output hidden unless verbose [11] | Yes | Hook `timeout` still applies [11]; needs settings or a plugin hook |
| Channel (MCP `claude/channel`) | Queued, delivered on the next turn [12] | Arrives and Claude acts [12][13] | `← name: text` line [12][13] | Yes | Research preview; claude.ai or Console auth; custom channels need `--dangerously-load-development-channels` with a confirmation dialog [13][14] |
| Cross-session inbox socket | Read between tool calls [15] | Starts a new turn [15] | Dim `› Message from …` line [15] | Yes | v2.1.224 or later; framed as a peer session, not the user [15]; wire format undocumented |
| Typed or queued message | Delivered after the current tool calls [7] | Normal prompt | Normal | (this is the terminal) | Not from the browser |
| Remote Control | — | — | — | Yes | Only claude.ai/code and the Claude apps, not a custom page [16] |

## Details

### (a) The agent waits on a file

**Background Bash.** Claude can start a command with `run_in_background: true` and keep working. Claude Code "can respond to new prompts while the command continues executing in the background" [4]. In the installed 2.1.306, the Bash tool tells the model that a background command "keeps running across turns and re-invokes you when it exits" [2]. The docs make the same point indirectly: Stop-hook input carries `background_tasks` so hooks can tell "'session is done' from 'session is paused waiting for background work to wake it back up'" [1]. In a terminal session, background commands have no time limit [3]. A sketch of the waiter: `until [ -s answers/round-N.md ]; do sleep 1; done; cat answers/round-N.md`.

- Mid-turn: not relevant, because the agent starts the waiter and then ends its turn.
- Idle: the waiter's exit starts a new turn.
- Terminal: the prompt is free while the waiter runs. If the user answers in the terminal instead, Claude should stop the waiter (`TaskStop`) and the companion should record the answer, so the browser does not ask the same round again.

**Monitor tool.** Monitor runs a script in the background and "feeds each output line back to Claude". The docs say: "You keep working in the same session and Claude interjects when an event arrives" [5]. Every watch has a deadline of 5 minutes by default and 30 minutes at most. When the deadline passes, Claude gets one notice and can restart the watch [5]. Monitor uses the Bash permission rules. It is unavailable on Bedrock, Google's Agent Platform and Foundry, and when `DISABLE_TELEMETRY` or `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` is set [5]. Its WebSocket source refuses private and link-local addresses [5]. A localhost map-view socket therefore probably fails; use a command watch instead. A user who takes longer than 30 minutes to answer costs one restart turn per deadline. That makes Monitor a worse fit than a plain background waiter.

**Plugin monitors.** A plugin can declare `monitors/monitors.json` entries. They start with the session, or the first time a named skill runs, and run until the session ends. "What it prints reaches Claude as notifications" [6]. They run only in interactive sessions, and the Monitor availability limits apply [6]. This option is attractive only if the companion ships as a plugin.

**Foreground wait.** A foreground Bash timeout defaults to 2 minutes and can be at most 10 minutes. After that, the command moves to the background instead of failing [8]. A foreground wait blocks the turn. A user who wants to answer in the terminal can only queue a message, which is delivered when the tool calls finish [7], or press Esc. Don't use it.

### (b) Hooks

- **Stop with `decision: "block"`** "Prevents Claude from stopping, continues the conversation" with `reason` delivered to Claude [9]. A synchronous Stop hook could poll for the answer file and return it as `reason`. That holds the turn open, with no clean way for the user to answer in the terminal. It is also bounded by the hook timeout of 600 s by default [9] and by an 8-consecutive-continuation cap (`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`) [10].
- **`asyncRewake`.** By default, async hook output "is delivered on the next conversation turn. If the session is idle, the response waits until the next user interaction. Exception: an `asyncRewake` hook that exits with code 2 wakes Claude immediately even when the session is idle." Claude Code still enforces `timeout` on `asyncRewake` hooks [11]. This works like the background waiter, but it must be configured in settings or a plugin, and it fires on every matching event in every session, not only during charting.
- **UserPromptSubmit** can only add `additionalContext` to a prompt the user, a scheduled task or a peer message has already sent [9][10]. It cannot start a turn.
- **Notification `idle_prompt`** fires about 60 s after Claude goes idle, but it has no decision control and cannot feed Claude [9][10].

### (c) Channels

"A channel is an MCP server that pushes events into your running Claude Code session" [13]. The server declares `capabilities.experimental['claude/channel']` and emits `notifications/claude/channel` with `content` and `meta`. Claude receives a `<channel source="…" …>` tag, and the terminal shows `← webhook: …` [12]. "Events queue into the session and are processed in order. If several notifications arrive while Claude is busy, they're delivered together on the next turn" [12]. The official **fakechat** demo is exactly a localhost browser chat UI into a session [13]. Limitations:

- Channels are a research preview, and "the `--channels` flag syntax and protocol contract may change". They need claude.ai or Console API-key auth. Team and Enterprise orgs must turn on `channelsEnabled` [13].
- Only allowlisted plugins run under `--channels`. A custom channel needs `claude --dangerously-load-development-channels server:<name>`, which shows a full-screen warning dialog at every start. The flag is ignored in `-p` mode and the SDK [14].
- Every session must be started with the flag. Being in `.mcp.json` is not enough [13].
- On the v2 MCP client runtime, a channel server that negotiates protocol revision 2026-07-28 is not registered. Workaround: `MCP_PROTOCOL_NEGOTIATION=legacy` [17].
- Notifications are not acknowledged, and they are dropped silently if the channel is not registered [12].
- The server needs `@modelcontextprotocol/sdk` and a Node-compatible runtime [14]. This is allowed by the map's note that the companion may bring its own toolchain.

### (d) Other mechanisms

**Cross-session inbox socket.** Since v2.1.224, each session binds a Unix socket and exports its path as `CLAUDE_CODE_MESSAGING_SOCKET`, with a token in `CLAUDE_CODE_MESSAGING_TOKEN`. Both are present in this 2.1.306 environment. The docs name posting into a session from "a script or hook" as a use case [15]. Delivery: "The receiving Claude reads the message between tool calls during an active turn, so a running tool is never interrupted. When the receiving session is idle, Claude Code starts a new turn with the message" [15]. A message from the session's own child processes, such as a map-view server that the agent started through Bash, is delivered by default [15]. Caveats:

- Claude is told the message came "from another session, not from you", and it "never counts as your consent" [15]. That framing is wrong for a user's answer.
- The JSON wire format for posted messages is not documented. Only the optional `{"type":"auth","token":…}` first line is documented [15].
- A connection must send a complete line within 30 s [15].
- A server that was not started by the session falls under the `crossSessionInbound` defaults [15].

This is a promising push path, but it relies on undocumented details.

**Remote Control** connects only claude.ai/code and the Claude mobile apps to a local session, so it cannot be driven from a custom page [16].

**`claude --resume`** and **the Agent SDK** start or drive a different process. They do not inject into a terminal session that is already open.

**`AskUserQuestion`** is answered only in the terminal dialog [5].

**The user typing in the terminal** always works. A message typed mid-turn is queued and delivered "as soon as those tool calls finish, within the same turn" [7].

## Recommendation for the map view

1. When the companion posts a round, it starts a background Bash waiter on the round's answer file and ends the turn. The map view's only write, the answer, creates that file. The waiter exits, and Claude wakes and reads it.
2. The terminal stays usable. If the user answers there, the companion writes the same answer file itself and stops the waiter, so both surfaces stay consistent.
3. Monitor is the fallback where background tasks are off. Plan for its 30-minute deadline.
4. Channels are the upgrade path if push semantics are needed beyond a single waiting round. They depend on a research preview and a development flag at every launch.

## Sources

1. Hooks reference, Stop input (`background_tasks`, `session_crons`): https://code.claude.com/docs/en/hooks
2. Installed Claude Code 2.1.306, Bash tool description for `run_in_background` (observed in the agent's own tool schema)
3. Tools reference, "Time limit for background commands": https://code.claude.com/docs/en/tools-reference
4. Interactive mode, "How backgrounding works": https://code.claude.com/docs/en/interactive-mode
5. Tools reference, "Monitor tool", "WebSocket source", "AskUserQuestion tool behavior": https://code.claude.com/docs/en/tools-reference
6. Plugin components, "Monitors": https://code.claude.com/docs/en/plugins/components
7. Interactive mode, "Queue messages while Claude works": https://code.claude.com/docs/en/interactive-mode
8. Tools reference, "Timeout and output limits", "Foreground commands that move to the background": https://code.claude.com/docs/en/tools-reference
9. Hooks reference, decision control, timeouts and the Notification matcher: https://code.claude.com/docs/en/hooks
10. Hooks reference, Stop loop prevention and UserPromptSubmit sources: https://code.claude.com/docs/en/hooks
11. Hooks reference, "Run hooks in the background" (`async`, `asyncRewake`, limitations): https://code.claude.com/docs/en/hooks
12. Channels reference, "Notification format" and the webhook example: https://code.claude.com/docs/en/channels-reference
13. Channels: https://code.claude.com/docs/en/channels
14. Channels reference, "What you need" and "Test during the research preview": https://code.claude.com/docs/en/channels-reference
15. Cross-session messaging, "Message delivery", "How a session treats an incoming message", "The session's inbox socket": https://code.claude.com/docs/en/cross-session-messaging
16. Remote Control: https://code.claude.com/docs/en/remote-control
17. MCP, "Push messages with channels": https://code.claude.com/docs/en/mcp
