# Python (CPython 3.10–3.14, as of September 2026)

Concrete tooling per layer. Read only the entries for the layer you are actually
proposing. Verified against documentation in September 2026; check versions before
quoting a flag as current.

## What is unusual here

Unusually easy in Python: (a) Property-based testing — Hypothesis is arguably the strongest PBT library in any language, and you get shrinking, a failure database, stateful/model-based testing, and a pytest integration for free; (b) fault injection at the library boundary — no compile step and `unittest.mock.patch` can reach into any module, so simulating `OSError(ENOSPC)`, timeouts, or a bad HTTP response is three lines; (c) branch coverage — one flag, and now genuinely fast on 3.14 via `sys.monitoring`; (d) snapshot testing — mature, two good choices.

Unusually hard in Python: anything that needs control of the runtime. There is NO stdlib virtual clock, NO deterministic scheduler (asyncio is explicitly nondeterministic; trio's MockClock is the lone exception and only helps if you're on trio), NO crash-consistency or power-loss harness, NO maintained binding for syscall-level fault injection, and NO way to strip assertions per-module — `python -O` is a global on/off switch, which is why most production Python just ships with asserts enabled. Sanitizers only apply to the C layer and require rebuilding the interpreter (`./configure --with-address-sanitizer`), so they are irrelevant to pure-Python code and expensive to set up for extension authors. Mutation testing works but is slow enough to be a nightly job, never a PR gate. And two techniques that are single tools elsewhere — differential/oracle testing and bug-to-regression-test auditing — have no Python tooling at all; you assemble them from `parametrize` + `hypothesis` and from `git log` + grep respectively, which is fine but means nobody does it by default.

2026 version pivots worth knowing: Python 3.14 made free-threading officially supported (not default), creating a new class of nondeterminism that `pytest-run-parallel` and TSan now address. coverage.py's `sysmon` core became the default on 3.14 and finally supports branch coverage there (7.7.0+), but still does not on 3.12/3.13. pytest 9 (Nov 2025) added native `subtests`, native TOML config (`pytest.toml` / `[tool.pytest]`), and a `strict` mode, and dropped Python 3.9. Hypothesis began migrating internals to Rust in 6.156.0 (2026-07) and now ships native wheels.

Flagged as unverified: one search result claimed Hypothesis 6.168 changed the example-database internal format incompatibly; I could not confirm this in the changelog and have not relied on it. Also unverified: mutmut's exact exit code on surviving mutants — I read the source and found no threshold gate on `mutmut run`, which is why the row recommends gating on `export-cicd-stats` JSON instead.

---

## Assertions / invariant checks compiled or stripped out of production builds

**Reach for** — stdlib: `assert` + `__debug__`, erased by `python -O` / `PYTHONOPTIMIZE=1`. Richer contracts: `icontract` 2.7.3 or `deal` 4.24.6 (both gate on `__debug__`, so the same switch disables them).

```
# dev/CI: checks live
pytest
# production: `assert` AND the body of `if __debug__:` are compiled away
PYTHONOPTIMIZE=1 python -m myapp      # equivalently: python -O -m myapp
python -m compileall -o 1 -o 2 src/   # emits .opt-1/.opt-2 .pyc
```

**Caveat** — Verified on 3.14: `-O` removes both the assert and the whole `if __debug__:` block. It is process-global and all-or-nothing — there is no per-module or per-severity gating, and no equivalent of Rust's `debug_assert!` vs `assert!`. NEVER run pytest under `-O`/`PYTHONOPTIMIZE`: your test asserts are erased too and the suite goes silently green (pytest warns, but still runs). Because `-O` is so coarse, most production Python ships WITH asserts enabled; if an assert must never fire in prod, raise an exception instead.

## Regression test per fixed bug + auditing git history for fix-commits that added no test

**Reach for** — No Python-specific tool exists. Plain `git log --grep` + a path filter. Forward enforcement: a marker convention (`@pytest.mark.regression("#1234")`) plus pytest 9's `strict` config option, which turns on `strict_markers`.

```
git log --since='12 months ago' --format='%H %s' -i --perl-regexp \
  --grep='^(fix|bugfix)(\(|:)|\bfixes #|\bcloses #' |
while read -r sha subj; do
  git show --name-only --format= "$sha" |
    grep -qE '(^|/)tests?/|(^|/)test_.*\.py$|_test\.py$' || echo "NO TEST $sha $subj"
done
```

