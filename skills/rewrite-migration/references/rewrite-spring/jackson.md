# rewrite-spring: Jackson

Rules that rewrite-spring's Recipes report about Jackson wiring in Spring code. The Jackson 3 API rules of
rewrite-jackson are in `../rewrite-jackson/jackson.md`.

## jackson/custom-http-converter

`MigrateJacksonJsonHttpMessageConverter` moves ordinary construction of `MappingJackson2HttpMessageConverter` (no
argument, or a known `JsonMapper`) to Spring Framework 7's `JacksonJsonHttpMessageConverter`. It reports the rest:
a mapper of uncertain type, a converter subclass, converter method calls, and a converter referenced but not
constructed in the file. The row is `BEHAVIOUR` while jackson-databind 2 is on the source set's class path (the
deprecated converter still compiles and starts) and `BLOCKER` when it is not.

Start from the reported file, then search the repository for `MappingJackson2HttpMessageConverter`,
`HttpMessageConverters`, and `ObjectFactory<HttpMessageConverters>`: callers in other files need the same decision.

- Trace the mapper to its producer, including bean qualifiers and factory return types. The new converter requires
  `tools.jackson.databind.json.JsonMapper`. Cast an `ObjectMapper` only where its producer is known to build a JSON
  mapper.
- When a producer is known to create a JSON mapper, update its declaration and callers together. A mapper from a
  library, a custom subtype or another format (XML, YAML, CBOR) needs that contract read first. Keep the configured
  mapper: a fresh default mapper loses its configuration.
- Keep modules, naming strategy, inclusion, date and time settings, mixins, custom serializers, supported media types,
  and every converter override the application uses. Jackson 3 moves some features and builds mappers with builders;
  start from the configuration the Run already migrated.
- Check setter-based configuration and subclasses against the resolved Spring Framework 7 API. A class rename does
  not adapt removed methods or superclass contracts.
- Resolve the key once the case is settled in every file that shares the converter.

Check: serialize and deserialize representative DTOs with the application's customized dates, enums, naming and null
handling, through the converter (a `@WebMvcTest` or `MockMvc` round trip), and assert the content type.

