# Sprint Testing Insights (tqa)

Read-only analytics over Azure DevOps for a test manager: tester Gantt, utilisation and balance,
story test lifecycle and work-item hygiene. The report is available as offline HTML and as Excel.

## Setup
```
pip install -r requirements.txt
copy ado.properties.example ado.properties   # then set org, project and teams (ado.properties is git-ignored)
set ADO_PAT=<token>        # Work Items: Read, Test Management: Read, Project & Team: Read, Code: Read
python -m tqa --list-teams # copy team names into ado.properties (team.N.name / team.N.area)
```

## Run
```
python -m tqa                          # current sprint, all configured teams -> reports/
python -m tqa --iteration previous     # last completed sprint (sprint-end review)
python -m tqa --iteration "Sprint 42"  # a named sprint
python -m tqa --team "Phoenix" --format html
python -m tqa --from-snapshot reports/snapshots/<file>.json   # re-analyse without calling ADO
python -m tqa --iteration previous --sprints 6   # last 6 finished sprints + trends report
python -m tqa --sprints 6 --refresh    # re-collect even cached (finished) sprints
python -m tqa --demo                   # sample data (add --sprints 4 for a demo trends report)
```

## How things are derived
| Signal | Source |
|---|---|
| Testing task | Task in the team's sprint + area with Activity = Testing **or** title containing `QA` (covers `Auto QA`) |
| Activity type | Title keywords, see `tqa/classify.py` (tune the regexes to your naming) |
| Daily effort | Change in Completed Work between revisions, dated by the revision and credited to the assignee at that time |
| Capacity / days off | Sprint capacity per member (all activities summed) + team days off; members across teams are merged |
| Test start ≈ deployment | First activation of an execution task (manual/compat/automation exec/post-script/perf exec) |
| Story progress | Test points of test cases linked via *Tested By* (optional `report.testplan.filter`) |
| Open bugs | Bugs linked to the story as child or related |
| Contribution | Bugs created/closed in the sprint, every test result run in the sprint (manual + automated), test cases created / moved to Ready, Git commits & PRs (author email or name must match the ADO identity), unplanned (created after sprint start) and reassigned tasks |
| Test cases | Linked via *Tested By*; runs come from test points, executor from the result, evidence = result + step + work item attachments |

## Testers only
A task is analysed only if its owner is a tester, or a tester logged effort on it. Testers are taken from
`team.N.testers` / `testers` in `ado.properties` if set (recommended), otherwise from sprint-capacity members whose
Activity is in `tester.activities`. Anything left out is listed under **Rules & scope → Excluded tasks**.

## Hygiene rules
All rules are in `tqa/rules.py`, one decorated function each. The file header explains how to add one.
Switch rules off or change severity in `ado.properties` (`rule.H07.enabled=false`, `rule.H04.severity=High`).
The report's **Rules & scope** tab lists every rule, whether it's on, and how many findings it raised.
After any change run `python -m tqa.selfcheck` (must end with `SELFCHECK OK`).

## AI assistance (GitHub Copilot – no AI packages in this repo)
Every run also writes `reports/<name>_digest.json`. Copilot Chat uses it through the prompt files in `.github/prompts`
(Agent mode; type `/` in Copilot Chat):

| Prompt | What it does |
|---|---|
| `/add-rule` | Turns a plain-English rule into a config change, a new rule, or a collector extension, then verifies it with selfcheck |
| `/sprint-summary` | Writes the one-page testing summary (risks, start timing, workload, hygiene, actions) |
| `/tester-nudges` | Drafts a friendly Teams message per tester with their fix list |
| `/review-closing-comments` | Judges whether closing comments are meaningful and suggests templates |
| `/tune-classification` | Fixes title→activity regexes using the Unclassified titles |
| `/coaching-notes` | Private 1:1 notes per tester: recognise, explore (as questions), one growth focus, next-sprint load |
| `/trend-review` | Reviews the last N sprints: what's improving, what persists, balance over time, late-deployment tax, 3 actions |
| `/balance-next-sprint` | Workload and skills-spread suggestions for next sprint, including single-person dependencies |

`.github/copilot-instructions.md` and `.github/instructions/rules.instructions.md` give Copilot the architecture,
constraints (read-only ADO, no new dependencies) and the fields available to rules.
