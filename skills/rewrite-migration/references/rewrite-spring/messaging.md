# rewrite-spring: messaging

Rules that rewrite-spring's Recipes report about RabbitMQ and Kafka configuration.

## messaging/rabbit-retry-placeholder

Spring Boot 4.0 replaced RabbitMQ `retry.max-attempts` (deliveries) with `retry.max-retries` (retries after the
first delivery), so `max-attempts=N` is `max-retries=N-1`. A literal number is converted. This value is not one (a
placeholder): the key is renamed and the value kept, so the message is delivered once more than before.

- Find where the value is set and subtract one there, or write `max-retries` with the converted value per
  environment. If the source is outside the repository, resolve `deferred` with a note naming the variable.

Check: a listener test that fails every delivery counts the deliveries before the message is rejected.

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## messaging/rabbit-retry-default-kept

Where RabbitMQ retry is enabled and `max-attempts` was never set, Spring Boot 3 delivered a failing message 3 times
and Spring Boot 4.0 delivers it 4 times (`max-retries` defaults to 3). The Migration adds
`spring.rabbitmq.<listener.simple|listener.direct|template>.retry.max-retries=2` with the provenance comment, and
reports a `PRESERVED` row.

- Leave the item unresolved. Adopting the new default deletes the pin together with its comment, and only when the
  human asks.

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## messaging/kafka-backoff-random-dropped

Spring Boot 4.0 replaced `spring.kafka.retry.topic.backoff.random` (a boolean) with
`spring.kafka.retry.topic.backoff.jitter` (a duration). The Migration removes `random`; `random=true` (or a
placeholder) is reported, because the retry topic back off is no longer randomized. The same row marks
`@RetryableTopic(backoff = @Backoff(random = ..))`: spring-kafka 4.0's `@BackOff`, which replaces spring-retry's
`@Backoff` there, has `jitter` instead of `random`, so the attribute is dropped.

- Set `spring.kafka.retry.topic.backoff.jitter` (or `jitter` on `@BackOff`) to a duration that gives the spread the
  team wants (a fraction of `delay`), or resolve `no-change` with a note when exact delays are fine.

Check: the context starts, and the retry topic configuration bean shows the back off with jitter.

Source: [Spring Boot 4.0.0 configuration changelog](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0.0-Configuration-Changelog).

## messaging/rabbit-retry-template-customizer-removed

Spring Boot 4.0 moved `org.springframework.boot.autoconfigure.amqp` to `org.springframework.boot.amqp.autoconfigure`,
but `RabbitRetryTemplateCustomizer` has no type there: Spring AMQP 4 retries without Spring Retry's `RetryTemplate`.
The Recipe keeps the old name and reports the use; the module does not compile on Boot 4.

- A customizer of the template's retries becomes a `RabbitTemplateRetrySettingsCustomizer` bean; one of the listener
  retries becomes a `RabbitListenerRetrySettingsCustomizer` bean. Both receive the retry settings to change.
- Drop customizations that only restated the `spring.rabbitmq.*.retry.*` properties.

Check: a listener test that fails a message and counts the deliveries.

Source: [Spring Boot 4.0 Migration Guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## messaging/kafka-producer-linger-ms

kafka-clients 4.0 raised the producer `linger.ms` default from 0 to 5. For a module with spring-kafka that sets no
`linger.ms`, the Migration adds `spring.kafka.producer.properties.linger.ms=0` with the provenance comment and reports
a `PRESERVED` row. A module that builds a `ProducerFactory` in Java, as a bean of its own or from a configuration map
that is not `KafkaProperties.buildProducerProperties(..)`, gets a `BEHAVIOUR` row instead, because that factory does
not read Spring Boot's producer properties.

- `PRESERVED`: leave the item unresolved; adopt the new default only when the human asks.
- `BEHAVIOUR`: put `ProducerConfig.LINGER_MS_CONFIG, 0` into the factory's configuration map, or resolve as
  `no-change` with a note when 5 ms of batching is acceptable.

Source: [Kafka 4.0 upgrade notes](https://kafka.apache.org/40/documentation.html#upgrade_servers_400_notable).

## messaging/kafka-retry-topic-reuse-default

spring-kafka 4.1 sends retries with the same interval through one retry topic (`SINGLE_TOPIC`); before, each retry
had its own topic. For a module that started below spring-kafka 4.1, the Migration adds
`sameIntervalTopicReuseStrategy = SameIntervalTopicReuseStrategy.MULTIPLE_TOPICS` to a `@RetryableTopic` without one,
and `.sameIntervalTopicReuseStrategy(MULTIPLE_TOPICS)` to a `RetryTopicConfigurationBuilder` chain without one, with
the provenance comment above the annotation or the statement, and reports a `PRESERVED` row.

- Leave the item unresolved. Adopting the new default changes the topics the retries go to: drain the old retry topics
  first, and only when the human asks. `AdoptKafkaRetryTopicReuseDefault` will remove the commented setting.

Source: [spring-kafka 4.1 what's new](https://docs.spring.io/spring-kafka/reference/4.1/whats-new.html).

## messaging/kafka-clients-4-behaviour-defaults

kafka-clients 4 changes producer and consumer behaviour: `linger.ms` defaults to 5 (was 0), more than 5 in-flight requests per connection with idempotence on fails the producer at startup (`BLOCKER`), `describeConsumerGroups` throws `GroupIdNotFoundException` for an unknown group, and the consumer group protocols change. Producers that Spring Boot configures get `linger.ms` through `messaging/kafka-producer-linger-ms` and no row.

Inspect: producer configurations built in Java, `max.in.flight.requests.per.connection`, admin calls and `group.protocol`; the broker version (2.1 or later).

Decide: pin `linger.ms=0` in code where latency matters, lower in-flight requests to 5 or turn idempotence off on purpose, handle `GroupIdNotFoundException`.

Prove: a producer test for a latency-sensitive path, and a startup test.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).
