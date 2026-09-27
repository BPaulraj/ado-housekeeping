---
description: "Judge whether testers' closing comments on tasks are meaningful (quality check beyond rule H01)"
agent: "agent"
---

Rule H01 only checks that the owner left a comment. Here you judge whether each comment is **useful**.

## Input
`closing_comments` from the attached digest, or the newest `reports/*_digest.json`. Each entry has task, title, type (activity), owner, completed_h and comment.

## What makes a good closing comment (by activity type)
| Type | Should mention |
|---|---|
| Test case execution / Compatibility | counts run / passed / failed / blocked, bug ids raised, environment or build |
| Test case design / review | number of cases written or reviewed, coverage notes, rework done |
| Evidence review | what was reviewed, gaps found |
| Automation scripting / execution / commit | scripts added or updated, pass rate, repo / PR / commit reference |
| Performance | scenario, load profile, key result vs target |
| Bug retest | bug id(s) and retest result |
| Support | who was supported and on what |

## Output
1. A table: task | owner | verdict (Good / Thin / Not useful) | what's missing, in at most 12 words. Sort Not useful first.
2. Per owner: how many of their comments are Thin or Not useful.
3. Offer a one-line comment template per activity type that the team can adopt.

Judge only from the comment text; don't guess at work that isn't described. Be fair: short comments can be fine when they contain the facts.
