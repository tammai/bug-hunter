# Edge inputs: Rust

Use with the generic list. Each line: the input, and the kind of bug it tends to find. Build and run with `cargo run --locked` or `cargo test --locked` in the copy after `cargo fetch --locked`.

- `unwrap()` and `expect()` on input that can be absent or malformed: an empty file, a missing env var, a parse error, which panics instead of returning an error.
- Integer overflow: it panics in debug builds and wraps in release, so the same input behaves differently in each; `usize` subtraction below 0.
- `as` casts that truncate or saturate silently (`x as u8`, `f64 as i32` on `NaN`).
- UTF-8: slicing a `&str` at a byte index inside a multi-byte character panics; `len()` is bytes; non-UTF-8 paths and `to_str().unwrap()`.
- Path handling: `Path::join` with an absolute second path replaces the first; `..` in user input; Windows separators.
- Iterators: `zip` stopping at the shorter input, `windows`/`chunks` on short input, off-by-one in ranges (`..` vs `..=`).
- Error handling: `?` converting errors and losing context, `let _ =` dropping a `Result`, a partial write before an error.
- Sorting floats with `partial_cmp().unwrap()` on `NaN`.
