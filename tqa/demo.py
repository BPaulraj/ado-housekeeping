"""Synthetic sprint snapshot for trying the report without ADO access (--demo)."""

from datetime import date, timedelta

START = date(2026, 9, 14)          # Monday; 10 working days to Fri 25 Sep
DAYS = [START + timedelta(days=i) for i in range(12) if (START + timedelta(days=i)).weekday() < 5]


def _who(name):
    return {"name": name, "unique": name.lower().replace(" ", ".") + "@contoso.com"}


A, B, C, D, E = (_who(n) for n in ("Tester A", "Tester B", "Tester C", "Tester D", "Tester E"))
LEAD = _who("QA Lead")
DEV = _who("Dev One")


def _ts(day_no, hhmm):
    d = DAYS[day_no - 1] if day_no >= 1 else START - timedelta(days=1 - day_no)
    return f"{d.isoformat()}T{hhmm}:00Z"


def _day(day_no):
    return f"{DAYS[day_no - 1].isoformat()}T00:00:00Z"


class _Ids:
    n = 5000

    def __call__(self):
        self.n += 1
        return self.n


_next = _Ids()


def task(title, owner, hours, start, end=None, orig=None, parent=None, activity="Testing",
         lazy=False, owner_comment=True, closed_by=None, remaining_left=0.0, state=None):
    """hours: {day_no: h}. end=None means still Active."""
    total = sum(hours.values())
    orig = orig if orig is not None else total
    revs = [{"rev": 1, "date": _ts(0, "10:00"), "state": "New", "assignee": owner, "changed_by": LEAD,
             "completed": None, "remaining": orig, "original": orig}]
    if start:
        revs.append({"rev": 2, "date": _ts(start, "09:00"), "state": "Active", "assignee": owner, "changed_by": owner,
                     "completed": None, "remaining": orig, "original": orig})
    cum = 0.0
    if not lazy:
        for d in sorted(hours):
            cum += hours[d]
            revs.append({"rev": len(revs) + 1, "date": _ts(d, "11:00"), "state": "Active", "assignee": owner, "changed_by": owner,
                         "completed": cum, "remaining": max(orig - cum, 0), "original": orig})
    final_state = state or ("Closed" if end else ("Active" if start else "New"))
    if end:
        revs.append({"rev": len(revs) + 1, "date": _ts(end, "12:30"), "state": "Closed", "assignee": owner,
                     "changed_by": closed_by or owner, "completed": total, "remaining": remaining_left, "original": orig})
    comments = [{"by": owner, "date": _ts(end or start or 1, "12:00"), "text": "Done - details in test run."}] if owner_comment and end else []
    if end and not owner_comment:
        comments = [{"by": LEAD, "date": _ts(end, "13:00"), "text": "Please add summary."}]
    return {"id": _next(), "title": title, "state": final_state, "activity": activity, "assignee": owner,
            "created": _ts(0, "10:00"), "original": orig, "completed": total if (end or not lazy) else 0,
            "remaining": remaining_left if end else max(orig - cum, 0), "area": "", "iteration": "",
            "tags": "", "parent": parent, "revisions": revs, "comments": comments}


_tc_ids = iter(range(9001, 99999))


def _points(n_pass, n_fail=0, n_block=0, n_notrun=0, tester=None):
    pts = []
    for outcome, n in (("Passed", n_pass), ("Failed", n_fail), ("Blocked", n_block), ("Not run", n_notrun)):
        for _ in range(n):
            tc = next(_tc_ids)
            ran = outcome != "Not run"
            pts.append({"test_case": tc, "outcome": outcome, "plan": "Sprint 42 Plan", "suite": "", "tester": tester,
                        "last_updated": None, "run_id": 700 + tc % 50 if ran else None, "result_id": 100000 + tc if ran else None})
    return pts


def _test_cases(stories):
    """One test case per point; executed ones get a run with one evidence attachment."""
    out = []
    for s in stories:
        s["test_cases"] = [pt["test_case"] for pt in s["points"]]
        for i, pt in enumerate(s["points"]):
            ran = pt["outcome"] != "Not run"
            out.append({
                "id": pt["test_case"], "title": f"{s['title']} - scenario {i + 1}", "state": "Ready", "priority": 2,
                "assignee": pt["tester"], "attachments_wi": 0, "stories": [s["id"]],
                "runs": [{"run_id": pt["run_id"], "result_id": pt["result_id"], "outcome": pt["outcome"], "plan": pt["plan"],
                          "run_by": pt["tester"], "completed": _ts(6, "10:00"), "attachments_result": 1, "attachments_steps": 0}] if ran else [],
            })
    return out


