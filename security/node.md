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
