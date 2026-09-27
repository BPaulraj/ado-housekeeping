"""Per-tester contribution profile for balancing and coaching.

Five angles, deliberately no single score or ranking:
  effort        hours logged vs capacity (from analysis)
  output        test cases written / moved to Ready, executions, bugs raised, commits, PRs, story points touched
  quality       share of bugs rejected (approximate), evidence on executed test cases, hygiene findings
  flow          unplanned tasks, reassignments, tasks per day
  collaboration reviews for others, PR reviews, support hours, bug retests and turnaround

Observations are short factual statements for a coaching conversation; the
Copilot prompt /coaching-notes turns them into 1:1 notes.
"""

import statistics
from collections import Counter
from datetime import timedelta

FIXED_REASONS = {"", "fixed", "new", "build failure", "approved", "investigation complete", "work finished"}


def _same(identity, person):
    """Identity match on email/unique name, falling back to display name (git author emails can differ)."""
    if not identity:
        return False
    return identity.get("unique") == person["key"] or identity.get("name", "").lower() == person["name"].lower()


def build(model, snapshot, cfg, clock):
    teams = snapshot["teams"]
    bugs = {b["id"]: b for t in teams for b in t.get("bugs", [])}.values()
    tca = {x["id"]: x for t in teams for x in t.get("test_case_activity", [])}.values()
    executions = snapshot.get("executions", [])
    code = snapshot.get("code", {})
    tasks = model["tasks"]
    stories = {s["id"]: s for s in model["stories"]}

    reasons_known = any((b.get("resolved_reason") or b.get("reason") or "").lower() not in FIXED_REASONS
                        for b in bugs if b.get("resolved") or b.get("closed"))
    rejected = set(cfg.rejected_bug_reasons)

    out = []
    for p in model["people"]:
        days = set(p["days"])
        start = min(days) if days else None

        def in_sprint(iso):
            d = clock.day(iso)
            return d in days if days else bool(d)

        # ---- output ----
        authored = [x for x in tca if x["created"] and _same(x["created_by"], p)]
        readied = [x for x in tca if x["ready_on"] and _same(x["ready_by"], p)]
        for_others = [x for x in readied if not _same(x["created_by"], p)]
        mine_ex = [e for e in executions if _same(e["run_by"], p) and in_sprint(e["completed"])]
        manual = [e for e in mine_ex if not e["automated"]]
        raised = [b for b in bugs if _same(b["created_by"], p) and in_sprint(b["created"])]
        raised_rejected = [b for b in raised if (b.get("resolved_reason") or b.get("reason") or "").lower() in rejected]
        commits = [c for c in code.get("commits", []) if _same(c["author"], p)]
        prs = [x for x in code.get("pull_requests", []) if _same(x["created_by"], p)]
        pr_reviews = [x for x in code.get("pull_requests", [])
                      if not _same(x["created_by"], p) and any(_same(r, p) and r.get("vote") for r in x["reviewers"])]
        own_tasks = [tasks[i] for i in p["task_ids"] if tasks[i]["owner_key"] == p["key"]]
        sp = sum((stories[sid].get("story_points") or 0) for sid in {t["parent"] for t in own_tasks} if sid in stories)

        # ---- quality ----
        my_tcs = [tc for tc in model["test_cases"] if any(_same(r["run_by"], p) for r in tc["runs"])]
        evidence_pct = round(100 * sum(1 for tc in my_tcs if tc["attachments_total"]) / len(my_tcs)) if my_tcs else None

        # ---- flow ----
        unplanned = [t for t in own_tasks if start and t["created"] and t["created"] > start]
        reassigned = [t for t in own_tasks if t["reassigned"]]

        # ---- collaboration ----
        retests = [b for b in bugs if _same(b["closed_by"], p) and b.get("resolved") and in_sprint(b["closed"])]
        turnaround = [_working_days(clock.day(b["resolved"]), clock.day(b["closed"])) for b in retests]
        turnaround = [t for t in turnaround if t is not None]

        prof = {
            "key": p["key"], "name": p["name"],
            "effort": {"capacity_h": p["capacity"], "logged_to_date_h": p["logged_to_date"],
                       "utilisation_pct": round(p["util"] * 100) if p["util"] is not None else None,
                       "days_off": len(p["days_off"]), "mix_h": p["mix"]},
            "output": {
                "test_cases_written": len(authored), "test_cases_moved_to_ready": len(readied),
                "executions_manual": len(manual), "executions_automated": len(mine_ex) - len(manual),
                "distinct_test_cases_executed": len({e["test_case"] for e in mine_ex}),
                "execution_outcomes": dict(Counter(e["outcome"] for e in mine_ex)),
                "execution_days": len({clock.day(e["completed"]) for e in mine_ex}),
                "bugs_raised": len(raised), "bugs_by_severity": dict(Counter((b["severity"] or "unset") for b in raised)),
                "commits": len(commits), "pull_requests": len(prs), "story_points_touched": sp,
            },
            "quality": {
                "bugs_rejected": len(raised_rejected) if reasons_known else None,
                "bugs_rejected_pct": (round(100 * len(raised_rejected) / len(raised)) if raised else None) if reasons_known else None,
                "evidence_pct": evidence_pct, "self_moved_to_ready": len(readied) - len(for_others),
                "hygiene_findings": p["flags"],
            },
            "flow": {"unplanned_tasks": len(unplanned), "unplanned_h": round(sum(t["completed"] for t in unplanned), 1),
                     "reassigned_tasks": len(reassigned), "avg_tasks_per_day": p["switching"]},
            "collaboration": {
                "reviews_for_others": len(for_others), "pr_reviews": len(pr_reviews),
                "support_h": p["mix"].get("Support", 0), "bugs_retested": len(retests),
                "retest_turnaround_days_median": round(statistics.median(turnaround), 1) if turnaround else None,
            },
        }
        prof["observations"] = _observations(prof, p, cfg)
        out.append(prof)

    return {"people": out, "bug_reasons_maintained": reasons_known,
            "repos": code.get("repos", []), "has_code_data": bool(code.get("repos"))}


