---
description: "Write the test manager's sprint testing summary from the latest tqa digest"
agent: "agent"
argument-hint: "Optional: audience or focus, e.g. 'for sprint retro' or 'focus on Phoenix'"
---

Write a sprint **testing** summary for the test manager (delivery status is covered elsewhere, so focus on testing and testers). Focus / audience: ${input:focus:leave blank for the standard summary}

## Input
Use the digest file attached to the chat. If none is attached, find the newest sprint digest `reports/*_digest.json` (list the folder in the terminal; skip files named `trends_…`) and read it. If a trends digest exists for the same sprint, add one line per section saying whether it's better or worse than the previous sprints. Don't read the HTML or Excel files, and don't call ADO.

## Rules
- **Every number must come from the digest.** Don't estimate, and don't invent causes the data doesn't show. If something can't be determined, say so.
- Utilisation is a workload-balance signal, **not** a performance ranking. Use neutral, supportive wording about people.
- Group repeated hygiene issues into patterns rather than listing every item.

## Output (Markdown, around one page)
1. **Headline:** one sentence on the state of testing this sprint.
2. **Delivery risk from a testing view:** open stories with `test_start_timing` Late / Not started, open Sev-1/2 bugs, low `executed_pct`. Show which story, why (use `why_not_done`) and what would unblock it.
3. **When testing started:** counts of Early / Mid / Late / Not started. Say what it suggests about deployment timing, the "late-deployment tax".
4. **Tester workload & contribution:** who is over or under capacity, notable output from `contribution.people` (reviews for others, bugs raised, automation code) without ranking anyone, the `workload_balance_cv` interpretation (<0.15 even, 0.15–0.3 uneven, >0.3 very uneven), effort-mix observations (e.g. someone doing only execution), unplanned Support hours.
5. **Test quality & hygiene:** the top 3 rules by count, test cases executed without evidence or while in Design, and who owns the fix.
6. **Recommended actions:** 3–5 concrete actions for next sprint, each tied to a number above.

Save the summary as `reports/<same name as digest>_summary.md` (replace `_digest.json`), and also show it in chat.
