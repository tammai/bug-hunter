# Leak-check follow-ups: word-like logins, upper-cased escapes, other address spellings, default ports

## Why

**Request (verbatim):** C3 from docs/sdlc/plan-week-2026-11-23.md: leak-check follow-ups. Clears todo items "Leak check for word-like logins" (M-2: a word after a second word between field and value is missed; L-2: lowercase-only random token of 6–15 letters treated as a word) and from "Leak scan known limits": R6-1 (upper-cased escapes \X2F, \U002F not decoded), R6-2 (other spellings of one address: expanded/zero-padded IPv6, 10.0.0.01, 127.1, 0.0.0.0), C4-7 (localhost:80 for a portless loopback target). High risk: stop for approval before Build and for the review choice.

`drafts.py check` is the last gate before a live-mode draft becomes a public GitHub issue (`/hunt-post`). Each item here is a draft that passes the gate while it still names the owner's dev or UAT host, or holds an account's login. The plan ranked these as real leaks, unlike the over-refusals that were closed as "the safe side".

**The user's words:** none asked. The plan (2026-11-20, owner's OK) put these five items in C3 and closed the other leak-scan limits as won't-fix.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| **M-2:** `_holds_login`'s field match also takes (a) after the field's punctuation, one optional `value` key or attribute and its punctuation (`name="password" value="member"`, `{"name":"token","value":"member"}`), and (b) prose `<field> is <value>` or `<field> was <value>` (`the password is member`) | any number of words or fields in between | `{"token": "x", "role": "member"}` is an ordinary draft. Allowing anything between the field and the value would refuse it. `value` is the one key that pairs with a `name` key in markup and in name/value JSON |
| **L-2:** a lowercase piece counts as a word only if none of its letter pairs is a rare English pair. The rare pairs are an embedded constant, generated once from `/usr/share/dict/words` (pairs below a frequency of 1e-4) | vowel or consonant-run rules; shipping or reading a dictionary | Measured on 20,000 random tokens: about 2% of 10-letter tokens and 0.2% of 15-letter tokens still pass as words. A consonant-run rule lets 21% of 10-letter tokens through. About 5% of dictionary words read as random, which means they count anywhere (the safe side). `/usr/share/dict` isn't on every OS |
| **R6-1:** `HEX_ESCAPE` takes `\x` and `\X`; `_json_unescaped` decodes `\u` and `\U` followed by 4 hex digits | — | A JSON parser rejects `\U`, but decoding more spellings only ever adds refusals |
| **R6-2, IPv4:** a zero-padded spelling of the target's IPv4 address matches (`0*10\.0*0\.0*0\.0*1(?!\d)`). As now, there is no left boundary | short forms (`10.1`) for non-loopback targets; integer or hex IPv4 | Version numbers like `10.1` would be refused. The ticket names only padded forms for non-loopback hosts |
| **R6-2, IPv6:** runs that look like IPv6 are parsed with `ipaddress` and compared to the target (expanded, zero-padded, compressed and IPv4-mapped forms compare equal). Every suffix of a run is tried, so a hex letter in front can't hide the address | a regex for every compression | The `::` compressions can't be listed by regex. Trying suffixes keeps the "no left boundary" rule of `_host_patterns` |
| **R6-2, loopback:** loopback aliases also match `127.1`, `127.0.1`, zero-padded `127.0.0.1`, any IPv6 spelling of `::1`, and `0.0.0.0` | `::` and a bare `0` | `std::vector` and prose would refuse. Neither is named in the ticket |
| **C4-7:** a loopback target's effective port is its port or the scheme's default (80 or 443). It matches as `alias:<port>`. When the effective port is 80 or 443 it also matches as a scheme, then the alias, then no port (`http://localhost/x`) | treating `http://localhost` with no port as harmless | That is the same address as `localhost:80`, which drafts write too |

**Proposals not asked for:** decoding Python's 8-digit `\U0000002F` escape (same class as R6-1); dropped unless kept.

## Acceptance criteria

