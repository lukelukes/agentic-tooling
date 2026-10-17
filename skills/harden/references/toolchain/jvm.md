# JVM (Java / Kotlin)

Concrete tooling per layer. Read only the entries for the layer you are actually
proposing. Verified against documentation in September 2026; check versions before
quoting a flag as current.

## What is unusual here

Current baseline as of Sept 2026: JDK 27 GA (15 Sep 2026), JDK 25 is the latest LTS. JUnit 6.1.3 is current and requires Java 17+ — but this matters a lot in practice because most of the ecosystem has NOT moved: Kotest 6.2.5 still compiles against JUnit Platform 1.13.4 and jqwik 1.10.1 against Platform 1.14.4, and jqwik explicitly will not support Platform 6 in its 1.x line. If you adopt JUnit 6, verify every engine and extension first; pinning to junit-jupiter 5.13/5.14 is still the safe default.

What is unusually EASY on the JVM: bytecode instrumentation makes coverage and mutation testing first-class and trivially available (JaCoCo, Kover, PIT all just work, no source annotation required); the same mechanism gives you Byteman, which can throw an exception from literally any call site in the JDK without touching your code — few ecosystems have anything that surgical. Assertions are wired into the build tools by default (both Gradle's Test task and Maven Surefire set enableAssertions=true). Concurrency correctness is exceptionally well served: jcstress (OpenJDK itself) and Lincheck have no real equivalent in most languages. Testcontainers makes real-dependency fault injection (Toxiproxy, container kill) routine.

What is unusually HARD: (a) There is no memory-unsafety class of bug to sanitize, so ASan/UBSan/TSan have no Java-level analogue — the closest things are NonDex for *unspecified* behaviour and jcstress/Lincheck for the memory model, and ASan only ever covers JNI/FFM native code. (b) Deterministic whole-program simulation is essentially unsolved: real threads, System.nanoTime, ThreadLocalRandom, HashMap iteration order, GC and JIT deoptimisation all leak nondeterminism; kotlinx-coroutines-test gives Kotlin a genuinely good virtual-clock story for coroutines only, and OpenDST (0.1.0, Java 25+) is the first serious FoundationDB-style attempt but is far too new to depend on. (c) Power-loss / torn-write testing has no maintained library at all — SIGKILL leaves data in the page cache, so a missing-fsync bug survives the test; you need dm-flakey/CharybdeFS below the JVM or a hand-rolled FileSystemProvider wrapper. (d) Kotlin degrades several tools: JaCoCo branch counts are inflated by synthetic null-checks and default-argument masks, and free Kotlin mutation testing is effectively dead (pitest-kotlin last committed March 2023; the working option, arcmutate, is commercial).

Abandoned but still widely cited, do not use: junit-quickcheck (1.0, Nov 2020), QuickTheories (0.26, 2019), pitest-kotlin (2023). Slow-moving but still canonical and fine to use: jcstress (0.16, Feb 2023; last commit Jun 2025), junit-pioneer (2.3.0, Oct 2024).

Agent-specific flag: jqwik 1.10.1's release notes state "This project is not meant to be used by any 'AI' coding agents at all." It is a notice in the docs, not a licence restriction, but for a coding-agent skill table it is worth surfacing — prefer Kotest property testing on Kotlin projects, and expect friction if an agent drives jqwik.

Could not verify: whether Jazzer 0.30.0 works on JUnit Platform 6; whether NonDex 2.2.5 actually runs on JDK 25/27 (its README still claims Java 8–21); a canonical server-side ProGuard/R8 rule for stripping assertions from a non-Android jar.

---

## Assertions / invariant checks compiled or stripped out of production builds

**Reach for** — stdlib/toolchain: Java `assert` keyword + JVM `-ea`/`-da`; Kotlin `kotlin.assert` + compiler flag `-Xassertions=jvm`. Always-on variants: `Objects.requireNonNull`, Kotlin `require`/`check` (contract-aware, never stripped).

```
// Java – present in bytecode, gated on $assertionsDisabled, off unless -ea
assert inv(x) : "bad " + x;
// Gradle Test task and Maven Surefire BOTH default enableAssertions = true
// Kotlin: without this flag the predicate is evaluated even when -da:
kotlinc -Xassertions=jvm Foo.kt   // Gradle: freeCompilerArgs.add("-Xassertions=jvm")
java -ea:com.example... -jar app.jar   # scope by package in staging
```

**Caveat** — Nothing is actually *stripped*: javac emits a `$assertionsDisabled` static-field check, so the code ships in the jar and only execution is skipped. Kotlin's `assert()` is worse — it evaluates the condition first and only then reads `kotlin._Assertions.ENABLED`, so an expensive predicate costs you in production; `-Xassertions=jvm` (Kotlin 1.3+) restores Java-like short-circuiting. Real removal only happens on Android via R8/D8 (AGP adds `--force-enable-assertions` for debug variants); I found no canonical server-side ProGuard rule I could verify. `require`/`check` are always enabled — use them for real preconditions, `assert` only for expensive internal invariants.

## Regression test per fixed bug + AUDIT git history for fix-commits with no test

**Reach for** — No JVM-specific tool exists; this is plain git + shell. Develocity can report per-test history but does not do this audit. Convention: name the test after the issue id (`parse_emptyHeader_issue412`).

```
git log --no-merges -i --grep='^fix\|bug\|#[0-9]' --format='%H %s' --since=1.year |
while read -r sha subj; do
  git show --name-only --format= "$sha" \
    | grep -qE 'src/(test|[a-zA-Z]+Test)/|Test\.(java|kt)$|Spec\.kt$' \
    || echo "NO-TEST $sha $subj"
done
```

**Caveat** — `git show --name-only` prints nothing for merge commits, hence `--no-merges` (or add `-m --first-parent`). Multi-module repos need the path regex widened. This finds commits with no test file touched at all — it cannot tell you whether the test that *was* touched actually covers the fix; pair it with `mvn -DwithHistory ... mutationCoverage` on the changed classes (row 9) to check the new test actually kills the bug.

## Property-based testing

**Reach for** — Java: jqwik 1.10.1 (`net.jqwik:jqwik`, separate JUnit Platform engine). Kotlin: Kotest 6.2.5 `io.kotest:kotest-property` (`Arb` + `checkAll`/`forAll`). No stdlib option.

```
// jqwik – test { useJUnitPlatform { includeEngines 'jqwik','junit-jupiter' } }
@Property(tries = 1000) void roundTrip(@ForAll String s) { assertEquals(s, dec(enc(s))); }
// junit-platform.properties:  jqwik.database = .jqwik-database
//                             jqwik.failures.after.default = SAMPLE_FIRST
// Kotest: checkAll(1000, Arb.string(), Arb.int()) { s, n -> dec(enc(s)) shouldBe s }
// reproduce: forAll(PropTestConfig(seed = 127305235)) { ... }
```

**Caveat** — Big one for agents: jqwik 1.10.1's own release notes say "This project is not meant to be used by any 'AI' coding agents at all" (a notice, not a licence change). jqwik 1.10.x is also pinned to JUnit Platform 1.x (bundles 1.14.4) and will NOT run on JUnit Platform 6 / JUnit 6.x; the maintainer says 1.10 is "probably the last release" on 1.x. Kotest 6.2.5 still compiles against Platform 1.13.4, so if you are on JUnit 6.1.x you must pin back. `junit-quickcheck` (1.0, Nov 2020) and QuickTheories (0.26, 2019) are abandoned — do not reach for them. jqwik replays the last failing sample from `.jqwik-database`; Kotest caches failing seeds in `~/.kotest/seeds/` — neither file should be committed.

## Differential / oracle testing (same code, two configurations)

**Reach for** — No dedicated library. The idiomatic harness is JUnit Jupiter `@ParameterizedClass` + `@Parameter` (junit-jupiter 5.13+, current in 6.1.3) — runs an entire test class once per configuration. Combine with `@MethodSource` over a corpus, or with jqwik/Kotest for generated inputs.

```
@ParameterizedClass @EnumSource(Mode.class)   // CACHE_ON, CACHE_OFF
class ParserContract {
  @Parameter Mode mode;
  @ParameterizedTest @MethodSource("corpus")
  void matchesReference(Path f) { assertEquals(naiveParse(f), new Parser(mode).parse(f)); }
  static Stream<Path> corpus() throws IOException { return Files.list(Path.of("src/test/resources/corpus")); }
}
```

**Caveat** — `@ParameterizedClass` needs junit-jupiter 5.13+ (May 2025) — on older versions you fall back to an abstract base class with two concrete subclasses. Engines do not mix: a jqwik `@Property` cannot live inside a Jupiter `@ParameterizedClass`, so for generated differential inputs put the config loop *inside* the property instead. Nothing on the JVM diffs two implementations for you — you write the oracle, and you must make both sides produce canonically-ordered output (JVM `HashMap`/`HashSet` iteration order differs between runs and JDKs).

## Fault injection: I/O errors, OOM, ENOSPC, timeouts, partial writes, network faults

**Reach for** — Byteman 4.0.27 (`org.jboss.byteman`, JBoss/Red Hat, released Jun 2026) for arbitrary in-JVM call-site faults; Testcontainers Toxiproxy `org.testcontainers:testcontainers-toxiproxy:2.0.5` for network; WireMock 3.13.2 `Fault.*` for HTTP; Mockito 5.23.0 for local seams; Jimfs 1.3.2 (Google, Aug 2026) for a swappable in-memory `FileSystem`.

```
// Byteman: fail the write that a real ENOSPC would fail
@BMRule(name="enospc", targetClass="java.nio.channels.FileChannel", targetMethod="write",
        action="throw new java.io.IOException(\"No space left on device\")")
// Network: proxy.toxics().latency("l", ToxicDirection.DOWNSTREAM, 1100).setJitter(100);
//          proxy.toxics().timeout("t", ToxicDirection.DOWNSTREAM, 0);  // cut connection
// OOM:  java -Xmx24m -XX:+ExitOnOutOfMemoryError -jar app.jar
// Real ENOSPC: docker run --tmpfs /data:size=1m   (or a loop-mounted small ext4)
```

**Caveat** — Byteman needs `-javaagent:byteman.jar` (BMUnit can self-attach, which requires `-Djdk.attach.allowAttachSelf=true` and emits the JDK 21+ dynamic-agent-loading warning; use `-XX:+EnableDynamicAgentLoading` to silence). You cannot fake a real ENOSPC or a real OOM-killer from inside the JVM — mock `IOException`s test your catch blocks but not the kernel's behaviour; for the real thing use a tiny tmpfs/loop device and a small `-Xmx`. Partial/short writes on `FileChannel.write` are legal and rarely tested: Byteman can make `write` return fewer bytes than requested, which is usually where the bug is. Jimfs gives you a clean FS to swap in but has no fault-injection API of its own — you wrap its `FileSystemProvider`.

## Crash / kill / restart / recovery testing (power-loss of a file write)

**Reach for** — No framework. `Runtime.getRuntime().halt(n)` in a forked child JVM is the only true JVM-level kill (skips shutdown hooks and `finally`); `ProcessBuilder` + `Process.destroyForcibly()` (SIGKILL on Linux) from the parent test. Testcontainers 2.0.5 for killing a containerized dependency mid-transaction.

```
Process p = new ProcessBuilder(javaBin, "-cp", cp, "app.Writer", dir.toString())
                .inheritIO().start();
awaitFileExists(dir.resolve("wal.0"));
p.destroyForcibly().waitFor();          // SIGKILL: no shutdown hooks, no flush
assertTrue(new Recovery(dir).recover().isConsistent());
// in-child variant, at an injected fault point:  Runtime.getRuntime().halt(137);
```

**Caveat** — `System.exit()` does NOT simulate a crash — it runs shutdown hooks and `File.deleteOnExit`; use `halt()` or SIGKILL. Even SIGKILL does not simulate power loss: the OS page cache still holds the un-`fsync`'d bytes, so a missing-`force()` bug survives the test. Genuine power-loss semantics need block-layer help outside the JVM (`dm-flakey`, CharybdeFS) or a hand-written `FileSystemProvider`/`FileChannel` wrapper that discards writes not yet `force()`d and replays a torn prefix. There is no maintained JVM library for this — you build it. This is the weakest spot in the JVM testing story.

## Deterministic seeded simulation (clock, scheduler, randomness, I/O from one seed)

**Reach for** — Kotlin has the best story: `kotlinx-coroutines-test` 1.11.0 `runTest` (virtual time, `TestCoroutineScheduler`) + `kotlin.time.TestTimeSource` (stdlib, stable since 1.9) + `kotlin.random.Random(seed)`. Java: inject `java.time.Clock` and `java.util.random.RandomGenerator` (JDK 17+, JEP 356). Whole-program: OpenDST 0.1.0 (Ping Identity) and Fray 0.9.0 (CMU, `org.pastalab.fray`) for deterministic thread-interleaving replay.

```
@Test fun sim() = runTest(timeout = 5.minutes) {   // delays skipped, clock virtual
  val rnd = Random(seed); val ts = TestTimeSource()
  launch { delay(1.hours); ts += 1.hours }
  testScheduler.advanceUntilIdle()
  assertEquals(expectedFor(seed), state())
}
// Fray: @ExtendWith(FrayTestExtension.class) @FrayTest void racy() { ... }
```

**Caveat** — There is no stdlib or mainstream way to make a whole JVM run a pure function of a seed. Real `Thread`s, `System.nanoTime`, `ThreadLocalRandom`, `HashMap`/`HashSet` iteration order, GC timing and JIT deoptimisation all leak nondeterminism, and `runTest` only controls coroutines — work dispatched to `Dispatchers.IO` or blocking threads escapes it (default 60 s wall-clock timeout). OpenDST is genuinely new and 0.1.0-experimental, requires Java 25+, and rewrites `Thread` subclasses via a ClassFile-API (JEP 484) agent with documented KNOWN_GAPS. Fray 0.9.0 is research-grade but real and gives reproducible traces. Treat FoundationDB/TigerBeetle-style DST as not-yet-solved on the JVM.

## Branch (not line) coverage measurement

**Reach for** — JaCoCo 0.8.15 (Jun 2026; Java 26 official, Java 27 experimental — 0.8.16 snapshot adds Java 27 official). Kotlin: Kover 0.9.9 (`org.jetbrains.kotlinx.kover`) with `CoverageUnit.BRANCH`; its IntelliJ engine handles Kotlin bytecode better than JaCoCo, and `kover { useJacoco() }` switches back.

```
mvn verify   # jacoco:prepare-agent + jacoco:check bound to the build
<rule><element>BUNDLE</element><limits><limit>
  <counter>BRANCH</counter><value>COVEREDRATIO</value><minimum>0.75</minimum>
</limit></limits></rule>
// Gradle: jacocoTestCoverageVerification { violationRules { rule { limit {
//   counter = "BRANCH"; value = "COVEREDRATIO"; minimum = 0.75.toBigDecimal() } } } }
```

**Caveat** — JaCoCo counts *bytecode* branches, so Kotlin inflates the denominator badly: null-check intrinsics, `when` over sealed types, default-argument masks, `data class` equals/hashCode and inline functions all add branches you cannot write a test for. 0.8.13–0.8.15 added Kotlin filters but Kotlin branch coverage still reads artificially low — prefer Kover for Kotlin. JaCoCo hard-fails with "Unsupported class file major version" on a JDK newer than it knows, so pin your JDK to the JaCoCo release. Neither tool does MC/DC; there is no MC/DC tool on the JVM outside of avionics-certified commercial products.

## Mutation testing

**Reach for** — PIT / pitest 1.30.0 (`org.pitest:pitest-maven`, Aug 2026) + `org.pitest:pitest-junit5-plugin:1.2.3`. Gradle: `info.solidsoft.pitest`. Kotlin: commercial arcmutate `com.arcmutate:pitest-kotlin-plugin:1.5.1`.

```
mvn -DwithHistory test-compile org.pitest:pitest-maven:mutationCoverage \
  -DtargetClasses='com.example.*' -DtargetTests='com.example.*' \
  -DmutationThreshold=70 -Dmutators=STRONGER -Dfeatures='+auto_threads'
# Gradle: ./gradlew pitest
# pom: add pitest-junit5-plugin to the <dependencies> of the pitest-maven <plugin>
```

**Caveat** — JUnit 5 requires `pitest-junit5-plugin` on the *plugin's* dependency list, not the project's — omitting it silently reports zero tests. The default mutator set is deliberately conservative; `-Dmutators=STRONGER` (or `ALL`) is where the value is. Kotlin: the free `pitest/pitest-kotlin` plugin is dead (last commit March 2023) — real Kotlin mutation needs arcmutate's commercial plugin (licence file `arcmutate-licence.txt` at project root, requires pitest 1.22.0+); without it PIT generates a flood of equivalent/unkillable mutants from Kotlin null-check and inline bytecode. Runtime is the real constraint: use `-DwithHistory` for incremental runs and scope `targetClasses` to the diff.

## Fuzzing with a persistent corpus + crash-to-seed regression discipline

**Reach for** — Jazzer 0.30.0 (`com.code-intelligence:jazzer-junit`, Feb 2026, libFuzzer-based, by Code Intelligence; powers JVM support in Google OSS-Fuzz). Alternative: JQF 3.0 (`edu.berkeley.cs.jqf`, Jul 2026) for generator-based/Zest fuzzing.

```
// testImplementation "com.code-intelligence:jazzer-junit:0.30.0"
@FuzzTest(maxExecutions = 100_000)          // or maxDuration = "5m" (default)
void parse(@NotNull byte[] data) { Parser.parse(data); }

JAZZER_FUZZ=1 mvn test -Dtest=ParserFuzzTest   # fuzzing mode
mvn test                                        # regression mode: replays saved crashes
```

**Caveat** — The corpus discipline is built in and is the main reason to pick Jazzer: new-coverage inputs land in `.cifuzz-corpus/<pkg>.<Class>/<method>`, crashing inputs are written to `src/test/resources/<pkg>/<Class>Inputs/<method>` and are automatically replayed as ordinary unit tests on every plain `mvn test`. Commit that resources directory and add `src/test/resources/** binary` + `.cifuzz-corpus/** binary` to `.gitattributes` or git will corrupt fixtures via line-ending normalisation. Set `JAZZER_COVERAGE=1` to also replay the generated corpus. Requires JUnit 5.9+ and native bits for Linux/macOS 12+/Windows on x86_64 or arm64 — I could not verify JUnit Platform 6 compatibility. Jazzer's "sanitizers" are security bug detectors (SSRF, path traversal, deserialization, command injection), not memory sanitizers. Autofuzz is deprecated.

## Sanitizers and undefined/unspecified behaviour detection

**Reach for** — The JVM has no undefined behaviour, so the analogues are: NonDex 2.2.5 (`edu.illinois:nondex-maven-plugin`, Mar 2026) for *unspecified* API behaviour (HashMap/HashSet order, `Class.getDeclaredMethods` order, Locale defaults); jcstress 0.16 (OpenJDK) for Java Memory Model / racy publication; Lincheck 3.7 (JetBrains, `org.jetbrains.lincheck`) for linearizability + bounded model checking; Error Prone 2.50.0 + NullAway 0.14.1 + `javac -Xlint:all -Werror` at compile time. For JNI/FFM native code: `-Xcheck:jni`, NMT, and ASan via LD_PRELOAD.

```
mvn edu.illinois:nondex-maven-plugin:2.2.5:nondex     # ./gradlew nondexTest
java -jar jcstress.jar -m quick -t MyRaceTest         # -m {sanity,quick,default,stress}
java -Xcheck:jni -XX:NativeMemoryTracking=summary -jar app.jar
LD_PRELOAD=$(gcc -print-file-name=libasan.so) \
  ASAN_OPTIONS=handle_segv=0:detect_leaks=0 java -jar app.jar
// Lincheck: @Test fun t() = ModelCheckingOptions().check(this::class)
```

**Caveat** — NonDex's README states Java 8–21 support (version 2.2.5 is recent, Mar 2026, but I could not verify it runs on JDK 25/27 — test it before relying on it). jcstress's last tagged release is 0.16 (Feb 2023) and its last commit is Jun 2025; Maven Central is stale, prebuilt jars live at builds.shipilev.net — it is still the canonical JMM tool and part of OpenJDK, just slow-moving. ASan under HotSpot needs `LD_PRELOAD` (the JVM binary isn't ASan-linked), produces false interception warnings, and LeakSanitizer is unreliable — it only covers your JNI/FFM native code, never Java. Note that Java 22+ FFM `Arena` already gives deterministic use-after-free (`IllegalStateException`) without any sanitizer, which is the main reason ASan matters less than it used to.

## Golden/snapshot testing + corpus of malformed inputs

**Reach for** — Selfie 3.1.1 (`com.diffplug.selfie:selfie-runner-junit5`, May 2026) for inline *and* disk snapshots; ApprovalTests 31.0.0 (`com.approvaltests:approvaltests`, Jun 2026) for classic file-based golden files with diff-tool review. Malformed-input corpus: plain JUnit `@ParameterizedTest` + `@MethodSource` over a resources directory.

```
expectSelfie(render(input)).toMatchDisk();      // ./gradlew test -Pselfie=overwrite
Approvals.verify(render(input));                // writes X.received.txt vs X.approved.txt

@ParameterizedTest @MethodSource("malformed")
void neverThrowsRaw(Path p) { assertThrows(ParseException.class, () -> parse(p)); }
static Stream<Path> malformed() throws IOException {
  return Files.list(Path.of("src/test/resources/malformed")); }
```

**Caveat** — Add `*.approved.* binary` (ApprovalTests' own recommendation) and `src/test/resources/malformed/** binary` to `.gitattributes`, or git line-ending normalisation silently mutates your fixtures. Selfie's inline snapshots only work when the test source is Java (8+, 15+ for text blocks), Kotlin, Groovy or Scala; disk snapshots work for any JVM language. Update flags differ: `mvn test -Dselfie=overwrite` vs `./gradlew test -Pselfie=overwrite`, or a `//selfieonce` comment. Make output canonical (sorted maps, fixed clock, stable ids) *before* snapshotting or you get permanent diff churn — `Files.list` order is filesystem-dependent, so sort it if the display name matters.

## Flake elimination / enforcing run-to-run determinism in the test suite

**Reach for** — JUnit Jupiter config parameters (`MethodOrderer$Random` + pinned seed, `junit.jupiter.testclass.order.default`), NonDex 2.2.5, `@RepeatedTest`, Gradle `forkEvery`, and for *detection* (not hiding) Gradle `org.gradle.test-retry` 1.6.6 or Maven Surefire `rerunFailingTestsCount` feeding Develocity's FLAKY classification. Awaitility 4.3.0 instead of `Thread.sleep`.

```
# src/test/resources/junit-platform.properties
junit.jupiter.testmethod.order.default = org.junit.jupiter.api.MethodOrderer$Random
junit.jupiter.testclass.order.default  = org.junit.jupiter.api.ClassOrderer$Random
junit.jupiter.execution.order.random.seed = 42
# build.gradle: test { forkEvery = 1
#   jvmArgs '-Duser.timezone=UTC','-Dfile.encoding=UTF-8','-Duser.language=en','-Duser.country=US' }
```

**Caveat** — `junit.jupiter.execution.order.random.seed` defaults to `System.nanoTime()` — you MUST pin it or your "random order" runs are not reproducible. JUnit has no built-in retry at any version including 6.1.3; `@RepeatedTest` is not retry, and junit-pioneer's `@RetryingTest` is the usual answer but its last release is 2.3.0 (Oct 2024). Retry only helps if CI actually fails or quarantines on FLAKY, otherwise it launders bugs. `junit.jupiter.execution.parallel.enabled` is `false` by default — turning it on is the single largest new source of flakes. `forkEvery = 1` is slow but is the only reliable way to catch static-state leakage between test classes. Gradle and Surefire both enable `-ea` in tests by default, which is usually what you want (see row 1).

---

## Sources

- https://kotlinlang.org/api/core/kotlin-stdlib/kotlin/assert.html
- https://publicobject.com/2019/11/18/kotlins-assert-is-not-like-javas-assert/
- https://jakewharton.com/d8-optimization-assertions/
- https://docs.gradle.org/current/dsl/org.gradle.api.tasks.testing.Test.html
- https://maven.apache.org/surefire/maven-surefire-plugin/test-mojo.html
- https://jqwik.net/docs/current/user-guide.html
- https://jqwik.net/release-notes.html
- https://github.com/jqwik-team/jqwik/releases/tag/1.10.1
- https://kotest.io/docs/proptest/property-test-seeds.html
- https://docs.junit.org/current/user-guide/
- https://docs.junit.org/current/api/org.junit.jupiter.api/org/junit/jupiter/api/MethodOrderer.Random.html
- https://docs.junit.org/6.1.0/api/org.junit.jupiter.params/org/junit/jupiter/params/ParameterizedClass.html
- https://docs.junit.org/6.1.0/writing-tests/parameterized-classes-and-tests.html
- https://byteman.jboss.org/downloads.html
- https://github.com/bytemanproject/byteman/blob/main/docs/asciidoc/src/main/asciidoc/chapters/Using-Byteman.adoc
- https://java.testcontainers.org/modules/toxiproxy/
- https://github.com/testcontainers/testcontainers-java/releases
- https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-test/
- https://kotlinlang.org/api/core/kotlin-stdlib/kotlin.time/-test-time-source/
- https://github.com/pingidentity/opendst
- https://github.com/cmu-pasta/fray
- https://github.com/JetBrains/lincheck
- https://www.jacoco.org/jacoco/trunk/doc/changes.html
- https://www.jacoco.org/jacoco/trunk/doc/check-mojo.html
- https://kotlin.github.io/kotlinx-kover/gradle-plugin/
