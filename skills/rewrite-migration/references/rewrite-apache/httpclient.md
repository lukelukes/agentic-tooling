# rewrite-apache: HttpClient and HttpCore 5

Rules of `org.openrewrite.apache.httpclient5.UpgradeApacheHttpClient_5` and its HttpCore NIO steps. Read the resolved
`httpclient5` and `httpcore5` versions and their sources first; 4.x and 5.x types often share a simple name.

## NIO buffers

HttpCore 5 has `org.apache.hc.core5.http.nio.support.classic.SharedInputBuffer` and `SharedOutputBuffer` for the
classic-over-async bridge. They are driven by the async data channel, not by an `IOControl`, so the 4.x calls that
pumped the reactor have no counterpart.

## httpclient/consume-content-removed

`SharedInputBuffer.consumeContent(..)` was removed. Feed incoming data with `fill(ByteBuffer)` from the
`AsyncDataConsumer` that owns the buffer (its `consume(ByteBuffer)` callback), or delete the call when it only drained
the decoder. This does not compile until handled.

## httpclient/wait-for-data-removed

`SharedInputBuffer.waitForData()` was removed; `read(..)` now blocks until data or end of stream. Delete the call, and
check that the code after it reads with `read(..)`.

## httpclient/simple-input-buffer-removed

`SimpleInputBuffer` has no HttpCore 5 equivalent. Replace it with a `SharedInputBuffer` when another thread fills it,
or with a plain `ByteBuffer` or `ByteArrayOutputStream` when one thread fills and reads it.

## httpclient/shared-input-buffer-capacity

`capacity()` on the 5.x `SharedInputBuffer` returns what the 4.x `available()` returned (the Recipe renamed
`available()` calls to `capacity()`). An old `capacity()` call meant the buffer size and now means the free space.
Keep the call only if free space is what the code wants; otherwise use the size the buffer was built with.

## httpclient/produce-content-removed

`SharedOutputBuffer.produceContent(..)` was removed. Data leaves the buffer through the `AsyncDataProducer` that owns
it (`produce(DataStreamChannel)` calls `flush(DataStreamChannel)`); delete the call and wire the producer.

## httpclient/flush-removed

`SharedOutputBuffer.flush()` was removed. Writes are flushed by the producer side; `writeCompleted()` marks the end of
the stream. Delete the call, and call `writeCompleted()` where the 4.x code flushed for the last time.

## httpclient/simple-output-buffer-removed

`SimpleOutputBuffer` has no HttpCore 5 equivalent. Replace it with a `SharedOutputBuffer` when another thread drains
it, or with a plain `ByteBuffer` or `ByteArrayOutputStream`.

## httpclient/shared-output-buffer-capacity

As `httpclient/shared-input-buffer-capacity`, for `SharedOutputBuffer`: `capacity()` now returns the free space.

## httpclient/buffer-array-reuse

`read(byte[])` and `write(byte[])` became `read(b, 0, b.length)` and `write(b, 0, b.length)`, so the array expression
is evaluated twice. When the expression has side effects or may return a different array (`next()`, `new byte[..]`,
a getter that allocates), assign it to a local variable first and pass the local three times.

## Packages without a counterpart

## httpclient/params-package-not-migrated

An import of `org.apache.http.params` (`HttpParams`, `BasicHttpParams`, `HttpConnectionParams`, `CoreProtocolPNames`,
...). HttpClient 5 removed the package, so the code does not compile; the Recipe has no generic mapping for it.

- Timeouts (`HttpConnectionParams.setConnectionTimeout`, `setSoTimeout`): `RequestConfig.custom()
  .setConnectTimeout(..)` and `.setResponseTimeout(..)`, or `ConnectionConfig` and `SocketConfig` on the connection
  manager. 5.x takes `Timeout` values, not milliseconds as `int`.
- Protocol settings (`CoreProtocolPNames`: user agent, protocol version, expect-continue): the client builder
  (`setUserAgent(..)`) or `RequestConfig` (`setExpectContinueEnabled(..)`).
- Read the 4.x defaults the old params relied on and set them explicitly when 5.x changed them; drop a setting that
  only restated a default, with a `no-change` note.

Check: a request to a local stub that answers slower than the configured timeout fails with a timeout.

## Authentication and connection management

## httpclient/auth-scheme-credentials-removed

HttpClient 5 keeps credentials on a `CredentialsProvider`, not on the `AuthScheme` or `AuthExchange`.
`AuthExchange.update(AuthScheme, Credentials)`, `AuthExchange.setCredentials(..)` and `AuthScheme.getCredentials()`
do not exist.

- Register the credentials with a `BasicCredentialsProvider` (`setCredentials(new AuthScope(host, port), creds)`) on
  the client builder or the `HttpClientContext`, and drop the call.
- Code that read credentials back from the scheme reads them from the provider:
  `provider.getCredentials(authScope, context)`.

Check: a request to a stub that demands the scheme gets through with the credentials.

## httpclient/pooling-async-connection-manager-config-lost

A `PoolingNHttpClientConnectionManager` constructor with a connection factory, scheme `Registry`, port resolver, DNS
resolver or TTL became a `PoolingAsyncClientConnectionManager`, and those arguments were dropped.

- Rebuild the manager with `PoolingAsyncClientConnectionManagerBuilder`: TLS from the registry with
  `setTlsStrategy(..)` (`ClientTlsStrategyBuilder` with the old `SSLContext` and hostname verifier), `setDnsResolver(..)`,
  `setSchemePortResolver(..)`, and the TTL with `setConnectionTimeToLive(..)` or a `ConnectionConfig`.
- A custom connection factory: find what it configured (I/O, charset, message parsers) and set the 5.x equivalent, or
  resolve as `no-change` with a note when it only restated defaults.

Check: a TLS request to a local stub with the application's trust material, when the registry configured TLS.
