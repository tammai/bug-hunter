# A task key that isn't a number crashes the server
Set before running: `BASE` (the rebuild URL), `REF_BASE` (the reference URL)
Severity: high
Oracle: spec-gap
Defect: yes

## What happens
`GET /api/tasks/abc` answers 500, on the rebuild and the reference alike.

## Steps to reproduce
Rendered from the Repro section.

## Repro (finding-v1)
```json
[
  {"request": {"method": "GET", "path": "/api/tasks/abc"}, "expect": {"status": 404}}
]
```

## Observed (finding-v1)
```json
{"rebuild": {"result": "fail", "step": 1, "message": "step 1: status 500, expected 404"},
 "reference": {"result": "fail", "step": 1, "message": "step 1: status 500, expected 404"}}
```

## Expected
No criterion or rule covers this. A key that names no task should give 404, not a server error.

## Root cause
`rebuild.py`, `Handler.do_GET`, lines 26–30: `int()` on the key's text fails and answers 500.
