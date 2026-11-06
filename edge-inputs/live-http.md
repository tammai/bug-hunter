# Edge inputs: a running HTTP server (dev or UAT)

Use with the other lists when `/hunt --target` hunts a running server. Read the route, its validation and its handler in the code first, then send the request through the proxy. Each line: what to send, and the bug it tends to find.

**How to try them:** `curl -sS -i "$BASE/<path>" -H "$ALICE_AUTH" …`, where `BASE` is the proxy URL and each `<ACCOUNT>_AUTH` logs in as that account. Send requests to the proxy only. Writes need a target that allows them; a 403 from the proxy means it doesn't.

## Who is asking
- **Missing credentials:** no auth header on a route the code protects. Look for 200 with data, or a 500 instead of 401.
- **Expired or invented credentials** (`-H "Authorization: Bearer invented"`): 500, a stack trace, or a guest session that still sees data.
- **Another account's credentials:** call alice's resource as bob. Look for 200 instead of 403 or 404.
- **Another user's IDs (IDOR):** change an ID in the path, query or body (`/orders/7` to `/orders/8`, `"userId"`) to one the account doesn't own.

## What the body holds
- **Missing field, extra field, wrong type, null:** drop a required field, add one the model doesn't expect (`"role": "admin"`, `"price": 0`), send `"qty": "3"` or `null`. Look for a 500, a silent default, or an extra field that gets stored (mass assignment).
- **Malformed JSON** (a trailing comma, a cut-off body, `{}` vs `[]`) and the **wrong Content-Type** (JSON sent as `text/plain` or form): 500 instead of 400, or the body silently ignored.
- **Boundary and negative numbers:** 0, -1, the type's max and max+1, `1e309`, decimals where integers are expected. Look for negative totals, overflow, or rounding that loses money.
- **Unicode and long strings:** emoji, combining marks, right-to-left text, NUL, a 10 KB name. Look for 500, truncation that cuts a character in half, or a different length check on the client and the server.

## How it's asked
- **Pagination bounds:** `page=0`, `page=-1`, a page past the end, `limit=0`, `limit=100000`. Look for 500, duplicates across pages, or every row returned at once.
- **Double submit:** send the same create or pay request twice quickly, or with the same idempotency key. Look for two records or two charges.
- **A method the route doesn't allow** (`PUT` on a `GET` route, `OPTIONS`): 500 instead of 405, or a write that succeeds.
- **Trailing slash and case:** `/api/orders/` vs `/api/orders`, `/API/Orders`. Look for a route that skips its auth middleware in one form.

## What comes back
- **Error bodies that leak internals:** a stack trace, SQL text, file paths, framework versions or another user's data in a 4xx or 5xx body.
- **Wrong status for the outcome:** 200 with `{"error": …}`, 201 for nothing created, 500 for bad input.
