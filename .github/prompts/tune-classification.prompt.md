---
description: "Improve task-title classification using the Unclassified titles from the latest digest"
agent: "agent"
---

Improve `tqa/classify.py` so real task titles map to the right activity code.

## Input
From the attached digest (or the newest `reports/*_digest.json`), read `unclassified_task_titles`, and `classified_examples` (label, title) to spot misclassifications.

## Steps
1. For each unclassified title, decide the correct code from `ACTIVITIES` in `tqa/classify.py`. If a title isn't testing work at all, say so rather than forcing a code.
2. Scan `classified_examples` for obvious mistakes, e.g. "Auto QA - JMeter script" labelled as automation instead of performance design.
3. Update the `_RULES` regexes as little as possible. Order matters: the first match wins, so specific patterns go above generic ones. Prefer widening an existing pattern to adding a new one.
4. **Check that no existing example changes label unintentionally.** Write a small throwaway Python snippet that runs `classify()` over the titles before and after the change, show the before/after table, then delete the snippet.
5. Run `python -m tqa.selfcheck` (must print `SELFCHECK OK`).

Report the regex changes and the before/after table. If the titles show the team isn't following the naming convention, suggest the convention to adopt, e.g. `QA - <Activity> - <Story>`.
