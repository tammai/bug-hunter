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

## Severity
- **critical:** unauthenticated access to other users' data or admin actions; remote code execution; a live production secret.
- **high:** authenticated IDOR or missing role check on sensitive data; SQL, command or path injection; SSRF to internal hosts; auth bypass.
- **medium:** personal data logged or sent to a third party without need; weak session handling; CORS misconfiguration; findings that rest on an assumed policy.
- **low:** hardening gaps with no direct exploit: missing headers, verbose errors, placeholder secrets in fixtures.
