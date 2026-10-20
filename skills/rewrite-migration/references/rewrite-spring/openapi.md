# rewrite-spring: OpenAPI (Springfox to SpringDoc)

`org.openrewrite.java.springdoc.SpringFoxToSpringDoc` replaces the dependencies, annotations, `ApiInfo` and
security configuration. Springfox code it leaves behind is reported, then `CleanupRemainingSpringfox` runs.
Springfox does not work on Boot 3 or later, so these rules are `BLOCKER`.

## openapi/springfox-docket-manual

A `Docket` too complex to migrate. Replace each `Docket` bean with a `GroupedOpenApi` bean:

- `groupName(..)` → `GroupedOpenApi.builder().group(..)`;
- `.select().apis(RequestHandlerSelectors.basePackage(..))` → `.packagesToScan(..)`;
- `.paths(PathSelectors.ant(..)|regex(..))` → `.pathsToMatch(..)`;
- global parameters, response messages and security contexts → an `OpenApiCustomizer` or
  `OperationCustomizer` on the group, or `@SecurityRequirement` on the operations;
- `ApiInfo` already became an `OpenAPI` bean; check that the group does not need its own.

Check: the application starts and `/v3/api-docs/<group>` lists the same paths as the Springfox group did.

## openapi/springfox-json-types

`springfox.documentation.spring.web.json.Json` and `JsonSerializer` are Springfox internals with no SpringDoc
equivalent. Code that wraps or serializes them (custom `HttpMessageConverter`s for Swagger JSON, Gson adapters) is
usually only there for Springfox.

- Remove that code when its only purpose was Springfox output.
- When the application still needs the JSON, serialize with the application's Jackson mapper directly.

Check: `/v3/api-docs` returns JSON (a context test with `MockMvc`).

Source: [Migrating from Springfox](https://springdoc.org/migrating-from-springfox.html).
