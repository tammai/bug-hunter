# Edge inputs: PHP

Use with the generic list. Each line: the input, and the kind of bug it tends to find. Run with `php` or the project's test runner in the copy after `composer install --no-scripts --no-plugins`.

- Loose `==` type juggling: `"abc" == 0` (true before PHP 8), `"1e3" == "1000"`, `null == false`, `in_array` and `array_search` without `strict`.
- `empty("0")` is true, so a valid `"0"` input is treated as missing; `isset` on a key whose value is `null`.
- `strpos` returning `0` for a match at the start, tested with `if (!strpos(...))`.
- Array key casting: `"1"` becomes the integer key `1`, `true` becomes `1`, floats are truncated, so two inputs share a key.
- `json_decode` returning `null` on invalid JSON with no error unless `JSON_THROW_ON_ERROR`; objects vs associative arrays.
- `intval("12abc")` is 12; `(int)` on large numbers; float money and `round`.
- Multibyte strings: `strlen`, `substr` and `strtoupper` on UTF-8 instead of `mb_*` functions.
- Dates: `date()` with the server's default time zone, `strtotime` guessing formats, `DateTime` mutation vs `DateTimeImmutable`.
