# rewrite-migrate-java: web runtime

Rules that the Jakarta EE Recipes of rewrite-migrate-java report.

## web-runtime/jetty-gzip-handler

`JettyUpgradeEE11` (wired into the Spring Boot 4 Migration) moves Jetty EE10 to EE11 on Jetty 12.1, which deprecates
`GzipHandler` in favour of `CompressionHandler`. The Migration keeps the `GzipHandler` with a `PRESERVED` row; the
anchor is the method, field or class that builds it, and the `setting` names it
(`<file>#<anchor>:GzipHandler`).

- Leave the item unresolved. Moving to `CompressionHandler` (with the `jetty-compression-gzip` module) is an
  Improvement: set `adopted` only when the human asks for it, after replacing the handler and checking the
  compressed responses.

Check: a request with `Accept-Encoding: gzip` still gets a gzip-encoded response.

Source: [Jetty 12.1 compression](https://jetty.org/docs/jetty/12.1/programming-guide/server/compression.html).
