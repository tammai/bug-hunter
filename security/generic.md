# Security checklist: any web backend or app

Work through each item that fits the code. Each line: what to look for, and the CWE to cite.

## Authorization (category `authz`)
- **IDOR:** an id from the request (`/orders/:id`, `?userId=`, a body field) loads or changes a record with no check that it belongs to the caller. CWE-639.
- **Missing role check:** admin or staff actions (users, refunds, exports, settings) reachable by any logged-in user, or by anyone. CWE-862 (missing), CWE-863 (incorrect).
- Checks done only in the client, or only on the list route but not the detail or update route.
- Mass assignment: the request body written straight to the model, so a user sets `role`, `isAdmin`, `ownerId` or `price`. CWE-915.

## Injection (category `injection`)
- **SQL injection:** queries built with string concatenation or template strings from input; raw-query escape hatches in ORMs. CWE-89.
- NoSQL operator injection: a request object passed as a query (`{ "$ne": null }`). CWE-943.
- **Command injection:** input reaching `exec`, `spawn` with `shell: true`, `system`, or backticks. CWE-78.
- **Path traversal:** input in a file path for reads, writes, uploads or downloads (`../`). CWE-22.
- **SSRF:** a URL from input fetched by the server (webhooks, image proxies, imports). CWE-918.
- Template or HTML injection: unescaped input rendered as HTML. CWE-79.

## Secrets and config (categories `secrets`, `config`)
- A secret in source, config or a committed `.env` (the secrets scan covers patterns; you look for the rest: hard-coded passwords, signing keys, default admin credentials). CWE-798.
- Debug mode, stack traces or verbose **error** responses in production config; errors that echo queries or internals. CWE-209.
- **CORS:** `Access-Control-Allow-Origin: *` with credentials, or an origin reflected from the request. CWE-942.
- Missing security headers or cookies without `Secure` / `HttpOnly` / `SameSite` on session cookies. CWE-614.

## Session and auth (category `session`)
- Tokens that never expire, sessions not invalidated on logout or password change. CWE-613.
- Password reset or email tokens that are guessable, reusable or don't expire. CWE-640.
- No **rate limit** on login, signup, password reset, OTP or other expensive endpoints. CWE-307.
- Passwords hashed with a fast hash (MD5, SHA-1, plain SHA-256) or not at all. CWE-916.
- Missing CSRF protection on cookie-authenticated state changes. CWE-352.

## A04 Cryptographic Failures
- **Weak or home-made crypto:** DES, 3DES, RC4, ECB mode, MD5 or SHA-1 for signatures or integrity, RSA with PKCS#1 v1.5 padding or keys under 2048 bits, or hand-written "encryption" (XOR, base64, a custom cipher). CWE-327, CWE-326.
- **Static keys, IVs and nonces:** an IV or nonce that is a constant, a counter reset on restart, or reused with the same key (breaks CBC and GCM); an encryption key derived from a short string or stored beside the data it protects. CWE-329, CWE-323, CWE-321.
- **Predictable randomness for secrets:** tokens, reset links, API keys, session ids or salts from `Math.random`, `rand`, `random`, time or a counter instead of the platform's secure random source. CWE-338, CWE-330.
- **Cleartext in transit:** `http://` URLs, `ftp`, `smtp` without TLS or database connections with TLS off for services carrying credentials or personal data; TLS certificate or hostname checks switched off in a client. CWE-319.
- **Unprotected sensitive data at rest:** passwords, card numbers, health data or tokens stored in plain text columns, files or backups, or in a reversible form where a one-way hash would do (this adds to the fast-hash item above, which covers how passwords are hashed; here, whether they are hashed or encrypted at all), or hashed with no per-user salt. CWE-261, CWE-759.

## A06 Insecure Design
- **No limit on a costly or abusable action:** coupon or gift-card redemption, free-trial signup, SMS or email sending, search export or report generation with no per-user cap, quota or cost guard (rate limits on login are covered above). CWE-799.
- **Business-logic trust in the client:** price, discount, quantity, currency, shipping cost or "step completed" flags taken from the request instead of recomputed on the server; negative quantities or amounts accepted. CWE-602, CWE-841.
- **Skippable multi-step flows:** checkout, email verification, MFA enrolment or approval flows where the last step can be called without the earlier ones, or where state lives in a hidden field or a client-held token. CWE-841.
- **Check-then-act races:** balance, stock, one-time code or coupon read, checked, then updated in separate statements with no transaction, row lock or unique constraint, so parallel requests all pass. CWE-362.
- **Unsafe uploads and sensitive features by design:** accepting executable or active content (`.html`, `.svg`, `.php`, scripts) from users and serving it from the app's own origin, or letting user content reach admin-only views. CWE-434.
- **Sensitive responses cached:** pages or API responses carrying personal data or tokens sent without `Cache-Control: no-store` (or `private`), so a shared proxy, CDN or the browser's back button keeps them. CWE-525.

