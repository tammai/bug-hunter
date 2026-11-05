# Edge inputs: Node, TypeScript, Vue and Svelte

Use with the generic list. Each line: the input, and the kind of bug it tends to find. Run code with `node` and the project's own tools from `node_modules/.bin` (`tsx`, `vitest`) after its locked install. Never download a tool with `npx`.

## Values
- `undefined` vs `null` vs a missing key: `obj.a.b` crashes, `??` vs `||` on `0`, `""` and `false`, and optional fields dropped by `JSON.stringify`.
- `parseInt("08")`, `parseInt("1e3")`, `parseInt` without a radix, `Number("")` (0), `Number(" ")`, `NaN` passing a `<` check.
- `==` vs `===`: `"0" == false`, `null == undefined`, comparing ids that are a number on one side and a string on the other.
- floating point money: `0.1 + 0.2`, `toFixed` rounding, summing cents as floats.
- Default `sort()` sorts as strings: `[10, 9, 1].sort()` gives `[1, 10, 9]`; `localeCompare` without numeric collation.

## Time
- `new Date("2026-11-05")` is UTC but `new Date("2026-11-05T00:00")` is local: off-by-one days across time zone boundaries; month numbers start at 0; DST changes.

## Async
- unhandled promise rejections that crash the process or are silently lost; a missing `await` that returns a pending promise; `forEach` with an async callback that never waits; errors thrown in an `.on("data")` handler.

## Input and output
- `JSON.parse` on an empty body, `"null"`, or a byte-order mark; request bodies missing fields the handler assumes; query params that arrive as arrays (`?id=1&id=2`).
- String length vs bytes for emoji and non-ASCII; `encodeURIComponent` vs `encodeURI`; `path.join` with user input containing `..`.

## Vue and Svelte logic
- Composables and stores: state shared across calls by accident (a module-level `ref`), watchers that miss the first value, computed values that mutate state.
- Formatting helpers used in templates: dates, currency and pluralisation for 0, 1 and negative numbers.
