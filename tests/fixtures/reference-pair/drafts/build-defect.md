# An empty title is accepted
Set before running: `BASE` (the rebuild URL), `REF_BASE` (the reference URL)
Severity: high

## What happens
Creating a task with an empty title answers 201 and saves it.

## Steps to reproduce
Rendered from the Repro section.

## Repro (finding-v1)
```json
[
  {"request": {"method": "POST", "path": "/api/tasks", "json": {"title": ""}}, "expect": {"status": 400}}
]
```

## Observed (finding-v1)
```json
{"rebuild": {"result": "fail", "step": 1, "message": "step 1: status 201, expected 400"},
 "reference": {"result": "pass"}}
```

## Expected
F-TSK-01.AC2: when the title is empty, the request fails with 400.

## Root cause
`rebuild.py`, `Handler.do_POST`, line 39: the title is never checked.
