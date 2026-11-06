# Security checklist: Vue frontends

Use with the generic and PII checklists. A frontend can't enforce anything: every check here must also exist on the server, and a check that exists *only* here is a finding against the backend.

- **`v-html`** (and `innerHTML`, `insertAdjacentHTML`) with data from the API, the URL or user input: XSS. CWE-79. Also check `marked`, `markdown-it` or other renderers whose output feeds `v-html` without sanitizing.
- **Secrets in the bundle:** everything under `VITE_*`, `VUE_APP_*` or `import.meta.env` is shipped to every visitor. An API secret, a service-account key or a private token there is a finding (`secrets`, CWE-798); a public key or site key is not.
- **Tokens in `localStorage` or `sessionStorage`:** readable by any XSS. Prefer `HttpOnly` cookies (`session`, CWE-922).
- **Route guards** (`router.beforeEach`, `meta.requiresAuth`, role checks in components) as the only protection for admin pages or data. Find the API calls those pages make and check the backend enforces the same rule.
- **Open redirect:** `router.push(route.query.redirect)`, `window.location = ...` with a value from the URL, with no check that it's a same-site path. CWE-601.
- Personal data kept in the store or `localStorage` after logout, or sent to analytics, error tracking (Sentry and the like) or chat widgets in event payloads (`pii-third-party`).
- `postMessage` listeners that don't check `event.origin`; `target="_blank"` links to user-supplied URLs without `rel="noopener"`.
