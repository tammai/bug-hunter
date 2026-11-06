# Edge inputs: Go

Use with the generic list. Each line: the input, and the kind of bug it tends to find. Run with `go run` or `go test` in the copy after `go mod download`.

- Writing to a nil map panics; a nil slice vs an empty slice marshals to `null` vs `[]` in JSON.
- The loop variable captured by a closure or goroutine (before Go 1.22 semantics, or `go.mod` declaring an older version).
- Error shadowing: `err :=` inside an `if` or block hides the outer `err`, so a failure is returned as nil.
- Slice aliasing: `append` to a sub-slice overwrites the parent's elements; returning a slice of an internal buffer.
- `defer` in a loop holds every file or lock until the function returns; `defer f.Close()` ignoring the error on a written file.
- Integer conversion overflow (`int32(x)`), `strconv.Atoi` on `" 3"` or `"+3"`, division by zero on an empty input.
- `range` over a string gives runes with byte offsets; `len(s)` is bytes, not characters.
- Unchecked type assertions (`v.(string)`) on decoded JSON, where numbers arrive as `float64`.
- Time: `time.Parse` without a location, `time.Now()` vs UTC in stored values, comparing `time.Time` with `==`.
