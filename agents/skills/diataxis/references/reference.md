# Reference (Information-oriented)

Technical descriptions of the machinery and how to operate it. Contains propositional knowledge a user consults while working.

## Constraints

- **Describe and only describe.** No instruction, no explanation, no opinion. Neutral, objective, austere.
- **Do not instruct.** Link to tutorials and how-to guides for that.
- **Do not explain.** Link to explanation documents for context and rationale.

## Requirements

- **Authoritative.** No doubt or ambiguity. Users consult reference; they do not read it.
- **Consistent patterns.** Reference is useful when it is consistent. Adopt standard formats and maintain them.
- **Mirror the structure of the machinery.** Documentation structure should reflect the product structure, so users navigate both simultaneously.
- **Accuracy, precision, completeness.** The primary imperatives.
- **Provide examples without instructing.** Use illustrations to clarify, not to teach.

## What reference contains

- Commands, flags, options, parameters
- Return values and error codes
- Limitations and edge cases
- Warnings and caveats
- Brief usage examples
- Type signatures and schemas

## Structure

Mirror the product. If the product has three subsystems, reference has three corresponding sections. Use consistent formatting:

```
## `command-name`

**Synopsis:** `command-name [OPTIONS] <argument>`

**Description:** Brief neutral description of what the command does.

**Arguments:**
- `<argument>` — What this argument represents

**Options:**
- `--flag` — What this flag does
- `--option <value>` — What this option controls. Default: `default-value`

**Returns:** Description of output

**Errors:**
- `E001` — When this error occurs
```

## Example: Good reference entry

```
## `booster pkg pin`

**Synopsis:** `booster pkg pin <package> <version>`

Pin a package to a specific version, preventing automatic updates.

**Arguments:**
- `<package>` — Package name as registered in the manifest
- `<version>` — Semver version string

**Errors:**
- Returns exit code 1 if the version is not tracked
- Returns exit code 2 on dependency conflict
```

## Example: Bad reference (explains instead of describing)

```
## `booster pkg pin`

The pin command is useful when you want to prevent a package from
being updated. This is important in production environments because
unexpected updates can cause...
```

## Common failure: Reference that absorbs explanation

Examples are engaging. A brief example expands into "why this works," which becomes a paragraph of context. Resist. If the example needs explanation, link to an explanation document.