- **AC-001** Given an account whose login is a word (`Bearer member`), when a draft holds `<input name="password" value="member">`, `{"name":"token","value":"member"}` or `the password is member`, then `leaks` reports that account's login, while `{"token": "x", "role": "member"}` and the prose already allowed ("Author: a member") report nothing.
- **AC-002** Given an account whose login is a lowercase random token (`Bearer qwxzkvbnmt`), when a draft holds that token alone in prose, then `leaks` reports it, while a word login (`member`, `admin1`, `editor`) alone in prose still reports nothing.
- **AC-003** Given a target `http://ref` (a plain name with no port, so only its URL form names it), when a draft writes its address with upper-cased escapes (`http:\X2F\X2Fref/x`, `http:\U002F\U002Fref/x`), then `leaks` reports the host.
- **AC-004** Given a target at `http://10.0.0.1:8080`, when a draft holds `10.0.0.01` or `010.000.000.001`, then `leaks` reports the host, while `10.0.0.12` reports nothing.
- **AC-005** Given a target at `http://[2001:db8::1]:8080`, when a draft holds `2001:0db8:0:0:0:0:0:1`, `[2001:db8:0::0001]` or `2001:db8::1` after a hex letter (`a2001:db8::1`), then `leaks` reports the host, while `2001:db8::12` reports nothing.
- **AC-006** Given a loopback target `http://127.0.0.1:5000`, when a draft holds `127.1:5000`, `127.000.000.001:5000`, `[0:0:0:0:0:0:0:1]:5000` or `0.0.0.0:5000`, then `leaks` reports the host, while `127.0.0.1:50003` and `127.1:5001` report nothing.
- **AC-007** Given a loopback target with no port (`http://localhost`), when a draft holds `localhost:80`, then `leaks` reports the host. Given `http://localhost:80`, `http://localhost/api` is reported. Given `http://localhost:3000`, `http://localhost/api` reports nothing.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_drafts.py › test_word_login_after_a_value_key_or_is_is_a_credential | `uv run pytest tests/test_drafts.py::test_word_login_after_a_value_key_or_is_is_a_credential` |
| AC-002 | tests/test_drafts.py › test_lowercase_random_token_login_counts_anywhere | `uv run pytest tests/test_drafts.py::test_lowercase_random_token_login_counts_anywhere` |
| AC-003 | tests/test_drafts.py › test_host_behind_upper_cased_escapes_is_found | `uv run pytest tests/test_drafts.py::test_host_behind_upper_cased_escapes_is_found` |
| AC-004 | tests/test_drafts.py › test_zero_padded_ipv4_host_is_found | `uv run pytest tests/test_drafts.py::test_zero_padded_ipv4_host_is_found` |
| AC-005 | tests/test_drafts.py › test_other_spellings_of_an_ipv6_host_are_found | `uv run pytest tests/test_drafts.py::test_other_spellings_of_an_ipv6_host_are_found` |
| AC-006 | tests/test_drafts.py › test_other_loopback_spellings_with_the_port_are_found | `uv run pytest tests/test_drafts.py::test_other_loopback_spellings_with_the_port_are_found` |
| AC-007 | tests/test_drafts.py › test_default_port_loopback_target_is_found_either_way | `uv run pytest tests/test_drafts.py::test_default_port_loopback_target_is_found_either_way` |

## Must never break

- Every case in `test_live_drafts_hide_host_and_credentials` and `test_login_value_that_is_a_common_word_only_counts_as_a_credential` keeps its result: the placeholders a draft is told to write (`$BASE`, `$MEMBER_AUTH`, `ACCEPT_ACCOUNT_MEMBER`) and the allowed prose stay clean.
- The scan stays linear on hostile drafts (`tests/test_drafts_scan_time.py`): possessive runs, no new nested quantifier that backtracks (drafts and echoed responses are untrusted, see the comment in `_holds_login`). A 1 MB draft of `authauth…`, `:::…` or digits and dots is checked in about the same time as today.
- `leaks` never echoes the host or the login in its messages.

## Failure modes

