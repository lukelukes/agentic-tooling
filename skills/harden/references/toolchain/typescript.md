# TypeScript / Node.js (verified against Node 25.6.1 + npm registry state, 2026-09-19; current release line Node 26.x, TypeScript 7.0.2, Vitest 5.0.1)

Concrete tooling per layer. Read only the entries for the layer you are actually
proposing. Verified against documentation in September 2026; check versions before
quoting a flag as current.

## What is unusual here

Unusually easy in Node, relative to other ecosystems:

- The stdlib now covers a surprising amount. `node:test` alone gives you snapshots (stable since 23.4), file snapshots, fake timers including `Date`, function and module mocking, branch-coverage thresholds, seeded test-order randomization (26.1), global setup/teardown, and rerun-failures state. On Node 24+ it runs `.ts` files directly with zero build step — no ts-jest, no tsx, no transform config. A rigorous suite can be written with zero devDependencies plus fast-check.
- Property-based testing is genuinely best-in-class. fast-check is more capable than most QuickCheck ports (built-in shrinking with a replayable `{seed, path}`, model-based testing, and `fc.scheduler()` for async interleavings), it is maintained weekly, and it drops straight into `node:test` with no adapter.
- Mutation testing is mature and CI-practical. StrykerJS with `--since <base> --incremental` gives sub-2-minute PR gates, which is better than most ecosystems manage.
- Crash/restart testing is trivial because processes are cheap and `spawn` + SIGKILL is in the stdlib.
- There is no memory-unsafety bug class, so the entire ASAN/MSAN/TSAN apparatus is simply unnecessary for pure-JS code.

Genuinely awkward or missing, relative to other ecosystems:

- Assertion stripping. There is no `-O`/`NDEBUG`/`debug_assert!`. Every invariant you write ships and runs unless a bundler erases it, and the classic tool for that (unassert) is dead. `esbuild --drop-labels=DEV` works but is a convention you have to establish and lint around.
- Branch coverage is actively misleading by default. The stdlib's own `--test-coverage-branches` and `c8` both report raw V8 block coverage, which counts implicit `else` as covered. I measured 66.67% from Node/c8 versus 25% from istanbul on the same two-`if` function. A 90% branch gate on `node --test` is not the gate you think it is.
- Deterministic simulation testing is the weakest area. You can seed randomness and the clock, but libuv's threadpool (fs, dns, crypto, zlib), native async, and worker_threads are not controllable, so a run is only a pure function of a seed if you injected every effect behind an interface yourself. There is no madsim/Flow/Antithesis-grade harness.
- Syscall-level fault injection does not exist as a library. Everything is monkeypatched `fs`, which only exercises paths you already anticipated; real ENOSPC/EIO/EMFILE require OS-level setup (tiny tmpfs, `ulimit`) outside the test runner. Power-loss testing requires `dm-flakey`/`dm-log-writes` and root.
- Fuzzing is single-vendor. Jazzer.js works well and is maintained, but it is the only serious option, with no stdlib or foundation-backed alternative.
- OOM is uncatchable. V8 aborts the process; you cannot assert on it in-process and must always shell out to a child.

One ecosystem-specific footgun worth flagging: the three-way split between `node:test`, Vitest, and Jest means invocation syntax is not portable, and version churn is fast (TypeScript 7 went Go-native in July 2026; Vitest 5 dropped odd-numbered Node releases; ESLint is at 10.x). Pin the Node major in CI.

---

## Assertions / invariant checks compiled or stripped out of production builds

**Reach for** — `node:assert/strict` (stdlib) for the check + esbuild `--drop-labels=` (esbuild >= 0.18.13) to erase them at build. Vite: `esbuild: { dropLabels: ['DEV'] }`; rolldown/tsdown: `dropLabels`. Rollup-only: `@rollup/plugin-strip`.

