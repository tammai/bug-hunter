# Security checklist: React frontends (JSX, Next.js)

Use with the generic and PII checklists. A frontend can't enforce anything: every check here must also exist on the server, and a check that exists *only* here is a finding against the backend.

## Rendering and XSS
- **`dangerouslySetInnerHTML`** with a value from an API response, the URL, `localStorage` or user input, and no sanitizer (DOMPurify or similar) between them. Also trace markdown, rich-text or CMS renderers (`marked`, `react-markdown` with `rehype-raw`) whose HTML output ends up there. React escapes text for you; this prop turns that off. CWE-79.
- **`href` or `src` built from data:** `<a href={user.website}>`, `<iframe src={url}>`, `<form action={url}>` or `window.open(url)` where the value could be `javascript:` or `data:`. React only warns about `javascript:` URLs before version 19, and nothing covers `window.location` or `window.open`. Allow only `http:`, `https:` and relative paths. CWE-79.
- **Direct DOM writes:** `ref.current.innerHTML = ...`, `document.write`, `insertAdjacentHTML`, `eval` or `new Function` on strings from props, state, or the URL. These skip React's escaping. CWE-79 (CWE-94 for `eval`).
- **Server-rendered state in HTML:** `<script>window.__STATE__ = ${JSON.stringify(data)}</script>` or similar hand-rolled hydration without escaping `<` (a value of `</script>` ends the tag). Use a serializer that escapes it. CWE-79.
- **Props spread from data:** `<Component {...userObject} />` or `React.createElement(type, props)` where `type` or `props` (including `dangerouslySetInnerHTML`, `href`) come from the API or the URL. The data picks the element or its attributes. CWE-79.

## Secrets and storage
- **Secrets in the bundle:** every `NEXT_PUBLIC_*`, `REACT_APP_*`, `VITE_*` or `import.meta.env` value (and anything in `next.config.js` `env`) is shipped to every visitor. An API secret, service-account key, database URL or private token there is a finding (`secrets`, CWE-798); a public key or site key is not. Also check committed `.env.production` files.
- **Tokens in `localStorage` or `sessionStorage`:** a JWT or refresh token stored there is readable by any XSS or compromised script. Prefer `HttpOnly`, `Secure`, `SameSite` cookies set by the server. CWE-922.
- Personal data left in Redux, Zustand, React Query caches, `localStorage` or the URL after logout; query strings holding emails, tokens or ids that then reach analytics, `Referer` headers or browser history (`pii-storage`, `pii-third-party`). CWE-200.
- Error tracking and analytics (Sentry, LogRocket, Hotjar, Segment) capturing form values, full state or request bodies with passwords, card numbers or health data; session replay without masking inputs (`pii-third-party`). CWE-359.

## Routing and access
- **Client-only route guards:** a `<ProtectedRoute>`, `useEffect` redirect, `if (!user) return null`, or a hidden menu item as the only protection for admin pages or data. The page code still ships to everyone and the API is callable directly. Find the API calls and check the backend enforces the rule. CWE-602, CWE-862.
- **Open redirect:** `router.push(searchParams.get('next'))`, `navigate(redirectTo)`, `window.location.href = query.returnUrl`, `redirect(url)` in Next.js with a value from the URL, with no check that it is a same-site relative path (watch for `//evil.com` and `/\evil.com`). CWE-601.
- **Roles from the client:** `user.role === 'admin'` read from a token body that is decoded but not verified, from `localStorage`, or from a cookie the user can edit, and then used to decide what the server returns. CWE-639, CWE-863.
- **`postMessage`:** `window.addEventListener('message', ...)` handlers that don't check `event.origin` against an exact value, or `postMessage(data, '*')` carrying tokens or personal data. CWE-346.

## Next.js server code
- **SSR data leaks:** `getServerSideProps`, `getStaticProps`, `loader` functions and server components returning a whole database row, user object or session (password hashes, tokens, emails of other users, internal flags) when the page uses two fields. Props are serialized into the HTML and `__NEXT_DATA__`. CWE-200.
- **API routes and route handlers without auth:** files under `pages/api/` or `app/**/route.ts` that read `req.query.id` or `req.body` and touch data with no session check and no ownership check. Each exported `GET`, `POST`, `PUT`, `DELETE` handler needs its own. CWE-862, CWE-639.
- **Server actions without auth:** functions marked `'use server'` are public POST endpoints; ones that take an id or fields from the client and write data without checking the session, the owner and the input shape are directly callable. Also actions that import secrets and return them. CWE-862, CWE-20.
- **Middleware as the only guard:** `middleware.ts` matchers that protect `/admin` but miss `/api/admin`, `/_next/data/...` or trailing-slash and locale variants, with no re-check in the handler or data layer. CWE-863.
- **Image and fetch proxies:** `next/image` `remotePatterns` or `domains` set to a wildcard, or a route handler that `fetch`es a URL from the query (SSRF). CWE-918.
- **CSRF on cookie auth:** route handlers or server actions that change state on `GET`, or `pages/api` endpoints using cookie sessions with no token or `SameSite` protection and no `Origin` check. CWE-352.

## Third-party code and links
- **Third-party scripts:** `<script src="https://...">` or `next/script` pulling tag managers, chat widgets or CDNs without `integrity` (SRI) and `crossorigin`, loaded on pages that show account or payment data. They run with full access to the page. CWE-829, CWE-353.
- **`target="_blank"`** links to user-supplied URLs without `rel="noopener noreferrer"` in older browsers or custom `window.open` calls (reverse tabnabbing). CWE-1022.
- **Dependencies:** packages with known advisories, or `postinstall` scripts, copied snippets from forums; check with the lockfile audit. CWE-1104.

Sources: React documentation on `dangerouslySetInnerHTML` and escaping (https://react.dev/reference/react-dom/components/common), the Next.js documentation on data security, authentication, server actions and Content Security Policy (https://nextjs.org/docs/app/guides/data-security), the OWASP Cross Site Scripting Prevention, DOM based XSS Prevention, HTML5 Security, Content Security Policy, Unvalidated Redirects and Forwards, and Third Party Javascript Management cheat sheets (https://cheatsheetseries.owasp.org/).
