# rewrite-hibernate: Hibernate ORM and Validator

Rules of the Hibernate 7 step (`MigrateToHibernate70`) and of the Hibernate Validator 9 step that a Boot 4 Migration
runs. Hibernate 7 removed the legacy `Session` methods `save`, `delete`, `update` and `saveOrUpdate`; the JPA methods
that replace them treat detached entities differently.

## hibernate/save-result-used

`session.save(entity)` returned the generated identifier, and the code uses it. `persist(..)` returns nothing, so the
Recipe left the call; the module does not compile on Hibernate 7.

- Call `session.persist(entity)`, then read the identifier from the entity (`entity.getId()`); call
  `session.flush()` first when the identifier is generated on insert (`IDENTITY`).
- When the entity may be detached, use `T managed = session.merge(entity)` and read the identifier from `managed`.

Check: the code that used the identifier, against a database.

Prove: fixture pin 28b, `HibernateSessionHandoffPinTest.saveReturnsId` (the used result).

## hibernate/persist-maybe-detached

`session.save(entity)` became `session.persist(entity)`. `save` inserted a new row for a detached entity (one with an
identifier from an earlier session); `persist` throws `EntityExistsException` or `PersistentObjectException` for it.
The Recipe could not show that the entity is new (created with `new` in the same method).

- When the entity can be detached, use `session.merge(entity)` and keep using the returned instance.
- When it is always new, resolve as `no-change` with a note naming where it is created.

Check: the path that calls this method with an entity loaded in an earlier transaction, if there is one.

Prove: a repository test that passes a detached instance through the converted call; fixture pin 28a covers the statement-position `save`.

## hibernate/remove-maybe-detached

`session.delete(entity)` became `session.remove(entity)`. `delete` reattached a detached entity; `remove` throws
`IllegalArgumentException` for it. The Recipe could not show that the entity was loaded in the same method.

- Remove a managed instance: `session.remove(session.contains(entity) ? entity : session.merge(entity))`, or load it
  by id first (`session.find(Type.class, id)`).

Check: a test that deletes an entity loaded in an earlier transaction.

Prove: fixture pin 28b, `HibernateSessionHandoffPinTest.deleteDetached`.

## hibernate/delete-entity-name

`session.delete(entityName, entity)` became `session.remove(entity)`: Hibernate 7 has no `remove` with an entity name,
so the entity's class decides the mapping. This only differs for a class mapped under several entity names (dynamic
models, `entity-name` mappings).

- Resolve as `no-change` when the class has one mapping.
- Otherwise remove through the mapping you need, for example by loading the instance with
  `session.find(entityName, id)` first.

Check: the delete removes the row from the table the entity name mapped to.

Prove: a repository test for the entity.

## hibernate/update-removed

`session.update(entity)` was removed in Hibernate 7. `merge(entity)` is the replacement, but it returns a managed copy
and leaves the argument detached, so code that keeps using the argument after the call changes behaviour. The Recipe
left the call; the module does not compile.

- Replace it with `entity = session.merge(entity)` (or use the returned instance from then on).
- When the entity is already managed in this session, delete the call: changes are flushed anyway.

Check: a test that updates a detached entity and reads it back.

Prove: fixture pin 28b, `HibernateSessionHandoffPinTest.updateDetached`.

## hibernate/save-or-update-removed

`session.saveOrUpdate(entity)` was removed in Hibernate 7. The Recipe left the call; the module does not compile.

- For an entity that may be new or detached, use `entity = session.merge(entity)`.
- For an entity that is always new, use `session.persist(entity)`.

Check: tests for a new and for a detached entity.

Prove: fixture pin 28b, `HibernateSessionHandoffPinTest.saveOrUpdateNewAndDetached`.

## hibernate/not-empty-on-container

`@NotEmpty` sits on a container that Hibernate Validator unwraps (`Optional<T>` of a type without emptiness, a raw
`Optional`, `OptionalInt`, `OptionalLong`, `OptionalDouble`, `ObservableValue`). There is no empty value to check, so
Hibernate Validator 9 rejects the constraint when it validates; `@NotNull` would constrain something else, so the
Recipe left it. `@NotEmpty` on an `Optional` of a string, collection, map or array stays without a row: it constrains
the value.

- Delete the annotation when the intent was "present": an `Optional` field is better replaced by a nullable value with
  `@NotNull`.
- Put a constraint that fits the value instead (`@NotNull` on the element type, `@Positive` for a number).

Check: a validation test of the class, with the container empty and filled.

Source: [Hibernate ORM 7.0 Migration Guide](https://docs.jboss.org/hibernate/orm/7.0/migration-guide/migration-guide.html),
[Hibernate Validator built-in constraints](https://docs.jboss.org/hibernate/validator/9.0/reference/en-US/html_single/#section-builtin-constraints).

## hibernate/removed-annotations

Hibernate 7 removed `org.hibernate.annotations` types that no rewrite-hibernate recipe rewrites: `@Where`, `@WhereJoinTable`, `@Loader`, `@Persister`, `@Proxy`, `@SelectBeforeUpdate`, `@Polymorphism`, `@LazyToOne` and more (the generated table of `FindRemovedHibernateAnnotations`). Each use, import included, is reported and does not compile. The message names the replacement where Hibernate 7 has one (`@Where` -> `@SQLRestriction`, `@WhereJoinTable` -> `@SQLJoinTableRestriction`).

Inspect: each use and the SQL or behaviour it adds.

Decide: port each use to the replacement, or remove it where Hibernate 7 has no equivalent; keep the restriction SQL unchanged.

Prove: the module compiles, and a repository test shows the restricted rows are still filtered; on the fixture, pin 29 (`HibernateAnnotationsPinTest`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).