```
// src/x.ts — label a single statement (use `DEV: { ... }` for a block)
DEV: assert(next >= 0, 'overdraft');

npx esbuild src/x.ts --bundle --format=esm                    # dev: kept
npx esbuild src/x.ts --bundle --format=esm --drop-labels=DEV  # prod: erased
# alt: --define:process.env.NODE_ENV='"production"' --minify  (DCEs `if (NODE_ENV!=='production')`)
```

**Caveat** — Node has NO runtime way to disable asserts — there is no `-O`/`NDEBUG`; stripping is purely a bundler step, so anything you `node --test` or ship unbundled keeps every assert. ESLint's `no-unused-labels` (in eslint:recommended) flags `DEV:` — turn it off or allowlist. The classic `unassert` / `babel-plugin-unassert` family is effectively abandoned (last npm publish 2023-04 and 2022-06); do not reach for it. `@rollup/plugin-strip` last published 2023-10.

## Regression test per fixed bug + auditing git history for fix-commits with no test

**Reach for** — No tool exists for the audit — write it with `git log`. Enforce going forward with a commit-msg/pre-push hook or a CI job (`husky`/`lefthook`, or a plain `.git/hooks` script).

```
git log --no-merges --format='%H%x09%s' --grep='^fix' -i |
while IFS=$'\t' read -r sha subj; do
  git show --name-only --format= "$sha" |
    grep -qE '(\.(test|spec)\.[jt]sx?$|(^|/)(tests?|__tests__)/)' ||
    printf '%s  %s\n' "${sha:0:8}" "$subj"
done
```

**Caveat** — Verified working on a real repo. Accuracy depends entirely on commit-message hygiene (Conventional Commits `fix:` makes it reliable; free-form messages need `--grep='fix\|bug\|regress'`). Squash-merge workflows collapse fix+test into one commit, which this handles; rebase-merge workflows can split them across commits and produce false positives — audit by PR via `gh pr list --search 'fix'` instead. Add `--since=<tag>` to keep CI runs bounded.

## Property-based testing

**Reach for** — `fast-check` (v4.10.1, actively maintained, ~weekly releases). Runner adapters: `@fast-check/vitest` (`test.prop`), `@fast-check/jest`. Works as-is inside `node:test` with no adapter.

```
import { test } from 'node:test';
import fc from 'fast-check';
test('roundtrip', () => {
  fc.assert(fc.property(fc.array(fc.integer()), (xs) =>
    decode(encode(xs)).every((v, i) => v === xs[i])), { numRuns: 1000 });
});
// replay a failure verbatim: { seed: -1019804066, path: "1:1:0:...", endOnFailure: true }
```

**Caveat** — The seed defaults to `Date.now()`, so property tests are non-deterministic run-to-run by default — a real flake source. Pin it in a setup file: `fc.configureGlobal({ seed: Number(process.env.FC_SEED ?? 0), numRuns: 1000 })`. There is no env var for this built in. On failure fast-check prints `{ seed, path, endOnFailure }` — paste that object back into `fc.assert` options to replay the exact shrunk case (verified).

## Differential / oracle testing (same code, two configs; fast path vs naive; new impl vs old)

**Reach for** — No dedicated library — `fast-check` + a hand-written oracle is the de-facto approach. For old-vs-new across published versions, install the old one under an alias: `npm i mylib-old@npm:mylib@1.2.3`.

```
fc.assert(fc.property(fc.array(fc.string()), fc.boolean(), (input, cacheOn) => {
  const a = run(input, { cache: cacheOn });   // config A
  const b = run(input, { cache: !cacheOn });  // config B
  assert.deepStrictEqual(a, b);               // structural oracle
}), { numRuns: 2000 });
// snapshot-style oracle across versions: import old from 'mylib-old'
```

**Caveat** — `assert.deepStrictEqual` compares prototypes and own enumerable properties but treats `-0`/`0` and `NaN` via SameValue — it will NOT catch key *ordering* differences, which is a common real divergence between a cached and uncached path. For order-sensitive oracles compare `JSON.stringify` or `util.inspect(x, { sorted: false })`. Also make sure the two configs do not share module-level state; put each behind a fresh `await import()` or `t.mock.module` if they do.

