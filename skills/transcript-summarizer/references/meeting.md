# Meeting template

Several participants deciding or coordinating. The reader wants to act on the meeting, not relive it.

Keep it under 400 words unless the meeting ran over an hour. Ask for the meeting date if relative deadlines ("next Friday") need resolving and the transcript doesn't give it. Otherwise keep them as spoken.

## Purpose & outcome
1–2 sentences.

## Decisions
Only what was agreed, not proposals. One line each, with timestamp and who agreed if stated.

## Action items
| Owner | Task | Due | When |
|---|---|---|---|
Write "unassigned" or "no date" when the transcript doesn't say. Never infer an owner from who raised the topic.

## Key discussion points
3–6 bullets with timestamps.

## Risks & concerns raised
Bullets with timestamps, and who raised them if identified.

## Parked / unresolved
Bullets.

## Optional extras (only if asked)
- **Follow-up email:** subject plus a body of 3 sentences or fewer.
- **JSON:** `{"summary": str, "decisions": [str], "actions": [{"who": str|null, "task": str, "due": "YYYY-MM-DD"|null}], "risks": [str]}`. Output JSON only, with null for anything not stated.
