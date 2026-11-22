# Leak scan limits: one address source with the masker, cut messages, more spellings and login shapes

## Why

**Request (verbatim):** Feature 2026-11-22-m-leak-scan-limits (risk high, track medium), based on C3 (2026-11-22-m-leak-check-followups, commit 06e2ea1). Leak scan (drafts.leaks) known limits from docs/sdlc/todo.md: C4-6 one shared address source for drafts._host_patterns and live_proxy._masker (bytes, longest-first, links still routed); C4-8/S-7 host/login cut by 500-char message cap leaves a prefix; trailing-dot host; S-5 8.3 short path spec folder skips link guard, folder links scope._any_matches doesn't check. Plus C3 review tickets: zero-padded ports, reversed name/value, attribute between name and value, IPv6 zone [::1%25lo], IPv6 right boundary at ':', mapped hex ::ffff:a00:1, cookie anywhere-match limited to auth/session-like pieces. Keep scan linear. Review deferred; stop at approval gate.

Live hunts must never put the owner's dev or UAT host, or an account's login, into a public issue, and agents must never see them. Two gates stand in the way: the proxy's masker (`live_proxy._masker`), which rewrites what responses show agents, and the leak scan (`drafts.leaks`), the last check before a draft or finding is kept. Today they disagree on what an address looks like, so a response can show an agent `127.1:5000` or `xuat.acme.test` unmasked, and the finding it proves is then dropped at write time ("a target echoed it past the proxy's masking"). The other items are spellings and shapes that still pass the scan (or, for cookies, over-refuse), a message cut that leaves half a host behind, and two link guards that a different spelling of a path gets around.

Builds on C3 (`2026-11-22-m-leak-check-followups`, not merged yet): its `_host_patterns`, `_ipv6_pattern` tree, `_holds_login` and the linear-scan test are kept and extended, not redone.

