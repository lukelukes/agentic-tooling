# rewrite-spring: Spring Security

Rules of the Spring Security 5.x to 6 and 7 steps that a Boot 4 Migration runs on older code. Read the resolved
Spring Security version first; the configuration DSL differs between 6.x and 7.x.

## security/web-security-configurer-adapter-conflict

`WebSecurityConfigurerAdapter` was removed. The Recipe turns its `configure(..)` overrides into `SecurityFilterChain`,
`WebSecurityCustomizer` and `InMemoryUserDetailsManager` beans. When a method cannot be moved (overrides of
`authenticationManagerBean()` or `userDetailsServiceBean()`, or a `configure(AuthenticationManagerBuilder)` that is
not plain in-memory users), the class keeps extending the adapter and this row names the method. The class does not
compile on Security 6.

- Expose the `AuthenticationManager` as a bean from `AuthenticationConfiguration.getAuthenticationManager()`, or build
  one from the `AuthenticationProvider`s the method configured.
- Turn a `configure(AuthenticationManagerBuilder)` with JDBC, LDAP or a custom `UserDetailsService` into the
  matching bean (`JdbcUserDetailsManager`, an `AuthenticationProvider`, the `UserDetailsService` itself).
- Then drop `extends WebSecurityConfigurerAdapter`, and keep the filter chain the Recipe produced.

Check: the security tests that already exist (`@WithMockUser`, `MockMvc` with `httpBasic()`/`formLogin()`), and one
request that must be rejected.

## security/user-details-expression-unrecognized

In an in-memory `configure(AuthenticationManagerBuilder)`, the Recipe found a user whose expression it could not
read (not a chain of `withUser(..).password(..).roles(..)`). The generated `InMemoryUserDetailsManager` lacks that
user, so the application compiles but the user cannot log in.

- Add the user to the generated bean with `User.withUsername(..).password(..).roles(..).build()`, keeping its
  password encoding (`{noop}`, `{bcrypt}`, a `PasswordEncoder` bean) and its roles or authorities.

Check: a test that authenticates as that user.

## security/access-decision-manager-removed

`authorizeRequests()` became `authorizeHttpRequests()`, which has no `accessDecisionManager(..)`. The Recipe
removes the call from the chain and reports it, so the voters it carried no longer run.

- Re-express each voter as an `AuthorizationManager<RequestAuthorizationContext>` and attach it with
  `.access(manager)` after the request matchers it guarded, or with `.anyRequest().access(manager)`.
- `AuthorizationManagers.allOf(..)` and `anyOf(..)` replace `UnanimousBased` and `AffirmativeBased`.

Check: one request each voter allowed and one it denied.

