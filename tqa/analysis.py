"""Turns a sprint snapshot into metrics: effort per day, utilisation, Gantt spans,
story test lifecycle and work-item hygiene findings.

All numbers are computed deterministically here; renderers only format them.
"""

import re
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from html import unescape

from types import SimpleNamespace

from . import classify as cls
from . import contribution
from . import rules as hygiene
from .config import testers_for
from .rules import ACTIVE_STATES, NEW_STATES

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
CLOSED_STATES = {"closed", "done", "resolved"}
STORY_DONE_STATES = {"closed", "done", "resolved", "removed"}

SEVERITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


# ---------------------------------------------------------------- helpers ---
class Clock:
    """Converts ADO UTC timestamps into local calendar dates."""

    def __init__(self, tz_name=""):
        self.tz = None
        if tz_name:
            try:
                from zoneinfo import ZoneInfo
                self.tz = ZoneInfo(tz_name)
            except Exception:
                print(f"  warning: time zone '{tz_name}' unavailable (pip install tzdata) - using machine local time")

    def local(self, iso):
        if not iso:
            return None
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone(self.tz) if self.tz else dt.astimezone()

    def day(self, iso):
        dt = self.local(iso)
        return dt.date() if dt else None


def iso_date(iso):
    """Calendar dates (sprint start/finish, days off) are stored as midnight UTC - take the date part."""
    return date.fromisoformat(iso[:10]) if iso else None


