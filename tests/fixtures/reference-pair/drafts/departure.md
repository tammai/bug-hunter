# Task keys are padded with zeros
Set before running: `BASE` (the rebuild URL), `REF_BASE` (the reference URL)
Severity: low

## What happens
A new task's key is `TSK-0003` instead of `TSK-3`.

## Steps to reproduce
Rendered from the Repro section.

## Repro (finding-v1)
```json
[
  {"request": {"method": "POST", "path": "/api/tasks", "json": {"title": "C"}}, "expect": {"status": 201, "json": [{"pointer": "/key", "rule": "regex:^TSK-[1-9][0-9]*$"}]}}
]
```

## Observed (finding-v1)
```json
{"rebuild": {"result": "fail", "step": 1, "message": "step 1 /key: \"TSK-0003\" does not satisfy rule regex:^TSK-[1-9][0-9]*$"},
 "reference": {"result": "pass"}}
```

## Expected
Per F-TSK-01.AC1 and domain.md §Keys, a key is `TSK-<n>` with no leading zeros.

## Root cause
`rebuild.py`, `Handler.do_POST`, line 42: formats the number with `:04d`.
