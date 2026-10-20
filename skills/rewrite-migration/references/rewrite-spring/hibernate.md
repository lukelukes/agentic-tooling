# rewrite-spring: Hibernate

Rules that rewrite-spring's Spring Boot Migration reports about Hibernate. The Hibernate ORM API rules of
rewrite-hibernate are in `../rewrite-hibernate/hibernate.md`.

## hibernate/json-format-mapper

The module maps an attribute to a JSON column (`@JdbcTypeCode(SqlTypes.JSON)`). With Jackson 3 on the class path,
Hibernate 7 would store and read that JSON with Jackson 3. The Migration kept the Jackson 2 artifacts the module
resolved before the Run (row on the build file) and added
`spring.jpa.properties.hibernate.type.json_format_mapper=jackson` with the provenance comment (row on the
configuration file), so the stored JSON keeps its format.

- Leave the items unresolved to keep the stored JSON. Moving the column to Jackson 3 (`jackson3`) needs a check of
  every stored document's format, dates and enums in particular.

Check: an entity written after the Run stores the same JSON text as before, and a row stored before the Run reads back.

Source: [Hibernate ORM 7 user guide](https://docs.jboss.org/hibernate/orm/7.2/userguide/html_single/Hibernate_User_Guide.html).
