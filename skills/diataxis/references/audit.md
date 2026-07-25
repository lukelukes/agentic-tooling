# Auditing Documentation with Diataxis

## Process

For each document or section:

1. **Classify** — Apply the compass. Ask: action or cognition? Acquisition or application?
2. **Check purity** — Does the content stay within its quadrant?
3. **Identify bleed** — Flag content that belongs in a different quadrant
4. **Recommend** — Suggest extraction, cross-referencing, or restructuring

## What to look for

### Tutorials containing explanation

**Symptom:** Paragraphs of "why" or "how this works" between action steps.
**Fix:** Remove the explanation. Add a link: "To understand why, see [explanation doc]."

### Tutorials containing choices

**Symptom:** "You can use either X or Y..." or "If you prefer..."
**Fix:** Pick one path. Remove alternatives entirely. This is a tutorial, not a how-to guide.

### How-to guides that teach

**Symptom:** Extensive background before getting to the steps. Assumes the reader has no context.
**Fix:** Strip the background. Move it to explanation. Start with prerequisites and steps.

### Reference that explains

**Symptom:** A parameter description expands into rationale: "This flag exists because..."
**Fix:** Move rationale to explanation. Keep reference to: what it is, what it does, what values it accepts.

### Explanation that describes machinery

**Symptom:** Exact command syntax, parameter lists, or step-by-step procedures in a conceptual document.
**Fix:** Replace with conceptual descriptions. Link to reference for specifics.

### Mixed documents

**Symptom:** A single page titled "Getting Started" that contains tutorial steps, reference tables, conceptual background, and how-to procedures.
**Fix:** Split into separate documents, one per quadrant. Cross-reference between them.

## Audit report format

For each finding:

```
**Location:** [file/section]
**Current quadrant:** [what it is trying to be]
**Bleed from:** [which other quadrant is leaking in]
**Specific content:** [quote or describe the problematic content]
**Recommendation:** [extract to X / remove / replace with link to Y]
```

## Severity levels

- **Structural collapse:** Two or more quadrants fully merged in a single document. Requires rewrite.
- **Significant bleed:** Multiple paragraphs from wrong quadrant. Requires extraction.
- **Minor bleed:** A sentence or two. Quick fix — extract or remove.
