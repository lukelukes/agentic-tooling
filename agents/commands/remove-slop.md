---
description: Remove AI-generated code patterns from the current branch
---

# Remove AI Code Slop (Go)

Check the diff against main and remove all AI-generated patterns introduced in this branch. AI code generation often produces syntactically correct but stylistically inconsistent code that experienced Go developers wouldn't write.

## What to look for

### Comments (be aggressive here)

Go code should be self-documenting. Remove comments unless they explain _why_ something non-obvious exists. Delete:

- Any comment that restates what the code does (`// increment counter`, `// check if nil`, `// return error`)
- Section dividers or organizational comments (`// Helper functions`, `// Main logic`)
- Comments explaining standard library or language features
- Redundant godoc that just repeats the function name (`// GetUser gets a user`)
- TODO/FIXME comments added by AI that weren't in the original
- Comments on unexported functions unless genuinely subtle

When in doubt, delete the comment. The bar for keeping a comment is: "Would a senior Go dev add this?"

### Error handling

- Excessive error wrapping where a simple return would suffice
- Defensive nil checks in trusted internal codepaths
- Unnecessary panic/recover blocks for recoverable situations
- Error messages that don't add context beyond what the type provides

### Type patterns

- Unnecessary `interface{}` or `any` to work around type issues
- Type assertions without good reason
- Over-abstraction: interfaces with single implementations, unnecessary factories

### Style inconsistencies

- Naming that doesn't match file conventions (stuttering like `user.UserID` vs `user.ID`)
- Inconsistent receiver names within the same type
- Variable declarations that don't match surrounding code style
- Empty else blocks or unnecessary else after return

### Structural patterns

- Unnecessary getter/setter methods on exported fields
- Over-engineered abstractions for simple operations
- Code that handles impossible cases given the call sites

## Approach

1. Gather all changes:
   - `git diff master` — committed + staged + unstaged changes vs main
   - `git ls-files --others --exclude-standard` — untracked files (review these in full)
2. For each changed/new file, compare against existing patterns in the codebase
3. Remove or simplify anything that feels "off" relative to the codebase
4. Preserve functional correctness—only change style and structure

## Output

Provide only a 1-3 sentence summary of what you changed. Do not list every edit.