def _sprint_bug(bid, sev, raised_by, day, resolved_day=None, closed_day=None, closed_by=None, reason="Fixed"):
    return {"id": bid, "title": f"Defect {bid}", "severity": sev, "priority": 2,
            "state": "Closed" if closed_day else ("Resolved" if resolved_day else "Active"),
            "reason": reason, "resolved_reason": reason if resolved_day else "",
            "created": _ts(day, "10:30"), "created_by": raised_by,
            "resolved": _ts(resolved_day, "09:00") if resolved_day else None, "resolved_by": _who("Dev One") if resolved_day else None,
            "closed": _ts(closed_day, "15:00") if closed_day else None, "closed_by": closed_by if closed_day else None}


def _authored(test_cases, story_id, author, day, reviewer=None, review_day=None):
    """Test case authoring/review activity for a story's test cases."""
    return [{"id": tc["id"], "title": tc["title"], "state": "Ready" if reviewer else "Design",
             "created": _ts(day, "11:00"), "created_by": author,
             "ready_on": _ts(review_day, "16:00") if reviewer else None, "ready_by": reviewer}
            for tc in test_cases if story_id in tc["stories"]]


def _executions(test_cases, automated_by=()):
    out = []
    for tc in test_cases:
        for r in tc["runs"]:
            out.append({"run_id": r["run_id"], "result_id": r["result_id"], "automated": r["run_by"] in automated_by,
                        "test_case": tc["id"], "title": tc["title"], "outcome": r["outcome"], "run_by": r["run_by"],
                        "completed": r["completed"], "plan": r["plan"], "plan_area": ""})
    return out


def _tweak(test_cases, story_id, n, **changes):
    """Apply changes to the n-th test case of a story (to seed hygiene issues)."""
    tc = [t for t in test_cases if story_id in t["stories"]][n]
    for key, value in changes.items():
        if key == "evidence":
            for r in tc["runs"]:
                r["attachments_result"] = r["attachments_steps"] = value
        else:
            tc[key] = value


def _bug(bid, sev, state="Active"):
    return {"id": bid, "title": f"Defect {bid}", "state": state, "severity": sev, "assignee": _who("Dev One"),
            "created": _ts(5, "10:00"), "open": state in ("New", "Active")}


