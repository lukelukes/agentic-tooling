<task>
Research current best practices for {{TARGET}} and produce a terse, LLM-optimized guidance file that AI coding agents can reference when working with this technology.
</task>

<inputs>
<target>{{TARGET}}</target>
<version>{{VERSION | "latest stable"}}</version>
<project_type>{{PROJECT_TYPE | "general"}}</project_type>
<focus_areas>{{FOCUS_AREAS | "balanced"}}</focus_areas>
</inputs>

<research_instructions>
Search comprehensively across these source types, prioritizing recency:

1. Official documentation and style guides
2. Language/framework team blogs and RFCs
3. Established style guides (Google, Airbnb, Uber, etc.)
4. GitHub discussions on the main repository
5. Conference talks from the past 12 months
6. Recognized expert blogs and tutorials
7. Community consensus from high-signal sources

Prioritize modern, idiomatic patterns. When a newer approach supersedes an older one, document only the newer approach unless the older remains significantly prevalent.

If {{VERSION}} is specified, constrain recommendations to that version. Otherwise, target the latest stable release and note any bleeding-edge patterns with explicit version requirements.
</research_instructions>

<output_format>
Produce a markdown file with the following structure. Keep total length between 150-200 lines. Write for an LLM reader that can see the codebase—be terse, specific, and actionable.

Use this exact structure:
```markdown
# {{TARGET}} Guidance

> Version: {{resolved_version}}
> Last researched: {{date}}
> Project type: {{PROJECT_TYPE}}

## Quick Reference

One-paragraph summary of the most critical guidance. What should the agent internalize before touching any code?

## Code Patterns

{{For each pattern}}
### {{Pattern Name}}
[MUST|PREFER|CONSIDER] {{one-line description}}
{{2-3 sentence explanation of when and why}}
{{End for}}

## Anti-Patterns

{{For each anti-pattern}}
### {{Anti-Pattern Name}}
[NEVER|AVOID|DEPRECATED] {{one-line description}}
{{Why this is problematic, what to do instead}}
{{End for}}

## Performance

{{Bulleted list of performance-critical guidance}}
{{Each item: specific, measurable where possible}}

## Security

{{Bulleted list of security considerations}}
{{Focus on common vulnerabilities specific to this technology}}

## Common Pitfalls

{{Numbered list of mistakes agents frequently make}}
{{Each: problem → symptom → fix}}

## Decision Heuristics

{{if-then rules for common decision points}}
Format: `IF {{condition}} THEN {{action}}`

## Related Guidance

{{Only if applicable}}
When working with {{TARGET}} alongside other technologies:
- For TypeScript specifics: @typescript.md
- For testing patterns: @testing.md
- {{other relevant cross-references}}
```
</output_format>

<confidence_markers>
Use these markers consistently:
- MUST: Non-negotiable. Violating this causes bugs, security issues, or significant problems.
- PREFER: Strong recommendation. Deviate only with clear justification.
- CONSIDER: Situationally beneficial. Evaluate based on context.
- NEVER: Causes serious problems. No exceptions.
- AVOID: Generally problematic. Rare exceptions may exist.
- DEPRECATED: Was acceptable, now superseded. Migrate away.
</confidence_markers>

<style_constraints>
- No code snippets (they consume line budget; agent can look up syntax)
- No preamble or meta-commentary
- No obvious/generic advice ("write clean code", "use meaningful names")
- Every statement should be specific to {{TARGET}}
- Use concrete thresholds where applicable ("if > 10 items", "when latency exceeds 100ms")
- Assume the agent has full codebase access—reference file patterns, not hypotheticals
- Front-load the most important information in each section
</style_constraints>

<focus_weighting>
{{IF FOCUS_AREAS specified}}
Weight the following sections more heavily, providing additional depth:
{{FOCUS_AREAS}}
Other sections should remain present but can be more condensed.
{{END IF}}
</focus_weighting>

<project_type_context>
{{IF PROJECT_TYPE specified}}
Tailor recommendations for a {{PROJECT_TYPE}}:
- CLI tool: emphasize startup time, argument parsing patterns, exit codes
- Web app: emphasize request handling, state management, routing
- Library: emphasize API design, backwards compatibility, documentation
- Microservice: emphasize resilience, observability, inter-service communication
- Monorepo: emphasize module boundaries, shared code patterns, build optimization
{{END IF}}
</project_type_context>

<quality_checks>
Before finalizing, verify:
1. Every recommendation is specific to {{TARGET}}, not generic programming advice
2. Confidence markers are applied consistently
3. Anti-patterns include what to do instead
4. Decision heuristics cover the most common branch points
5. Total length is 150-200 lines
6. No code snippets included
7. Information is current as of the latest stable release
</quality_checks>
