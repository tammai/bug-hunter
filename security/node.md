# Security checklist: Node backends (Express, Fastify, Nest, Koa)

Use with the generic and PII checklists.

## Authorization
- `req.params.id`, `req.query`, `req.body` ids passed to `findById`, `findOne`, `update` or `delete` with no `where: { userId: req.user.id }` or ownership check. Look at the service and repository layer too: the route may look fine.
- **Middleware order:** `app.use(auth)` registered after the routes it should cover, a router mounted before the auth middleware, or a route defined on `app` that skips a router-level guard. In Nest, a controller missing `@UseGuards` while siblings have it; `@Public()` on the wrong handler.
- Role checks that compare strings loosely, read the role from the request body or a client-set header, or trust a JWT claim without verifying the signature.

## Tokens and sessions
- JWT: `jwt.decode` used where `jwt.verify` is needed; `verify` without pinning `algorithms` (the `alg: none` and HS/RS confusion attacks); a hard-coded or default signing secret; no `exp`.
- `express-session` with the default `MemoryStore`, a hard-coded `secret`, or cookies without `secure` / `httpOnly`.

## Injection and code execution
- `eval(`, `new Function(`, `vm.runInNewContext`, or `child_process.exec` with request data.
- Sequelize, Knex, TypeORM or Prisma raw queries (`$queryRawUnsafe`, `sequelize.query` with template strings, `knex.raw` with concatenation).
- Mongo/Mongoose queries built from `req.body` objects (operator injection).
- **Prototype pollution:** deep merges of request data (`_.merge`, `Object.assign` on nested input, custom `deepMerge`), or `obj[key] = value` with `key` from input (`__proto__`, `constructor`).
- **ReDoS:** regexes with nested quantifiers (`(a+)+`, `(.*)*`) run on request input.
- `res.redirect(req.query.next)` and similar open redirects; `res.sendFile` or `path.join` with input (traversal); `fetch(req.body.url)` (SSRF).

## Logging and errors
- `console.log(req.body)`, `logger.info({ user })`, or logging whole request or response objects, which writes passwords, tokens and personal data to logs.
- Error handlers that send `err.stack` or `err.message` from the database to the client.

## Uploads, headers and outbound calls
- **File uploads:** `multer` (or `busboy`, `formidable`, `express-fileupload`) with no `limits.fileSize` or `fileFilter`, a stored name taken from `file.originalname`, or uploads saved under a served static directory. Users can upload scripts or huge files, or overwrite other files. CWE-434.
- **Process spawning:** `child_process.exec` or `execSync` building a shell string, where `execFile` or `spawn` with an argument array and no `shell: true` would avoid the shell. Also an `execFile` call whose first argument comes from input, or arguments starting with `-` that the target program reads as options. CWE-78.
- **No security headers:** an Express app with no `helmet()` (or equivalent header middleware in Fastify and Nest), no `x-powered-by` removal and no CSP on pages that render user content. Hardening gap, not an exploit by itself. CWE-693.
- **Outbound calls with user URLs:** `axios`, `got`, `node-fetch` or `http.request` fed a URL, host or redirect target from the request with no allow-list, no block on private and link-local addresses (`169.254.169.254`, `127.0.0.1`, `10.*`), and redirects followed automatically. Also `axios` or `fetch` calls with no timeout that a client can use to pin workers. CWE-918.
