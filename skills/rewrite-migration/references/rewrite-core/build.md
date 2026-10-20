# rewrite-core: build

Rows the runner makes after a Run from what a Recipe left in the tree: a warning that it could not finish a change,
or an exception. The text never reaches a file; the row's `message` is the only copy, and `recipe` names the Recipe
when the Run had one leaf. The anchor is the file plus a hash of the message.

## build/recipe-warning

A Recipe changed the file only partly, or not at all, and said why.

- Read the message, then the diff of the file in `fix.patch`. Finish the change by hand where the Recipe stopped.
- When the message names a Recipe gap that will recur, list it as a Recipe candidate in the summary.

## build/recipe-error

A Recipe threw while visiting the file; its change to that file was dropped, the rest of the Run stands.

- Find what that Recipe does (`rewrite recipe show <name>`) and make its change to this file by hand, checking it
  compiles.
- Always list the error in the summary as a Recipe candidate, with the message's first line.