## Fault injection: I/O errors, OOM, ENOSPC, timeouts, partial writes, network faults

**Reach for** — Stdlib for FS/syscall faults: `node:test` `t.mock.method` / `t.mock.module` (`--experimental-test-module-mocks`). Network: `undici` `MockAgent` (npm `undici`, v8.10.2) — it intercepts global `fetch`. `nock` v14 also now supports native fetch. Real TCP faults: Toxiproxy via `toxiproxy-node-client`. Virtual FS: `memfs`. OOM: `--max-old-space-size` in a child process.

```
t.mock.method(fs, 'writeSync', (fd, b) => Math.floor(b.length / 2)); // partial write
t.mock.method(fs, 'writeFileSync', () => { const e = new Error(); e.code='ENOSPC'; throw e; });

const agent = new MockAgent(); agent.disableNetConnect(); setGlobalDispatcher(agent);
agent.get('https://api.x').intercept({path:'/y',method:'GET'}).replyWithError(new Error('ECONNRESET'));
agent.get('https://api.x').intercept({path:'/z',method:'GET'}).reply(503,'').delay(5000);
agent.assertNoPendingInterceptors();
```

**Caveat** — There is NO maintained Node library that injects real ENOSPC/EIO at the syscall layer (verified — the closest tools are Go/FUSE: faultfs, CharybdeFS). Mocking `fs` only tests the code paths you already thought of. For genuine ENOSPC, mount a 1 MiB tmpfs and write to it; for EMFILE use `ulimit -n 16`. OOM in Node is an **uncatchable V8 abort** — `try/catch` does not fire (verified); you must `spawn` a child with `--max-old-space-size=24` and assert on exit code/stderr. `undici` is NOT importable as a built-in — you must `npm i undici`, but its `setGlobalDispatcher` does hijack Node's internal global `fetch` via a shared well-known symbol (verified on Node 25 / undici 8.10.2).

## Crash / kill / restart / recovery testing (incl. power-loss simulation of a file write)

**Reach for** — Stdlib: `node:child_process` `spawn` + `child.kill('SIGKILL')` in a loop, then reopen and assert the invariant. Container-level: `testcontainers` (v12) + `container.restart()`. Power loss: no Node tooling — Linux `dm-flakey` / `dm-log-writes`, or intercept unsynced writes yourself.

```
for (let i = 0; i < 20; i++) {
  const c = spawn(process.execPath, ['src/worker.ts', file]);
  await setTimeout(120); c.kill('SIGKILL'); await once(c, 'exit');
  const n = Number(fs.readFileSync(file, 'utf8'));
  assert.ok(n >= last, `state went backwards: ${n} < ${last}`); last = n;
}
```

**Caveat** — Verified working. SIGKILL tests the **process-crash** contract only — the kernel page cache survives, so a program that never calls `fsync` will still pass. That is the single biggest trap here. For real power-loss semantics you need `dm-flakey`/`dm-log-writes` (root, Linux-only, outside Node), or simulate in-process by mocking `fs.writeSync` to truncate at a seeded offset and `fs.fsyncSync` to be a no-op, then replay the resulting prefix through your recovery path. Node exposes `fs.fsyncSync`/`fs.fdatasyncSync` but nothing for directory fsync after `rename` — use `fs.openSync(dir)` + `fsyncSync(fd)`.

## Deterministic seeded simulation (clock, scheduler, randomness, I/O as a pure function of a seed)

