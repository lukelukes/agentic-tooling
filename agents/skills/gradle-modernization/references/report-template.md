# Audit Report Template

Use this structure. Keep the executive summary to five lines. Put the detail in the change groups. Each finding cites a best-practice ID from `best-practices.md`, for example D2, or a Gradle version from `gradle-9x-features.md`, for example "9.2.0 daemon toolchain". The user can then look it up.

```markdown
# Gradle modernization audit: <project name>

## Coverage
- Gradle executed: <yes | no, with reason>
- Scanned: <builds and files from scanner facts.coverage, plus manually inspected paths>
- Skipped: <external builds, symlinks, unreadable files, Kotlin DSL, dynamic includes>
- Dynamic checks not performed: <commands and configurations, with reasons>
- Upgrade sources: <target-pinned guides read; version boundaries crossed>

## Snapshot
- Gradle: <current> (`-all` or `-bin`); target: <latest compatible; plugin blockers; gap to newest>
- Daemon JVM: <version, vendor>; compiler toolchain: <>; bytecode or release target: <>; test framework: <>
- Structure: <single | multi (N subprojects)>; build logic in <subprojects{} | buildSrc | build-logic | apply from>
- Version catalog: <default | named | imported | programmatic | none>; preserved exceptions: <>
- Flags: <declared root values compared with observed effective values>
- Deprecation warnings (`--warning-mode=all`): <count; top 3 by type>
- Configuration cache: <baseline mode; store and reuse result on <tasks>; not verified: reason>
- Test tasks: <each Test task with outcome, case count and XML directory; missing or NO-SOURCE tasks>

## Best-practice scorecard
| Area | ✅ Followed | ❌ Violated | ⚠ Suspected (not verified) | ❓ Not checked | ➖ N/A |
|---|---|---|---|---|---|
| General (9) | | | | | |
| Structuring (5) | | | | | |
| Dependencies (9) | | | | | |
| Tasks (11) | | | | | |
| Performance (5) | | | | | |
| Security (4) | | | | | |
| Testing (1) | | | | | |

Violated: <comma-separated IDs, for example G2, G3, D1, D2, D4, P2, P3, Sec1>

## Proposed change groups (apply in order)

### 1. <Title>. Risk: Low. Confidence: confirmed. Prerequisites: <none | "group 3" | "plugin X 2.0 or later">
**What:** <one or two sentences>
**Why:** <practice ID or Gradle version, plus the benefit in one line>
**Evidence:** <file:line and the text found, or "scanner (suspected), not verified", or "build output: ...">
**Consequence if skipped:** <one line>
**Expected benefit:** <build blocker | measured performance benefit | maintenance preference>
**Files:** <list>
**Verification:** <commands to run again; what compare_runs, the dependency diff and the cache pair must show>

### 2. ...

## Information only, no action
- <9.x features that apply to this project but need no change. Example: "9.3.0 restructured the HTML test report; your CI reads it in ci/parse-tests.sh">
- <Isolated Projects: optional diagnostics run>
- <Kotlin DSL practice: out of scope>

## Deferred, needs a human decision
- <Product source and test edits, publication coordinates, behavior changes, experimental feature previews>
```

## Default order

Adjust the order by prerequisites. Example: a plugin that blocks the wrapper upgrade moves before the upgrade. For a major upgrade, go 8.x, then latest 8.x, then 9.x.

1. Clear current-version deprecations and update plugin compatibility. Then wrapper upgrade with checksum and `-bin` (G2, Sec1, P5).
2. Flag centralization. New caching, parallelism, encoding or JVM policy are separate items (G5, P1, P2).
3. Root project name. Remove subproject `gradle.properties` (G6, G7).
4. Repositories to settings, with content filtering (D4, D7).
5. `plugins {}` block and version catalog migration (G3, D1, D2, D3).
6. Dependency locking (C1). Keep existing locking, or enable it with generated state. No catalog prerequisite. Offer C2 only after you know whether the divergence is intentional.
7. Optional daemon pinning and separate compilation-toolchain proposals. Do not replace `sourceCompatibility` mechanically. The same Java number does not mean equal compilation.
8. Task hygiene: register, named, configureEach, lazy properties, `layout.buildDirectory` (T1, T4, T5, T6, T11, plus long-standing deprecations).
9. Convention plugins into `build-logic/` (S3, S5). One subproject at a time.
10. Parent-project lookup cleanup. `NO_IMPLICIT_LOOKUP_IN_PARENT_PROJECTS` only as an explicit experiment (9.6.0).
11. Configuration cache: baseline in the existing mode, then strict store and reuse with real task execution, then enable for the verified workloads (P3).
12. Narrow exclusions and remove redundant dependencies (D6, D8). These change behavior. Run the full tests.
13. Advisory items: modularization, root sources, reproducibility checks, Isolated Projects diagnostics.
