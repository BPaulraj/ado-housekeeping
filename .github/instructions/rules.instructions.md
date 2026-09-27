---
applyTo: "tqa/rules.py,tqa/demo.py,tqa/analysis.py"
description: "How hygiene rules are written in tqa, and the fields available to them"
---

# Writing hygiene rules (`tqa/rules.py`)

```python
@rule("H19", "Medium", "Short title shown in the report (<=70 chars)", scope="task")
def snake_case_name(t, ctx):
    """One sentence on what the rule means and why it matters – shown in the report."""
    if <problem>:
        return "detail shown in the report"   # "" = finding with no detail
    # return None (implicitly) when the item is fine
```

- **Ids:** next free `H` number, never reuse one. **Severity:** `High` / `Medium` / `Low`. **Scope:** `task` | `testcase` | `story`.
- **Return values:**
  - `None` means the item is OK.
  - A `str` is one finding; a `list` of `str` is several findings.
  - `(detail, person)` blames someone other than the item's owner, where `person` is an identity `{"name", "unique"}`.
  - Story rules return a list of `(task_dict, detail)` pairs, or `None`.
- Read thresholds from `ctx.cfg`. To add one, add a field to `Config` in `config.py`, parse it in `load_config` (key `rule.<name>`), and document it, commented out, in the rules section of `ado.properties`.
- Put the rule in the section matching its scope. Keep it pure: no I/O, no ADO calls, no imports beyond what `rules.py` already has.
- Add a demo case in `tqa/demo.py` that triggers the rule (e.g. with `task(...)` or `_tweak(...)`), and mark it with a `# H19 ...` comment.

## `ctx`
`cfg` (Config), `as_of` (date), `sprint_days` (list[date]), `elapsed` (list[date] up to as_of), `wd_between(a, b)` (working days after a up to and including b), `people` (key → person dict with `days_off`, `daily_capacity`, `daily_logged`).

## Task dict (scope `task`)
`id, title, team, state, activity_field, code` (see classify.py) `, label, group` (Design/Execution/Automation/Performance/Support/Unclassified), `owner` {name, unique} or None, `owner_key, original, completed, remaining` (hours), `parent` (story id), `activated, closed_on, span_start, span_end, last_effort` (dates or None), `closed_by` {name, unique}, `is_closed, is_exec` (bool), `daily` {person_key: {date: hours}}, `effort_updates` (int), `comments, owner_comments` (counts), `owner_last_comment` (plain text), `flags`.

## Test case dict (scope `testcase`)
`kind="Test case", id, title, team, state` (Design/Ready/Closed), `priority` (1–4 or None), `owner` (assigned to), `owner_key, stories` (linked story ids), `executors` (names), `attachments_total` (work item + result + step attachments), `flags`, and `runs`: a list of {`run_id, result_id, outcome, plan, run_by` {name, unique}, `completed` (ISO str), `attachments_result, attachments_steps`}, oldest first.

## Story dict (scope `story`)
`id, type, title, state, team, done, test_start` (date), `start_day, sprint_len, timing` (Early/Mid/Late/Not started), `test_days_left, points_total, executed, outcomes` {Passed, Failed, Blocked, Not run, …}, `exec_pct, pass_pct, bugs_open` (list of {id, severity, state…}), `bugs_total, effort, reasons`, `task_objs` (the story's task dicts), `tc_objs` (its test case dicts).

## Data not in these dicts?
Then the rule needs new data collected. Extend `ado_client.py` (read-only GET/POST query), normalise it in `collector.py`, add it to the demo snapshot, and carry it into the dict in `analysis.py`, reading it with `.get()` so old snapshots still load.
