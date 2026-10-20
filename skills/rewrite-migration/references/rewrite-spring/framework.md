# rewrite-spring: Spring Framework

Rules about `HttpComponentsClientHttpRequestFactory` timeouts, which moved from the request factory to the Apache
HttpClient 5 connection manager.

## framework/connect-timeout-removed

`HttpComponentsClientHttpRequestFactory.setConnectTimeout(..)` was deprecated in Framework 6.2 and removed in 7.0.
`MoveConnectTimeoutToConnectionConfig` migrates a local `PoolingHttpClientConnectionManager` wired into the factory;
every other call is reported and does not compile.

- Find the `HttpClient` the factory wraps, and its connection manager. Set the timeout there:
  `PoolingHttpClientConnectionManagerBuilder.create().setDefaultConnectionConfig(ConnectionConfig.custom()
  .setConnectTimeout(Timeout.ofMilliseconds(ms)).build())`.
- When the client comes from a bean shared with other code, change that bean, and check that the other users want
  the same connect timeout.
- Remove the `setConnectTimeout(..)` call.

Check: the factory's client has the timeout (a test that builds the bean and reads the connection config, or a
connect to an unroutable address that fails within the timeout).

## framework/http-components-read-timeout

`setReadTimeout(..)` on the request factory is moved to `SocketConfig.Builder.setSoTimeout(Timeout)` when the
argument is a literal or a constant and no `setDefaultSocketConfig(..)` is already present. Otherwise the call is kept
and reported: on Framework 7 it may no longer reach the socket.

- Move the value to the socket config of the connection manager, merging it into an existing
  `setDefaultSocketConfig(..)`, or set a response timeout with `RequestConfig.custom().setResponseTimeout(..)` when
  the intent is a per-request limit.
- Resolve as `no-change` with a note when the read timeout is set on purpose elsewhere.

Check: a slow stub response fails within the timeout.

