# Java / JUnit Jupiter

Targets JUnit Jupiter 5.11+ (`argumentSet` needs 5.11; everything here also works on JUnit 6.x), AssertJ, and Java 17+. **Check the project's JUnit version first**; on 5.8 to 5.10 use the fallback under **Row names**. Parameterized tests need `junit-jupiter-params`, which the `junit-jupiter` aggregator already includes. Import `junit-bom` so all JUnit versions stay aligned.

## Tables

```java
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.junit.jupiter.params.provider.Arguments.argumentSet;

class ShippingFeeTest {

    @ParameterizedTest(name = "{0} kg to {1} costs {2}")
    @CsvSource(textBlock = """
        0.5, DOMESTIC, 4.90
        2.0, DOMESTIC, 6.90
        2.0, EU,       12.50
        """)
    void fee_depends_on_weight_and_zone(BigDecimal kg, Zone zone, BigDecimal expected) {
        assertThat(ShippingFee.of(kg, zone)).isEqualByComparingTo(expected);
    }

    @ParameterizedTest
    @MethodSource
    void rejects_invalid_parcels(Parcel parcel, String reason) {
        assertThatThrownBy(() -> ShippingFee.of(parcel))
            .isInstanceOf(InvalidParcelException.class)
            .hasMessageContaining(reason);
    }

    static Stream<Arguments> rejects_invalid_parcels() {
        return Stream.of(
            argumentSet("zero weight", aParcel().weightKg("0").build(), "weight"),
            argumentSet("over 30 kg", aParcel().weightKg("30.01").build(), "weight"),
            argumentSet("unknown zone", aParcel().zone(null).build(), "zone"));
    }
}
```

- **Sources**:
  - `@CsvSource(textBlock = ...)` for scalar rows. `@MethodSource` for rows that need objects; with no name, it finds the factory method that has the test's name. `@EnumSource(names = {...})` for enum constants. `@ValueSource` for a single column.
- **Row names**:
  - Name rows with `argumentSet("behavior", ...)` or `@ParameterizedTest(name = ...)`, so the failure output says which case broke.
  - JUnit 5.8 to 5.10 (no `argumentSet`): wrap the first argument, `Arguments.of(Named.of("zero weight", parcel), "weight")`, or add a leading name column with `@ParameterizedTest(name = "{0}")` (e.g. `@CsvSource` rows starting with `'grace: 2 days late', 2, 0`).
  - `Arguments.of` is fine only when the arguments themselves read as a name.
  - Some Maven Surefire versions print only `[n]` for rows in console and XML reports. Put the row name into the assertion too (`assertThat(fee).as(rowName).isEqualTo(want)`), so the failure message names the case either way.
- **Several properties of one result**: check them all in one row with `assertSoftly(s -> {...})` or `assertAll(...)`, so a single failure reports every mismatch.
- **Shared context**: group related scenarios with `@Nested` classes ("given an expired session"), rather than giving table rows setup flags.
- **Valid vs invalid inputs**: put them in separate methods, as above. A `shouldFail` column is a split signal.

## Slice tests (Spring Boot example; the same shape works with Javalin, Micronaut, Quarkus)

```java
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
@Testcontainers
class PlaceOrderSliceTest {

    @Container @ServiceConnection
    static PostgreSQLContainer<?> db = new PostgreSQLContainer<>("postgres:16.4-alpine");

    // @TestBean (Spring Framework 6.2+ / Boot 3.4+) replaces the single bean of the field's type,
    // so the production adapter is never created. The instance comes from the static factory of the same name.
    @TestBean EmailSender emailSender;
    static EmailSender emailSender() { return new RecordingEmailSender(); }

    @TestBean Clock clock;
    static Clock clock() { return new MutableClock(Instant.parse("2026-03-01T10:00:00Z"), ZoneOffset.UTC); }

    @Autowired TestRestTemplate http;

    @Test
    void placing_an_order_persists_it_and_emails_a_confirmation() {
        var customer = "c-" + UUID.randomUUID();           // per-test data isolation

        var created = http.postForEntity("/orders",
            Map.of("customerId", customer, "sku", "A1", "qty", 2), OrderDto.class);

        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        var stored = http.getForObject("/orders/" + created.getBody().id(), OrderDto.class);
        assertThat(stored)
            .usingRecursiveComparison().ignoringFields("id")
            .isEqualTo(new OrderDto(null, customer, "A1", 2, "PENDING", Instant.parse("2026-03-01T10:00:00Z")));
        assertThat(((RecordingEmailSender) emailSender).sentTo(customer)).containsExactly("Order confirmation");
    }
}
```

