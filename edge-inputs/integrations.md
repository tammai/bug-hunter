# Edge inputs: calls to third-party services

Use with the other lists, for code that calls an HTTP API or a vendor SDK (payments, email, SMS, storage, auth, AI). Each line: what the service can do, and the bug it tends to find.

**How to try them, offline:**
- **Start the stub.** Run `<PLUGIN>/scripts/stub_server.py` in the copy with a scenario file. It answers on 127.0.0.1 with the statuses, delays, bodies and dropped connections you script, and logs every request it got. The log is the evidence: "the client sent the charge twice", "it never retried".
- **Point the code at it** through the code's own configuration: a base URL in env or config, or a client built in a small driver script. Never the real service.
- **If the URL can't be changed,** use the project's own installed mocking library (nock, msw, responses, httptest). Without one, mark the suspect "couldn't reproduce".

## Slow and silent
- **No timeout:** a slow response (`"delay": 30`) hangs the request, a worker or the whole event loop. Look for clients created without a timeout.
- **A timeout longer than the caller's own:** the user's request times out first, while the call carries on and still has its effect.
- **Connection refused** (nothing listening), a **connection reset** (`"reset": true`), a connection closed before any response (`"close": true`), or a body cut off mid-way (`"truncate": <bytes>`): an unhandled exception crashes the process, or the error turns into success.

## Errors the service is allowed to send
- **429** with `Retry-After`: no retry at all, a retry that ignores `Retry-After`, or retries with no limit or backoff that make the rate limit worse.
- **5xx** (500, 502, 503, 504): treated as success, retried forever, or surfaced to the user as a raw stack trace.
- A **4xx** body the code doesn't expect (validation errors, `{"error": {...}}` with a different shape): a crash while reading `response.data.result`.

## Bodies that aren't what the code assumes
- **Malformed JSON**, a **partial** or truncated body, an **empty** body with 200, or 204 where JSON was expected.
- An **HTML** error page (a proxy's 502 page, a login redirect) with status 200 or a JSON content type: the parse error isn't handled.
- Fields missing, `null`, or of another type (a number as a string, an id as a number), extra unknown fields, very large payloads.
- **Pagination:** the last page, an empty page, a cursor that repeats, `has_more` that's missing: infinite loops or dropped items.

## Retries and duplicates
- **Retries that aren't idempotent:** a timeout after the service already acted, then a retry, so the user is charged, emailed or created twice. Check for idempotency keys on retried POSTs.
- **Expired token:** a 401 mid-flow. The refresh isn't attempted, is attempted in a loop, or two concurrent refreshes race.

## Webhooks the code receives
- **Duplicate delivery** of the same event: the handler isn't idempotent, so an order is fulfilled or a refund issued twice. Call the handler twice with the same event id.
- **Out of order:** `updated` arrives before `created`, or `refunded` before `paid`. The state machine goes wrong.
- **Signature** not verified, verified with a non-constant-time compare, or verified on a re-serialized body instead of the raw bytes. Old timestamps are accepted (replay).
- The handler does slow work before answering, so the sender times out and retries, which causes duplicates.

## Failure handling around the call
- **Swallowed errors:** `catch {}` or a logged-and-ignored failure, then the code reports success or saves "sent" state.
- Partial batch failure: some items succeed, the batch reports all succeeded or retries all of them.
- No circuit breaker or fallback: one slow dependency takes every request down with it.
- Clock skew between the code and the service (token expiry, signed URLs, webhook timestamps).
