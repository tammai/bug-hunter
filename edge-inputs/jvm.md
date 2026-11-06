# Edge inputs: Java and Kotlin

Use with the generic list. Each line: the input, and the kind of bug it tends to find. Build with the project's own wrapper (`./gradlew`, `./mvnw`) or `mvn` after its locked install; run a small `main` or a test in the copy.

- `null` from maps, JSON fields and Java APIs reaching code that assumes a value; Kotlin `!!` and platform types from Java.
- `==` on strings or boxed numbers compares references (`Integer` outside -128..127); `equals` without `hashCode`.
- Integer overflow in `int` arithmetic, `Math.abs(Integer.MIN_VALUE)`, `long` from `int * int`.
- Time zones: `new Date()` and `LocalDateTime` without a zone, `SimpleDateFormat` shared across threads, DST changes, `YYYY` vs `yyyy`.
- Resources that never close: streams, readers and connections without try-with-resources or `use {}`, leaking on the error path.
- `BigDecimal` from a `double`, `equals` vs `compareTo` on `BigDecimal` (`2.0` vs `2.00`), rounding mode defaults.
- `String.split` with a regex special character, trailing empty strings dropped; `substring` indexes on short input.
- Collections: `ConcurrentModificationException` when removing while iterating, `Arrays.asList` being fixed-size, `subList` views.
- Default charset in `getBytes()`, `new String(bytes)` and `FileReader`.