def snapshot():
    iteration = lambda team: {"id": team, "name": "Sprint 42", "path": f"Demo\\{team}\\Sprint 42",
                              "start": _day(1), "finish": _day(10)}
    wd = ["monday", "tuesday", "wednesday", "thursday", "friday"]

    phoenix_tasks = [
        # Tester A - exactly the requested pattern: T1 D1, T2 D2-3, T3 D4-7, day off D8, T4 D9-10
        task("QA - Test case design - Login", A, {1: 6}, 1, 1, parent=101),
        task("QA - Test case review and rework - Login", A, {2: 5, 3: 6}, 2, 3, parent=101),
        task("QA - Test case execution - Login", A, {4: 6, 5: 5, 6: 6, 7: 6}, 4, 7, orig=20, parent=101),
        task("QA - Support to DEV - env triage", A, {5: 1}, 5, 5, parent=101),
        task("QA - Test evidence review - Login", A, {9: 4, 10: 5}, 9, 10, orig=4, parent=101),   # H04 overrun
        # Tester B - over-utilised, some hygiene misses
        task("QA - Test case design - Payments", B, {1: 7, 2: 7}, 1, 2, parent=102),
        task("QA - Test case execution - Payments", B, {8: 8, 9: 9}, 8, None, orig=24, parent=102),
        task("QA - Test case execution - Payments API", B, {3: 8, 4: 8, 5: 8, 6: 7}, 3, 6, orig=16, parent=102, owner_comment=False),
        task("QA - Bug retest - Payments", B, {7: 3, 10: 4}, 7, None, orig=4, parent=102),
        task("QA - Compatibility test execution - Payments", B, {7: 12}, 7, 7, parent=102, lazy=False),
        # Tester D (split across teams)
        task("QA - Test case execution - Profile", D, {3: 3, 4: 3, 5: 3}, 3, 5, parent=103, closed_by=LEAD),
        task("QA - Test evidence review - Profile", D, {6: 2}, 6, 6, parent=103, lazy=True),
        # Developer tasks that happen to match the QA naming/Activity - must be excluded
        task("Fix QA environment config", DEV, {2: 4}, 2, 2, parent=102, activity="Development"),
        task("QA handover notes for Payments", DEV, {6: 2}, 6, 6, parent=102),
    ]
    orion_tasks = [
        # Tester C - automation, under-logging
        task("Auto QA - Pre-scripting - Search", C, {1: 3, 2: 2, 3: 2}, 1, 3, orig=10, parent=201),
        task("Auto QA - Post-scripting - Search", C, {5: 2, 7: 3}, 5, 8, orig=8, parent=201, lazy=True),
        task("Auto QA - Test execution - Search", C, {9: 2}, 8, None, orig=6, parent=201),
        task("Auto QA - Code commit and push - Search", C, {10: 1}, 10, 10, parent=201, owner_comment=False, remaining_left=1),
        # Tester D - performance
        task("QA - JMeter test design - Checkout", D, {1: 3, 2: 3, 3: 3}, 1, 3, parent=202),
        task("QA - Performance test - Checkout", D, {7: 3, 8: 3, 9: 3}, 7, None, orig=12, parent=202),
        # Tester E - late start, stale task, conventions
        task("QA - Test case design - Orders", E, {1: 6, 2: 6}, 1, 2, parent=203),
        task("QA - Test case execution - Orders", E, {4: 5}, 4, None, orig=16, parent=203),
        task("QA - Compatibility test execution - Orders", E, {8: 6, 9: 6}, 8, 9, parent=203),
        task("QA - Test case execution - Reports", E, {}, None, None, orig=8, parent=204),
        task("Review requirements - Reports", E, {5: 4, 6: 4}, 5, 6, parent=204, activity="Development"),
        task("QA - Test case execution - Notifications", E, {8: 3, 9: 3}, 8, 9, orig=6, parent=205),
        task("QA - Test case review - Orders", E, {}, 3, 3, orig=2, parent=203),
        task("QA - Support to other teams - UAT", E, {10: 3}, 10, 10, parent=None),
        task("QA - Test case execution - Search filters", None, {}, None, None, orig=4, parent=201),  # H13 unassigned
    ]

    phoenix_stories = [
        {"id": 101, "type": "User Story", "title": "Login with SSO", "state": "Closed", "test_cases": [],
         "points": _points(18, tester=A), "bugs": [_bug(801, "3 - Medium", "Closed")]},
        {"id": 102, "type": "User Story", "title": "Card payments", "state": "Active", "test_cases": [],
         "points": _points(10, 3, 2, 9, tester=B), "bugs": [_bug(802, "2 - High"), _bug(803, "3 - Medium")]},
        {"id": 103, "type": "User Story", "title": "Edit profile", "state": "Resolved", "test_cases": [],
         "points": _points(7, tester=D), "bugs": []},
    ]
    orion_stories = [
        {"id": 201, "type": "User Story", "title": "Product search", "state": "Active", "test_cases": [],
         "points": _points(4, 1, 0, 5, tester=C), "bugs": [_bug(804, "3 - Medium")]},
        {"id": 202, "type": "User Story", "title": "Checkout performance NFR", "state": "Active", "test_cases": [], "points": [], "bugs": []},
        {"id": 203, "type": "User Story", "title": "Order history", "state": "Active", "test_cases": [],
         "points": _points(6, 0, 1, 7, tester=E), "bugs": [_bug(805, "1 - Critical")]},
        {"id": 204, "type": "User Story", "title": "Monthly reports", "state": "Active", "test_cases": [],
         "points": _points(0, 0, 0, 12, tester=E), "bugs": []},
        {"id": 205, "type": "User Story", "title": "Push notifications", "state": "Active", "test_cases": [],
         "points": _points(3, 0, 0, 4, tester=E), "bugs": []},
    ]

    for story, points in zip(phoenix_stories + orion_stories, (5, 8, 3, 5, 8, 5, 3, 2)):
        story["story_points"] = points
    phoenix_tcs, orion_tcs = _test_cases(phoenix_stories), _test_cases(orion_stories)
    _tweak(phoenix_tcs, 102, 0, state="Design")        # H16 executed while in Design
    _tweak(phoenix_tcs, 102, 1, evidence=0)            # H17 no evidence
    _tweak(phoenix_tcs, 101, 2, priority=None)         # H18 no priority
    _tweak(orion_tcs, 201, 0, evidence=0)              # H17

    phoenix_bugs = [
        _sprint_bug(801, "3 - Medium", A, 5, resolved_day=5, closed_day=6, closed_by=A),
        _sprint_bug(802, "2 - High", B, 8), _sprint_bug(803, "3 - Medium", B, 9),
        _sprint_bug(806, "3 - Medium", B, 4, resolved_day=5, closed_day=5, closed_by=B, reason="As Designed"),
        _sprint_bug(807, "4 - Low", B, 6, resolved_day=6, closed_day=10, closed_by=B),
    ]
    orion_bugs = [_sprint_bug(804, "3 - Medium", C, 9), _sprint_bug(805, "1 - Critical", E, 9)]
    phoenix_tca = (_authored(phoenix_tcs, 101, A, 1, reviewer=B, review_day=2)
                   + _authored(phoenix_tcs, 102, B, 1, reviewer=A, review_day=3)
                   + _authored(phoenix_tcs, 103, D, 2, reviewer=D, review_day=2))      # self-approved
    orion_tca = _authored(orion_tcs, 203, E, 1, reviewer=E, review_day=2) + _authored(orion_tcs, 201, C, 1)
    executions = _executions(phoenix_tcs) + _executions(orion_tcs, automated_by=(C,))
    code = {"repos": ["qa-automation"],
            "commits": [{"repo": "qa-automation", "id": f"c0ffee{i}", "date": _ts(d, "17:00"), "author": C,
                         "comment": f"Search scripts part {i} #5013", "work_items": [5013]} for i, d in enumerate((2, 3, 5, 7, 10), 1)],
            "pull_requests": [{"repo": "qa-automation", "id": 41, "title": "Search regression suite", "status": "completed",
                               "created": _ts(7, "12:00"), "closed": _ts(8, "10:00"), "created_by": C,
                               "reviewers": [{**D, "vote": 10}]}]}

    off = lambda n: [{"start": _day(n), "end": _day(n)}]
    return {
        "generated": "2026-09-25T18:00:00Z", "org": "https://dev.azure.com/demo-org", "project": "Demo", "selector": "demo",
        "teams": [
            {"name": "Phoenix", "areas": ["Demo\\Phoenix"], "iteration": iteration("Phoenix"), "working_days": wd, "team_days_off": [],
             "members": [
                 {**A, "activities": [{"name": "Testing", "capacity_per_day": 6}], "capacity_per_day": 6, "days_off": off(8)},
                 {**B, "activities": [{"name": "Testing", "capacity_per_day": 6}], "capacity_per_day": 6, "days_off": []},
                 {**D, "activities": [{"name": "Testing", "capacity_per_day": 3}], "capacity_per_day": 3, "days_off": off(6)},
                 {**DEV, "activities": [{"name": "Development", "capacity_per_day": 6}], "capacity_per_day": 6, "days_off": []},
             ],
             "testers": [A["unique"], B["unique"], D["unique"]], "tasks": phoenix_tasks, "stories": phoenix_stories, "test_cases": phoenix_tcs,
             "bugs": phoenix_bugs, "test_case_activity": phoenix_tca},
            {"name": "Orion", "areas": ["Demo\\Orion"], "iteration": iteration("Orion"), "working_days": wd, "team_days_off": [],
             "members": [
                 {**C, "activities": [{"name": "Testing", "capacity_per_day": 6.5}], "capacity_per_day": 6.5, "days_off": off(4)},
                 {**D, "activities": [{"name": "Testing", "capacity_per_day": 3}], "capacity_per_day": 3, "days_off": off(6)},
                 {**E, "activities": [{"name": "Testing", "capacity_per_day": 6.5}], "capacity_per_day": 6.5, "days_off": []},
             ],
             "testers": [C["unique"], D["unique"], E["unique"]], "tasks": orion_tasks, "stories": orion_stories, "test_cases": orion_tcs,
             "bugs": orion_bugs, "test_case_activity": orion_tca},
        ],
        "executions": executions,
        "code": code,
    }


