# rewrite-spring: web runtime

Rules about the embedded web server that the Spring Boot 4 Migration reports: Tomcat 11, Undertow, and the Spring Boot 4.1 HTTP client defaults.

## web-runtime/tomcat11-cookie-rfc6265

Spring Boot 4 runs Tomcat 11, which parses cookies by RFC 6265 only: a quoted value keeps its quotes, and some values are rejected. Reported per read site: `@CookieValue` parameters, `Cookie.getValue()`, `WebUtils.getCookie(..)`, a customizer that sets a cookie processor, and cookie attributes without a value.

Inspect: the cookie values clients really send (quotes, spaces, commas), and who writes them.

Decide: unquote at the read sites, or change how the cookies are written so they are valid RFC 6265 values.

Prove: an integration test with quoted and plain cookie values; on the fixture, pin 6 (`CookieReadPinTest.quotedCookieValue`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## web-runtime/tomcat-max-parameter-count

Tomcat 11 lowers the default request parameter limit from 10000 to 1000. A handler that binds every parameter (`@RequestParam Map`/`MultiValueMap`, `@ModelAttribute`) in a module that sets no `server.tomcat.max-parameter-count` is reported, one row per handler. The rule is `review-only` (a security hardening): the Migration takes the new limit and names `server.tomcat.max-parameter-count=10000` without writing it.

Inspect: how many parameters clients send to the handler (large forms, bulk filters).

Decide: keep 1000, or set an explicit limit, only as high as the clients need, in the module's configuration.

Prove: a test that posts 1,500 and 9,000 parameters; on the fixture, pin 8 (`TomcatParameterLimitPinTest.manyParams`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## web-runtime/tomcat11-url-strictness

Tomcat 11 parses request lines and parameters strictly: `getParameter*()` may now throw on malformed input. Reported where the module relaxes the parser (`server.tomcat.relaxed-path-chars`, `server.tomcat.relaxed-query-chars`) or decodes with an encoding other than UTF-8 (`server.tomcat.uri-encoding`).

Inspect: the clients that send the relaxed characters, and how the application answers a malformed request today.

Decide: keep the relaxed characters only where clients need them, and handle the 400 that malformed input now gets.

Prove: tests for an invalid `%zz`, `a|b` and `[]` in a query; on the fixture, pin 9 (`TomcatParameterLimitPinTest.malformedQuery`).

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## web-runtime/failed-request-filter-removed

Tomcat 11 removed `org.apache.catalina.filters.FailedRequestFilter`; parameter parse failures fail the request with a 400 by themselves. Each reference (including a `FilterRegistrationBean`) is reported and does not compile.

Inspect: the registration and what the application expected the filter to do.

Decide: remove the filter and its registration; decide how a 400 for malformed parameters is answered.

Prove: the module compiles, and the tests of `web-runtime/tomcat11-url-strictness` pass.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## web-runtime/tomcat-basedir-cleanup

Spring Boot 4.1 deletes Tomcat's temporary base directory when the server stops. A module that enables the access log without `server.tomcat.basedir` or an absolute `server.tomcat.accesslog.directory` loses its logs.

Inspect: where the access log is read (log shipping, support).

Decide: set `server.tomcat.basedir` or an absolute access log directory, or accept that the log goes with the server.

Prove: a restart test that shows the access log kept, or dropped on purpose.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## web-runtime/reactor-netty-system-proxy-default

Spring Boot 4.1 builds Reactor Netty HTTP clients that use the JVM's proxy system properties. Reported in modules with `reactor-netty-http`: `WebClient`/`RestClient` builders, and `http(s).proxyHost`/`http.nonProxyHosts` in properties files.

Inspect: which hosts each client calls, and the proxy settings of each environment.

Decide: accept the system proxy, fix `http.nonProxyHosts`, or call `withoutHttpClientDefaults()` on a client that must not use it.

Prove: a client integration test with and without a proxy property.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).

## web-runtime/undertow-removed

Spring Boot 4 has no Undertow support. Each Undertow dependency, `server.undertow.*` key and use of the Undertow types of Spring Boot and Spring Framework is reported.

Inspect: the Undertow tuning (post size, encoded slash, threads, buffers, access log) and customizers.

Decide: choose Tomcat or Jetty, remove the `spring-boot-starter-tomcat` exclusion, and port the tuning and the customizers.

Prove: on the fixture, pins 45 (`UndertowTuningPinTest.maxPostSize`) and 46 (`.encodedSlash`) pass on the chosen server.

Resolutions: `fixed`, `no-change` (note why), `deferred` (note who decides).