**Caveat** — Script tested and working (run against this repo, found 4 untested fix-commits). Purely heuristic: depends on commit-message convention and on tests living under `tests/` or matching `test_*.py`. Squash-merge repos hide per-fix commits — also run it with `--first-parent` over merge commits. Nothing in the Python ecosystem automates this; the closest managed option is a CI job running the above as a soft gate.

## Property-based testing

**Reach for** — `hypothesis` 6.168.0 (2026-09-08). Unambiguous de-facto standard; nothing else is a serious contender. `hypothesis.stateful.RuleBasedStateMachine` + `@rule`/`@invariant`/`@precondition`/`Bundle` for model-based/stateful testing.

```
from hypothesis import given, settings, strategies as st

@given(st.lists(st.integers()))
@settings(max_examples=500)
def test_sort_is_idempotent(xs):
    assert sorted(sorted(xs)) == sorted(xs)
# pytest --hypothesis-show-statistics --hypothesis-seed=0 --hypothesis-explain
```

**Caveat** — Requires Python >= 3.10. Failures persist to `.hypothesis/examples` and auto-replay; that DB is a cache, not a durable regression record — paste the printed `@example(...)` into the test. `derandomize` defaults to True under CI detection and `deadline` (200ms) is disabled in CI, so local and CI behaviour differ. 6.156.0+ ships Rust-backed native wheels. `pip install hypothesis[crosshair]` enables `settings(backend="crosshair")` symbolic execution, but the docs mark backends "EXPERIMENTAL AND UNSTABLE".

## Differential / oracle testing (same code, two configurations)

**Reach for** — No dedicated library, and none is needed. `pytest.mark.parametrize` or a parametrized fixture over the two configurations, with `hypothesis.given` supplying inputs. pytest 9's native `subtests` fixture reports each config's failure separately. For model-vs-real, `hypothesis.stateful.RuleBasedStateMachine` with `@invariant`.

```
@given(st.text())
def test_cache_on_equals_cache_off(s):
    parse.cache_clear()
    fast, slow = parse(s, cache=True), parse(s, cache=False)
    assert canon(fast) == canon(slow)   # canon = json.dumps(..., sort_keys=True)
# pytest -p no:randomly tests/test_differential.py
```

**Caveat** — The real trap is the comparison, not the harness: `__eq__` on your objects is often shallow, and dict/set iteration order leaks into `repr()`. Normalise to a canonical form (`json.dumps(..., sort_keys=True)`) or pin `PYTHONHASHSEED=0`. If the fast path is memoised with `functools.lru_cache`, the two "configurations" are not independent unless you call `fn.cache_clear()` between them (`pytest-antilru` 2.0.1 automates disabling lru_cache in tests). Floating-point fast/slow paths need `pytest.approx`, not `==`.

## Fault injection: I/O errors, OOM, ENOSPC, timeouts, partial writes, network faults

**Reach for** — stdlib `unittest.mock.patch(..., side_effect=OSError(errno.ENOSPC, ...))`; stdlib `resource.setrlimit(RLIMIT_AS, ...)` for OOM; `pyfakefs` 6.2.0 `fs.set_disk_usage()` for genuine ENOSPC-on-write; `pytest-socket` 0.8.1 `--disable-socket` to prove no network; `pytest-httpserver`/`vcrpy` for HTTP faults; `pytest-timeout` for hangs.

```
def test_enospc(fs):                       # pyfakefs `fs` fixture
    fs.set_disk_usage(100)
    with pytest.raises(OSError) as e:
        pathlib.Path("/f").write_text("a" * 200)
    assert e.value.errno == errno.ENOSPC
# OOM (in a CHILD proc): resource.setrlimit(resource.RLIMIT_AS, (64<<20,)*2)
```

**Caveat** — Both verified locally (ENOSPC via pyfakefs docs example; RLIMIT_AS → MemoryError in a subprocess). `RLIMIT_AS` is POSIX-only and MUST be set in a `subprocess`/`multiprocessing` child or you kill the test runner. Partial writes have no library — patch `os.write` to return a truncated count (verified: `lambda fd, d: orig(fd, d[:1])`). There is NO maintained Python binding for syscall-level fault injection (`libfiu` bindings are dead); for that you drop to `LD_PRELOAD` or a fault-injecting FUSE mount. `toxiproxy-python` is abandoned (2019) — shell out to the toxiproxy CLI instead.

