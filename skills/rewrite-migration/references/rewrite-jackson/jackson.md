# rewrite-jackson: Jackson 2 to 3

Rules of `org.openrewrite.java.jackson.UpgradeJackson_2_3`. In Jackson 3 mappers and factories are immutable and
built with builders, `com.fasterxml.jackson` packages moved to `tools.jackson` (annotations stay in
`com.fasterxml.jackson.annotation`), and exceptions are unchecked. Read the resolved Jackson 3 version and its
sources before choosing an API; Spring wiring of mappers is in `../rewrite-spring/jackson.md`.

## jackson/mapper-setter-not-folded

A configuration call on an existing mapper (`configure`, `enable`, `disable`, `registerModule`, `setSerializationInclusion`,
`addMixIn`, ...) that the Recipe could not fold into the builder where the mapper is made, for example because the
mapper comes from a parameter, a field set elsewhere, or a factory method.

- Move the call to where the mapper is built, as the builder method of the same name on `JsonMapper.builder()`
  (or the format's builder).
- When the mapper cannot be rebuilt there, replace the mutation with `mapper = mapper.rebuild().<call>(..).build()`
  and make sure every user reads the rebuilt instance; the old instance stays unconfigured.

Check: a test that serializes with the configured mapper and shows the setting took effect.

## jackson/factory-setter-not-folded

The same for `JsonFactory` (and format factories): a setter that could not be folded into `JsonFactory.builder()`.
Move it to where the factory is built, or use `factory.rebuild().<call>(..).build()` and use the result.

## jackson/mapper-method-removed

An `ObjectMapper` method with no Jackson 3 replacement in that place:

- `canSerialize(..)` / `canDeserialize(..)`: removed
  ([jackson-databind#1917](https://github.com/FasterXML/jackson-databind/issues/1917)). Attempt the
  serialization or deserialization and catch `JacksonException` instead, or drop the check when it only guarded
  logging.
- `serializationConfig()` / `deserializationConfig()`: configure through the builder; read settings with
  `mapper.isEnabled(..)` where only a flag was wanted.
- A setter kept in a builder chain because it was removed: find its builder or feature equivalent in the Jackson 3
  sources (`MapperBuilder`, `DateTimeFeature`, `EnumFeature`, ...), or remove it when it set a default.

## jackson/simple-module-call-commented-out

A module that no longer extends `SimpleModule` in Jackson 3 (`JodaModule`) received `addSerializer(..)`,
`addDeserializer(..)` or a similar call. Create a `SimpleModule` holding those calls and register it after the
original module, so it keeps overriding the module's own (de)serializers.

Check: a round trip of a type the custom (de)serializer handles.

## jackson/tree-to-value-in-deserializer

`parser.getCodec().treeToValue(node, Foo.class)` has no Jackson 3 equivalent on `ObjectReadContext`. Inside
`deserialize(JsonParser, DeserializationContext)` the Recipe rewrites it to `ctxt.readTreeAsValue(node, Foo.class)`;
this row is a call with no `DeserializationContext` in scope.

- Pass the `DeserializationContext` down to the helper that makes the call, and call `readTreeAsValue(..)` on it.
- Where no context exists (code outside deserialization), use the application's mapper: `mapper.treeToValue(..)`.

## jackson/json-ignore-removed

`FindJsonSetterNullsAsEmptyCollections` audits fields that carry `@JsonSetter(nulls = Nulls.AS_EMPTY)` as their only
argument. rewrite-jackson 1.17.0 to 1.28.0 replaced `@JsonIgnore` with exactly that annotation, which starts
serializing properties that were hidden on purpose.

- Read the field's history (`git log -L` or blame on the annotation line) or the pre-migration build. If the field had
  `@JsonIgnore`, restore it (both annotations can stay, or only `@JsonIgnore`).
- If the property should be in the JSON, resolve as `no-change` with the reason.

Check: serialize the type and assert the property is absent (or present, for `no-change`).

## jackson/builtin-module-customized

Jackson 3 builds in `JavaTimeModule`, `Jdk8Module` and `ParameterNamesModule`. `RemoveBuiltInModuleRegistrations`
deletes an argument-less registration whose instance has no other use. A module customized with `addSerializer`,
`addDeserializer`, ... has its calls moved onto a `new SimpleModule()` registered in its place, and the row says so.
A registration from an instance used or configured elsewhere is kept and reported.

- `SimpleModule` row: the built-in module now registers its defaults first and the `SimpleModule` adds yours. Check
  that your serializers still win for the types they cover.
- Kept row: move what the instance configures onto a `SimpleModule` or the mapper builder, then drop the registration
  and the instance.

Check: serialize and deserialize a value of each customized type and compare with the JSON from before the Run.

Source: [Jackson 3.0 release notes](https://github.com/FasterXML/jackson/wiki/Jackson-Release-3.0).

## jackson/parameter-names-mode

`new ParameterNamesModule(JsonCreator.Mode.PROPERTIES|DELEGATING)` on a mapper builder becomes
`.constructorDetector(ConstructorDetector.USE_PROPERTIES_BASED|USE_DELEGATING)`. This row is for a registration that
sets a mode in a shape the Recipe did not convert (a mapper setter, another mode, a variable).

- Set the same mode on the mapper builder with `constructorDetector(..)`, and remove the registration.

Check: deserialize a type with a single-argument constructor and one with several, and compare with before the Run.

Source: [Jackson 3.0 release notes](https://github.com/FasterXML/jackson/wiki/Jackson-Release-3.0).

## jackson/creator-visibility

Jackson 3 no longer detects a non-public constructor as a creator. The Recipe adds `@JsonCreator` only to the one
safe shape: a class (not an enum or record) with exactly one non-public constructor with parameters, no no-arg
constructor, and parameter names that match its properties. A class that names its creator already (a
`@JsonCreator` constructor or static factory) is left alone. Every other candidate constructor is reported, anchored
on the constructor.

- Pick the constructor Jackson should use and annotate it with `@JsonCreator` (with `mode = PROPERTIES` for a single
  parameter that names a property), or make it public.
- If Jackson used setters with a no-arg constructor before, and that is still wanted, resolve `no-change`.

Since WP5 the scan also reports two shapes that `spring.jackson.visibility.creator=any` does not reach: a private
single-scalar-argument constructor (`private Sku(String value)`), and a non-public creator of a class that a mapper
other than Spring Boot's reads (hand-built, Kafka, Feign).

- For the single-scalar constructor, add `@JsonCreator` (choose `mode = DELEGATING` when the JSON is the bare value,
  `PROPERTIES` when it is an object) or make it public.
- For a class that a non-Boot mapper reads, the row is on each non-public constructor with parameters of a class
  that has neither a public constructor nor a `@JsonCreator`: annotate the one Jackson should use with
  `@JsonCreator`, or make it public.

Check: deserialize the DTO from a JSON sample of the API and assert every field.

Source: [Jackson 3.0 release notes](https://github.com/FasterXML/jackson/wiki/Jackson-Release-3.0).

## jackson/jackson2-island

The file is a Jackson 2 island: a Jackson 2 value in it crosses into an API that only takes Jackson 2 (a library
method or constructor with a `com.fasterxml.jackson` parameter or return type, a `ContextResolver<ObjectMapper>`), or
it uses one of Spring's Jackson 2 serializers that the Migration keeps. The Migration left every
`com.fasterxml.jackson` import, type and method name in the file, and its module keeps `jackson-databind` 2 (the
setting names the build file). The row's message names the boundary and, for a known library, what it lacks.

- Leave the item unresolved while the library has no Jackson 3 API. The island compiles and behaves as before.
- Once the library supports Jackson 3, move the file to `tools.jackson` (the library's Jackson 3 artifact, its new
  types) and remove the kept Jackson 2 artifacts when no island is left in the module.

Check: the module compiles, and the code that hands the Jackson 2 value over still runs (its test, or the library call
in a test).

Source: [Migrating to Jackson 3](https://github.com/FasterXML/jackson/blob/main/jackson3/MIGRATING_TO_JACKSON_3.md).

## jackson/jackson2-kept-in-module

The module has a Jackson 2 island, a kept Jackson 2 sink, or a Kafka Jackson 2 serde in its configuration, so the
Migration kept this `com.fasterxml.jackson` artifact (declared before the Run, or added because the module resolved
it then) and added `tools.jackson.core:jackson-databind` for the code that moved to Jackson 3.

- Leave the item unresolved while the module has islands or sinks (see their rows).
- Remove the artifact once the last island and sink of the module have moved to Jackson 3.

Check: the module compiles and its tests pass.

Source: [Migrating to Jackson 3](https://github.com/FasterXML/jackson/blob/main/jackson3/MIGRATING_TO_JACKSON_3.md).

## jackson/island-shared-jackson-class

A repository class with a Jackson 2 supertype (a serializer, a module) is used both by a Jackson 2 island and by code
that moved to Jackson 3. The Migration moved the class to Jackson 3, so the island code that uses it does not compile.

- Give the island its own Jackson 2 copy of the class (keep the original for the Jackson 3 code), or move the island
  to Jackson 3 if its library allows.

Check: the module compiles, and both mappers write the same JSON for a sample value as before the Run.

Source: [Migrating to Jackson 3](https://github.com/FasterXML/jackson/blob/main/jackson3/MIGRATING_TO_JACKSON_3.md).

## jackson/island-payload-databind-annotation

A DTO outside the islands carries `com.fasterxml.jackson.databind.annotation` annotations (`@JsonSerialize`,
`@JsonDeserialize`, ...) and a Jackson 2 island serializes it. The Migration moved the annotations to
`tools.jackson.databind.annotation`, which the island's Jackson 2 mapper does not read.

- If the island must keep the old JSON, put the Jackson 2 annotation back next to the Jackson 3 one (both can be on
  the element), or serialize a Jackson 2 copy of the DTO in the island.

Check: the island writes and reads the DTO as before the Run (a round trip through its mapper).

Source: [Migrating to Jackson 3](https://github.com/FasterXML/jackson/blob/main/jackson3/MIGRATING_TO_JACKSON_3.md).

## jackson/island-mixed-file

The island file also holds a method that uses Jackson 2 without crossing into a Jackson 2 API. Because the whole file
stays on Jackson 2, that code did not move to Jackson 3.

- Move the method (and what only it uses) to another file, then rerun the Jackson 3 migration on that file, or move it
  by hand. Leave the boundary code where it is.

Check: the module compiles and the moved code's tests pass.

Source: [Migrating to Jackson 3](https://github.com/FasterXML/jackson/blob/main/jackson3/MIGRATING_TO_JACKSON_3.md).

## jackson/kafka-json-serde

spring-kafka 4.0 keeps its Jackson 2 serializer, deserializer, serde, message converters and type mappers
(`JsonSerializer`, `JsonDeserializer`, `DefaultJackson2JavaTypeMapper`, ...), deprecated. The Migration kept them, so
the record bytes and the `__TypeId__` headers stay identical; the configuration properties keep their class names. A
file that builds them in code is a Jackson 2 island.

- Leave the item unresolved. Moving a topic to `JacksonJsonSerializer`/`JacksonJsonDeserializer` changes the wire
  format and needs a plan for records already on the topic (an Improvement).

Check: a record produced after the Run equals one produced before (value bytes and `__TypeId__`), and a record
written before the Run is still consumed.

Source: [spring-kafka 4.0 what's new](https://docs.spring.io/spring-kafka/reference/4.0/whats-new.html#x40-jackson3-support).

## jackson/redis-jackson2-serializer

spring-data-redis keeps its Jackson 2 serializers (`GenericJackson2JsonRedisSerializer`, `Jackson2JsonRedisSerializer`,
`Jackson2HashMapper`). The Migration kept them, so stored values (sessions, cache entries) keep their bytes, including
their `@class` type ids. The file is a Jackson 2 island.

- Leave the item unresolved. Moving the store to the Jackson 3 serializers changes the stored bytes; it needs a
  migration of the stored data (an Improvement).

Check: a value written after the Run equals the bytes written before, and a value stored before the Run is read back.

Source: [Spring Data Redis](https://github.com/spring-projects/spring-data-redis/wiki).

## jackson/security-jackson2-modules

`SecurityJackson2Modules` and the `org.springframework.security.jackson2` mixins stay: they are what reads the
security context of sessions stored before the Run. The authorization server's JDBC services
(`JdbcOAuth2AuthorizationService`, `JdbcRegisteredClientRepository`) are kept the same way: they store authorizations
and registered clients as JSON written with those modules. The file is a Jackson 2 island.

- Leave the item unresolved. Moving to Spring Security 7's Jackson 3 modules changes the stored session format.

Check: a session stored before the Run still authenticates after it, and an authorization stored before the Run is
still found by its token.

Source: [Spring Security 7.0 migration](https://docs.spring.io/spring-security/reference/7.0/migration/index.html).

## jackson/amqp-jackson2-message-converter

spring-amqp keeps `Jackson2JsonMessageConverter` and its type mapper. The Migration kept them, so message bodies and
type headers stay identical. The file is a Jackson 2 island.

- Leave the item unresolved; moving a queue to the Jackson 3 converter changes the wire format.

Check: a message sent after the Run equals one sent before (body and type headers).

Source: [Spring AMQP 4.0 what's new](https://docs.spring.io/spring-amqp/reference/4.0/whats-new.html).

## jackson/batch-jackson2-execution-context

Spring Batch 6 keeps `Jackson2ExecutionContextStringSerializer`. The Migration kept it, so the stored
`SERIALIZED_CONTEXT` of job and step executions keeps its format and restarts read contexts written before the Run.

- Leave the item unresolved; switching serializers needs every stored context to be readable by the new one.

Check: a context written after the Run equals the stored format, and a job execution stored before the Run restarts.

Source: [Spring Batch 6.0 migration guide](https://github.com/spring-projects/spring-batch/wiki/Spring-Batch-6.0-Migration-Guide).

## jackson/jms-jackson2-message-converter

Spring's `MappingJackson2MessageConverter` (JMS and spring-messaging) stays, deprecated. The Migration kept it, so
message bodies and type id properties stay identical. The file is a Jackson 2 island.

- Leave the item unresolved; moving to the Jackson 3 converter changes the wire format.

Check: a message sent after the Run equals one sent before.

Source: [Upgrading to Spring Framework 7](https://github.com/spring-projects/spring-framework/wiki/Upgrading-to-Spring-Framework-7.x).

## jackson/mongo-session-jackson2-converter

Spring Session's MongoDB support moved to MongoDB's `org.mongodb:mongodb-spring-session`. The Migration changed
`JacksonMongoSessionConverter` to its `Jackson2MongoSessionConverter`, not to the new module's Jackson 3
`JacksonMongoSessionConverter`, so stored session documents keep their format.

- Leave the item unresolved; moving to the Jackson 3 converter changes the stored documents.

Check: a session document stored before the Run still authenticates.

Source: [mongodb-spring-session](https://github.com/mongodb/mongo-spring-session).

## jackson/enum-tostring

The enum overrides `toString()` without `@JsonValue`, and a mapper the application builds itself in a shape the
Migration does not give `configureForJackson2()` (a constructor with arguments other than a format factory, or an
anonymous subclass) reads or writes it. Jackson 3 writes and reads enums with `toString()` by default, Jackson 2 with
`name()`. The mappers the Migration converted get `configureForJackson2()`, which restores `name()`, and Jackson 2
islands and kept sinks stay on Jackson 2, so neither gets this row.

- Find the mapper that handles the enum (built in the file the row names). Disable
  `EnumFeature.WRITE_ENUMS_USING_TO_STRING` and `READ_ENUMS_USING_TO_STRING` on it,
  or put `@JsonValue` on the representation the JSON should carry.

Check: the enum's JSON value after the Run equals the one before, and stored JSON is read back.

Source: [Migrating to Jackson 3](https://github.com/FasterXML/jackson/blob/main/jackson3/MIGRATING_TO_JACKSON_3.md).

## jackson/jsonnode-strict-accessor

`textValue()`, `asText()` or `intValue()` runs on a `JsonNode` whose type the code does not check. Jackson 3 renames
them (`stringValue()`, `asString()`) and makes the accessors strict: they throw for a node of another type where
Jackson 2 returned `null`, `0` or `""`.

- Check the node type first (`isTextual()`, `isNumber()`, `isMissingNode()`), or use the `asX(default)` forms that keep
  a fallback, so numeric, null and missing nodes give the old result.

Check: run the code on numeric, null and missing nodes and compare with the Jackson 2 results.

Source: [Migrating to Jackson 3](https://github.com/FasterXML/jackson/blob/main/jackson3/MIGRATING_TO_JACKSON_3.md).

## jackson/xvalue-naming

A serialized getter has an upper-case second letter (`getXValue()`, `getURL()`). Jackson 2 named the property with the
leading capitals lower-cased (`xvalue`, `url`); Jackson 3 may keep them, and Spring Boot's Jackson 2 defaults do not
restore this.

- Add `@JsonProperty("<the Jackson 2 name>")` to the getter (the row names it), or keep the new name where the JSON is
  internal.

Check: the property name in the JSON after the Run equals the one before.

Source: [Migrating to Jackson 3](https://github.com/FasterXML/jackson/blob/main/jackson3/MIGRATING_TO_JACKSON_3.md).

## jackson/hand-built-mapper-defaults

The application builds this mapper itself, so Spring Boot's `spring.jackson.use-jackson2-defaults` does not reach it.
The Migration added `configureForJackson2()` right after `builder()` (or wrote
`JsonMapper.builderWithJackson2Defaults().build()` for a plain `new JsonMapper()`), with the provenance comment, so it
keeps the Jackson 2 defaults (dates as timestamps, enums by name, lenient trailing tokens, ...); explicit settings that
follow still win. Where the mapper registered `ParameterNamesModule`, parameter names and creator visibility `ANY` are
turned on again after it.

- Leave the item unresolved to keep the old JSON. Adopt the Jackson 3 defaults by removing the call and its comment
  once the JSON the mapper writes and reads may change.

Check: the mapper writes the same JSON for a sample payload as before the Run.

Source: [Migrating to Jackson 3](https://github.com/FasterXML/jackson/blob/main/jackson3/MIGRATING_TO_JACKSON_3.md).
