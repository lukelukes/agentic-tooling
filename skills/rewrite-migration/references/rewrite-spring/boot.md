# rewrite-spring: Spring Boot

## boot/constructor-binding-removed

Spring Boot 3 removed type-level `@ConstructorBinding`. The Recipe removes the annotation from classes with one
constructor (binding is implicit there). A class with several constructors keeps the annotation at type level, which
no longer compiles, and is reported.

- Pick the constructor that binding should use and put `@ConstructorBinding`
  (`org.springframework.boot.context.properties.bind.ConstructorBinding`) on it. Remove the type-level annotation.
- When the class is better as a `record` or with one constructor, that is a larger change: resolve as `deferred`
  with a note instead of reshaping it.

Check: a test that binds the properties (an `ApplicationContextRunner` with the property values, or the existing
context test) and asserts a bound value.

Source: [Spring Boot 3.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.0-Migration-Guide).

## boot/endpoint-access-placeholder

Spring Boot 3.4 replaced the actuator `management.endpoint.<id>.enabled` (and
`management.endpoints.enabled-by-default`) with `access` (`none`, `read-only`, `unrestricted`). The Migration moves
`true` to `unrestricted` and `false` to `none`. A placeholder value is moved unchanged, but it resolves to `true` or
`false`, which `Access` does not bind: startup fails.

- Find where the placeholder is set (environment, Helm values, profile files) and change what it resolves to:
  `unrestricted` where it was `true`, `none` where it was `false`. If the source is outside the repository, resolve
  `deferred` with a note naming the variable.

Check: the context starts with the placeholder resolved as in each environment (a test with that property value).

Source: [Spring Boot 3.4 release notes](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.4-Release-Notes).

## boot/endpoint-access-both-keys

The file sets both `enabled` and `access` for one endpoint (or `enabled-by-default` and `access.default`). Spring
Boot 3.4 and later refuse to start with both.

- Keep the `access` key, check that its value is what `enabled` meant (`true` is `unrestricted`, `false` is
  `none`), and remove the `enabled` key, in every profile file that sets it.

Check: the context starts.

Source: [Spring Boot 3.4 release notes](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.4-Release-Notes).

## boot/removed-type-client-http-request-factories

Spring Boot 4.0 moved `org.springframework.boot.web.client` to `org.springframework.boot.restclient`, but
`ClientHttpRequestFactories` and the deprecated `web.client.ClientHttpRequestFactorySettings` have no type there. The
Recipe keeps them on their old name (the rest of the package moves) and reports each import or fully qualified use,
and each `RestTemplateBuilder.requestFactory(Function)` call in a file that does not import the settings type (its
lambda takes the removed settings type without naming it).
The module does not compile on Boot 4. The 3.5 `http.client.ClientHttpRequestFactorySettings` was already renamed to
`HttpClientSettings`, which has the same members.

- `ClientHttpRequestFactories.get(settings)` becomes
  `ClientHttpRequestFactoryBuilder.detect().build(settings)` (or `.httpComponents()`, `.jdk()`, ... for a fixed
  client), with `HttpClientSettings` from `org.springframework.boot.http.client`.
- `web.client.ClientHttpRequestFactorySettings.DEFAULTS` becomes `HttpClientSettings.defaults()`; the three-argument
  constructor becomes `new HttpClientSettings(null, connectTimeout, readTimeout, sslBundle)`.
- `RestTemplateBuilder.requestFactory(Function<ClientHttpRequestFactorySettings, ..>)` becomes
  `requestFactoryBuilder(settings -> ..)`.

Check: the client's timeouts and SSL bundle, through a test that builds the `RestTemplate` or `RestClient`.

Source: [Spring Boot 4.0 Migration Guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## boot/epp-third-party-deprecated-key

Spring Boot 4.0 deprecated `org.springframework.boot.env.EnvironmentPostProcessor` for
`org.springframework.boot.EnvironmentPostProcessor`; 4.1 still reads the old `spring.factories` key and 4.2 removes it.
The Recipe moves the post-processors the repository declares to the new key and merges them into an existing entry.
A class the repository does not declare (a library's) stays under the old key and is reported, anchored on the class
name in `META-INF/spring.factories`.

- If the class comes from a library that ships its own registration under the new key in the version you resolve,
  delete the line here.
- If the library is on a version that only implements the old interface, leave the line: it works on 4.1. Resolve
  `no-change` with a note naming the library version that has to move before Spring Boot 4.2.
- If the class is the repository's own after all (generated, or in another module), move it to the new key by hand.

Check: the context starts, and the post-processor's property source is present (a test that reads one of its
properties from the `Environment`).

Source: [Spring Boot 4.0 Migration Guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## boot/health-probes-enabled-by-default

Spring Boot 4 enables the liveness and readiness health groups and probes on every platform; Spring Boot 3 enabled
them on Kubernetes only. For a module that declares `spring-boot-starter-actuator` and does not set
`management.endpoint.health.probes.enabled`, the Migration adds it as `false` with the provenance comment and reports
a `PRESERVED` row.

- Leave the item unresolved. When the deployment uses the probe endpoints, the human may adopt the new default by
  deleting the setting with its comment.

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## boot/optional-constructor-binding-empty

Spring Boot 4.1 binds an absent key to an `Optional` constructor parameter (or record component) of a `@ConfigurationProperties` type as `Optional.empty()`, never `null`. Reported: null checks and `requireNonNullElse` on such parameters, and `key: {}` entries in `application*.yml`.

Inspect: the null handling and the configuration files of each profile.

Decide: simplify the null handling, or fix it where an empty value means something else.

Prove: a `@ConfigurationProperties` binding test with the key absent and present.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## boot/micrometer-prometheus-naming

Micrometer's Prometheus export changes with Spring Boot 4: Micrometer 1.16 (Boot 4.0) no longer keeps `:` in meter and tag names, and Micrometer 1.17 (Boot 4.1) rejects meters whose names collide after Prometheus normalisation (`a.b` and `a_b`). Reported on literal names.

Inspect: the dashboards, alerts and recording rules that query the names.

Decide: rename the meters, or add a `PrometheusNamingConvention` that keeps the old names; update the dashboards.

Prove: a scrape test that asserts the exported names.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## boot/resttemplate-deprecations

Spring Boot 4.1 deprecates `RestTemplateBuilder.rootUri(..)` for removal in favour of `baseUri(..)`, which resolves relative paths by RFC 3986: a path that starts with `/` drops the base path. Reported where the root URI has a path (or cannot be resolved), and on `TestRestTemplate.HttpClientOption.ENABLE_COOKIES`.

Inspect: the root URI and every relative path used on templates built from it.

Decide: move to `baseUri(..)` and check that every relative path still gets the base path, or move the client to `RestClient`.

Prove: on the fixture, pin 17 (`RootUriPinTest.relativePaths`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).
