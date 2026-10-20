# rewrite-migrate-java: Java version upgrades

Rules of the Java version migrations (`org.openrewrite.java.migrate.*`). Read the Java version the build targets
first; it decides which removed APIs fail at compile time.

## java/base64-name-conflict

The file still uses `sun.misc.BASE64Encoder` or `BASE64Decoder`, because it already uses another class named
`Base64` (its own, or a library's), so `java.util.Base64` cannot be imported by its simple name. `sun.misc` is not
exported on Java 17, so this does not compile there.

- Replace the coder with `java.util.Base64` written by its fully qualified name:
  `java.util.Base64.getEncoder().encodeToString(..)` and `java.util.Base64.getDecoder().decode(..)`.
- `BASE64Encoder.encode(..)` wrapped lines at 76 characters with `\n`. When the output goes somewhere that expects
  that, use `java.util.Base64.getMimeEncoder(76, new byte[] {'\n'})`; otherwise the basic encoder.
- `BASE64Decoder.decodeBuffer(..)` ignored line breaks and threw `IOException`; use `getMimeDecoder()` for input with
  line breaks, and remove the now unneeded `catch (IOException ..)`.

Check: a round trip of a value longer than 57 bytes, compared with the old output.