Source: [Authorize HttpServletRequests](https://docs.spring.io/spring-security/reference/servlet/authorization/authorize-http-requests.html).

## security/regex-matchers-not-rewritten

`regexMatchers(..)` was removed in Spring Security 6, and `requestMatchers(String...)` reads Ant or MVC patterns, not
regular expressions. The Recipe turns each pattern into `RegexRequestMatcher.regexMatcher([method,] pattern)`. It
leaves a call it cannot see the patterns of: an array of patterns, or an HTTP method without patterns. That call does
not compile on Security 6.

- For an array, pass one `RegexRequestMatcher.regexMatcher(..)` per element, for example
  `requestMatchers(Arrays.stream(patterns).map(RegexRequestMatcher::regexMatcher).toArray(RequestMatcher[]::new))`.
- `regexMatchers(HttpMethod.X)` without patterns matched nothing in 5.x; delete the rule, or write the matcher it was
  meant to be.

Check: a request that matches one of the regular expressions and one that only an Ant reading would match.

## security/expression-needs-wiring

`access("expr")` became `access(new WebExpressionAuthorizationManager("expr"))`. That manager evaluates the
expression with a default handler that has no bean resolver and no permission evaluator, so `@bean.method(..)`
references and `hasPermission(..)` fail or deny at runtime. A non-literal expression gets this row too, since its
content is unknown.

- Build the manager with the application's handler:
  `WebExpressionAuthorizationManager.withExpressionHandler(handler).build("expr")`, where `handler` is a
  `DefaultHttpSecurityExpressionHandler` with `setApplicationContext(context)` (and the `PermissionEvaluator` the
  application defines).
- Or replace the expression with an `AuthorizationManager` that calls the bean directly:
  `.access((authentication, context) -> new AuthorizationDecision(tenantAuthz.check(authentication.get(), context.getRequest())))`.

Check: one request the expression allows and one it denies.

## security/dispatcher-types-authorized

The `authorizeRequests()` chain became `authorizeHttpRequests()`. The new filter authorizes every dispatcher type
(FORWARD, INCLUDE, ERROR, ASYNC), where the old one checked only REQUEST, so an error page or a forwarded view can
now be denied. Spring Security 7 has no switch back.

- Add `.dispatcherTypeMatchers(DispatcherType.FORWARD, DispatcherType.ERROR).permitAll()` at the start of the chain
  when error pages or forwards must stay open.
- Resolve as `no-change` when the application has no forwards and its error pages need the same authorization.

Check: a request that fails with an error page as an anonymous user, and one that renders a view through a forward.

## security/authorization-decision-used

`AuthorizationManager.check(..)` became `authorize(..)`, which returns an `AuthorizationResult` in Spring Security 7
(`Mono<AuthorizationResult>` for the reactive manager). The Recipe retypes a local that is only asked `isGranted()`,
and casts what a converted reactive override returns (`.cast(AuthorizationResult.class)`); this row marks a use it
could not retype: a return from a method declared to return `AuthorizationDecision`, an argument, a field initializer,
a `var` passed on as a decision, a chained reactive operator, or a call on a subclass method.

- Use `AuthorizationResult` where only `isGranted()` is read, including method return types and `Mono` type
  arguments (`AuthorizationDecision::isGranted` becomes `AuthorizationResult::isGranted`).
- Where the code needs an `AuthorizationDecision` subclass (`AuthorityAuthorizationDecision`), check the type with
  `instanceof` before casting.

Check: the module compiles, and one request the manager allows and one it denies.

## security/check-and-authorize-differ

The class overrides both `check(..)` and `authorize(..)`, and the two may decide differently. The Recipe left `check`,
which no longer exists on Spring Security 7, so the class does not compile. Which one decides today depends on the
manager:

- `AuthorizationManager` (servlet): since Spring Security 6.4, `AuthorizationFilter` and the method-security
  interceptors call `authorize(..)`; only code that calls `check(..)` directly reaches it. Keep the `authorize` logic
  (the Recipe widened its parameter to `Supplier<? extends Authentication>`, as Spring Security 7 declares it). If a
  direct caller (renamed to `authorize` by the Recipe) relied on the `check` decision, move that decision to the
  caller, or merge it into `authorize` only after confirming that the filters should apply it too.
- `ReactiveAuthorizationManager`: on 6.5, `AuthorizationWebFilter` calls `verify(..)`, whose default still calls
  `check(..)`, while reactive method security calls `authorize(..)`. A manager used in `authorizeExchange` has been
  deciding with `check`: move that logic into `authorize(Mono<Authentication>, T)`. A manager used for method security
  keeps its `authorize` logic. When it serves both, decide per path with the tests that cover each.
- Then delete `check`.

Check: the requests (or methods) the manager guards, for an allowed and a denied case, and each direct caller.

## security/xss-header-default-changed

`xssProtectionEnabled(true)` was dropped from the headers DSL (Spring Security 6 has no such method). The header is
still sent, but Spring Security 6 sends `X-XSS-Protection: 0` where 5.x sent `1; mode=block`. This is a `review-only`
rule: the new value follows current browser guidance (the XSS auditor is gone, and `1; mode=block` caused
information leaks), so the Migration takes it.

- Keep the new header unless something depends on the old value.
- To restore the old value, add `.headerValue(XXssProtectionHeaderWriter.HeaderValue.ENABLED_MODE_BLOCK)` to
  `xssProtection(..)`.

Check: the `X-XSS-Protection` header of one response.

## security/xss-enabled-non-literal

`xssProtectionEnabled(..)` with a non-literal argument was kept in the lambda DSL. Spring Security 6 removed the method,
so the module does not compile.

- When the argument can be false, replace the call with a branch: `xss.disable()` when it is false, and nothing when
  it is true.
- When it is always true, delete the call (the header is on by default; see `security/xss-header-default-changed`).

Check: the `X-XSS-Protection` header for each value of the argument.

Source: [Spring Security 6 migration](https://docs.spring.io/spring-security/reference/6.0/migration/index.html),
[Spring Security 7 migration](https://docs.spring.io/spring-security/reference/7.0/migration/index.html).

## security/lazy-csrf-token-repository-removed

Spring Security 7 removed `LazyCsrfTokenRepository`: CSRF tokens are deferred by default. The construction is kept
and does not compile.

- Pass the wrapped repository to `csrf(csrf -> csrf.csrfTokenRepository(..))` directly.
- When the application read the token eagerly through the lazy wrapper, set a `CsrfTokenRequestAttributeHandler`
  as Spring Security's migration guide shows.

Check: the module compiles, and a test that posts a form with the CSRF token passes.

## security/csrf-cookie-setter-not-merged

Spring Security 7 removed the cookie setters of `CookieCsrfTokenRepository` (`setCookieHttpOnly`, `setCookieDomain`,
`setCookieMaxAge`, `setSecure`). The Migration merges the setters called on one repository into one
`setCookieCustomizer(cookie -> ...)` call, except where the same block already calls `setCookieCustomizer` on that
repository: a merged customizer would replace the existing one. Those setters are kept and do not compile.

- Move each reported attribute into the existing customizer: `setCookieHttpOnly(x)` becomes `.httpOnly(x)`,
  `setCookieDomain(d)` `.domain(d)`, `setCookieMaxAge(s)` `.maxAge(s)` and `setSecure(b)` `.secure(b)` on the
  customizer's `ResponseCookie.ResponseCookieBuilder`, then delete the setter call.
- `setCookiePath` still exists in Spring Security 7 and is not reported.

Check: the module compiles, and the CSRF cookie of a response still carries the attributes (a test that reads the
`Set-Cookie` header).

## security/request-matcher-string-semantics

Spring Security 7 matches the string patterns of `requestMatchers(..)`, `securityMatcher(..)` and `ignoringRequestMatchers(..)` with Spring Framework's `PathPattern` instead of `AntPathMatcher`. The Migration reports each pattern that is not a literal (UNKNOWN), and each literal that `PathPattern` rejects (REJECTED, `BLOCKER`: startup fails) or matches differently (DIFFERENT; the message names a request path that only one matcher matches). It also reports the literal patterns of the removed `AntPathRequestMatcher` and `MvcRequestMatcher` that are REJECTED or DIFFERENT. A pattern that matches the same paths has no row.

Inspect: the anchor (the literal, or the expression) and the chain around it; for a non-literal, every value it can take. `PathPattern` allows `**` and `{*name}` only at the start or end, keeps empty segments (`//`) and compares segments after decoding; requests with `//`, `%2F`, `;` or `..` are rejected by the firewall first.

Decide: rewrite the pattern for `PathPattern` (`/files/*/download` or two rules for `/files/**/download`), fall back to `RegexRequestMatcher` where no `PathPattern` expresses it, or accept the new match set.

Prove: a MockMvc security test per rule with allowed and denied paths, including the trailing slash, upper case, an encoded slash and a suffix; on the fixture, pin 1 (`SecurityAccessTablePinTest.accessMatrix`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## security/request-matcher-servlet-path

The module uses string request matchers (or the removed `AntPathRequestMatcher`/`MvcRequestMatcher`) and sets `spring.mvc.servlet.path` to something other than `/`, or registers its own dispatcher servlet. Spring Security 7's `PathPatternRequestMatcher` does not add the servlet path, so the patterns no longer match the requests they matched (one row per module, on the property or the bean method).

Inspect: the servlet path, the servlets the application registers, and each filter chain's matchers.

Decide: build the matchers with `PathPatternRequestMatcher.withDefaults().basePath("/app")` (one builder per servlet), or split the filter chain per servlet.

Prove: a MockMvc security test under the servlet path (allowed and denied); on the fixture, pin 1 (the `MvcRequestMatcher` rules with `spring.mvc.servlet.path=/app`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## security/antpath-mvc-request-matcher-removed

Spring Security 7 removed `AntPathRequestMatcher` and `MvcRequestMatcher` (and its `Builder`). No recipe rewrites them in v1; each use is reported and does not compile. The message gives the classifier's verdict on the pattern.

Inspect: each construction, `antMatcher(..)` and `Builder.pattern(..)` call, its HTTP method and, for an `MvcRequestMatcher.Builder`, its `servletPath(..)`.

Decide: port each site to `PathPatternRequestMatcher.withDefaults().matcher([method,] pattern)` (`basePath(..)` for the servlet path); for a REJECTED or DIFFERENT pattern decide as for `security/request-matcher-string-semantics`.

Prove: the module compiles (`rewrite run verify --level compile`) and the security tests of `security/request-matcher-string-semantics` pass; on the fixture, pin 1.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## security/oauth2-password-grant-removed

Spring Security 7 removed the OAuth2 password grant: its client provider, request and token response clients, `OAuth2AuthorizedClientProviderBuilder.password()`, `AuthorizationGrantType.PASSWORD`, and `authorization-grant-type=password` registrations.

Inspect: which clients use the grant and what the identity provider offers.

Decide: pick a replacement flow together with the identity provider (authorization code, client credentials, token exchange).

Prove: a login-flow integration test.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## security/websocket-message-security

Spring Security 7 removed `AbstractSecurityWebSocketMessageBrokerConfigurer` (with `configureInbound` and `sameOriginDisabled`). The subclass is reported and does not compile.

Inspect: the message authorization rules and the CSRF setting for STOMP.

Decide: rewrite the configuration with `@EnableWebSocketSecurity` and an `AuthorizationManager<Message<?>>`; decide CSRF for STOMP.

Prove: a STOMP authorization test (allowed and denied destinations).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## security/web-redirect-and-entrypoint-defaults

Spring Security 7 redirects to the login page with a relative URL by default, and removed `PortResolver`. Reported: tests that assert an absolute login redirect, custom `LoginUrlAuthenticationEntryPoint` subclasses and `PortResolver` uses.

Inspect: what the clients (and proxies) do with the redirect.

Decide: keep relative redirects and update the tests, or call `setFavorRelativeUris(false)`.

Prove: a login redirect test.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## security/factor-granted-authority-in-persisted-auth

Spring Security 7 adds `FACTOR_*` authorities (`FACTOR_PASSWORD`, ...) to authenticated users. Reported: `OAuth2TokenCustomizer` implementations that may copy them into claims, modules that store sessions with Spring Session (on the build file), and tests that assert authority collections.

Inspect: the tokens, sessions and other stored state that hold authorities, and the code that reads them back.

Decide: a rollout strategy (forced re-login, a separate session namespace), and filter `FACTOR_*` out of tokens where the consumers do not expect them.

Prove: on the fixture, pin 38 (a golden session still authenticates).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## security/leftover-and-chain-detection

Spring Security 7 removed `and()` from `SecurityConfigurerAdapter`. Each `and()` that the lambda DSL steps of the Run left (chains split across variables, helper methods and custom DSL classes) is reported and does not compile.

Inspect: the whole chain, including the variables, helper methods and custom DSLs it goes through.

Decide: restructure the chain into the lambda DSL (`http.httpBasic(basic -> basic.realmName(..))`).

Prove: the module compiles; on the fixture, pin 3 (`SecurityChainPinTest.andChainAndFormLogin`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).
