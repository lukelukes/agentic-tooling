# Audit Report Template

Use this structure. Keep the executive summary to five lines; put the detail in the change groups. Every finding cites either a best-practice ID (from `best-practices.md`, e.g. D2) or a Gradle version (from `gradle-9x-features.md`, e.g. "9.2.0 daemon toolchain") so the user can look it up.

```markdown
# Gradle modernization audit — <project name>

## Coverage
- Gradle executed: <yes | no — reason>
- Scanned: <builds/files from scanner facts.coverage plus manually inspected paths>
- Skipped: <external builds, symlinks, unreadable files, Kotlin DSL, dynamic includes>
- Dynamic checks not performed: <commands/configurations + reasons>
- Upgrade sources: <target-pinned guides read; crossed boundaries>

## Snapshot
- Gradle: <current> (`-all`/`-bin`) → target <latest compatible; plugin blockers and gap to newest>
- Daemon JVM: <version/vendor>; compiler toolchain: <>; bytecode/release target: <>; test framework: <>
- Structure: <single|multi (N subprojects)>, build logic in <subprojects{} | buildSrc | build-logic | apply from>
- Version catalog: <default/named/imported/programmatic | none>; preserved exceptions: <>
- Flags: <declared root values vs observed effective values>
- Deprecation warnings (`--warning-mode=all`): <count, top 3 by type>
- Configuration cache: <baseline mode; store/reuse result on <tasks>; not verified: reason>
- Test tasks: <each Test task, outcome, case count, XML dir; missing/NO-SOURCE tasks>

## Best-practice scorecard
| Area | ✅ Followed | ❌ Violated | ⚠ Suspected (unverified) | ❓ Not checked | ➖ N/A |
|---|---|---|---|---|---|
| General (9) | | | | | |
| Structuring (5) | | | | | |
| Dependencies (9) | | | | | |
| Tasks (11) | | | | | |
| Performance (5) | | | | | |
| Security (4) | | | | | |
| Testing (1) | | | | | |

Violated: <comma-separated IDs, e.g. G2, G3, D1, D2, D4, P2, P3, Sec1>

## Proposed change groups (apply in order)

### 1. <Title> — risk: Low — confidence: confirmed — prerequisites: <none | "group 3" | "plugin X ≥ 2.0">
**What:** <one or two sentences>
**Why:** <practice ID / Gradle version + one-line benefit>
**Evidence:** <file:line + the offending text, or "scanner (suspected) — not yet verified", or "build output: …">
**Consequence if skipped:** <one line>
**Expected benefit:** <build blocker | measured performance benefit | maintenance preference>
**Files:** <list>
**Verification:** <commands to re-run; what compare_runs / dependency diff / cache pair must show>

### 2. …

## Worth knowing, not applying
- <9.x features relevant to this project that are informational — e.g. "9.3.0 restructured the HTML test report; your CI scrapes it (see ci/parse-tests.sh)">
- <Isolated Projects: optional diagnostics run>
- <Kotlin DSL practice: out of scope>

## Deferred / needs human decision
- <Product source/test edits, publication coordinates, behaviour changes and experimental feature previews>
```

Default ordering (adjust by prerequisites — e.g. a plugin that blocks the wrapper upgrade moves ahead of it; 8.x → latest 8.x → 9.x for major upgrades):

1. Clear current-version deprecations + plugin compatibility updates, then wrapper upgrade + checksum + `-bin` (G2, Sec1, P5)
2. Flag centralization; new caching, parallelism, encoding or JVM policy as separate items (G5, P1, P2)
3. Root project name, remove subproject `gradle.properties` (G6, G7)
4. Repositories to settings + content filtering (D4, D7)
5. `plugins {}` block + version catalog migration (G3, D1, D2, D3)
6. Dependency locking (C1) — preserve existing locking or enable with generated state; no catalog prerequisite. Offer C2 only after checking whether divergence is intentional.
7. Optional daemon pinning and separate compilation-toolchain proposals; don't mechanically replace `sourceCompatibility` or assume the same Java number means equivalent compilation
8. Task hygiene: register/named/configureEach, lazy properties, `layout.buildDirectory` (T1, T4, T5, T6, T11 + long-standing deprecations)
9. Convention plugins into `build-logic/` (S3, S5) — one subproject at a time
10. Parent-project lookup cleanup; `NO_IMPLICIT_LOOKUP_IN_PARENT_PROJECTS` only as an explicit experiment (9.6.0)
11. Configuration cache: existing-mode baseline → strict store/reuse with real task execution → enable for verified workloads (P3)
12. Narrow exclusions, redundant deps (D6, D8) — behaviour-affecting, run full tests
13. Everything advisory: modularization, root sources, reproducibility checks, Isolated Projects diagnostics