**The user's words:** none asked yet (the owner's lane brief, relayed by the orchestrator, is the request above).

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| **C4-6, one source:** `drafts.py` gives each target's address patterns once (the scan's: every spelling, no left boundary) and, beside them, the target's link pattern (its scheme, any spelling of its host, its port or none for the default). `_masker` compiles both into one bytes regex per proxy: links first, then host patterns by host length, longest first, one pass over every target. A link match goes to that target's listener; any other match becomes `<target>` | Keeping the masker's word boundaries (`(?<![\w.-])`) on top of the shared spellings | The point of the ticket: with boundaries, the scan still refuses text the masker let through (an undecoded escape, `_` or a letter before the host), so agents see the host and the proven finding is lost at write time. Masking more is the safe side for a mask. Cost: `xuat.acme.tests` now reads `x<target>s`, and `2001:fd00::1` reads `2001:<target>` for target `fd00::1`; two existing masker tests change their expected output (see Must never break) |
| **C4-6, links:** a link is routed only with the target's own scheme, then any spelling of its host (`http://127.1:5000` for a `localhost:5000` target), then its port, zero padding allowed, or no port when the target uses its scheme's default; never where the host continues (`uat.acme.test.evil`) | Routing any scheme | A `https://` link to an `http://` target is not a link the listener serves; it is masked as `<target>` instead |
| **C4-8 / S-7:** a message over the 500-character cap is cut back to the last whitespace, quote, backtick, `<` or `>` before the cap, so a host, URL or token is kept whole or dropped whole; with no such character before the cap, the whole run is dropped, never cut mid-run. `finding_v1._bounded` keeps the digest of the whole message (nothing parses it; `_failed_value` already rejects a cut message). `browser._message` gets the same cut, and no digest | Scanning for a host prefix before the `...` marker | The cut happens in `finding_v1` and `browser`, which don't know the targets. Hosts, URLs and Bearer or API tokens hold none of those characters. A Basic password or a whole Cookie value can hold a space or a quote, so a cut can still keep the part before it: those values pass through the proxy's masker as a whole before any message is built, so only a value the masker missed is exposed, and that was exposed whole before this change |
| **Trailing dot:** a target's host is read without a trailing dot (`uat.acme.test.` is `uat.acme.test`), and its patterns also take one | — | DNS treats both as the same host |
| **S-5, spec folder** (the original S-5 report isn't on disk; this reading comes from the code and the todo line): `oracle.build` refuses a spec folder when any folder on its path is a link whose parent resolves inside the repo. Resolving each parent, not comparing the text of two paths, so an 8.3 short name (`C:\Users\TAMMAI~1\repo\spec`) or a link above the repo can't make the spec look outside it | `GetLongPathNameW` like `isolate.py` | `Path.resolve()` already expands short names on Windows and follows links on every OS, so one check covers both and runs in tests on macOS and Linux |
| **S-5, folder links:** `scope._any_matches` skips a file when any folder between the repo and it is a link or junction (the check `oracle._linked` already does; it moves to `scope` and `oracle` keeps its name) | A second copy of the check | `oracle` imports `scope`, not the other way round |
| **Zero-padded ports:** `:0*<port>` wherever a port is matched (`localhost:080`, `127.0.0.1:05000`, `ref:03000`) | — | URL parsers read `:05000` as 5000 |
| **IPv6 zone on loopback:** `[::1%25lo]`, `[::1%lo]` (any zone, in brackets) | Unbracketed zones | A zone appears only in a bracketed URL host or with a `%` there |
| **IPv6 right boundary:** an IPv6 spelling must not run on into a letter, digit or `_`, or into `:` followed by one or by another `:` (`2001:db8::1:5`, `std::vector` for `[::]`); `2001:db8::1: timeout` still counts | Stopping at any `:` | Prose puts a colon after an address |
| **Mapped hex for IPv4 targets:** a plain IPv4 target also matches every IPv6 spelling of `::ffff:<it>` (`::ffff:a00:1`) | — | Same address |
| **Login shapes:** a `value` key may also come before the field's `name` key (`value="member" name="password"`, `{"value":"member","name":"token"}`), and up to three other quoted attributes or JSON keys may stand between name and value (`name="password" type="text" value="member"`) | Any number of attributes or words in between | `{"token": "x", "role": "member"}` must stay clean; three covers `type`, `id`, `autocomplete`. Bounded, possessive runs keep the scan linear |
| **Cookie pieces:** a cookie value counts anywhere (as a random token) only when its cookie's name looks like a session or auth cookie: contains `sess`, `sid`, `auth`, `tok`, `jwt`, `csrf`, `xsrf`, `login`, `remember`, `key`, `secret`, `pass`, `cred`, `bearer`, `access`, `refresh`, `user`, `account` or `identity`, or ends in `id`. Other cookies' values (`device=desktop`) count only in credential context, as word logins do. Header values and Basic logins are unchanged | Every cookie value anywhere (today); no cookie value anywhere | Over-refusal on `device`, `theme`, `lang` cookies, while unknown names on the list's side stay the safe side |

**Proposals not asked for:** none.

## Acceptance criteria

- **AC-001** (C4-6) Given a target and its listener, when a response holds an address spelling the scan finds (`127.1:5000`, `0.0.0.0:5000`, `[::1%25lo]:5000`, `localhost:05000`, `10.0.0.01`, `::ffff:a00:1`, `2001:0db8:0:0:0:0:0:1`, `xuat.acme.test`, `uat.acme.test.`), then the masker hides it, and `leaks` on the masked bytes reports no host.
- **AC-002** (C4-6) Given a `localhost:5000` target, when a response links to it under another spelling (`http://127.1:5000/x`, `http://[::1]:5000/x`, `http://localhost:05000/x`), then the link points at the listener; `https://uat.acme.test/x` for target `https://uat.acme.test` routes, `https://uat.acme.test.evil/x` does not.
- **AC-003** (C4-6) Given two targets at once (`localhost:3000` and `localhost:3001`; `acme.test` and `uat.acme.test`), when a response holds each one's address and link, including spellings only the shared patterns catch (`127.1:3001`, `http://127.1:3000/x`, `xuat.acme.test`), then each is masked or routed as its own, in bytes, Latin-1 neighbours included, and the listener URLs put in are never masked again.
- **AC-004** (C4-8/S-7) Given a message over the cap with a host, URL or token across the cut, or one run of 600 characters with no space, when `finding_v1._bounded` or `browser._message` cuts it, then no prefix of that host, URL, token or run is left; `_bounded`'s results for two messages that differ only past the cut still differ.
- **AC-005** (trailing dot) Given a target written with a trailing dot, `http://localhost.:5000`, `http://ref.:3000` or `http://uat.acme.test.`, when a draft holds `localhost:5000` (or `127.0.0.1:5000`), `ref:3000` or `uat.acme.test`, then `leaks` reports the host.
- **AC-006** (S-5) Given a spec folder inside the repo that is a link, when `oracle.build` is given its path through a different spelling of the repo's path (a link above the repo, as an 8.3 short name is on Windows), then it refuses it. (The test runs a link above the repo on macOS and Linux; a real 8.3 short name is not run, since no Windows session is in this lane.)
- **AC-007** (S-5) Given a part's file under a folder that is a link out of the repo, when `scope._any_matches` checks it, then it isn't read (no route or client call found through it).
- **AC-008** (ports, zone, IPv6, mapped) Given the matching targets, `localhost:080` (port-less http target), `127.0.0.1:05000`, `[::1%25lo]:5000` and `::ffff:a00:1` (target `10.0.0.1`) are reported, while `127.0.0.1:50003`, `2001:db8::1:5` (target `[2001:db8::1]`), `std::vector` (target `[::]`) and `::ffff:a00:2` report nothing, and `2001:db8::1: timeout` is still reported.
- **AC-009** (login shapes) Given a word login `Bearer member`, `value="member" name="password"`, `{"value":"member","name":"token"}`, `name="password" type="text" value="member"` and `{"name":"token","type":"x","value":"member"}` are reported, while `value="member" name="role"` and `name="role" type="text" value="member"` report nothing.
- **AC-010** (cookies) Given an account `Cookie: device=desktop; sid=qwxzkvbnmt`, a draft holding `desktop` in prose reports nothing, `device=desktop` reports the login, and `qwxzkvbnmt` alone is reported.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_leak_scan_limits.py › test_masker_hides_every_spelling_the_scan_finds | `uv run pytest tests/test_leak_scan_limits.py::test_masker_hides_every_spelling_the_scan_finds` |
| AC-002 | tests/test_leak_scan_limits.py › test_links_under_any_host_spelling_go_to_the_listener | `uv run pytest tests/test_leak_scan_limits.py::test_links_under_any_host_spelling_go_to_the_listener` |
| AC-003 | tests/test_leak_scan_limits.py › test_two_targets_are_masked_in_one_pass_longest_first | `uv run pytest tests/test_leak_scan_limits.py::test_two_targets_are_masked_in_one_pass_longest_first` |
| AC-004 | tests/test_leak_scan_limits.py › test_message_cut_never_leaves_a_host_or_login_prefix | `uv run pytest tests/test_leak_scan_limits.py::test_message_cut_never_leaves_a_host_or_login_prefix` |
| AC-005 | tests/test_leak_scan_limits.py › test_trailing_dot_host_is_the_same_host | `uv run pytest tests/test_leak_scan_limits.py::test_trailing_dot_host_is_the_same_host` |
| AC-006 | tests/test_leak_scan_limits.py › test_linked_spec_folder_is_refused_under_another_repo_spelling | `uv run pytest tests/test_leak_scan_limits.py::test_linked_spec_folder_is_refused_under_another_repo_spelling` |
| AC-007 | tests/test_leak_scan_limits.py › test_files_under_a_linked_folder_are_not_read | `uv run pytest tests/test_leak_scan_limits.py::test_files_under_a_linked_folder_are_not_read` |
| AC-008 | tests/test_leak_scan_limits.py › test_padded_ports_zones_and_ipv6_boundaries | `uv run pytest tests/test_leak_scan_limits.py::test_padded_ports_zones_and_ipv6_boundaries` |
| AC-009 | tests/test_leak_scan_limits.py › test_word_login_reversed_or_behind_other_attributes | `uv run pytest tests/test_leak_scan_limits.py::test_word_login_reversed_or_behind_other_attributes` |
| AC-010 | tests/test_leak_scan_limits.py › test_only_session_like_cookie_values_count_anywhere | `uv run pytest tests/test_leak_scan_limits.py::test_only_session_like_cookie_values_count_anywhere` |

## Must never break

- Every C3 test keeps its result (`tests/test_drafts.py`, `tests/test_drafts_leak_spellings.py`): the placeholders a draft is told to write (`$BASE`, `$MEMBER_AUTH`, `ACCEPT_ACCOUNT_MEMBER`) and the allowed prose stay clean, and `127.0.0.1:50003` (the proxy's own listener) is never the target.
- The scan and the masker stay linear on hostile text: `tests/test_drafts_scan_time.py` gains the new shapes (reversed and in-between attributes, zones, padded ports) and a masker run over the same 50,000-character runs, each under its bound.
- The masker's existing tests keep their results, except two expected outputs that change on purpose under the C4-6 decision: `xuat.acme.tests` → `x<target>s` and `2001:fd00::1` → `2001:<target>` (`tests/test_live_proxy.py`), and `::ffff:10.0.0.5` → `<target>` (whole mapped address). Account values are still masked exactly (`Password` in a label survives a `password` login).
- `leaks` and the masker never echo the host or a login in a message.
- A finding the proxy masked correctly is still written (`finding_v1.write` passes the masked text).

## Failure modes

- Untrusted input (responses and drafts quoting them): every new pattern runs on hostile text → must-never-break (linear time); the masker now runs the scan's IPv6 trees on every response, so its cost is timed too.
- Over-refusal or over-masking: each new spelling has a clean counter-example in its AC (AC-008, AC-009, AC-010); the masker's word-mangling is accepted for addresses only (Decisions).
- Paths an agent or target controls (S-5): resolving each parent touches only folders on the spec's own path; a `\\host\share` path is not newly opened (it was resolved before too).
- Concurrency: the masker is built once per proxy and swapped under its lock as today; nothing new is shared.
- Persisted data, deploy and rollback: none (pure functions; findings already written are not re-read).

## Out of scope

- One source of address *spellings*, not one matcher: the masker sees raw response bytes, the scan sees every decoded spelling. A host behind an encoding (`uat%2Eacme%2Etest`, `\x2F`) still passes the masker and is refused when the finding is written, as today.
- Short IPv4 forms for non-loopback hosts, integer or hex IPv4, unbracketed zones, a protocol-relative `//plainname` (unchanged known limits).
- All-caps or mixed-case letters-only tokens matched case-sensitively (C3 R3-1); short loopback forms behind an undecoded escape (CR3-6); `<password value='member'/>`, `the password "is" member` and `<password><string>` (CR3-7, CR2-5's other shapes).
- The `isolate.py` follow-ups, and any change to `findings.py`, `contracts/` or `CHANGELOG.md`.
- Ticking `docs/sdlc/todo.md` (the owner does that).
