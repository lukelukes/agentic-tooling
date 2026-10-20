# rewrite-spring: Spring Cloud

These notes apply when a Worklist item, a compile error or a test failure leads into OpenFeign or Spring Cloud AWS
code after a Boot 4 Run. Establish the resolved OpenFeign and Spring Cloud AWS versions first
(`dependencyInsight --configuration runtimeClasspath` in Gradle, `dependency:tree` in Maven): they are independent of
the Boot version.

## cloud/openfeign-decoder-converters

`MigrateSpringDecoder` adapts each one-argument `new SpringDecoder(..)` to OpenFeign 5's
`ObjectProvider<FeignHttpMessageConverters>` and reports it, anchored on the enclosing method. It decides in the first
cycle whether the repository declares an `HttpMessageConverters` bean of its own:
- No user bean, and the argument is an injected `ObjectFactory<HttpMessageConverters>` used only there (a `@Bean`
  method parameter, an `@Autowired` field, or a field set from the constructor Spring injects, which is retyped with
  its constructor parameter): it is retyped to `ObjectProvider<FeignHttpMessageConverters>`. The converters and their order now come from Feign's own
  assembly.
- A user bean, a lambda, or a factory used elsewhere: a generated `feignHttpMessageConverters(..)` adapter keeps the
  old factory and its converter list.

What to do:
- Retyped: compare the converters Feign now assembles with the ones the old `HttpMessageConverters` bean held. If the
  client relied on a custom converter or its position, add it the OpenFeign 5 way (see the next section), or put the
  adapter back.
- Adapter kept on a user bean: Spring Boot 4 deprecates `HttpMessageConverters`. Leave it if it works and resolve
  `no-change` with a note; moving the converters to a `ClientHttpMessageConvertersCustomizer` is a follow-up.
- Adapter on a lambda or a reused factory: check that the factory still resolves lazily and gives the same list.

Check: decode a real response through a local stub or the existing test server, with the content type and the
converter that matter.

## OpenFeign encoders and decoders

Start from: search for `SpringEncoder`, `SpringDecoder`, `ObjectFactory<HttpMessageConverters>` and generated
`feignHttpMessageConverters` adapters.

`MigrateSpringDecoder` handles only the one-argument `SpringDecoder` constructor, with an adapter that delegates to
the old converter factory. It keeps the original list and the lazy lookup, and it is a bridge, not the final
customizer-based design. Encoders, customizers and other constructor overloads each need their own decision.

- Decide whether the application needs a custom encoder or decoder at all, and keep deliberate customization. When
  Spring already supplies the required converters, inject its `ObjectProvider<FeignHttpMessageConverters>` in the
  Feign configuration that needs it.
- Keep a client-specific configuration scoped to that client. A global customizer changes every other HTTP client.
- Read the resolved OpenFeign API. In 5.0.0 the `FeignHttpMessageConverters` constructor takes providers of
  converters and list customizers. In 5.0.2 it takes providers of `ClientHttpMessageConvertersCustomizer` and list
  customizers. 5.x releases differ in these signatures.
- To replace the JSON converter with the builder-customizer API, use `builder.withJsonConverter(configuredConverter)`.
  `addCustomConverter` changes precedence and has different semantics.
- Keep converter ordering, supported content types, whether defaults were enabled, existing list customizers, and
  multipart and form encoding. OpenFeign 5.0.2 calls `registerDefaults()` before builder customization, so replacing
  JSON alone does not reproduce an old `new HttpMessageConverters(false, ...)` list. When the exact list matters,
  keep a deliberate adapter, or use a supported list customization after reading the target API.
- Prefer container-supplied providers. For a standalone provider that consumers read with `orderedStream()`,
  implement `stream()` (for example `Stream.of(value)`); `getObject()` alone is not enough. An empty
  `new ObjectProvider<>() {}` works only when no elements are intended and consumers iterate or use optional lookup:
  its `getObject()` throws. Check the methods consumers actually call, and keep lazy creation where the old factory
  relied on it.

Check: send a real encoded request and decode a real response through a local stub or the existing test server.
Assert the content type, converter precedence, and forms or multipart where used, and that unrelated clients keep
their configuration.

Source: [OpenFeign 5.0.2 `FeignHttpMessageConverters`](https://github.com/spring-cloud/spring-cloud-openfeign/blob/v5.0.2/spring-cloud-openfeign-core/src/main/java/org/springframework/cloud/openfeign/support/FeignHttpMessageConverters.java).

## Spring Cloud AWS alignment

`UpgradeSpringCloudAws_4` upgrades the `io.awspring.cloud:spring-cloud-aws-dependencies` BOM and explicitly versioned
`spring-cloud-aws-*` modules to 4.1.x and leaves BOM-managed modules versionless.

- Prefer the existing BOM. When modules still resolve to mixed versions, look for stale pins, constraints, imported
  BOM precedence and resolution rules in the dependency insight output.
- Pick an AWS release that is compatible on its own terms; it does not follow the Boot version number.
- Leave `software.amazon.awssdk` versions to their own change.

Check: every resolved `io.awspring.cloud` module has the same version, and the affected application or test context
starts with the existing mocks or a local emulator. Use no live AWS account to validate a dependency change.

Source: [Spring Cloud AWS compatibility](https://github.com/awspring/spring-cloud-aws#compatibility-with-spring-project-versions).

## cloud/gateway-trusted-proxies

The module runs a Spring Cloud Gateway server and sets neither `spring.cloud.gateway.server.webflux.trusted-proxies` nor `...webmvc.trusted-proxies` in any profile: the gateway ignores `X-Forwarded-*` and `Forwarded` headers (CVE-2025-41235). One row on the build file.

Inspect: the proxies in front of the gateway in each environment.

Decide: set `trusted-proxies` to a narrow regex of the real proxy addresses; never `.*`.

Prove: a proxy integration test with `X-Forwarded-*` headers from a trusted and an untrusted address.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## cloud/feign-okhttp-autoconfig-removed

Spring Cloud OpenFeign 5 removed the OkHttp auto-configuration: with `feign-okhttp` and `spring.cloud.openfeign.okhttp.enabled` (or `httpclient.ok-http.*`) Feign falls back to another client without a warning, and the OkHttp settings are ignored.

Inspect: the TLS, interceptor and timeout settings of the OkHttp client.

Decide: move to the HC5 transport (`feign-hc5`, `spring.cloud.openfeign.httpclient.hc5.enabled`), or register an OkHttp client by hand; port TLS, interceptors and timeouts.

Prove: on the fixture, pin 20 (`FeignTimeoutPinTest.readTimeout`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).
