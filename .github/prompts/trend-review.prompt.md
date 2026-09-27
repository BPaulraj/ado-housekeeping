---
description: "Review testing trends across the last N sprints from the tqa trends digest"
agent: "agent"
argument-hint: "Optional focus, e.g. 'for the quarterly review' or 'Phoenix only'"
---

Review how testing has changed across recent sprints, for the test manager. Focus: ${input:focus:leave blank for the standard review}

## Input
Use the attached trends digest, or the newest `reports/*trends_*_digest.json`. If none exists, tell the user to run `python -m tqa --iteration previous --sprints 6` first. The digest has:
- `labels`: sprints, oldest first.
- `sprints`: all-team metrics per sprint.
- `teams`: per-team series.
- `testers`: per-tester series, with `null` where the person wasn't in that sprint.
- `signals`: patterns already detected.

## Rules
- Every number comes from the digest. Describe **direction and persistence** (e.g. "three sprints running"), not one-off blips. One sprint is noise; three is a pattern.
- Balancing and coaching, not ranking. Don't order testers by any metric.
- Treat hygiene counts as a coaching signal. Credit improvements explicitly.

## Output (Markdown, around one page)
1. **What's improving:** 2–4 points with before → after numbers.
2. **What's persisting or getting worse:** 2–4 points, e.g. sustained overload, recurring spillover, late test starts rising. Name the team or tester and how many sprints.
3. **Workload balance over time:** the `balance_cv` trend, who has been over or under capacity repeatedly, and work-mix concentration.
4. **Late-deployment tax:** the `late_start_pct` and `avg_start_day` trend per team, and what to raise with the scrum masters.
5. **Three actions for the next 2 sprints,** each tied to a trend above, with how to tell in the next trends run whether it worked.

Save it as `reports/<same name as the trends digest>_review.md` (replace `_digest.json`), and also show it in chat.
