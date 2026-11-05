# Edge inputs: Ruby

Use with the generic list. Each line: the input, and the kind of bug it tends to find. Run with `bundle exec ruby` or the project's test runner in the copy after `BUNDLE_FROZEN=true bundle install`.

- `nil` from a missing hash key or an empty query result reaching a method call (`NoMethodError on nil`); `&.` hiding a value that should be there.
- Frozen string literals (`# frozen_string_literal: true`): `<<` or `gsub!` on a literal raises `FrozenError`.
- `"12abc".to_i` is 12 and `"".to_i` is 0, while `Integer("12abc")` raises: inputs that should be rejected are accepted.
- Encodings: strings read as `ASCII-8BIT`, `Encoding::CompatibilityError` when joining binary and UTF-8 strings, invalid byte sequences in `split`.
- Symbol vs string keys: `params[:id]` vs `params["id"]`, JSON parsed with string keys, `symbolize_names` mismatches.
- `Time.now` vs `Time.zone.now`, `Date.parse` guessing formats, month and year ends.
- Mutating a default argument or a constant (`DEFAULTS[:x] = …`) shared across calls.
- `Float` money and `round` on halves; integer division `7 / 2` is 3.