## Crash / kill / restart / recovery testing (incl. power-loss simulation)

**Reach for** — No library exists. stdlib `subprocess.Popen` + `p.kill()` (SIGKILL) with a control pipe so the parent knows which writes were acked. `pytest-forked` 1.7.5 (maintained, 2026-08) to isolate tests that segfault. Power loss proper: block-layer tools outside Python.

```
p = subprocess.Popen([sys.executable, "writer.py", db], stdout=subprocess.PIPE)
time.sleep(random.Random(seed).uniform(0, 0.5))
p.kill(); p.wait()          # SIGKILL: no atexit, no buffer flush, no __del__
acked = read_acked(p.stdout)
assert recover(db).prefix == acked   # durable prefix, never garbage
```

**Caveat** — Say this plainly: Python has no crash-consistency framework; every project hand-rolls the above. SIGKILL only simulates PROCESS death — the OS page cache is still flushed, so it does not catch a missing `fsync()`. Real power-loss simulation requires `dm-flakey`/`dm-log-writes`, CrashMonkey, or a FUSE layer that drops un-fsynced data — all outside Python. Use `p.kill()` not `p.terminate()`: SIGTERM runs `atexit` handlers and defeats the test.

## Deterministic seeded simulation (clock, scheduler, randomness, I/O as a pure function of a seed)

**Reach for** — Partial coverage only. Clock: `time-machine` 3.5.1 (C-level, fast) or `freezegun` 1.5.5. Randomness: explicit `random.Random(seed)`, plus `pytest-randomly` 5.0.0 which reseeds `random`/`numpy`/`faker`/`factory_boy` before every test. Hash order: `PYTHONHASHSEED`. Async scheduler: `trio.testing.MockClock(autojump_threshold=0)` + `trio.testing.wait_all_tasks_blocked`. Threads: `blanket` 1.0.

```
@pytest.fixture
def autojump_clock(): return trio.testing.MockClock(autojump_threshold=0)

def test_timeouts(autojump_clock):        # virtual time; jumps to next deadline
    trio.run(main, clock=autojump_clock)
# env: PYTHONHASHSEED=0 pytest -p randomly --randomly-seed=1234
```

**Caveat** — Trio's MockClock is the ONLY first-class virtual-time scheduler in Python and it is genuinely excellent. asyncio has no supported equivalent — you must subclass the event loop and override `loop.time()`, and the selector still blocks on real time. There is no Python analogue of FoundationDB/TigerBeetle whole-program deterministic simulation: you cannot make I/O a pure function of a seed without writing your own simulated transport. `blanket` 1.0 (2026-05-16, MIT, py>=3.11) makes your test the thread scheduler (`scenario.Lock()`, `api.relay(t2, t1)`), but it is brand new, `threading`-only (no asyncio/multiprocessing), and cannot interleave inside lockless ops like `x += 1` without its bytecode injector.

## Branch (not line) coverage measurement

**Reach for** — `coverage.py` 7.16.1, driven through `pytest-cov` 7.1.0 with `--cov-branch`.

```
pytest --cov=mypkg --cov-branch --cov-report=term-missing --cov-fail-under=90
# or, without the plugin:
coverage run --branch -m pytest
coverage report --show-missing --skip-covered --fail-under=90
```

**Caveat** — On Python 3.14+ coverage defaults to the `sys.monitoring` core (`COVERAGE_CORE=sysmon`, default since coverage 7.9.1) and it supports BRANCH coverage there (since coverage 7.7.0 + CPython 3.14.0a6). On 3.12/3.13 sysmon does NOT support branch measurement — coverage silently falls back to the much slower trace core, so branch coverage is a real CI cost below 3.14. sysmon is also incompatible with dynamic contexts and some concurrency settings. Mark intentionally-partial branches with `# pragma: no branch`; note a conditional is not counted as a branch at all if one of its arms is excluded.

## Mutation testing

**Reach for** — `mutmut` 3.8.0 (2026-09-12, BSD-3) is the active default. `cosmic-ray` 8.7.0 (2026-08-09, MIT) is also maintained and is the only one with a built-in score gate (`cr-rate --fail-over`).

