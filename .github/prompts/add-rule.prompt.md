---
description: "Add or change a hygiene rule from a plain-English description"
agent: "agent"
argument-hint: "Describe the rule, e.g. 'bug retest task must be closed within 2 days of the bug being resolved'"
---

You are the rule author for this repo. The test manager described a rule:

> ${input:rule:Describe the rule in plain English}

Follow [the rule-writing guide](../instructions/rules.instructions.md) and [the repo instructions](../copilot-instructions.md).

## 1. Decide the right kind of change (tell the user which one, and why, before editing)
1. **Already covered?** Check `tqa/rules.py`. If an existing rule does this with a different threshold, the change is only a setting in `ado.properties` (e.g. `rule.stale.days=3`), or `rule.HNN.enabled` / `rule.HNN.severity`. Make that change and stop.
2. **Computable from existing fields?** Look at the task, test case and story dicts in the guide. If yes, write a new rule.
3. **Needs data we don't collect?** Say exactly which ADO field or endpoint is needed. Then extend `ado_client.py` → `collector.py` → `demo.py` → `analysis.py` before writing the rule. Keep ADO access read-only.
4. **Ambiguous?** If the description could mean two different checks (e.g. which date counts, or who is responsible), ask **one** short question and wait.

## 2. Implement
- Use the next free id and the right scope, severity and title, plus a docstring written for a test manager.
- Put any threshold in config (`config.py` + a commented example in `ado.properties`); don't hard-code it.
- Name the right responsible person, e.g. the executor via `(detail, run["run_by"])` for test-run problems.
- Add a demo case in `tqa/demo.py` that triggers the rule.

## 3. Verify (mandatory)
Run in the terminal:
```
python -m tqa.selfcheck
python -m tqa --demo
```
`selfcheck` must print `SELFCHECK OK`, and your rule must show at least 1 demo hit. If not, fix it and rerun. Don't leave other rules' demo hit counts changed unless that's intended; explain any change.

## 4. Report back
Give the rule id, severity, the file(s) changed, the demo finding it produced, and any new setting. Keep it short.