## A07 Authentication Failures
- **Weak password policy:** no minimum length, accepting trivial or breached passwords, forced composition rules that push predictable choices, or a hard cap that truncates long passphrases. CWE-521.
- **Default or hard-coded credentials:** seeded admin accounts, `admin/admin` in fixtures or migrations, a shared service password in config, backdoor "master" passwords or debug login bypass flags. CWE-798, CWE-259.
- **Credential stuffing and enumeration:** different responses, status codes or timings for "unknown user" and "wrong password"; signup or reset endpoints that confirm which emails exist; no lockout, delay or captcha after repeated failures (the rate limit item above covers the missing limit; here, what the response reveals and whether failures are slowed). CWE-307.
- **Session identifiers handled badly:** session id not changed at login (fixation), accepted from the URL, or still valid after logout; the same token accepted on another account or tenant. CWE-384, CWE-613.
- **MFA and recovery bypass:** a second factor checked only on one route or client-side, OTP codes that can be brute-forced or reused, "remember this device" cookies that are unsigned, recovery that skips MFA. CWE-287, CWE-308.
- **Password change and reset flaws:** changing the password or email without asking for the current password, reset that leaves existing sessions and tokens valid, or a reset link that logs the user in without further proof. CWE-620, CWE-640.

## A08 Software or Data Integrity Failures
- **Deserializing untrusted data:** native object formats (Java `ObjectInputStream`, Python `pickle`, PHP `unserialize`, .NET `BinaryFormatter`, Ruby `Marshal`, YAML with arbitrary types) applied to requests, cookies, queue messages, cache entries or uploaded files. CWE-502.
- **Unsigned or unverified updates and artifacts:** code, plugins, templates, models or config downloaded and run or loaded with no signature, checksum or pinned hash; `curl | sh` in install or CI steps; auto-update that trusts a plain-HTTP source. CWE-494, CWE-829.
- **Scripts from outside without integrity:** `<script src>` or `<link>` to a CDN without `integrity`, or build steps that pull a moving `latest` tag. CWE-830, CWE-353.
- **Webhooks and callbacks not authenticated:** payment, Git or SaaS webhooks accepted with no signature check (HMAC) or with a non-constant-time compare, or a signature checked over a re-serialized body rather than the raw one. CWE-345.
- **Client-controlled state trusted:** a cookie, hidden field or JWT body holding a role, price or ownership flag that is read without a signature check or with a signature the client can skip. CWE-565, CWE-345.
- **Dynamic code from data:** loading classes, modules or plugins by a name taken from input or from a user-writable path or directory. CWE-426, CWE-427.

## A09 Security Logging and Alerting Failures
- **Sensitive data in logs:** passwords, tokens, session ids, card numbers, national ids or whole request and response bodies written to logs or traces (PII angle is in the PII checklist; here, secrets and credentials). CWE-532.
- **Log injection:** user input written to a log line (usernames, user agents, paths) with no newline or control-character neutralizing, so an attacker forges entries or breaks parsers. CWE-117.
- **No record of security events:** failed logins, permission denials, password or role changes, exports, admin actions and token revocations not logged at all, or logged with no user id, source address and time. CWE-778.
- **Logs that can't be trusted or reached:** audit logs writable by the app user it describes, stored only on the same host or container, deletable by the application, or shown in an unauthenticated admin page. CWE-532, CWE-778.
- **Silent security failures:** a catch block or fallback that swallows an auth, signature or validation error with no log and no alert, or an alert path (email, webhook) that was never wired up. CWE-778.

## A10 Mishandling of Exceptional Conditions
- **Fail-open handlers:** `catch` or error branches in auth, permission, signature or payment checks that continue as success (or return `true`) when the check itself throws or times out. CWE-755, CWE-636.
- **Ignored return values and errors:** results of permission checks, password verification, file writes, or crypto calls discarded; `_ = err`, `except: pass`, empty `catch {}`. CWE-252, CWE-390, CWE-391.
- **Overly broad catches:** `catch (Exception)`, `except Exception`, `recover()` or `catch {}` around large blocks so unrelated failures (a `NullPointerException`, a denied lookup) are treated as normal flow or hide state left half-updated. CWE-396, CWE-397, CWE-248.
- **Null and missing-value assumptions:** values from lookups, headers, session or optional claims used without a check (`user.profile.id`, `req.user!.id`), so a missing value crashes the request or compares as equal to another missing value. CWE-476.
- **Crash on bad input:** parsers, indexing, casts and unchecked unwraps on request data where one malformed request raises an unhandled error that kills a worker or the process, or leaves locks and transactions open. CWE-754, CWE-703.
- **Error output to the client:** stack traces, SQL text, file paths or framework debug pages in responses (the config section above covers debug mode; here, the error handler itself). CWE-209, CWE-215.

## Severity
- **critical:** unauthenticated access to other users' data or admin actions; remote code execution; a live production secret.
- **high:** authenticated IDOR or missing role check on sensitive data; SQL, command or path injection; SSRF to internal hosts; auth bypass.
- **medium:** personal data logged or sent to a third party without need; weak session handling; CORS misconfiguration; findings that rest on an assumed policy.
- **low:** hardening gaps with no direct exploit: missing headers, verbose errors, placeholder secrets in fixtures.