def _working_days(a, b):
    """Mon-Fri days after a up to and including b (0 = same day)."""
    if not a or not b or b < a:
        return None
    return sum(1 for n in range(1, (b - a).days + 1) if (a + timedelta(days=n)).weekday() < 5)


def _observations(prof, p, cfg):
    """Factual, neutral statements. 'strength' = worth recognising, 'watch' = worth a conversation."""
    obs = []
    e, o, q, f, c = prof["effort"], prof["output"], prof["quality"], prof["flow"], prof["collaboration"]
    add = lambda kind, text: obs.append({"kind": kind, "text": text})

    util = e["utilisation_pct"]
    if util is not None and util > cfg.over_util * 100:
        add("watch", f"Logged {util}% of capacity to date - check workload before next sprint")
    elif util is not None and util < cfg.under_util * 100:
        add("watch", f"Logged {util}% of capacity to date - blocked, unplanned work outside ADO, or not updating Completed Work?")
    total = sum(v for v in e["mix_h"].values() if v > 0)
    if total:
        top, hours = max(e["mix_h"].items(), key=lambda kv: kv[1])
        if hours / total >= 0.9 and total >= 10:
            add("watch", f"{round(100 * hours / total)}% of hours were {top} - fine if that is their specialism, "
                         "otherwise consider rotating in other activity types")
        if not {"Design", "Automation", "Performance"} & set(e["mix_h"]):
            add("watch", "Execution/support only - no design, automation or performance work this sprint")
    if o["executions_manual"] >= 20 and o["bugs_raised"] == 0:
        add("watch", f"{o['executions_manual']} executions and no bugs raised - stable areas, or bugs logged by someone else?")
    if o["bugs_raised"]:
        add("strength", f"Raised {o['bugs_raised']} bug(s)")
    if q["bugs_rejected_pct"] is not None and q["bugs_rejected_pct"] >= 30 and o["bugs_raised"] >= 3:
        add("watch", f"{q['bugs_rejected_pct']}% of raised bugs were rejected - review bug-raising quality together")
    if q["evidence_pct"] is not None and q["evidence_pct"] < 80:
        add("watch", f"Evidence attached on only {q['evidence_pct']}% of executed test cases")
    if q["self_moved_to_ready"]:
        add("watch", f"Moved {q['self_moved_to_ready']} of their own test case(s) to Ready - peer review skipped?")
    if f["unplanned_tasks"]:
        add("watch", f"{f['unplanned_tasks']} task(s) added after sprint start ({f['unplanned_h']:g}h)")
    if f["avg_tasks_per_day"] >= 3:
        add("watch", f"Worked on {f['avg_tasks_per_day']:g} tasks per day on average - high context switching")
    if c["reviews_for_others"]:
        add("strength", f"Reviewed {c['reviews_for_others']} test case(s) written by others")
    if c["pr_reviews"]:
        add("strength", f"Reviewed {c['pr_reviews']} pull request(s)")
    if o["commits"] or o["pull_requests"]:
        add("strength", f"Automation code: {o['commits']} commit(s), {o['pull_requests']} PR(s)")
    if c["support_h"] >= 8:
        add("strength", f"Spent {c['support_h']:g}h supporting others")
    if c["retest_turnaround_days_median"] is not None and c["retest_turnaround_days_median"] > 2:
        add("watch", f"Median bug retest turnaround {c['retest_turnaround_days_median']:g} days")
    if q["hygiene_findings"] == 0 and total:
        add("strength", "No ADO hygiene findings")
    return obs
