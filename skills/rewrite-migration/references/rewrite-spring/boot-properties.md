# rewrite-spring: Spring Boot properties

Rules that the property Recipes of the Spring Boot 3.5, 4.0 and 4.1 Migrations report. The Migrations keep a
deprecated key that still binds, unchanged, and comment out only keys that no longer bind (with an explanatory
comment above). The anchor of a row is the dotted key.

## boot-properties/dynatrace-v1-deprecated

Spring Boot 4.1 deprecates the Dynatrace V1 keys (`management.dynatrace.metrics.export.v1.*`), but they still bind,
and `v1.device-id` decides whether the V1 or the V2 API is used. The Migration keeps each key unchanged with a
`PRESERVED` row; the `setting` names the kept key and value.

- Leave the item unresolved. Moving to the V2 API (`management.dynatrace.metrics.export.api-token`, `uri`, and the
  metric key prefix) is an Improvement: set `adopted` only when the human asks for it, after moving the keys and
  removing `v1.*`.

Source: [Spring Boot 4.1.0 configuration changelog](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.1.0-Configuration-Changelog).

## boot-properties/livereload-deprecated

Spring Boot 4.1 deprecates the LiveReload keys, but they still bind. `spring.devtools.livereload.enabled=true` is kept
with a `PRESERVED` row: without it LiveReload is off, the default since 4.0. `enabled=false` and `port` are kept
without a row.

- Leave the item unresolved. Removing LiveReload (the key and the browser extension workflow) is an Improvement.

Source: [Spring Boot 4.1.0 configuration changelog](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.1.0-Configuration-Changelog).

## boot-properties/livereload-default-off

Spring Boot 4.0 changed the default of `spring.devtools.livereload.enabled` from `true` to `false`. The rule is
`review-only` (development tooling): in a module that declares `spring-boot-devtools` and sets the key in no
`application*` file, the Migration writes nothing and reports a `BEHAVIOUR` row whose message names
`spring.devtools.livereload.enabled=true`.

- Ask whether the team uses LiveReload. If it does, add `spring.devtools.livereload.enabled=true` to the module's
  development profile (or `application.properties` when there is none) and resolve `fixed`; otherwise resolve
  `no-change` with a note.

Check: none; DevTools is inactive in the packaged application.

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## boot-properties/template-engine-disabled-lost

Spring Boot 4.0 no longer reads `spring.{freemarker,groovy.template,mustache,thymeleaf}.enabled`; the Migration
comments the key out. An explicit `enabled=false` meant "the starter is on the class path, but do not auto-configure
the engine": on 4.0 the engine is auto-configured again.

- Replace the starter (`spring-boot-starter-thymeleaf` and so on) with the template library itself
  (`org.thymeleaf:thymeleaf-spring6` and so on) in that module, and keep any manual engine configuration. If nothing
  uses the engine, remove the starter instead.

Check: the context starts, and a test that rendered a view by hand still does; no template view resolver bean is
created (`ApplicationContextRunner` or the context test asserting the bean is absent).

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## boot-properties/removed-registry

Spring Boot 4.0 removed the Wavefront and SignalFx metrics support. The Migration comments out every
`management.wavefront.*`, `management.metrics.export.signalfx.*` and `management.signalfx.metrics.export.*` key and
reports one row per file and registry; the metrics stop being exported.

- Ask which backend replaces the registry (OTLP is the usual one: `micrometer-registry-otlp` and
  `management.otlp.metrics.export.*`), add it, and move the endpoint, token and step settings. Without a decision,
  resolve `deferred` with a note naming the lost registry.

Check: the context starts with the new registry, and a `MeterRegistry` bean of the new type exists.

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## boot-properties/neo4j-pool-metrics-enabled

Spring Boot 4.0 removed `spring.neo4j.pool.metrics-enabled`. The Migration turns `=false` into
`management.metrics.enable.neo4j=false` without a row. `=true` has no stated equivalent: the key is commented out and
reported.

- Driver pool metrics follow `management.metrics.enable.neo4j` (on by default). Confirm that the Neo4j pool meters
  are still wanted; if so, resolve `no-change` with a note. If the team relied on them being on only for some
  profiles, set `management.metrics.enable.neo4j` per profile.

Check: with a Neo4j test container, the `neo4j.driver.connections.*` meters are present in the `MeterRegistry`.

Source: [Spring Boot 4.0.0 configuration changelog](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0.0-Configuration-Changelog).

## boot-properties/pushgateway-url-unparsed

Spring Boot 3.5 replaced the Prometheus Pushgateway `base-url` (a URL) with `address` (`host:port`) and `scheme`. A
plain `http`/`https` URL is converted exactly. This value is not one (a placeholder, a path, user info): the key is
left in place, and it no longer binds.

- Work out what the value resolves to in each environment. Set
  `management.prometheus.metrics.export.pushgateway.address` to `host:port` and `scheme` to `https` where the URL
  was `https`; a path prefix has no property and needs a `PushGatewayManager` customization. Remove `base-url`.

Check: the context starts with `management.prometheus.metrics.export.pushgateway.enabled=true` against a test
Pushgateway, or the bound `PrometheusProperties` show the address.

Source: [Spring Boot 3.5 release notes](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.5-Release-Notes).
