---
description: "Suggest how to balance tester workload in the next sprint, from the latest tqa digest"
agent: "agent"
argument-hint: "Optional: known next-sprint changes, e.g. 'Tester B on leave 3 days, Phoenix has a perf-heavy release'"
---

Suggest how the test manager should balance testers across the 4 teams next sprint. Known changes: ${input:changes:none}

## Input
Use the attached digest, or the newest sprint digest `reports/*_digest.json` (not a `trends_` one). If a trends digest exists, weigh repeated overload or underload more heavily than a single sprint. Use `testers` (capacity, utilisation, remaining hours, effort mix, status), `contribution.people` (flow, collaboration), `stories` (open stories, remaining risk) and `teams`.

## Analyse
1. **Load this sprint:** who ran over 110% or under 60% of capacity, and whether it was planned (`plan_load_pct`) or unplanned (`contribution…flow.unplanned_h`, support hours).
2. **Carry-over:** `remaining_h` per tester and open stories likely to spill into next sprint, with their owners.
3. **Skills spread:** who did only one kind of work, and where one person is the only one doing a type (single point of failure). For example, only one person doing automation or performance.
4. **Review load:** who does reviews for others and who self-approves, so review work can be spread.

## Output
- A table: tester | this sprint (util %, main work) | carry-over h | suggestion for next sprint (keep / reduce / add X) | reason.
- 3–5 concrete moves, e.g. "Pair Tester D with Tester C on automation for the Search story to reduce single-person dependency".
- Risks to raise with the scrum masters, e.g. late deployments (`test_start_timing` Late) or unplanned support requests.

Base everything on the digest numbers, and state any assumptions (for example about next sprint's capacity) explicitly.
