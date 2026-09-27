---
description: "Draft a short, friendly Teams message per tester listing their ADO hygiene fixes"
agent: "agent"
argument-hint: "Optional: one tester's name, or 'all'"
---

Draft one short message per tester (for Microsoft Teams, written as their test manager) asking them to fix their ADO hygiene findings. Tester(s): ${input:tester:all}

## Input
Use the attached digest, or the newest `reports/*_digest.json`. Use `hygiene.by_person`, and `testers` for context (utilisation, status).

## Rules
- Use only findings in the digest. Include the ADO work item id for each item so they can find it.
- Be warm and brief: greeting, 1 line of context, a bulleted fix list grouped by kind of fix, then thanks. At most 120 words per person.
- Put High severity first. Merge repeats, e.g. "add a closing comment on 5001, 5003 and 5007".
- Turn each rule into the action to take, not the rule name:
  - H01 → "add a short closing comment in Discussion"
  - H02 → "log Completed Work"
  - H03 → "set Remaining to 0"
  - H05 / H06 → "update Completed Work daily"
  - H16 → "move the test case to Ready (after review) before executing"
  - H17 → "attach evidence to the test result"
  - H18 → "set Priority"
  - H15 → "evidence review should be picked up by another tester"
- If someone is over-utilised (`status` Over-utilised), add one supportive line and don't pile on.
- Skip anyone with no findings.

Output a Markdown section per tester (`### Name`), ready to copy and paste. Don't send anything.
