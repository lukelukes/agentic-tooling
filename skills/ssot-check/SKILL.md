---
name: ssot-check
description: Find Single Source of Truth violations in the codebase and report the drift each will cause, with concrete fixes.
disable-model-invocation: true
---

Analyze and identify places in the codebase, where we're not following the "Single Source of Truth" principle.
Not following the principle will cause implementation drift, subtle bugs and increased maintenance burden.

Tasks:
- [ ] Understand the codebase, ask the user questions if something is not clear
- [ ] Analyze the codebase for potential violations
- [ ] Craft report with the findings and potential fixes
