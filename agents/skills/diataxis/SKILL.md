---
name: diataxis
description: >
  Apply the Diataxis documentation framework to write, audit, restructure, or classify technical
  documentation. Use when: (1) writing new documentation of any kind — tutorials, how-to guides,
  reference, explanation, (2) auditing or reviewing existing docs for structural problems,
  (3) restructuring documentation that mixes concerns, (4) classifying content into the correct
  Diataxis quadrant, (5) user asks about Diataxis or documentation best practices, (6) user asks
  to "write docs", "add documentation", "document this", or similar requests.
---

# Diataxis Documentation Framework

Four documentation types derived from two axes of practice:

|                | Acquisition (Study) | Application (Work) |
|----------------|--------------------|--------------------|
| **Action**     | Tutorial           | How-to Guide       |
| **Cognition**  | Explanation         | Reference          |

## The Compass

Classify any content by asking two questions:

1. Does this inform **action** or **cognition**?
2. Does it serve **acquisition** (learning) or **application** (working)?

The answers place content in exactly one quadrant. Content spanning quadrants must be separated.

## Workflows

### Writing new documentation

1. Determine the quadrant using the compass
2. Read the corresponding reference file for that quadrant's constraints:
   - Tutorial → [references/tutorial.md](references/tutorial.md)
   - How-to guide → [references/howto.md](references/howto.md)
   - Reference → [references/reference.md](references/reference.md)
   - Explanation → [references/explanation.md](references/explanation.md)
3. Write following that quadrant's rules strictly
4. Self-audit: verify no content from adjacent quadrants has leaked in

### Auditing existing documentation

1. Read [references/audit.md](references/audit.md) for the full audit process
2. For each piece of content, apply the compass to classify it
3. Flag content that bleeds across quadrants
4. Recommend restructuring to separate mixed content

### Restructuring documentation

1. Audit first (see above)
2. Extract mixed content into the correct quadrant
3. Replace extracted content with cross-references
4. Verify each resulting document stays within its quadrant

## Critical Rules

- **Adjacent quadrants blur naturally.** Tutorials bleed into how-to guides. Reference bleeds into explanation. This is the central problem Diataxis solves — resist it.
- **Tutorials vs how-to guides is NOT basic vs advanced.** It is learning vs working.
- **Each type has strict prohibitions.** Tutorials must not explain. How-to guides must not teach. Reference must not instruct. Explanation must not describe machinery.
- **Iterate, don't plan.** Structure emerges from well-formed components, not top-down imposition.