Sources: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide),
[Spring Framework 7 `JacksonJsonHttpMessageConverter`](https://github.com/spring-projects/spring-framework/blob/v7.0.0/spring-web/src/main/java/org/springframework/http/converter/json/JacksonJsonHttpMessageConverter.java).

## jackson/jackson2-property-kept

Spring Boot 4.0 deprecates the `spring.jackson2.*` keys and `management.endpoints.jackson2.isolated-object-mapper`,
but they still bind and configure the Jackson 2 `ObjectMapper` that Boot keeps for Jackson 2 users. The Migration
keeps each key unchanged with a `PRESERVED` row.

- Leave the item unresolved. Moving the settings to the Jackson 3 `spring.jackson.*` keys, once the application no
  longer needs the Jackson 2 mapper, is an Improvement.

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## jackson/removed-mapper-feature-property

The key names a `MapperFeature` that Jackson 3 removed (`use-std-bean-naming`,
`sort-creator-properties-by-declaration-order`, `auto-detect-*=true`, and others). Spring Boot 4 fails to bind
`spring.jackson.mapper` while it is set, so the application does not start. (`auto-detect-<x>=false` is migrated to
`spring.jackson.visibility.<x>=none` without a row.)

- `auto-detect-*=true` was the default: remove the key.
- `use-std-bean-naming`: Jackson 3 always uses standard bean naming; remove the key and check the JSON names of
  properties with a one-letter lower-case prefix (`xValue`).
- `sort-creator-properties-by-declaration-order` and the others: remove the key, then restore the behaviour on a
  `JsonMapperBuilderCustomizer` if the JSON depends on it.

Check: the context starts, and a JSON round trip of an affected DTO gives the old field names and order.

Source: [Jackson 3 migration guide](https://github.com/FasterXML/jackson/blob/main/jackson3/MIGRATING_TO_JACKSON_3.md).

## jackson/stream-feature-property-dropped

`spring.jackson.parser.*` and `spring.jackson.generator.*` are gone in Spring Boot 4.0. Features with a Jackson 3
`JsonReadFeature`/`JsonWriteFeature` move to `spring.jackson.json.read/write`; this one is a stream feature
(`StreamReadFeature`/`StreamWriteFeature`), which Spring Boot 4.0 has no property for. The key is commented out.

- On a 4.0 target, set the feature on a `JsonMapperBuilderCustomizer`
  (`builder.enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION)`). On a 4.1 target,
  `spring.jackson.read.<feature>` and `spring.jackson.write.<feature>` bind the stream features again; use those.
- When the value was the default, resolve `no-change` with a note.

Check: a JSON round trip that exercises the feature (duplicate keys, BigDecimal output and so on).

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## jackson/jersey-needs-spring-boot-jackson2

Jersey does not support Jackson 3, and Spring Boot 4's Jersey support reads JSON through Spring Boot's Jackson 2
module. The Migration adds `org.springframework.boot:spring-boot-jackson2` (version from the Spring Boot BOM) next to
`spring-boot-starter-jersey` or `spring-boot-jersey`, with the provenance comment, and reports a `PRESERVED` row.

- Leave the item unresolved. Jersey resources and `ContextResolver<ObjectMapper>` providers stay on Jackson 2.
- Remove the dependency together with its comment only when the module no longer uses Jersey.

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## jackson/jackson-tester-mapper

Spring Boot 4's `JacksonTester.initFields(..)` takes a Jackson 3 `JsonMapper`. The Recipe retypes the argument when
it is a local or field whose value is a `JsonMapper` construction, a `JsonMapper.builder()...build()` chain, or an
injected field. This argument is another shape (a method result, a parameter, an `ObjectMapper` subclass) and was
kept; the test does not compile.

- Build the mapper as a `JsonMapper` (`JsonMapper.builder()...build()`), or inject Spring Boot's `JsonMapper` bean,
  and pass that.
- A test that must keep Jackson 2 uses `Jackson2Tester` instead (Jackson 2 islands).

Check: the test class compiles and its JSON assertions pass.

## jackson/boot-jackson2-defaults-property

Spring Boot 4 configures its mapper with Jackson 3's defaults. The module uses Spring Boot's Jackson auto-configuration
and started below Spring Boot 4.0, so the Migration added `spring.jackson.use-jackson2-defaults=true` and
`spring.jackson.mapper.detect-parameter-names=true` (each with the provenance comment and its own row). The pin is
close, not exact: XValue naming, JsonNode strictness, `ALLOW_VOID_VALUED_PROPERTIES`, map order with incomparable keys,
the fast number parsers and private single-scalar constructors still follow Jackson 3. Keys the application sets win:
Spring Boot applies them after the flag.

- Leave the item unresolved to keep the old JSON contract. Adopt the Jackson 3 defaults by removing the key and its
  comment once clients accept the new JSON.
- For the differences the pin does not cover, see `jackson/xvalue-naming`, `jackson/jsonnode-strict-accessor` and
  `jackson/creator-visibility`.

Check: the HTTP JSON of the application's endpoints equals the JSON before the Run (dates, enums, nulls, order,
unknown properties).

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## jackson/creator-visibility-pinned

Jackson 3 no longer detects non-public creators. The Migration added `spring.jackson.visibility.creator=any`, with the
provenance comment, so Spring Boot's mapper still binds through non-public multi-argument constructors as Jackson 2
did. It does not reach private single-scalar constructors (`jackson/creator-visibility`).

- Leave the item unresolved. Adopt the new default by removing the key once every bound class has a public or
  `@JsonCreator` creator.

Check: request bodies bound to classes with non-public constructors still bind.

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## jackson/island-boot-jackson2-bean

A Jackson 2 island of the module injects Spring Boot's `ObjectMapper` (or keeps a Jackson 2 customizer), which Spring
Boot 4 only provides with `org.springframework.boot:spring-boot-jackson2`. The Migration added that dependency with
the provenance comment, and mirrored every `spring.jackson.*` key the module set into `spring.jackson2.*` (one row per
key), which configures that Jackson 2 mapper.

- Leave the item unresolved while the island needs the Jackson 2 mapper. Remove the dependency and the
  `spring.jackson2.*` keys once no island injects it.

Check: the context starts, and the island's output (the Kafka record, the stored value) equals the one before the Run.

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## jackson/boot-mapper-customizer

This `Jackson2ObjectMapperBuilderCustomizer` (a lambda bean, or a class implementing `customize(..)`) calls builder
methods without a known `JsonMapper.Builder` equivalent (`postConfigurer`, `handlerInstantiator`, ...). The
Migration converts the customizers whose calls all map. Spring Boot 4 has no such customizer for its HTTP mapper, so
the code does not compile. (In a module with Jackson 2 islands the Migration moves it to
`org.springframework.boot.jackson2.autoconfigure.Jackson2ObjectMapperBuilderCustomizer` instead, which customizes the
Jackson 2 mapper.)

- Rewrite it as a `JsonMapperBuilderCustomizer` bean with the Jackson 3 builder calls that do the same (for
  `postConfigurer`, configure the builder instead of the built mapper).
- If it must customize a Jackson 2 mapper, use Spring Boot 4's Jackson 2 customizer and `spring-boot-jackson2`, and
  check which mapper the HTTP converters use.

Check: the HTTP JSON shows the customization (a test of the affected endpoint or a `JsonMapper` bean assertion).

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).