- **Container**:
  - `@ServiceConnection` needs Spring Boot 3.1+. Without Spring, read `db.getJdbcUrl()` and pass it to your own wiring.
  - For one container per JVM, do not just move the annotated field into a base class: `@Testcontainers`/`@Container` stop it after each class, and a cached Spring context then points at a dead port. Either drop both annotations and start it yourself (`static final PostgreSQLContainer<?> DB = new PostgreSQLContainer<>(...); static { DB.start(); }` in a base class or holder, plus `@ServiceConnection` or `@DynamicPropertySource`), or declare it as a `@Bean @ServiceConnection` in a shared `@TestConfiguration` so its lifecycle follows the application context.
- **`@Transactional` on HTTP slice tests**: it does nothing useful here, because the server runs on a different thread. Isolate data with unique IDs instead, or truncate at the start of each test.
- **Unmanaged dependencies**: replace them with a spy or fake at your own adapter bean.
  - Replace the bean definition (`@TestBean`, or on older Spring exclude the production adapter's configuration/profile and register the fake). A `@Bean @Primary` test bean only wins injection: the real adapter is still created (its constructor or init can contact the service) and still shows up in `List<EmailSender>` injection.
  - Recent Spring Boot has `@MockitoBean`. Keep it for unmanaged adapters only, and prefer a hand-written spy that records messages.
- **Server-side exceptions**: expose them through `http` responses. Assert on the status code and the error body.

## Fakes and spies

```java
final class RecordingEmailSender implements EmailSender {
    private final List<Email> sent = new CopyOnWriteArrayList<>();
    @Override public void send(Email email) { sent.add(email); }
    List<String> sentTo(String customerId) {
        return sent.stream().filter(e -> e.customerId().equals(customerId)).map(Email::subject).toList();
    }
}
```

- Write a fake as a real class that implements the port interface. Run the same contract test against the fake and against the real adapter: an abstract test class, with one subclass per implementation.
- Mockito is permitted only for unmanaged adapters. Verify each outgoing command individually, e.g. `verify(gateway).charge(...)` and `verify(gateway, never()).refund(any())`. Add `verifyNoMoreInteractions(gateway)` only when the adapter is command-only: Mockito counts calls to stubbed queries as interactions, so on a mixed adapter it would fail on legitimate lookups. Never `verify` a stubbed query, and never mock repositories or domain classes.

## Time

- Inject `java.time.Clock`. In production, use `Clock.systemUTC()`.
- For fixed-time tests, use `Clock.fixed(Instant.parse("2026-03-01T10:00:00Z"), ZoneOffset.UTC)`.
- Always set the zone explicitly when the code derives local dates (`LocalDate.now(clock)`). If time does not need to move, prefer `Clock.fixed` or `Clock.offset`.
- When a test needs time to move, use a small mutable clock that honors `withZone`:

```java
final class MutableClock extends Clock {
    private final AtomicReference<Instant> now;   // shared by every zone view
    private final ZoneId zone;
    MutableClock(Instant start, ZoneId zone) { this(new AtomicReference<>(start), zone); }
    private MutableClock(AtomicReference<Instant> now, ZoneId zone) { this.now = now; this.zone = zone; }
    void advance(Duration d) { now.updateAndGet(t -> t.plus(d)); }
    @Override public Instant instant() { return now.get(); }
    @Override public ZoneId getZone() { return zone; }
    @Override public Clock withZone(ZoneId z) { return new MutableClock(now, z); }
}
```

- Domain methods take `Instant now` as a parameter. Only the application service reads the clock.
- For async outcomes, poll with a bounded timeout (Awaitility `await().atMost(Duration.ofSeconds(5)).untilAsserted(...)`), never `Thread.sleep`.

## Naming and assertions

- Use `snake_case` method names that state facts, or `@DisplayName`, and name the behavior rather than the method.
- Prefer AssertJ over `assertTrue(x.equals(y))`, because its failure messages show both values.
- For value objects, compare with `isEqualTo` (their `equals`) or assert on public accessor results. Reserve `usingRecursiveComparison()` for DTOs, records and explicit observable snapshots: it walks fields, including private ones, and by default ignores overridden `equals`, so on an entity with private state (caches, counters) it fails when public behavior has not changed. For collections, use `containsExactly` or `containsExactlyInAnyOrder`.

## Pitfalls

- Mutable `@BeforeEach` fixtures stored in fields hide cause and effect. Use builder calls in each test instead.
- `@TestInstance(PER_CLASS)` combined with mutable fields leaks state between tests.
- `@MethodSource` factories must be `static`, unless the class uses `PER_CLASS`.
- Partial-mocking the class under test (`spy(new Service())`) means the class is overcomplicated: split it.
- H2 standing in for Postgres or MySQL: use Testcontainers with the production engine.