```
# pyproject.toml: [tool.mutmut] source_paths = ["src/"]
mutmut run --max-children 8 && mutmut browse
mutmut export-cicd-stats   # -> mutants/mutmut-cicd-stats.json {killed,survived,total}
# cosmic-ray, with a real CI gate:
cosmic-ray init cr.toml cr.sqlite && cosmic-ray exec cr.toml cr.sqlite
cr-rate --fail-over 20 cr.sqlite   # exit 1 if >20% mutants survive
```

**Caveat** — mutmut 3.x requires POSIX `fork` (Windows needs WSL) and Python >= 3.10, and has NO built-in threshold flag — confirmed by reading `src/mutmut/__main__.py`; you must gate CI on the exported JSON yourself. Use `mutate_only_covered_lines` and `type_check_command` (mypy/pyrefly pre-filter) to cut runtime; scope with `mutmut run "mypkg.mymodule*"` or `cr-filter-git`. Both are far too slow for a PR gate on a real codebase — run nightly on changed files. MutPy and mutatest are effectively dead.

## Fuzzing with a persistent corpus + crash-to-seed regression discipline

**Reach for** — `atheris` 3.1.0 (Google, libFuzzer-backed, Python 3.11–3.14, 2026-06) for byte-oriented fuzzing with an on-disk corpus. In the property-test world the equivalent is Hypothesis's `.hypothesis/examples` DB plus `@example(...)`. `hypofuzz` for coverage-guided Hypothesis.

```
import atheris, sys
with atheris.instrument_imports():
    import mylib
def TestOneInput(data): mylib.parse(data)
atheris.Setup(sys.argv, TestOneInput); atheris.Fuzz()
# python fuzz_parse.py corpus/ -max_total_time=300 -artifact_prefix=crashes/
```

**Caveat** — Atheris wheels bundle libFuzzer and work out of the box for pure Python; fuzzing C extensions under ASan requires building from source with clang. Discipline: commit `corpus/` and `crashes/`, then parametrize a normal pytest over `Path("crashes").glob("*")` so each crash becomes a permanent regression test. `-atheris_runs=N` is needed for coverage reports (they only emit on graceful exit). HypoFuzz (`hypothesis fuzz -n 4 -- -k parse`) is by the Hypothesis maintainers but is under a NON-COMMERCIAL licence — verified from its LICENSE file: any use in a commercial org, including internal CI, needs a paid agreement; last release 2025-11. `python-afl` (PyPI 2020) and `pythonfuzz` (2019) are abandoned.

## Sanitizers and undefined/unspecified behaviour detection

**Reach for** — Pure Python has no UB, so the analogue is stdlib `python -X dev` (`PYTHONDEVMODE=1`) + `-W error`. For C extensions and CPython itself: clang sanitizers via CPython's own configure flags. Optional runtime type contracts: `beartype` 0.22.9 / `typeguard` 4.6.0.

```
python -X dev -W error -m pytest   # alloc debug hooks, faulthandler, ResourceWarning, asyncio debug
# C extension / interpreter:
CC="clang -fsanitize=address,undefined" ./configure --with-address-sanitizer \
  --with-undefined-behavior-sanitizer --without-pymalloc && make && make test
PYTHONMALLOC=malloc ASAN_OPTIONS=detect_leaks=1 python -m pytest
```

**Caveat** — ASan/Valgrind need `PYTHONMALLOC=malloc` or `--without-pymalloc`, otherwise pymalloc's arena reuse hides the bugs. UBSan on CPython's C++ needs `-fno-sanitize=vptr`. Put `llvm-symbolizer` on PATH or set `ASAN_SYMBOLIZER_PATH` or traces are useless. TSan requires a separately built free-threaded interpreter: `./configure --disable-gil --with-thread-sanitizer`, then `TSAN_OPTIONS='allocator_may_return_null=1 halt_on_error=1' pytest -s`; prebuilt images exist in the `cpython_sanity` Docker repo. `-X dev` gives you buffer under/overflow and GIL-misuse detection in extension modules for free and costs nothing to enable — it is the single highest-value flag in this row.

## Golden/snapshot testing and a corpus of malformed inputs

**Reach for** — `syrupy` 6.1.1 (separate `__snapshots__/` files) or `inline-snapshot` 0.35.4 (snapshot values written back into the test source). `pytest-regressions` 2.11.0 for numeric/dataframe goldens. Malformed-input corpus: plain `pytest.mark.parametrize` over a globbed directory — stdlib + pytest, no library needed.