**Reach for** — No Node equivalent of madsim/FoundationDB Flow/Antithesis exists. Assemble it: `node:test` `mock.timers` (or `@sinonjs/fake-timers` v15) for clock, `pure-rand` (v8, fast-check's engine) for seeded RNG, `fast-check`'s `fc.scheduler()` for async interleavings, and `--test-random-seed` (Node >= 26.1.0) for test order.

```
t.mock.timers.enable({ apis: ['setTimeout','setInterval','Date'], now: 0 });
const rng = prand.xoroshiro128plus(SEED);           // pure-rand
await fc.assert(fc.asyncProperty(fc.scheduler(), async (s) => {
  const p = s.schedule(store.write(k, v));
  await s.waitAll(); assert.deepEqual(await store.read(k), v);
}), { seed: SEED, numRuns: 500 });
```

**Caveat** — Honest answer: full DST is awkward in Node. `fc.scheduler()` only controls promises you explicitly wrap with `s.schedule(...)` — it cannot reorder the libuv threadpool (fs, dns, zlib, crypto), native async, or worker_threads, so real I/O ordering is not seedable. You get determinism only if every effect is behind an injected interface. `mock.timers` does not patch `timers/promises` `scheduler.wait` in all versions, and needs a custom `act` wrapper when combined with `fc.scheduler()`. Node 26.1.0's `--test-randomize`/`--test-random-seed` seed test *order* only, not program execution; they cannot be combined with `--watch` or `--test-rerun-failures`. V8's `--predictable` exists but breaks the threadpool and is not a supported Node configuration.

## Branch (not line) coverage measurement

**Reach for** — Stdlib: `node --experimental-test-coverage --test-coverage-branches=<pct>` (flag added v22.8.0, still Experimental). Standalone: `c8` v12. Best accuracy: `@vitest/coverage-v8` v5 (AST-remapped since Vitest 3.2) or `@vitest/coverage-istanbul`.

```
node --test --experimental-test-coverage \
  --test-coverage-include='src/**' --test-coverage-branches=90 --test-coverage-lines=90
# or, more accurate numbers:
npx vitest run --coverage.enabled --coverage.provider=v8 \
  --coverage.thresholds.branches=90 --coverage.thresholds.perFile
```

**Caveat** — MEASURED DISCREPANCY, same file + same test: istanbul **25%**, `@vitest/coverage-v8` (AST-remapped) **25%**, `c8` **66.66%**, `node --experimental-test-coverage` **66.67%**. Raw V8 block coverage counts implicit `else` as covered, so Node's built-in and c8 materially over-report branch coverage — do not set a gate on them and believe it. Also: `node --test` reports a vacuous `all files 100.00` unless you pass `--test-coverage-include`, because test files are excluded by default and nothing else is loaded. Separately, `node --test <dir>` is broken — a bare directory is resolved as a module (`MODULE_NOT_FOUND`, verified on 25.6.1); pass a glob such as `'test/**/*.test.ts'`.

## Mutation testing

**Reach for** — StrykerJS — `@stryker-mutator/core` v10.0.0 (Aug 2026, actively maintained), requires Node >= 22. Runners: `@stryker-mutator/vitest-runner`, `jest-runner`, `mocha-runner`, `tap-runner`, plus `@stryker-mutator/typescript-checker` to discard type-invalid mutants.

```
npm init stryker@latest            # writes stryker.config.mjs
npx stryker run
npx stryker run --since main --incremental   # PR-scoped, typically < 2 min
# config: { mutate: ['src/**/*.ts'], testRunner: 'vitest',
#   checkers: ['typescript'], thresholds: { high: 80, low: 60, break: 60 } }
```

**Caveat** — There is no first-class `node:test` runner — use `@stryker-mutator/tap-runner` with `--test-reporter=tap`, or switch that project to Vitest. `disableTypeChecks` defaults to `true` (Stryker strips type annotations so mutants compile), which means `checkers: ['typescript']` is what actually keeps type-invalid mutants out of your score — it roughly doubles runtime. `thresholds.break` is what fails CI; `high`/`low` only colour the report. Full runs are 5-30 min on a medium codebase, so gate PRs with `--since <base> --incremental` and run the full sweep nightly. Known issue #6004: the vitest-runner generates non-deterministic test IDs that churn the incremental baseline.

## Fuzzing with a persistent corpus + crash-to-seed regression discipline

**Reach for** — `@jazzer.js/core` v4.0.0 (Code Intelligence; libFuzzer-backed, coverage-guided, in-process; actively maintained — v4.0.0 Apr 2026, commits through Sep 2026). Jest integration via `@jazzer.js/jest-runner`. This is the only real option; `jsfuzz` is abandoned.

```
module.exports.fuzz = (data) => parse(new FuzzedDataProvider(data).consumeRemainingAsString());

npx jazzer target.js --sync ./corpus -- -max_total_time=300 -artifact_prefix=./crashes/
# crash -> ./crashes/crash-<sha1>;  commit both ./corpus and ./crashes
npx jazzer target.js --sync ./crashes/crash-<sha1> -- -runs=0   # replay one crash
npx jazzer target.js --sync ./corpus  -- -runs=0                # corpus regression in CI
```

**Caveat** — Fully verified end to end on Node 25 (found a planted bug in 7s at ~75k exec/s, wrote `crash-<sha1>`, corpus persisted, both replay modes work). Gotchas: the corpus directory must already exist or libFuzzer silently starts empty; without `-artifact_prefix=` crashes land in CWD; `--sync` is required for synchronous targets and mutually exclusive with async ones. Jazzer.js instruments only modules matched by `-i/--includes`, so by default your `node_modules` are not covered. It is a single-vendor project — if Code Intelligence stops, there is no fallback; `fast-check` with a saved `{seed, path}` is the poor-man's substitute.

## Sanitizers / undefined-and-unspecified-behaviour detection

**Reach for** — JS has no memory-unsafety class, so the analogues are: TypeScript `strict` + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` + `erasableSyntaxOnly`; `typescript-eslint` v8.70 `strictTypeChecked` config; Node runtime flags `--throw-deprecation --trace-uncaught --frozen-intrinsics --disallow-code-generation-from-strings --force-node-api-uncaught-exceptions-policy`. For native addons: real ASAN/UBSAN via `binding.gyp` cflags.

```
// eslint.config.js
extends: [tseslint.configs.strictTypeChecked],
languageOptions: { parserOptions: { projectService: true } }
// key rules: no-floating-promises, no-misused-promises, await-thenable,
//            no-unnecessary-condition, switch-exhaustiveness-check
node --throw-deprecation --trace-uncaught --frozen-intrinsics --test 'test/**/*.test.ts'
```

**Caveat** — `no-unnecessary-condition` and `no-floating-promises` are the two rules that actually catch bugs here; both need type-aware linting (`projectService: true`), which roughly 5-10x's lint time. `--frozen-intrinsics` is still Experimental (v11.12.0) and breaks many polyfills/libraries — use it only in a dedicated CI job. Unhandled rejections already throw by default since Node 15, so `--unhandled-rejections=strict` is a no-op on modern Node. For N-API addons, add `'cflags+': ['-fsanitize=address,undefined']` and `'ldflags+': [...]` to `binding.gyp` and run with `LD_PRELOAD=$(gcc -print-file-name=libasan.so)`; you will get false positives from V8 unless Node itself was built `--enable-asan`. TypeScript 7.0 (Go port, GA 2026-07-08) tightened several defaults — expect new errors on upgrade.

## Golden / snapshot testing + a corpus of malformed inputs

**Reach for** — Stdlib: `t.assert.snapshot()` and `t.assert.fileSnapshot(value, path)` (added v22.3.0, Stable since v23.4.0) with `--test-update-snapshots`; `snapshot.setDefaultSnapshotSerializers()` to control formatting. Vitest: `toMatchSnapshot` / `toMatchFileSnapshot` + `-u`.

```
for (const name of fs.readdirSync(fixturesDir).sort()) {
  test(`malformed: ${name}`, (t) => {
    let out; try { out = render(fs.readFileSync(join(fixturesDir,name))); }
    catch (e) { out = `ERR ${e.name}: ${e.message}`; }
    t.assert.fileSnapshot(out, `__snapshots__/${name}.txt`);
  });
}
// node --test --test-update-snapshots 'test/**/*.test.ts'
```

**Caveat** — Verified. Two real traps: (a) `fileSnapshot`'s path is resolved relative to **process.cwd()**, not the test file — CI running from a different directory writes goldens somewhere else entirely; build an absolute path from `import.meta.dirname`. (b) The default serializer JSON-stringifies, so a plain string golden comes out wrapped in quotes with escapes — call `snapshot.setDefaultSnapshotSerializers([(v) => String(v)])` for raw text goldens. Capture error *messages* in the golden too, so a wording change in a parser error is a visible diff. Also note error strings differ across Node majors (V8 rewords `SyntaxError`), so goldens over engine-produced messages will churn on upgrade — normalise them.

## Flake elimination / enforcing run-to-run determinism in the suite

**Reach for** — Stdlib: `--test-randomize` + `--test-random-seed=<n>` (Node >= 26.1.0), `--test-rerun-failures=<file>` (v24.7.0), `--test-isolation=none|process`, `--test-concurrency`. Vitest: `--sequence.shuffle --sequence.seed`, `--retry`. Open-handle hunting: `why-is-node-running` (v3.2.2). Environment pinning: `TZ=UTC LC_ALL=C`.

```
TZ=UTC LC_ALL=C node --test --test-randomize --test-random-seed=$SEED \
  --test-concurrency=1 'test/**/*.test.ts'
npx vitest run --sequence.shuffle --sequence.seed=$SEED --retry=0
# flake hunt: for i in $(seq 1 50); do node --test --test-random-seed=$i ... || break; done
# a pass-on-retry is the flake signal; a clean pass or hard fail is not
```

**Caveat** — `--test-randomize`/`--test-random-seed` landed only in Node 26.1.0 (confirmed absent in 25.6.1 — `node: bad option`) and cannot be combined with `--watch` or `--test-rerun-failures`. Treat `--test-force-exit` as a smell, not a fix: it papers over leaked handles that are themselves the flake; run the suite without it and use `why-is-node-running` to find the leak. Vitest 5.x engines are `^22.12 || ^24 || >=26` — it will silently resolve to 4.x on an odd non-LTS Node (verified on 25.6.1). `fast-check`'s random default seed is a top flake source in otherwise deterministic suites; pin it. `node:test` has no built-in retry; `expectFailure` (v25.5.0) marks a known-failing test rather than retrying, which is the better quarantine primitive.

---

## Sources

- https://nodejs.org/api/test.html
- https://nodejs.org/api/cli.html
- https://nodejs.org/api/cli.json
- https://nodejs.org/learn/test-runner/collecting-code-coverage
- https://github.com/nodejs/node/issues/54812
- https://fast-check.dev/
- https://fast-check.dev/docs/advanced/race-conditions/
- https://github.com/dubzzz/fast-check
- https://www.npmjs.com/package/fast-check
- https://stryker-mutator.io/docs/stryker-js/getting-started/
- https://stryker-mutator.io/docs/stryker-js/configuration/
- https://stryker-mutator.io/docs/stryker-js/incremental/
- https://github.com/stryker-mutator/stryker-js/issues/6004
- https://github.com/CodeIntelligenceTesting/jazzer.js/
- https://github.com/CodeIntelligenceTesting/jazzer.js/blob/main/docs/fuzz-targets.md
- https://www.code-intelligence.com/blog/jazzer-js
- https://github.com/evanw/esbuild/blob/main/CHANGELOG-2023.md
- https://esbuild.github.io/api/#drop-labels
- https://github.com/evanw/esbuild/issues/2398
- https://vitest.dev/guide/coverage
- https://vitest.dev/guide/cli
- https://github.com/vitest-dev/vitest/discussions/7587
- https://github.com/jestjs/jest/issues/11188
- https://undici.nodejs.org/#/docs/best-practices/mocking-request
- https://typescript-eslint.io/users/configs/
