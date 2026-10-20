# Spring Boot 4

Notes that cut across the Boot 4 Migrations. Rule sections are under `../rewrite-*/`; Spring Cloud and build notes
without rule ids are in `../rewrite-spring/cloud.md` and `../rewrite-spring/build.md`.

## org.openrewrite.java.spring.boot4.UpgradeSpringBoot_4_0

### Resolved versions first

Before choosing any API, read what the migrated build resolves: Spring Boot, Spring Framework, Spring Security,
Jackson (2 and 3 can both be present), Hibernate, Spring Cloud OpenFeign and Spring Cloud AWS. Their version numbers
are independent: Boot 4.0 runs Framework 7.0 and Jackson 3, OpenFeign 5.x and Spring Cloud AWS 4.x each follow their
own release lines. Use `dependencyInsight --configuration <name>` (Gradle) or `dependency:tree` (Maven), and the
sources or JARs of those versions. A successful Run or a green compile does not establish behavioural compatibility;
the BEHAVIOUR items and step 6 of the loop do.

### Two Runs with a commit between

Use only when compile errors remain that need the new version's type hierarchy (members or supertypes of types that
exist only after the upgrade) and the human agrees:

1. Resolve or defer every `BLOCKER` of Run 1, and commit (Run commit, then the agent commits).
2. `rewrite recipe run <the Recipes that need the new hierarchy> --verify` as Run 2.
3. Work Run 2's Worklist on its own. From then on name Run 1 by its id, because `run show` defaults to the newest Run.
   Resolutions do not carry over between Runs.

### Guide

[Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## org.openrewrite.java.spring.boot4.UpgradeSpringBoot_4_1

Runs `UpgradeSpringBoot_4_0` first, so everything above applies. Boot 4.1 stays on Spring Framework 7.0 and moves
Spring Security to 7.1 and Hibernate to 7.4; check those resolved versions in particular.
