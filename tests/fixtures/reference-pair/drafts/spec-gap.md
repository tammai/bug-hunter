# Tasks are listed oldest first
Set before running: `BASE` (the rebuild URL), `REF_BASE` (the reference URL)
Severity: medium

## What happens
After creating "A" then "B", the task list starts with "A", on the rebuild and the reference alike.

## Steps to reproduce
Rendered from the Repro section.

## Repro (finding-v1)
```json
[
  {"request": {"method": "POST", "path": "/api/tasks", "json": {"title": "A"}}, "expect": {"status": 201}},
  {"request": {"method": "POST", "path": "/api/tasks", "json": {"title": "B"}}, "expect": {"status": 201}},
  {"request": {"method": "GET", "path": "/api/tasks"}, "expect": {"status": 200, "json": [{"pointer": "/0/title", "equals": "B"}]}}
]
```

## Observed (finding-v1)
```json
{"rebuild": {"result": "fail", "step": 3, "message": "step 3 /0/title: got \"A\", expected \"B\""},
 "reference": {"result": "fail", "step": 3, "message": "step 3 /0/title: got \"A\", expected \"B\""}}
```

## Expected
F-TSK-02.AC1: given tasks "A" then "B", "B" is listed first.

## Root cause
`rebuild.py`, `Handler.do_GET`, line 24: returns the tasks in the order they were created.
