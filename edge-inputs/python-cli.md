# Edge inputs: Python CLIs and scripts

Use with the generic list. Each line: the input, and the kind of bug it tends to find.

## Arguments
- No arguments, `--help`, an unknown flag, a flag given twice, a value that starts with `-`, `--` before a positional.
- A file argument that is a directory, missing, unreadable or empty; the same file given twice.
- Errors that print a traceback instead of a one-line message, or exit 0 on failure.

## Files and text
- `open()` or `read_text()` without `encoding=`: breaks on non-ASCII under a non-UTF-8 locale.
- `str.split("\n")` vs `splitlines()`, `strip()` that eats meaningful spaces, `re.match` vs `re.search`, `$` and `re.MULTILINE`.
- `Path.read_text()` translates CRLF but `open(..., newline="")` and bytes reads don't: compare both sides.
- Writes that aren't atomic (`write_text` straight over the target): a kill or error mid-write leaves it truncated.

## Data
- `dict["key"]` on JSON that may lack it; `None` where a string is expected (`None.strip()`); `json.loads` on empty input.
- `sorted()` on strings that hold numbers; `int()` on `"08"`, `" 3"`, `"3.0"`; float formatting and rounding.
- Mutable default arguments; globals reused across calls in one process.

## Processes and environment
- `subprocess.run` without `check=` or without looking at `returncode`; `shell=True` with a path that has spaces or quotes; a tool missing from `PATH` (`FileNotFoundError`).
- `HOME`, `TMPDIR` or another env var unset or pointing somewhere unusual; `~` that is never expanded.
- Running from another working directory: paths resolved against `cwd` instead of the script or the repo.
- Naive `datetime` vs aware, local time vs UTC, dates at month and year ends.
