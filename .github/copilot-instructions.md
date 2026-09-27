# Sprint Testing Insights (tqa) – instructions for GitHub Copilot

This repo is a Python CLI that reads Azure DevOps (ADO) and reports, from a **test manager's** point of view, on each sprint: tester utilisation and Gantt, story test lifecycle, test cases, and work-item hygiene. Output is offline HTML, Excel and a JSON digest.

## Hard constraints
- **No AI or LLM packages or API calls** (no openai, anthropic, langchain and so on). The organisation only allows GitHub Copilot, so all AI help comes from the prompt files in `.github/prompts/`.
- **Dependencies:** only `requests` and `openpyxl`, plus the standard library. Don't add others without asking the user.
- **ADO access is read-only.** Never add calls that create, update or delete ADO data.
- Never print, log or commit the PAT. `ado.properties` and `reports/` are git-ignored.

## Architecture (data flows one way)
| Step | File | Responsibility |
|---|---|---|
| 1 | `tqa/ado_client.py` | Thin REST client, one method per ADO endpoint (api-version 7.1) |
| 2 | `tqa/collector.py` | Builds a **normalised snapshot** (plain JSON: teams → members/capacity, tasks with revisions and comments, stories, test cases with runs, sprint bugs, test case authoring/review; project-level executions (all test results) and Git commits/PRs) |
| 3 | `tqa/classify.py` | Maps task titles to activity codes (TD, TR, TE, ER, RT, CT, AP, AS, AE, AC, PD, PE, SD, SO, UN) with ordered regexes |
| 4 | `tqa/analysis.py` | All metrics: daily effort from Completed Work deltas, capacity, utilisation, Gantt spans, story timing, tester scoping, then runs the rules |
| 5 | `tqa/rules.py` | Hygiene rules H01…: one `@rule` function each (task / testcase / story scope) |
| 5b | `tqa/contribution.py` | Per-tester contribution profile (effort, output, quality, flow, collaboration) and factual observations for coaching |
| 5c | `tqa/trends.py` + `tqa/report_trends.py` | Sprint-over-sprint series and multi-sprint signals (`--sprints N`); finished sprints are cached in `reports/snapshots/cache` |
| 6 | `tqa/report_html.py`, `tqa/report_excel.py`, `tqa/digest.py` | Formatting only. They never compute metrics |
| – | `tqa/demo.py` | Synthetic snapshot covering every rule (`python -m tqa --demo`) |
| – | `tqa/selfcheck.py` | Validates rules and runs the whole pipeline on demo data |
| – | `tqa/config.py` + `ado.properties` | All settings and thresholds |

If a change needs new ADO data, it flows through every step: client method → collector (normalised field) → demo snapshot → analysis object → rule/report. Old snapshots may lack new fields, so read them with `.get(..., default)`.

## Domain conventions (user's organisation)
- Agile process. Testing tasks have Activity = `Testing` and "QA" / "Auto QA" in the title.
- Deployment isn't recorded in ADO. The **first activation of an execution task** stands in for "deployed to test".
- Only testers are analysed: `team.N.testers` / `testers` in `ado.properties`, otherwise capacity Activity = Testing.
- Capacity is 5–6.5 h/day, agreed at sprint planning, and varies by team. It already excludes ceremonies and meetings.
- Completed Work is updated at least daily, so daily effort from revisions is reliable.
- Tasks are selected with `IterationPath EVER <sprint>`, so work later moved to another sprint still counts where it was done (effort is credited by date).
- All 4 teams share the same sprint dates. Code is in ADO Git.
- Bug Resolved Reason is **not** maintained, so bug-rejection metrics are shown only when reasons exist.
- The purpose is **balancing and coaching, never ranking**. Don't add composite scores or leaderboards.

## Coding style
- Match the existing code: small functions, plain dicts, f-strings, no classes unless needed, short comments only where the reason isn't obvious.
- Thresholds belong in `ado.properties` (parsed in `config.py`), never hard-coded in rules.
- **After any change, run** `python -m tqa.selfcheck` (must print `SELFCHECK OK`), then `python -m tqa --demo`.
