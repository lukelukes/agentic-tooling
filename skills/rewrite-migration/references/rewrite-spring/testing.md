# rewrite-spring: Spring test support

Rules of `ReplaceMockBeanAndSpyBean`, which moves Spring Boot's deprecated `@MockBean` and `@SpyBean` to Spring
Framework's `@MockitoBean` and `@MockitoSpyBean`.

## testing/mock-bean-in-configuration-class

The `@MockBean` (or `@SpyBean`) became `@MockitoBean`, but it is declared in a `@Configuration` or
`@TestConfiguration` class, on a field or on the class itself.
Spring Framework reads bean overrides only from test classes (and their enclosing and super classes), so the mock no
longer replaces the bean: the test runs against the real bean.

- Move the `@MockitoBean` field into the test class (or a common superclass of the tests that imported the
  configuration), and stub it there.
- Or keep a mock bean in the configuration class as a plain `@Bean` method returning `Mockito.mock(Type.class)`.

Check: the test that stubbed the mock passes and asserts the stubbed behaviour.

## testing/mock-bean-type-differs

`@MockBean(SomeType.class)` (or `classes = ..`) on a field named another type than the field's. `@MockitoBean` on a
field mocks the field's type and has no type attribute there, so the Recipe dropped it: the mock now has the field's
type and replaces the bean of that type.

- Declare the field with the type that was mocked, or move the mock to class level with
  `@MockitoBean(types = SomeType.class)` and inject it with `@Autowired`.

Check: the test that uses the mock, and that the bean it replaces is the one the test meant.

## testing/proxy-target-aware-dropped

`@SpyBean(proxyTargetAware = false)` became `@MockitoSpyBean`, which has no such attribute and always spies on the
target behind a Spring proxy. Verifications that relied on spying the proxy itself may now see different calls.

- Check the `verify(..)` calls of the spy; with a proxied bean (`@Transactional`, `@Async`), calls through the proxy
  reach the spied target.

Check: the tests that verify calls on the spy.

Source: [@MockitoBean and @MockitoSpyBean](https://docs.spring.io/spring-framework/reference/testing/annotations/integration-spring/annotation-mockitobean.html).

## testing/mockito-test-execution-listener-removed

Spring Boot 4 removed `MockitoTestExecutionListener`, which initialized the `@Mock`, `@Spy` and `@Captor` fields of
Spring tests, leniently. For a `@SpringBootTest` or test-slice class with such fields that neither uses
`MockitoExtension` nor calls `MockitoAnnotations.openMocks`, the Migration adds
`@ExtendWith(MockitoExtension.class)` and `@MockitoSettings(strictness = Strictness.LENIENT)` with the provenance
comment, and reports a `PRESERVED` row.

- Leave the item unresolved. Removing `@MockitoSettings` makes Mockito strict: unused stubs then fail the test.
  `AdoptMockitoTestExecutionListenerRemoval` will remove both annotations with their comment.

Source: [Spring Boot 4.0 migration guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide).

## testing/testresttemplate-cookie-handling

Spring Boot 4.1's `TestRestTemplate` keeps cookies between requests. A test method that makes two or more requests through one template, reads a `Set-Cookie` or `Cookie` header, or posts a login form is reported. The rule is `review-only`: `spring.http.clients.cookie-handling=disable` would change every Boot HTTP client in the tests, so the Migration writes no setting.

Inspect: whether the test expects the second request to carry (or not carry) the first response's cookies.

Decide: per test: pin `.withCookieHandling(HttpCookieHandling.DISABLE)`, set `ENABLE`, or fix the test's assumption.

Prove: the reported tests pass on the 4.1 Run; on the fixture, pin 16 (`TestRestTemplateCookiePinTest.secondRequestCookie`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## testing/mockito-spy-bean-semantics

`@SpyBean` becomes `@MockitoSpyBean`, which spies on an existing bean of exactly one candidate. Reported where that differs: spies in slice tests (`@WebMvcTest`, `@DataJpaTest`, ...), where the bean may not exist, and spies of an interface with several implementations in the module. `proxyTargetAware` is `testing/proxy-target-aware-dropped`.

Inspect: the test's context (slice or full), and the beans of the spied type.

Decide: use `@MockitoBean` or `@Import` the bean for a slice; name the bean for an ambiguous type.

Prove: the tests pass under `rewrite run verify --level test`; on the fixture, pin 49 (`SpyBeanPinTest.partialMock`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## testing/spring-extension-method-scope

Spring Framework 7's `SpringExtension` scopes test instances per method for `@Nested` classes. Reported: `@Nested` classes of Spring tests that use field injection, and `TestExecutionListener.prepareTestInstance` overrides that read `getTestClass()`.

Inspect: what the nested tests inject and share with the outer class, and what the listener looks up.

Decide: opt out with `@SpringExtensionConfig`, or restructure the test.

Prove: the suite passes under `rewrite run verify --level test`.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## testing/restdocs-restassured-removed

Spring REST Docs 4 removed its REST Assured support. The `spring-restdocs-restassured` dependency and each use of its types are reported and do not compile.

Inspect: the documentation tests and the snippets they produce.

Decide: port the tests to MockMvc, `WebTestClient` or `RestTestClient`, keeping the snippet names.

Prove: the docs build regenerates the same snippet set.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## testing/restdocs-jackson3-snippet-output

Spring REST Docs 4 writes snippets with Jackson 3, so `prettyPrint()` and custom `ContentModifier`s may produce other field orders and indentation.

Inspect: the generated snippets and the documents that include them.

Decide: accept the new ordering, or configure the output.

Prove: regenerate the snippets and diff them.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## testing/junit4-leftover-worklist

The test class is still on JUnit 4 after the Run's JUnit 5 migration (`org.junit.Test`, `@RunWith`, `@Rule`, or a `AbstractJUnit4SpringContextTests` superclass). A JUnit 4 class can stop running without failing the build.

Inspect: whether the class runs under JUnit Platform today (vintage engine) and what kept it on JUnit 4.

Decide: convert it to JUnit Jupiter (parameterized classes and custom rules by hand), or keep it on the vintage engine on purpose.

Prove: the class runs and asserts under `rewrite run verify --level test`; on the fixture, pin 15b (`LegacyBaseClassPinTest`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).
