# rewrite-spring: data and batch

## data/default-batch-configurer-removed

Spring Batch 5 removed `DefaultBatchConfigurer`. The Recipe drops the superclass and the methods that only returned
defaults; a method with a body of its own stays, no longer overriding anything, and is reported.

- `getTransactionManager()`, `getJobRepository()`, `getJobLauncher()`, `getJobExplorer()`: make the method a `@Bean`
  of that type, or move the setting into `@EnableBatchProcessing` attributes
  (`transactionManagerRef`, `dataSourceRef`, `isolationLevelForCreate`, `tablePrefix`), or extend
  `DefaultBatchConfiguration` and override the matching method.
- `setDataSource(..)`: Batch now takes the `DataSource` bean (or `dataSourceRef`); remove the method once that holds.
- Remove a method that is now dead, and resolve the key `fixed`.

Check: the batch context starts (the existing `@SpringBatchTest` or a context test) and one job runs against the
test database.

Source: [Spring Batch 5.0 migration guide](https://github.com/spring-projects/spring-batch/wiki/Spring-Batch-5.0-Migration-Guide).

## data/lettuce-adaptive-refresh-forced

Spring Boot 4.1 removed `spring.data.redis.lettuce.cluster.refresh.adaptive`, and Lettuce 7.5 enables all adaptive
cluster topology refresh triggers. The row is for an explicit `adaptive=false` (commented out) and for a module that
sets `spring.data.redis.cluster.nodes` without the key (adaptive refresh was off by default before).

- If the extra refreshes are acceptable, resolve `no-change` with a note.
- To keep them off, declare a `LettuceClientConfigurationBuilderCustomizer` bean that sets `ClusterClientOptions`
  with a `ClusterTopologyRefreshOptions` without adaptive triggers (keep the periodic refresh the application had).

Check: the context starts against a Redis cluster test container, and the client options show the intended refresh
triggers.

Source: [Spring Boot 4.1.0 configuration changelog](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.1.0-Configuration-Changelog).

## data/session-store-mongo-removed

Spring Boot 4.0 no longer auto-configures the MongoDB Spring Session store, so `spring.session.mongodb.*` binds to
nothing and no property replaces it. The Migration leaves the keys and `@Value` uses in place and reports each.

- If sessions must stay in MongoDB, add `@EnableMongoHttpSession` (spring-session-data-mongodb) with the collection
  name and timeout the keys held, then remove the keys. Otherwise move to a supported store
  (`spring-session-data-redis` or JDBC) with the team.

Check: an integration test that creates a session and reads it back from the store.

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## data/session-store-hazelcast-removed

Spring Boot 4.0 no longer auto-configures the Hazelcast Spring Session store, so `spring.session.hazelcast.*`
(`flush-mode`, `map-name`, `save-mode`) binds to nothing. The keys and `@Value` uses are left in place and reported.

- If sessions must stay in Hazelcast, add `@EnableHazelcastHttpSession` (spring-session-hazelcast) with the map name,
  flush mode and save mode the keys held, then remove the keys. Otherwise move to a supported store with the team.

Check: an integration test that creates a session and reads it back from Hazelcast.

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## data/batch-chunk-fault-tolerant

Spring Batch 6.0 deprecates `StepBuilder.chunk(int, PlatformTransactionManager)` for the chunk-oriented model
(`ChunkOrientedStepBuilder`), which skips and retries differently. The Migration keeps the deprecated call on every
chunk step and rewrites none of them; this row marks a fault-tolerant chain (`.faultTolerant()`), anchored on the
enclosing method. A step built over several statements counts when the builder is kept in a local variable and the
later calls on it are in the same block; a builder passed to another method is not followed, so such a step has no
row. The `setting` names the kept call.

- Leave the item unresolved: the deprecated call works on Batch 6. Moving to the chunk-oriented model is an
  Improvement (`AdoptChunkOrientedStepBuilder`): set `adopted` only when the human asks for it, after checking skip
  and retry counts, listener order and restart with the team.

Check: a job test that drives a skip and a retry still sees the same counts in the `StepExecution`.

Prove: fixture pin 34, `BatchFaultTolerantChunkPinTest.skipAndRetryCounts` (the kept chain keeps the counts).

Source: [Spring Batch 6.0 migration guide](https://github.com/spring-projects/spring-batch/wiki/Spring-Batch-6.0-Migration-Guide).

## data/batch-chunk-task-executor

As `data/batch-chunk-fault-tolerant`, for a chunk step with a `taskExecutor(..)`: the chunk-oriented model of Spring
Batch 6 runs it concurrently in a different way, so the step keeps `chunk(int, PlatformTransactionManager)`. The
`setting` names the kept call.

- Leave the item unresolved. Moving to the chunk-oriented model is an Improvement, as above; it also needs a decision
  on the step's thread safety and its restart.

Check: the job test runs the step with the executor, and the write count and the step status are unchanged.

Prove: a step test with the executor that compares the read, write and commit counts with Spring Batch 5.

Source: [Spring Batch 6.0 migration guide](https://github.com/spring-projects/spring-batch/wiki/Spring-Batch-6.0-Migration-Guide).

## data/mongo-uuid-representation

Spring Boot 3 configured MongoDB with the `java-legacy` UUID representation; Spring Boot 4 leaves it `unspecified`,
so reading or writing a `UUID` fails until a representation is set. For a module that uses Spring Data MongoDB and
sets neither `spring.mongodb.representation.uuid` nor the old `spring.data.mongodb.uuid-representation`, the
Migration adds `spring.mongodb.representation.uuid=java-legacy` with the provenance comment and reports a
`PRESERVED` row.

- Leave the item unresolved. Existing documents store UUIDs in the legacy format; adopting `standard` needs a data
  migration, and only when the human asks.

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## data/mongo-bigdecimal-representation

Spring Data MongoDB 4 stored `BigDecimal` and `BigInteger` as strings; Spring Data MongoDB 5 leaves the
representation `unspecified`. For a module with a `@Document` type that has such a field, the Migration adds
`spring.data.mongodb.representation.big-decimal=string` with the provenance comment and reports a `PRESERVED` row.

- Leave the item unresolved. Adopting `decimal128` changes how new documents store the values and how queries compare
  them, and needs a data migration.

Source: [Spring Data MongoDB 5.0 release notes](https://github.com/spring-projects/spring-data-mongodb/wiki/Spring-Data-MongoDB-5.0-Release-Notes).

## data/batch-jobparameters-format-restart

The module keeps its Spring Batch job repository in a database (a JDBC driver, a JDBC, Data JPA or jOOQ starter, or `spring.datasource.*`/`spring.batch.jdbc.*`). Spring Batch 6 cannot restart the FAILED, STOPPED or UNKNOWN executions that Spring Batch 5 left there. One row per module, on its build file.

Inspect: the `BATCH_JOB_EXECUTION` rows of the production databases that are not COMPLETED or ABANDONED, and who runs the jobs.

Decide: an operational plan with whoever runs the jobs: complete or abandon the executions before the cutover. Record it as `deferred` (with the owner) or `no-change` (nothing left to restart).

Prove: on the fixture, pin 33 (`BatchRestartPinTest.restartResumesFromCheckpoint`).

Resolutions: `deferred` (note the owner), `no-change` (note why), `fixed`.

## data/batch-incrementer-extra-parameters

A job with an `incrementer(..)`, in a module whose launchers (`JobLauncher.run`, `JobOperator.start*`) pass parameters built with `JobParametersBuilder`. Spring Batch 6 changes how a job with an incrementer combines its next parameters with the ones a launcher passes.

Inspect: each launcher of the job and the parameters it adds.

Decide: fix the launchers that relied on their extra parameters, or drop the incrementer.

Prove: on the fixture, pin 33 (the incrementer with extra parameters).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## data/batch-schema-sequence-rename

Spring Batch 6 renames the `BATCH_JOB_SEQ` sequence to `BATCH_JOB_INSTANCE_SEQ`. Reported on each SQL, Flyway or Liquibase file that names `BATCH_JOB_SEQ`; without one, on the build file of a module whose schema Spring Batch does not create (`spring.batch.jdbc.initialize-schema` other than `always`).

Inspect: who owns the schema, and the vendor migration scripts in `spring-batch-core` (`org/springframework/batch/core/migration/6.0/`); DB2 LUW differs.

Decide: add the vendor migration as the next changeset, or hand it to the schema owners.

Prove: on the fixture, pin 32 (`BatchJdbcRepositoryPinTest.metadataPersisted`) still passes after the agent loop.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## data/jpa-deferred-bootstrap-executor

`spring.data.jpa.repositories.bootstrap-mode=deferred` in a module without an `AsyncTaskExecutor` bean: Spring Boot 4.1 no longer bootstraps the repositories on a default executor.

Inspect: the startup path and the executors the application defines.

Decide: define an `AsyncTaskExecutor` bean for the bootstrap, or switch the bootstrap mode.

Prove: a context-start test (`rewrite run verify --level test`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## data/h2-2x-file-format-and-sql-behaviour

Spring Boot 4 manages H2 2.4. Reported in modules on H2 2.3: committed `*.mv.db` files, file-based URLs (`jdbc:h2:file:`, `jdbc:h2:~`, `jdbc:h2:./`), compatibility modes (`MODE=`) and `FullTextLucene`.

Inspect: how the database files are made, and the SQL that relies on a compatibility mode.

Decide: regenerate file fixtures from scripts with H2 2.4; fix SQL that relied on the old mode quirks.

Prove: the repository tests pass on H2 2.4.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## data/mssql-jdbc-13-vector-and-metadata

Spring Boot 4 manages mssql-jdbc 13. Reported in modules on mssql-jdbc 12: `VECTOR` SQL, `useBulkCopyForBatchInsert`, `DatabaseMetaData.getProcedures`/`getFunctions`, and multi-statement result loops (`getUpdateCount`, `getMoreResults`).

Inspect: the SQL and the code that reads the results.

Decide: adopt the native vector type, or set `vectorTypeSupport=off` on the connection; fix the result handling.

Prove: the repository tests pass on mssql-jdbc 13.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## data/persisted-type-ids-vs-recipe-relocations

A field is typed with a Spring type that this Run relocates, in a class whose instances may be stored by type name: a `Serializable` class, a class with `@JsonTypeInfo`, or a `@KafkaListener`/`@RabbitListener` payload. Stored data then names a class that no longer exists.

Inspect: where instances of the class are stored (sessions, caches, messages) and how long they live.

Decide: alias the old type id (`spring.json.type.mapping`, `setIdClassMapping`), drain the stored data, or migrate it.

Prove: on the fixture, pin 39 (golden `@class` read-back).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## data/data-jpa-specification-nullability

Spring Data JPA 4 makes `Specification` non-null. Reported: `Specification.where`, `and` and `or` with a `null` argument (ambiguous, `BLOCKER`), `return null` in methods that return a `Specification`, and `JpaSpecificationExecutor.delete(Specification)` (`BLOCKER`).

Inspect: how each specification is composed and what a `null` meant (no restriction).

Decide: use `Specification.unrestricted()` where the specification is only and-composed; restructure the null handling under `or()`, which `unrestricted()` widens to everything.

Prove: a repository test for each filter combination; on the fixture, pin 31 (`SpecificationPinTest.whereNull`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).
