# rewrite-migrate-java: build

Rules that `MigrateGraalVMResourceConfig` reports when it moves a GraalVM `resource-config.json` from the regex
`includes`/`excludes` format to the glob format. The anchor is the JSON path of the entry (`resources.excludes[0]`).

## build/graalvm-resource-exclude-dropped

The glob format has no excludes, so the exclude was dropped. native-image may now include resources the image left
out before (backups, secrets, large test data).

- Narrow the include globs so they no longer match what the exclude removed, or move the files out of the included
  paths. Resolve `fixed`.
- If the excluded files are harmless in the image, resolve `no-change` with a note.

Check: build the native image and list its resources (`-H:+PrintResources` or the build report); the excluded files
are absent, or their presence is accepted.

Source: [GraalVM reachability metadata: resources](https://www.graalvm.org/latest/reference-manual/native-image/metadata/#resources).

## build/graalvm-resource-pattern-unconverted

The include pattern uses regex syntax with no glob equivalent (a character class, an alternation, a bounded
quantifier, `\d`, an anchor, ...), so the entry stays a `pattern` entry inside the new `resources` array, which the
glob format does not read.

- Replace the entry with one or more `glob` entries that match the same files. Resolve `fixed`.

Check: build the native image and confirm the resources are present at run time.

Source: [GraalVM reachability metadata: resources](https://www.graalvm.org/latest/reference-manual/native-image/metadata/#resources).