def date_range(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def days_off_set(ranges):
    out = set()
    for r in ranges:
        out.update(date_range(iso_date(r["start"]), iso_date(r["end"])))
    return out


def num(v):
    return float(v) if v not in (None, "") else 0.0


def pkey(identity):
    return identity["unique"] if identity else None


# ---------------------------------------------------------------- model -----
def analyse(snapshot, cfg, as_of=None):
    clock = Clock(cfg.timezone)
    today = as_of or date.today()
    people = {}
    tasks = {}
    stories = []
    findings = []
    team_views = []
    excluded = []
    active_rules = hygiene.effective(cfg)

    test_cases = []

    def add_finding(r, item, detail, person=None):
        """item is a task or test case; person overrides who the finding is attributed to."""
        who = person or item["owner"]
        item["flags"].append(r.id)
        findings.append({"rule": r.id, "severity": r.severity, "text": r.title, "detail": detail,
                         "kind": item.get("kind", "Task"), "task": item["id"], "title": item["title"], "team": item["team"],
                         "person": who["name"] if who else "(unassigned)", "person_key": pkey(who)})

    def person(identity):
        k = pkey(identity)
        if k not in people:
            people[k] = {
                "key": k, "name": identity["name"], "teams": [], "is_tester": False,
                "daily_capacity": defaultdict(float), "days_off": set(), "sprint_days": set(),
                "daily_logged": defaultdict(float), "task_ids": set(),
            }
        return people[k]

    for team in snapshot["teams"]:
        it = team["iteration"]
        start, finish = iso_date(it["start"]), iso_date(it["finish"])
        working = {WEEKDAYS.index(d) for d in team["working_days"]}
        sprint_days = [d for d in date_range(start, finish) if d.weekday() in working]
        day_no = {d: i + 1 for i, d in enumerate(sprint_days)}
        team_off = days_off_set(team["team_days_off"])
        team_as_of = min(today, finish)
        elapsed = [d for d in sprint_days if d <= team_as_of]
        testers, tester_source = testers_for(cfg, team["name"], team["members"])
        if not testers and team.get("testers"):
            testers, tester_source = set(team["testers"]), "snapshot"

        def is_tester(key):
            return not testers or key in testers  # no tester list at all -> nothing to filter on

        def wd_between(a, b):
            """Working days strictly after a up to and including b."""
            if not a or not b or b <= a:
                return 0
            return sum(1 for d in date_range(a + timedelta(days=1), b) if d.weekday() in working and d not in team_off)

        # capacity
        for m in team["members"]:
            if not is_tester(m["unique"]):
                continue
            p = person(m)
            p["is_tester"] = True
            p["teams"].append({"team": team["name"], "capacity_per_day": m["capacity_per_day"]})
            off = days_off_set(m["days_off"]) | team_off
            p["days_off"] |= {d for d in off if start <= d <= finish}
            p["sprint_days"] |= set(sprint_days)
            for d in sprint_days:
                if d not in off:
                    p["daily_capacity"][d] += m["capacity_per_day"]

        team_tasks = []
        for t in team["tasks"]:
            code = cls.classify(t["title"])
            revs = t["revisions"]
            owner = t["assignee"]
            daily = defaultdict(lambda: defaultdict(float))  # person -> date -> hours
            effort_updates = []
            prev = 0.0
            activated = closed_on = closed_by = None
            last_state = None
            reassigned, prev_owner = 0, None
            for r in revs:
                d = clock.day(r["date"])
                if r["assignee"] and prev_owner and r["assignee"]["unique"] != prev_owner["unique"]:
                    reassigned += 1
                prev_owner = r["assignee"] or prev_owner
                cw = num(r["completed"])
                if abs(cw - prev) > 1e-9:
                    who = r["assignee"] or owner or r["changed_by"]
                    daily[pkey(who)][d] += cw - prev
                    effort_updates.append(d)
                prev = cw
                st = (r["state"] or "")
                if st != last_state:
                    if st.lower() in ACTIVE_STATES and activated is None:
                        activated = d
                    if st.lower() in CLOSED_STATES:
                        closed_on, closed_by = d, r["changed_by"]
                    elif last_state and last_state.lower() in CLOSED_STATES:
                        closed_on = closed_by = None  # reopened
                    last_state = st

            follows_convention = t["activity"] == "Testing" or "qa" in t["title"].lower()
            keep = (not testers
                    or (owner and pkey(owner) in testers)
                    or any(k in testers for k in daily)          # a tester logged effort on it
                    or (not owner and follows_convention))      # unassigned QA task - keep so H13 flags it
            if not keep:
                excluded.append({"id": t["id"], "title": t["title"], "team": team["name"], "state": t["state"],
                                 "owner": owner["name"] if owner else "(unassigned)",
                                 "reason": "owner is not a tester" if owner else "unassigned and no tester effort"})
                continue

            is_closed = t["state"].lower() in CLOSED_STATES
            first_effort = min(effort_updates) if effort_updates else None
            span_start = activated or first_effort or (closed_on if is_closed else None)
            span_end = closed_on if is_closed else (team_as_of if span_start else None)
            if span_start and span_end and span_end < span_start:
                span_end = span_start

            task = {
                "id": t["id"], "title": t["title"], "team": team["name"], "state": t["state"],
                "activity_field": t["activity"], "code": code, "label": cls.label(code), "group": cls.group(code),
                "owner": owner, "owner_key": pkey(owner),
                "original": num(t["original"]), "completed": num(t["completed"]), "remaining": num(t["remaining"]),
                "parent": t["parent"],
                "activated": activated, "closed_on": closed_on if is_closed else None,
                "span_start": span_start, "span_end": span_end, "is_closed": is_closed,
                "daily": {k: dict(v) for k, v in daily.items()},
                "effort_updates": len(effort_updates),
                "created": clock.day(t.get("created")),
                "reassigned": reassigned,
                "last_effort": max(effort_updates) if effort_updates else None,
                "closed_by": closed_by if is_closed else None,
                "is_exec": code in cls.EXECUTION_START_CODES,
                "owner_comments": sum(1 for c in t["comments"] if owner and c["by"] and c["by"]["unique"] == owner["unique"]),
                "owner_last_comment": _plain(next((c["text"] for c in reversed(t["comments"])
                                                   if owner and c["by"] and c["by"]["unique"] == owner["unique"]), "")),
                "comments": len(t["comments"]),
                "flags": [],
            }
            tasks[t["id"]] = task
            team_tasks.append(task)

            for who_key, per_day in task["daily"].items():
                if who_key in people:
                    people[who_key]["task_ids"].add(t["id"])
                    for d, h in per_day.items():
                        people[who_key]["daily_logged"][d] += h
            if owner and is_tester(pkey(owner)):
                person(owner)["task_ids"].add(t["id"])

        ctx = SimpleNamespace(cfg=cfg, as_of=team_as_of, sprint_days=sprint_days, elapsed=elapsed,
                              wd_between=wd_between, people=people)
        for task in team_tasks:
            for r, item, detail, who in hygiene.run(active_rules, "task", task, ctx):
                add_finding(r, item, detail, who)

        # ---- test cases linked (Tested By) to stories that have tester tasks ----
        scoped_stories = {x["parent"] for x in team_tasks if x["parent"]}
        team_tcs = []
        for tc in team.get("test_cases", []):
            linked = [sid for sid in tc["stories"] if sid in scoped_stories]
            if not linked:
                continue
            owner = tc["assignee"]
            obj = {
                "kind": "Test case", "id": tc["id"], "title": tc["title"], "team": team["name"],
                "state": tc["state"], "priority": tc["priority"], "owner": owner, "owner_key": pkey(owner),
                "stories": linked, "runs": tc["runs"], "flags": [],
                "attachments_total": tc["attachments_wi"] + sum(r["attachments_result"] + r["attachments_steps"] for r in tc["runs"]),
                "executors": sorted({r["run_by"]["name"] for r in tc["runs"] if r["run_by"]}),
            }
            team_tcs.append(obj)
            for r, item, detail, who in hygiene.run(active_rules, "testcase", obj, ctx):
                add_finding(r, item, detail, who)
        test_cases.extend(team_tcs)

        # ---- stories: test lifecycle ----
        for s in team["stories"]:
            st_tasks = [x for x in team_tasks if x["parent"] == s["id"]]
            if not st_tasks:
                continue  # only reached via non-tester tasks
            exec_starts = [x["span_start"] for x in st_tasks if x["code"] in cls.EXECUTION_START_CODES and x["span_start"]]
            test_start = min(exec_starts) if exec_starts else None
            outcomes = defaultdict(int)
            for pt in s["points"]:
                outcomes[pt["outcome"]] += 1
            total_pts = sum(outcomes.values())
            executed = total_pts - outcomes["Not run"] - outcomes["In progress"]
            open_bugs = [b for b in s["bugs"] if b["open"]]

            if test_start and test_start in day_no:
                start_day = day_no[test_start]
            elif test_start and test_start < start:
                start_day = 1
            else:
                start_day = None
            n = len(sprint_days)
            if start_day is None:
                timing = "Not started"
            elif start_day <= n / 3:
                timing = "Early"
            elif start_day <= 2 * n / 3:
                timing = "Mid"
            else:
                timing = "Late"

            done = s["state"].lower() in STORY_DONE_STATES
            done_on = clock.day(s.get("done_on"))
            # judged as at sprint end when the sprint is over (a story finished later still spilled over)
            done_by_end = done and (done_on <= finish if done_on else True) if today > finish else done
            reasons = []
            if not done:
                if timing == "Not started":
                    reasons.append("Execution not started (build likely not deployed)")
                elif timing == "Late":
                    reasons.append(f"Late test start (day {start_day} of {n})")
                if open_bugs:
                    reasons.append(f"{len(open_bugs)} open bug(s)")
                if outcomes["Blocked"]:
                    reasons.append(f"{outcomes['Blocked']} blocked test(s)")
                if total_pts and executed < total_pts:
                    reasons.append(f"{total_pts - executed} test point(s) not executed")
                if not total_pts:
                    reasons.append("No test cases linked (Tested By)")
                if not st_tasks:
                    reasons.append("No testing tasks")
                if any(not x["is_closed"] for x in st_tasks if x["code"] in ("TD", "TR")):
                    reasons.append("Test design/review still open")

            stories.append({
                "id": s["id"], "type": s["type"], "title": s["title"], "state": s["state"], "team": team["name"],
                "story_points": s.get("story_points"), "done_by_end": done_by_end,
                "done": done, "test_start": test_start, "start_day": start_day, "sprint_len": n, "timing": timing,
                "test_days_left": sum(1 for d in sprint_days if test_start and d >= test_start) if test_start else 0,
                "points_total": total_pts, "executed": executed, "outcomes": dict(outcomes),
                "exec_pct": round(100 * executed / total_pts) if total_pts else None,
                "pass_pct": round(100 * outcomes["Passed"] / total_pts) if total_pts else None,
                "bugs_open": open_bugs, "bugs_total": len(s["bugs"]),
                "tasks": [x["id"] for x in st_tasks],
                "effort": round(sum(x["completed"] for x in st_tasks), 1),
                "reasons": reasons,
            })
            story_ctx = {**stories[-1], "task_objs": st_tasks,
                         "tc_objs": [tc for tc in team_tcs if s["id"] in tc["stories"]]}
            for r, item, detail, who in hygiene.run(active_rules, "story", story_ctx, ctx):
                add_finding(r, item, detail, who)

        team_views.append({
            "name": team["name"], "iteration": it["name"], "start": start, "finish": finish,
            "days": sprint_days, "as_of": team_as_of, "elapsed": len(elapsed),
            "tasks": len(team_tasks),
            "capacity_to_date": round(sum(h for m in team["members"] if is_tester(m["unique"])
                                          for d in elapsed if d not in days_off_set(m["days_off"]) | team_off
                                          for h in [m["capacity_per_day"]]), 1),
            "logged_to_date": round(sum(h for x in team_tasks for k, per_day in x["daily"].items() if is_tester(k)
                                        for d, h in per_day.items() if start <= d <= team_as_of), 1),
            "unplanned_h": round(sum(x["completed"] for x in team_tasks if x["created"] and x["created"] > start), 1),
            "tasks_closed": sum(1 for x in team_tasks if x["is_closed"]),
            "effort": round(sum(x["completed"] for x in team_tasks), 1),
            "remaining": round(sum(x["remaining"] for x in team_tasks if not x["is_closed"]), 1),
            "group_hours": _sum_by(team_tasks, "group"),
            "testers": len(testers), "tester_source": tester_source if testers else "none found - not filtered",
            "excluded": sum(1 for x in excluded if x["team"] == team["name"]),
        })

    # ---- per person roll-up ----
    for p in people.values():
        days = sorted(p["sprint_days"])
        window = (days[0], days[-1]) if days else (None, None)
        as_of_p = min(today, window[1]) if window[1] else today
        p["days"] = days
        p["capacity"] = round(sum(p["daily_capacity"].values()), 1)
        p["capacity_to_date"] = round(sum(h for d, h in p["daily_capacity"].items() if d <= as_of_p), 1)
        in_window = {d: h for d, h in p["daily_logged"].items() if window[0] and window[0] <= d <= window[1]}
        p["logged"] = round(sum(in_window.values()), 1)
        p["logged_to_date"] = round(sum(h for d, h in in_window.items() if d <= as_of_p), 1)
        p["logged_outside"] = round(sum(p["daily_logged"].values()) - p["logged"], 1)
        own = [tasks[i] for i in p["task_ids"] if tasks[i]["owner_key"] == p["key"]]
        p["planned"] = round(sum(t["original"] or (t["completed"] + t["remaining"]) for t in own), 1)
        p["remaining"] = round(sum(t["remaining"] for t in own if not t["is_closed"]), 1)
        p["tasks_total"] = len(own)
        p["tasks_closed"] = sum(1 for t in own if t["is_closed"])
        p["util"] = p["logged_to_date"] / p["capacity_to_date"] if p["capacity_to_date"] else None
        p["plan_load"] = p["planned"] / p["capacity"] if p["capacity"] else None
        p["mix"] = defaultdict(float)
        for tid in p["task_ids"]:
            t = tasks[tid]
            p["mix"][t["group"]] += sum(t["daily"].get(p["key"], {}).values())
        p["mix"] = {g: round(h, 1) for g, h in p["mix"].items() if abs(h) > 0.01}
        p["flags"] = sum(1 for f in findings if f["person_key"] == p["key"])
        p["switching"] = _avg_tasks_per_day(p, tasks)
        if p["util"] is None:
            p["status"] = "No capacity set" if p["logged"] else "-"
        elif p["util"] > cfg.over_util:
            p["status"] = "Over-utilised"
        elif p["util"] < cfg.under_util:
            p["status"] = "Under-utilised / not logging"
        else:
            p["status"] = "Balanced"

    relevant = list(people.values())
    utils = [p["util"] for p in relevant if p["util"] is not None]
    balance = None
    if len(utils) >= 2 and statistics.mean(utils) > 0:
        balance = statistics.pstdev(utils) / statistics.mean(utils)

    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["rule"], f["team"], f["task"]))
    model = {
        "org": snapshot["org"], "project": snapshot["project"], "generated": snapshot["generated"],
        "as_of": today, "teams": team_views,
        "people": sorted(relevant, key=lambda p: p["name"].lower()),
        "tasks": tasks, "stories": sorted(stories, key=lambda s: (s["done"], s["team"], s["id"])),
        "findings": findings, "balance_cv": balance,
        "rules": active_rules, "excluded": excluded,
        "test_cases": sorted(test_cases, key=lambda t: (t["team"], t["id"])),
    }
    model["contribution"] = contribution.build(model, snapshot, cfg, clock)
    return model


def _plain(html_text):
    """Discussion comments are HTML - reduce to plain text."""
    text = re.sub(r"<[^>]+>", " ", html_text or "")
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _sum_by(task_list, key):
    out = defaultdict(float)
    for t in task_list:
        out[t[key]] += t["completed"]
    return {k: round(v, 1) for k, v in out.items()}


def _avg_tasks_per_day(p, tasks):
    per_day = defaultdict(set)
    for tid in p["task_ids"]:
        for d, h in tasks[tid]["daily"].get(p["key"], {}).items():
            if h > 0:
                per_day[d].add(tid)
    return round(statistics.mean(len(v) for v in per_day.values()), 1) if per_day else 0.0


def gantt_rows(model, person_key):
    """Tasks a person owns or logged effort on, ordered by when they started."""
    rows = [t for t in model["tasks"].values() if t["owner_key"] == person_key or person_key in t["daily"]]
    far = date.max
    return sorted(rows, key=lambda t: (t["span_start"] or far, t["id"]))