Source: [spring-framework#35748](https://github.com/spring-projects/spring-framework/issues/35748).

## framework/listenablefuture-custom-implementation

The class implements `ListenableFuture`, which Spring Framework 7 removes. A class cannot implement
`CompletableFuture`, so the Recipe leaves the whole file on `ListenableFuture` and reports the class. The same row
marks a `completable()` call on such a class (also Spring's `SettableListenableFuture` and `ListenableFutureTask`):
only `ListenableFuture` itself becomes a `CompletableFuture`, so the Recipe kept the call.

- Return a `CompletableFuture` where the class was returned: `CompletableFuture.completedFuture(value)`, or a future
  completed by the code that completed this one (`future.complete(value)`, `future.completeExceptionally(ex)`).
- Callers that registered callbacks use `whenComplete((result, ex) -> ..)`.
- Then delete the class.

Check: the module compiles, and a test that waits on the future.

## framework/async-result-unresolved

`AsyncResult` is removed in Spring Framework 7. The Recipe turns an `AsyncResult` that is returned or assigned as a
`ListenableFuture` into `CompletableFuture.completedFuture(..)` or `failedFuture(..)`. This one is used otherwise (as a
`Future`, as an `AsyncResult` variable, as an argument), or sits in a file that keeps `ListenableFuture` for a class
that implements it (see `framework/listenablefuture-custom-implementation`), and was kept.

- Use `CompletableFuture.completedFuture(value)` (or `failedFuture(ex)` for `forExecutionException`), and declare the
  `@Async` method to return `CompletableFuture<T>`.

Check: the module compiles, and the caller still reads the value or the exception.

Source: [Spring Framework 7.0 Release Notes](https://github.com/spring-projects/spring-framework/wiki/Spring-Framework-7.0-Release-Notes).

## framework/okhttp-request-factory-removed

Spring Framework 7 removed `OkHttp3ClientHttpRequestFactory` and has no OkHttp request factory. The construction is
kept and does not compile.

- Use `JdkClientHttpRequestFactory`, `HttpComponentsClientHttpRequestFactory` or `JettyClientHttpRequestFactory`, and
  move the OkHttp client's timeouts, proxy and interceptors to the new client.
- When OkHttp itself is needed (for its interceptors), wrap it in a `ClientHttpRequestFactory` of the project's own.

Check: the module compiles, and a test that sends a request through the `RestTemplate` or `RestClient` passes.

## framework/orm-hibernate5-removed-type

Spring Framework 7 removed `org.springframework.orm.hibernate5`. The Migration moves the types that
`org.springframework.orm.jpa.hibernate` keeps (`HibernateTransactionManager`, `LocalSessionFactoryBean`,
`LocalSessionFactoryBuilder`, ...). This import names a type without a counterpart (`HibernateTemplate`,
`HibernateDaoSupport`, `HibernateCallback`, `SessionFactoryUtils`, the `Hibernate*Exception` types), which no longer
compiles.

- Replace `HibernateTemplate` and `HibernateDaoSupport` with the `Session` of the `SessionFactory`
  (`sessionFactory.getCurrentSession()`) or with JPA's `EntityManager`.
- Catch Spring's `DataAccessException` subtypes instead of the Hibernate-specific ones.

Check: the module compiles and its repository tests pass.

## framework/antpathmatcher-deprecated-pathpattern-semantics

Spring MVC keeps the `AntPathMatcher` path matching, which Spring Framework 7 deprecates: `spring.mvc.pathmatch.matching-strategy=ant-path-matcher`, `PathMatchConfigurer.setPathMatcher(..)` or `setUrlPathHelper(..)`. The Migration keeps it (a declined rewrite, `PRESERVED`); the row's setting names the key or call that keeps it.

Inspect: the setting and the controllers' mappings that rely on `AntPathMatcher` (suffixes, `**` in the middle, encoded slashes).

Decide: nothing for the Migration. Switching to `PathPattern` is a separate improvement (`AdoptPathPatternMatching`, specified, not built).

Prove: when adopted: routing tests for an encoded slash, a double slash and matrix variables.

Resolutions: `preserved` (none needed: PRESERVED rows are not open), `adopted` once the improvement is made, `deferred`.

## framework/path-matching-options-removed

Spring Framework 7 removed the trailing slash and suffix pattern options: `setUseTrailingSlashMatch`, `setUseSuffixPatternMatch`, `setUseRegisteredSuffixPatternMatch`, `favorPathExtension`, `ignoreUnknownPathExtensions` and `setMatchOptionalTrailingSeparator`. The calls are kept and do not compile.

Inspect: the argument of each call: a literal `false` is a no-op on 6.x; `true` or a variable turns the option on.

Decide: delete the no-op calls. For `true`: trailing slashes through a `UrlHandlerFilter` (`trailingSlashHandler(..)`, redirect or `wrapRequest`), suffixes through Accept-header content negotiation.

Prove: the module compiles, and a request with a trailing slash and one with a suffix reach the handler as intended; on the fixture, pin 11 (`TrailingSlashPinTest.slashAndSuffix`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## framework/cookie-generator-removed

Spring Framework 7 removed `CookieGenerator` and `CookieThemeResolver`. Each use is reported (a subclass that overrides `createCookie` too) and does not compile.

Inspect: what each generator sets: name, path, max age, domain, `HttpOnly`, `Secure`, and what a `createCookie` override adds.

Decide: write the cookie with `ResponseCookie` (`response.addHeader(HttpHeaders.SET_COOKIE, cookie.toString())`), and decide `SameSite` and `Partitioned`.

Prove: a test of the exact `Set-Cookie` header; on the fixture, pin 7 (`CookieWritePinTest.cookieGeneratorHeader`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## framework/runtime-default-changes-70

Spring Framework 7.0 changes runtime defaults that no compile error shows. Reported per site, with the sub-change in the message: SpEL parsers, JMS destination resolvers, CORS configuration used as it is, `@EnableAsync`, and `MockHttpServletRequest.addHeader(.., null)`. The Framework 7.1 parts (multipart limits, `ProblemDetail.instance`, JAXB) belong to Spring Boot 4.2.

Inspect: the site and the behaviour the application relies on (the CORS response headers, the destinations resolved, the expressions evaluated, the executor of `@Async` methods).

Decide: configure the old behaviour explicitly where it is needed; otherwise resolve as `no-change` with a note.

Prove: a contract test per site.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## framework/hateoas-behaviour-changes

Spring HATEOAS 3 changes the hypermedia it renders. Reported: affordances, `@EnableHypermediaSupport(type = HAL_FORMS)`, and tests that assert on `_templates.default` or the HAL and HAL-FORMS media types.

Inspect: the clients of the hypermedia API and the documents they parse.

Decide: keep the client contract (configure the old rendering) or update the clients.

Prove: contract or snapshot tests of the rendered documents.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## framework/graphql-jackson3-transport

Spring for GraphQL 2 serializes with Jackson 3. Reported in modules with spring-graphql: Jackson 2 mapper beans and customizers, Jackson 2 codecs (for `GraphQlClient`/`GraphQlTester` builders), and a `GraphQlWebSocketHandler` built by hand.

Inspect: the GraphQL responses and the Jackson settings they depend on.

Decide: port the configuration to a `JsonMapperBuilderCustomizer` and Jackson 3 codecs, or keep Jackson 2 on purpose.

Prove: a response snapshot test.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## framework/httpheaders-not-multivaluemap

Spring Framework 7's `HttpHeaders` implements only `Serializable`, not `MultiValueMap`. Reported: `Map` methods called on `HttpHeaders` (`containsKey`, `keySet`, `entrySet`, `values`, `containsValue`) and `HttpHeaders` passed (to a method or constructor), assigned or returned as a `Map`/`MultiValueMap`; they do not compile.

Inspect: each site and what it does with the headers.

Decide: use the `HttpHeaders` API (`containsHeader`, `headerNames`, `headerSet`, `containsHeaderValue`), `toSingleValueMap()`, or the deprecated `asMultiValueMap()`; fix tests that compare headers to maps.

Prove: the module compiles; on the fixture, pin 12 (`HeaderAdapterPinTest.mapStyleUsage`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## framework/message-converter-configuration-api

`WebMvcConfigurer.configureMessageConverters(List)` and `extendMessageConverters(List)` are deprecated in Spring Framework 7 for `HttpMessageConverters.ServerBuilder`. Order, media types and the default set are behaviour; a plain `@Bean HttpMessageConverter<?>` is still picked up.

Inspect: the converters the override adds or removes, their order and media types.

Decide: port the list to the builder, keeping the order, the media types and the choice of defaults.

Prove: an MVC test for each custom media type; on the fixture, pin 26 (`ConverterBeanPinTest.csvConverterBean`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).