- Untrusted input (a hunter's draft quoting a hostile response): long runs of colons, hex or digits fed to the IPv6 run finder and `ipaddress` → must-never-break (linear time). Runs are capped in length, and `ipaddress` errors are caught as "not an address", never a traceback.
- Over-refusal: each new spelling may refuse an ordinary draft. Each AC has a clean counter-example, and the existing allowed prose is a must-never-break line.
- Concurrency, persisted data, deploy and rollback: none apply (a pure function over text).

## Out of scope

- C4-6 (one source of truth for addresses between `_host_patterns` and `live_proxy._masker`). The masker is left as it is, so the scan still catches more than it masks.
- C4-8 (prefixes cut by the 500-character cap), trailing-dot hosts, S-5 (8.3 spec paths and folder links): still open in `todo.md`.
- Short IPv4 forms for non-loopback hosts, integer or hex IPv4, `::` and a bare `0` (see Decisions).
- The `isolate.py` follow-ups.

## Review

- **Recommended and chosen:** security + code, because `Risk: high` (secrets and hosts into public issue drafts) fired both rows; chosen by the user.
- **Verdicts:** round 1 → `.sdlc/.work/findings/2026-11-22-m-leak-check-followups/security-r1.md` FAIL (S1–S4; S5 confirmed by repro), `code-reviewer-r1.md` FAIL (C1–C4). Round 2 → `security-r2.md` FAIL (R2-5), `code-reviewer-r2.md` (built-in `code-review`, rated by the orchestrator) FAIL (CR2-1–CR2-3). Round 3 (one more round, the user's choice at the cap) → `security-r3.md` PASS, `code-reviewer-r3.md` FAIL (CR3-1, CR3-2). Round 4 (the user's choice at the cap) → `code-reviewer-r4.md` FAIL (CR4-1 high; CR4-2, CR4-4 medium). Round 4 waived by the user: its three findings are folded into 2026-11-22-m-leak-scan-limits, which is built on this change and ships right after it.
- **Fixed:**
  - S1/C1: an IPv4-mapped or zoned IPv6 target crashed `leaks` with a traceback printing the host; groups now come from `int(address)`, zones are dropped, mapped targets also get their IPv4 patterns (`test_mapped_and_zoned_ipv6_targets_are_checked_not_crashed`).
  - S2/C8: IPv6 spellings with a dotted IPv4 tail (`test_ipv6_spellings_with_a_dotted_ipv4_tail_are_found`).
  - S3, CR2-7: letters-only random tokens of any length match in any case (`test_random_token_login_is_found_in_any_case`, `test_long_random_token_login_is_found_in_any_case`).
  - S4/C2, C4, C6, R2-6, R2-7, CR3-3: login context after `is:`/`was`, `value` only as a key or element, prose limited to credential names, two-word fields, no crossing a full stop or an empty value (`test_word_login_after_is_with_punctuation_or_a_value_word`, `test_word_login_after_two_word_fields_and_a_value_element`, `test_is_and_an_empty_value_do_not_reach_the_next_words`).
  - S5, CR2-3: quadratic scheme prefix and a 5–9x slowdown on hostile runs; the scheme starts only at its run's start and IPv6 spellings render as one prefix-shared tree (`tests/test_drafts_scan_time.py`; 1 MB hostile runs about 2–3x base, linear).
  - C3: short loopback forms bounded so they don't match inside other addresses (`test_short_loopback_forms_do_not_match_inside_other_addresses`).
  - C9, CR2-2/R2-5, CR3-2, R3-3: a port-less loopback URL follows the draft's scheme (80: http/ws, 443: https/wss), compound schemes, ws/wss targets' default ports (`test_a_url_without_a_port_follows_the_drafts_scheme`, `test_a_compound_scheme_without_a_port_is_found`, `test_a_websocket_loopback_target_has_a_default_port`).
  - CR2-1/R2-1: a mapped loopback target keeps its port (`test_mapped_loopback_target_keeps_its_port`).
  - CR3-1: an account's own placeholders are blanked before the anywhere-match (`test_placeholder_named_after_a_random_looking_login_is_clean`).
- **Tickets:** carried by 2026-11-22-m-leak-scan-limits: CR4-1 (a literal http/ws prefix behind the scheme lookbehind misses `...http://localhost`), CR4-2, CR4-4, CR4-3, CR4-5, CR3-4–CR3-9, S6–S8, C5, C7, CR2-4–CR2-6, R2-2–R2-4, R2-8, R2-9, R3-1, R3-4 (zero runs about 3x base, linear).
- **Drift and manual checks:** every Deviations line in `.sdlc/state/2026-11-22-m-leak-check-followups.md`: AC-003's target has no port; the timing test file; the review-fix test file; IPv6 by an enumerating (then tree) regex instead of `ipaddress` parsing (this file's R6-2 Decision row still says parsing); the 2–3x constant on colon runs; round 1's code review ran as `sdlc:code-reviewer`; rounds 3 and 4 fixes; the round-4 waiver. No manual ACs.
- **Security:** no dependency change (stdlib only), so no dependency audit; no secrets in the diff.
- **Lessons filed:** `docs/sdlc/recurring-defects.md` (a boundary added to a leak matcher to cut over-refusal or cost hides a value behind a prefix).