```
def test_render(snapshot): assert render(doc) == snapshot   # syrupy; update: pytest --snapshot-update

from inline_snapshot import snapshot
def test_render2(): assert render(doc) == snapshot()         # pytest --inline-snapshot=create

@pytest.mark.parametrize("p", sorted(Path("tests/corpus/bad").glob("*")), ids=str)
def test_malformed_never_crashes(p): pytest.raises(ParseError, parse, p.read_bytes())
```

**Caveat** — `pytest-snapshot` is abandoned (last release 2022-04) — do not reach for it despite the obvious name. Guard `--snapshot-update` / `--inline-snapshot=fix` so they can never run in CI; syrupy fails on unused AND missing snapshots by default, which is the property you want. Snapshots containing dicts/sets need `sort_keys=True` or a fixed `PYTHONHASHSEED` to be stable across runs. syrupy and inline-snapshot are complements, not rivals: syrupy explicitly points at inline-snapshot for the inline case.

## Flake elimination / enforcing run-to-run determinism in the suite itself

**Reach for** — `pytest-randomly` 5.0.0 (shuffles module/class/function order, reseeds `random`/`numpy`/`faker`/`factory_boy`/`polyfactory` before each test, prints the seed). `pytest-repeat` 0.9.4. `pytest-xdist` 3.8.0 for parallel/order stress. `pytest-replay` 1.7.1 (pytest's own recommendation for reproducing a CI/xdist run). `PYTHONHASHSEED`. pytest 9 `strict` mode.

```
PYTHONHASHSEED=random pytest -p randomly        # new order + seed every run
pytest --randomly-seed=last                      # replay the previous run exactly
pytest --count=50 -x tests/test_suspect.py       # pytest-repeat: hunt the flake
pytest -p no:randomly                            # bisect: is it order-dependence?
pytest -n auto --dist loadgroup                  # xdist parallel stress
```

**Caveat** — `pytest-rerunfailures` 16.7 (`--reruns 3`) HIDES flakes rather than eliminating them; pytest's docs list it as mitigation, not a fix — if you use it, surface reruns as a CI signal. Several widely-cited tools here are dead or stale: `flaky` (last release 2024-03), `pytest-flakefinder` (2022-10), `pytest-quarantine` (2019), `pytest-xflaky` (2024-10). Best practice: pin `PYTHONHASHSEED` in CI for reproducibility AND run a nightly job with `PYTHONHASHSEED=random` + shuffled order to catch what the pin is hiding. Python 3.14's officially-supported free-threaded build introduces a new flake class — `pytest-run-parallel` 0.10.0 and TSan are the tools for it.

---

## Sources

- https://docs.python.org/3/library/devmode.html
- https://docs.pytest.org/en/stable/changelog.html
- https://docs.pytest.org/en/stable/explanation/flaky.html
- https://hypothesis.readthedocs.io/en/latest/reference/api.html
- https://hypothesis.readthedocs.io/en/latest/reference/integrations.html
- https://hypothesis.readthedocs.io/en/latest/stateful.html
- https://hypothesis.readthedocs.io/en/latest/changelog.html
- https://coverage.readthedocs.io/en/latest/branch.html
- https://raw.githubusercontent.com/coveragepy/coveragepy/master/CHANGES.rst
- https://devguide.python.org/development-tools/clang/
- https://py-free-threading.github.io/thread_sanitizer/
- https://docs.python.org/3/howto/free-threading-python.html
- https://raw.githubusercontent.com/google/atheris/master/README.md
- https://raw.githubusercontent.com/boxed/mutmut/master/README.rst
- https://raw.githubusercontent.com/boxed/mutmut/master/src/mutmut/__main__.py
- https://mutmut.readthedocs.io/en/latest/
- https://cosmic-ray.readthedocs.io/en/latest/tutorials/intro/index.html
- https://github.com/sixty-north/cosmic-ray/blob/master/src/cosmic_ray/tools/survival_rate.py
- https://hypofuzz.com/docs/manual/cli.html
- https://github.com/Zac-HD/hypofuzz/blob/master/LICENSE
- https://pytest-pyfakefs.readthedocs.io/en/stable/convenience.html
- https://trio.readthedocs.io/en/stable/reference-testing.html
- https://bernat.tech/posts/blanket-deterministic-threading/
- https://lwn.net/Articles/1090579/
- https://github.com/pytest-dev/pytest-randomly
