---
name: port-from
description: Port tooling, config, or a set of commits from a sibling repo into this one, adapted to this repo's stack.
argument-hint: "<../repo> [what: tooling | commit <sha..sha> | feature <name>] [except ...]"
disable-model-invocation: true
---

Port from $ARGUMENTS into this repo.

1. Read the source: the named commits (`git -C <repo> log -p`), or its tooling (justfile, Makefile, mise.toml, lint configs, CI workflows, pre-commit hooks, editor config).
2. Read this repo's stack and existing tooling. List each item as one of: port as-is / adapt / skip (with reason, e.g. a package manager this repo does not use). Respect any `except` in the arguments.
3. Show the table and wait for my go, unless the arguments are explicit.
4. Port. Use this repo's package manager and paths. Keep versions in one source of truth.
5. Run the ported checks once to prove they work here, and report the results.
