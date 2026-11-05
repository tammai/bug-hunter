# Edge inputs: any code

Try each one that fits the code in your part. Each line: the input, and the kind of bug it tends to find.

## Paths
- Paths with spaces (`my dir/file.txt`): unquoted shell use, naive `split()`.
- Non-ASCII paths (`naïve/ö.md`, emoji): `git` quoting them (`core.quotepath`), byte vs str handling, default encodings.
- Windows separators (`dir\file`) and drive letters: string joins and `startswith("/")` checks.
- Relative vs absolute, `./x`, trailing slash, `..`, symlinks, running from a different working directory.

## Text and files
- CRLF line endings: `split("\n")` leaving `\r`, regexes anchored with `$`, exact-match comparisons.
- Trailing spaces and tabs, a missing final newline, a BOM.
- Empty files, empty sections, a file with only a header, a heading with nothing under it.
- Markdown variants: bold or code in table cells (`**B2**`, `` `B2` ``), escaped pipes, headings with trailing `#`s or colons, setext headings, lists with `*` vs `-`.

## Names, numbers and order
- Digits inside words (`OAuth2`, `v2beta`, `S3Bucket`): splitting on digits, slug and case conversion.
- Off-by-one: first and last items, a range's end, counts of 0 and 1, `--max 1`.
- `B10` sorting before `B2` (string sort of numbered IDs), `09` vs `9`, leading zeros, `int("08")`.

## Structured input
- Missing or null keys in JSON on stdin, a key with the wrong type, an empty object or list, stdin that isn't JSON at all, empty stdin.
- Duplicate keys or IDs, unknown fields, very long values.

## The environment
- Subprocess failures: the tool isn't installed, exits non-zero, prints to stderr only, or prints something unexpected; errors swallowed and reported as success.
- Encodings: non-UTF-8 bytes, a non-UTF-8 locale, `open()` without an `encoding`.
- Running a step twice: is it idempotent, does it duplicate entries, overwrite work, or fail because its own output exists?
- Stray files in folders the code scans: `.DS_Store`, `Thumbs.db`, editor swap files, a directory where a file is expected.
- A crash part way through a write: is the file left half-written or empty?