AS_OF = DAYS[-1]


def _shift(obj, days):
    """Move every ISO timestamp in a snapshot by whole days (weekdays are preserved for multiples of 7)."""
    if isinstance(obj, dict):
        return {k: _shift(v, days) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_shift(v, days) for v in obj]
    if isinstance(obj, str) and len(obj) >= 11 and obj[4] == "-" and obj[10] == "T" and obj[:4].isdigit():
        return (date.fromisoformat(obj[:10]) + timedelta(days=days)).isoformat() + obj[10:]
    return obj


def history(n=4):
    """n demo sprints, oldest first, with differences that exercise the trend signals:
    Tester A's hygiene improves, Tester C's automation share grows, Tester B stays overloaded."""
    out = []
    for back in range(n - 1, -1, -1):
        snap = _shift(snapshot(), -14 * back)
        for team in snap["teams"]:
            team["iteration"]["name"] = f"Sprint {42 - back}"
            if back:
                for t in team["tasks"]:
                    if t["assignee"] == A:
                        t["comments"] = []                    # older sprints: more H01 for Tester A
                keep_c = max(1, 4 - back)
                c_tasks = [t for t in team["tasks"] if t["assignee"] == C]
                team["tasks"] = [t for t in team["tasks"] if t["assignee"] != C] + c_tasks[:keep_c]
        out.append(snap)
    return out
