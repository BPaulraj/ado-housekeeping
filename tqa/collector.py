"""Collects a normalised sprint snapshot from Azure DevOps.

The snapshot is plain JSON so a sprint can be re-analysed later (--from-snapshot)
without calling ADO again.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

from .ado_client import AdoError
from .config import testers_for

F_STATE = "System.State"
F_ASSIGNED = "System.AssignedTo"
F_CHANGED_DATE = "System.ChangedDate"
F_CHANGED_BY = "System.ChangedBy"
F_COMPLETED = "Microsoft.VSTS.Scheduling.CompletedWork"
F_REMAINING = "Microsoft.VSTS.Scheduling.RemainingWork"
F_ORIGINAL = "Microsoft.VSTS.Scheduling.OriginalEstimate"
F_ACTIVITY = "Microsoft.VSTS.Common.Activity"

PARENT = "System.LinkTypes.Hierarchy-Reverse"
CHILD = "System.LinkTypes.Hierarchy-Forward"
RELATED = "System.LinkTypes.Related"
TESTED_BY = "Microsoft.VSTS.Common.TestedBy-Forward"

class NotEnoughSprints(AdoError):
    pass


OPEN_BUG_STATES = {"new", "active", "proposed", "committed", "open", "in progress", "reopened"}


def ident(value):
    """Normalise an ADO identity (dict or 'Name <email>' string) to {name, unique}."""
    if not value:
        return None
    if isinstance(value, dict):
        return {"name": value.get("displayName", ""), "unique": (value.get("uniqueName") or value.get("displayName", "")).lower()}
    m = re.match(r"(.*)<(.+)>", str(value))
    if m:
        return {"name": m.group(1).strip(), "unique": m.group(2).strip().lower()}
    return {"name": str(value), "unique": str(value).lower()}


def _id_from_url(url):
    return int(url.rstrip("/").rsplit("/", 1)[-1])


def _q(text):
    return text.replace("'", "''")


def _log(msg):
    print(f"  {msg}", flush=True)


# --------------------------------------------------------------------------
def select_iteration(client, team, selector, offset=0):
    """selector: 'current' | 'previous' | iteration name or path; offset = how many sprints before that one."""
    iterations = client.team_iterations(team)
    iterations = [i for i in iterations if i.get("attributes", {}).get("startDate")]
    iterations.sort(key=lambda i: i["attributes"]["startDate"])
    if not iterations:
        raise AdoError(f"Team '{team}' has no dated iterations")
    sel = (selector or "current").strip().lower()
    if sel in ("current", "previous"):
        idx = next((n for n, i in enumerate(iterations) if i["attributes"].get("timeFrame") == "current"), None)
        if idx is None:
            now = datetime.now(timezone.utc).isoformat()
            past = [n for n, i in enumerate(iterations) if i["attributes"]["startDate"] <= now]
            idx = past[-1] if past else 0
        if sel == "previous":
            idx = max(0, idx - 1)
        it = iterations[idx]
    else:
        it = next((i for i in iterations if sel in (i["name"].lower(), i["path"].lower())), None)
        if not it:
            names = ", ".join(i["name"] for i in iterations[-8:])
            raise AdoError(f"Iteration '{selector}' not found for team '{team}'. Recent: {names}")
    if offset:
        pos = iterations.index(it) - offset
        if pos < 0:
            raise NotEnoughSprints(f"Team '{team}' has only {iterations.index(it) + 1} sprint(s) up to '{selector}'")
        it = iterations[pos]
    a = it["attributes"]
    return {"id": it["id"], "name": it["name"], "path": it["path"], "start": a["startDate"], "finish": a["finishDate"]}


def _members(raw_members):
    out = []
    for m in raw_members:
        who = ident(m.get("teamMember"))
        if not who:
            continue
        acts = [{"name": a.get("name") or "", "capacity_per_day": float(a.get("capacityPerDay") or 0)} for a in m.get("activities", [])]
        out.append({
            **who,
            "activities": acts,
            "capacity_per_day": round(sum(a["capacity_per_day"] for a in acts), 2),
            "days_off": [{"start": d["start"], "end": d["end"]} for d in m.get("daysOff", [])],
        })
    return out


def _area_clause(areas):
    if not areas:
        return ""
    parts = [f"[System.AreaPath] {'UNDER' if inc else '='} '{_q(path)}'" for path, inc in areas]
    return " AND (" + " OR ".join(parts) + ")"


def _task_query(iteration_path, areas, testers):
    area_clause = _area_clause(areas)
    who = ""
    if testers:
        who = " OR [System.AssignedTo] IN (" + ", ".join(f"'{_q(t)}'" for t in testers) + ")"
    return (
        "SELECT [System.Id] FROM WorkItems"
        " WHERE [System.TeamProject] = @project"
        " AND [System.WorkItemType] = 'Task'"
        f" AND [System.IterationPath] EVER '{_q(iteration_path)}'"   # incl. tasks later moved to another sprint
        f"{area_clause}"
        " AND [System.State] <> 'Removed'"
        f" AND ([{F_ACTIVITY}] = 'Testing' OR [System.Title] CONTAINS 'QA'{who})"
    )


def _norm_revision(r):
    f = r.get("fields", {})
    return {
        "rev": r.get("rev"),
        "date": f.get(F_CHANGED_DATE),
        "state": f.get(F_STATE),
        "assignee": ident(f.get(F_ASSIGNED)),
        "changed_by": ident(f.get(F_CHANGED_BY)),
        "completed": f.get(F_COMPLETED),
        "remaining": f.get(F_REMAINING),
        "original": f.get(F_ORIGINAL),
    }


def _norm_comment(c):
    return {"by": ident(c.get("createdBy")), "date": c.get("createdDate"), "text": c.get("text", "")}


def _norm_task(wi, revisions, comments):
    f = wi["fields"]
    parent = next((_id_from_url(r["url"]) for r in wi.get("relations") or [] if r["rel"] == PARENT), None)
    return {
        "id": wi["id"],
        "title": f.get("System.Title", ""),
        "state": f.get(F_STATE, ""),
        "activity": f.get(F_ACTIVITY) or "",
        "assignee": ident(f.get(F_ASSIGNED)),
        "created": f.get("System.CreatedDate"),
        "original": f.get(F_ORIGINAL),
        "completed": f.get(F_COMPLETED),
        "remaining": f.get(F_REMAINING),
        "area": f.get("System.AreaPath", ""),
        "iteration": f.get("System.IterationPath", ""),
        "tags": f.get("System.Tags", ""),
        "parent": parent,
        "revisions": [_norm_revision(r) for r in sorted(revisions, key=lambda r: r.get("rev", 0))],
        "comments": [_norm_comment(c) for c in comments],
    }


def _outcome(point):
    raw = (point.get("outcome") or "").lower()
    state = (point.get("state") or "").lower()
    if raw == "passed":
        return "Passed"
    if raw == "failed":
        return "Failed"
    if raw == "blocked":
        return "Blocked"
    if raw == "notapplicable":
        return "N/A"
    if raw == "inprogress" or state == "inprogress":
        return "In progress"
    return "Not run"


def collect_team(client, team_cfg, selector, cfg, workers=8, offset=0):
    team = team_cfg.name
    _log(f"[{team}] resolving sprint ...")
    iteration = select_iteration(client, team, selector, offset)
    settings = client.team_settings(team)
    members = _members(client.capacities(team, iteration["id"]))
    team_off = client.team_days_off(team, iteration["id"])

    if team_cfg.area_path:
        areas = [(team_cfg.area_path, True)]
    else:
        tfv = client.team_field_values(team)
        areas = [(v["value"], v.get("includeChildren", False)) for v in tfv.get("values", [])]

    testers, source = testers_for(cfg, team, members)
    _log(f"[{team}] sprint '{iteration['name']}' ({iteration['start'][:10]} -> {iteration['finish'][:10]}), "
         f"{len(members)} members with capacity, {len(testers)} testers (from {source})")
    if not testers:
        _log(f"[{team}] WARNING: no testers identified - set team.N.testers or testers= in ado.properties; "
             "report will include everyone's QA-named tasks")

    try:
        ids = client.wiql(team, _task_query(iteration["path"], areas, sorted(testers)))
    except AdoError:
        # Identity matching in WIQL can reject some identity formats; fall back to the naming convention only.
        ids = client.wiql(team, _task_query(iteration["path"], areas, []))
    _log(f"[{team}] {len(ids)} testing tasks - fetching history & comments ...")

    items = {w["id"]: w for w in client.work_items(ids, relations=True)}

    def detail(wid):
        return wid, client.revisions(wid), client.comments(wid)

    tasks = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for wid, revs, comments in pool.map(detail, list(items)):
            tasks.append(_norm_task(items[wid], revs, comments))

    stories, test_cases = collect_stories(client, {t["parent"] for t in tasks if t["parent"]}, cfg)

    return {
        "name": team,
        "areas": [a for a, _ in areas],
        "iteration": iteration,
        "working_days": [d.lower() for d in settings.get("workingDays", ["monday", "tuesday", "wednesday", "thursday", "friday"])],
        "team_days_off": [{"start": d["start"], "end": d["end"]} for d in team_off],
        "members": members,
        "testers": sorted(testers),
        "tasks": sorted(tasks, key=lambda t: t["id"]),
        "stories": stories,
        "test_cases": test_cases,
        "bugs": collect_sprint_bugs(client, team, areas, iteration),
        "test_case_activity": collect_test_case_activity(client, team, areas, iteration),
    }


def _sprint_dates(iteration):
    return iteration["start"][:10], (date.fromisoformat(iteration["finish"][:10]) + timedelta(days=1)).isoformat()


def collect_sprint_bugs(client, team, areas, iteration):
    """Bugs created, resolved or closed during the sprint in the team's area (raised / retested by testers)."""
    start, end = _sprint_dates(iteration)
    ids = client.wiql(team, (
        "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = @project AND [System.WorkItemType] = 'Bug'"
        f"{_area_clause(areas)} AND [System.CreatedDate] < '{end}'"
        f" AND ([System.CreatedDate] >= '{start}' OR [Microsoft.VSTS.Common.ResolvedDate] >= '{start}'"
        f" OR [Microsoft.VSTS.Common.ClosedDate] >= '{start}')"))
    fields = ["System.Id", "System.Title", "System.State", "System.Reason", "Microsoft.VSTS.Common.Severity",
              "Microsoft.VSTS.Common.Priority", "System.CreatedDate", "System.CreatedBy",
              "Microsoft.VSTS.Common.ResolvedDate", "Microsoft.VSTS.Common.ResolvedBy", "Microsoft.VSTS.Common.ResolvedReason",
              "Microsoft.VSTS.Common.ClosedDate", "Microsoft.VSTS.Common.ClosedBy"]
    out = []
    for b in client.work_items(ids, fields=fields):
        f = b["fields"]
        out.append({
            "id": b["id"], "title": f.get("System.Title", ""), "state": f.get("System.State", ""),
            "reason": f.get("System.Reason", ""), "severity": f.get("Microsoft.VSTS.Common.Severity", ""),
            "priority": f.get("Microsoft.VSTS.Common.Priority"),
            "created": f.get("System.CreatedDate"), "created_by": ident(f.get("System.CreatedBy")),
            "resolved": f.get("Microsoft.VSTS.Common.ResolvedDate"), "resolved_by": ident(f.get("Microsoft.VSTS.Common.ResolvedBy")),
            "resolved_reason": f.get("Microsoft.VSTS.Common.ResolvedReason", ""),
            "closed": f.get("Microsoft.VSTS.Common.ClosedDate"), "closed_by": ident(f.get("Microsoft.VSTS.Common.ClosedBy")),
        })
    _log(f"[{team}] {len(out)} bugs raised/resolved/closed in sprint")
    return out


def collect_test_case_activity(client, team, areas, iteration, workers=8):
    """Test cases created in the sprint (authoring) and moved to Ready in the sprint (review), with who did it."""
    start, end = _sprint_dates(iteration)
    ids = client.wiql(team, (
        "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = @project AND [System.WorkItemType] = 'Test Case'"
        f"{_area_clause(areas)} AND (([System.CreatedDate] >= '{start}' AND [System.CreatedDate] < '{end}')"
        f" OR ([Microsoft.VSTS.Common.StateChangeDate] >= '{start}' AND [Microsoft.VSTS.Common.StateChangeDate] < '{end}'))"))
    fields = ["System.Id", "System.Title", "System.State", "System.CreatedDate", "System.CreatedBy",
              "Microsoft.VSTS.Common.StateChangeDate"]
    items = client.work_items(ids, fields=fields)

    def ready_transition(wi):
        f = wi["fields"]
        changed = (f.get("Microsoft.VSTS.Common.StateChangeDate") or "")[:10]
        if f.get("System.State", "").lower() not in ("ready", "closed") or not (start <= changed < end):
            return wi, None
        last, prev_state = None, None
        for r in client.revisions(wi["id"]):
            st = r["fields"].get(F_STATE)
            if st and st.lower() == "ready" and (prev_state or "").lower() != "ready":
                last = {"date": r["fields"].get(F_CHANGED_DATE), "by": ident(r["fields"].get(F_CHANGED_BY))}
            prev_state = st
        return wi, last

    out = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for wi, ready in pool.map(ready_transition, items):
            f = wi["fields"]
            created = f.get("System.CreatedDate") or ""
            out.append({
                "id": wi["id"], "title": f.get("System.Title", ""), "state": f.get("System.State", ""),
                "created": created if start <= created[:10] < end else None,   # authored only if created in sprint
                "created_by": ident(f.get("System.CreatedBy")),
                "ready_on": ready["date"] if ready and start <= (ready["date"] or "")[:10] < end else None,
                "ready_by": ready["by"] if ready else None,
            })
    _log(f"[{team}] {len(out)} test cases authored/reviewed in sprint")
    return out


def collect_executions(client, start, end, workers=8):
    """Every test result completed in the window (manual and automated), with who ran it and the plan's area."""
    plans = {str(p["id"]): p for p in client.test_plans()}
    runs = client.test_runs(start, end)

    def results(run):
        return run, client.run_results(run["id"])

    out = []
    lo, hi = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for run, res in pool.map(results, runs):
            plan = plans.get(str((run.get("plan") or {}).get("id")), {})
            for r in res:
                done = r.get("completedDate") or ""
                if not (lo <= done[:10] < hi):
                    continue
                out.append({
                    "run_id": run["id"], "result_id": r["id"], "automated": bool(run.get("isAutomated")),
                    "test_case": int((r.get("testCase") or {}).get("id") or 0), "title": r.get("testCaseTitle", ""),
                    "outcome": _outcome(r), "run_by": ident(r.get("runBy")), "completed": done,
                    "plan": plan.get("name", ""), "plan_area": plan.get("areaPath", ""),
                })
    _log(f"[project] {len(out)} test results executed in sprint window ({len(runs)} runs)")
    return out


def collect_code(client, start, end, include=""):
    """Commits and pull requests in the window across the project's Git repos (automation contribution)."""
    rx = re.compile(include, re.I) if include else None
    repos = [r for r in client.repositories() if not rx or rx.search(r["name"])]
    commits = []
    for repo in repos:
        if repo.get("isDisabled"):
            continue
        for c in client.commits(repo["id"], start, end):
            author = c.get("author") or {}
            commits.append({
                "repo": repo["name"], "id": c["commitId"][:10], "date": author.get("date"),
                "author": {"name": author.get("name", ""), "unique": (author.get("email") or "").lower()},
                "comment": (c.get("comment") or "")[:160],
                "work_items": [int(x) for x in re.findall(r"#(\d+)", c.get("comment") or "")],
            })
    prs = []
    end_iso = end.strftime("%Y-%m-%dT%H:%M:%S")
    for p in client.pull_requests_since(start):
        repo = (p.get("repository") or {}).get("name", "")
        if (rx and not rx.search(repo)) or p.get("creationDate", "") >= end_iso:
            continue
        prs.append({
            "repo": repo, "id": p["pullRequestId"], "title": p.get("title", ""), "status": p.get("status", ""),
            "created": p.get("creationDate"), "closed": p.get("closedDate"), "created_by": ident(p.get("createdBy")),
            "reviewers": [{**ident(r), "vote": r.get("vote", 0)} for r in p.get("reviewers", []) if not r.get("isContainer")],
        })
    _log(f"[project] {len(commits)} commits and {len(prs)} pull requests in {len(repos)} repo(s)")
    return {"repos": [r["name"] for r in repos], "commits": commits, "pull_requests": prs}


def collect_stories(client, story_ids, cfg):
    """Returns (stories, test_cases) for the given parent story ids."""
    if not story_ids:
        return [], []
    raw = client.work_items(sorted(story_ids), relations=True)
    linked, tested_by = set(), {}
    for s in raw:
        rels = s.get("relations") or []
        tested_by[s["id"]] = [_id_from_url(r["url"]) for r in rels if r["rel"] == TESTED_BY]
        linked.update(_id_from_url(r["url"]) for r in rels if r["rel"] in (CHILD, RELATED) and "/workItems/" in r["url"])

    bug_fields = ["System.Id", "System.WorkItemType", "System.Title", "System.State",
                  "Microsoft.VSTS.Common.Severity", "System.AssignedTo", "System.CreatedDate"]
    bugs = {b["id"]: b for b in client.work_items(sorted(linked), fields=bug_fields)
            if b["fields"].get("System.WorkItemType") == "Bug"}

    all_cases = sorted({tc for v in tested_by.values() for tc in v})
    points_by_case = {}
    if all_cases:
        plan_re = re.compile(cfg.testplan_filter, re.I) if cfg.testplan_filter else None
        plan_names = client.test_plan_names()
        for p in client.test_points_for_cases(all_cases):
            plan_ref = p.get("testPlan") or {}
            plan = plan_ref.get("name") or plan_names.get(str(plan_ref.get("id")), str(plan_ref.get("id", "")))
            if plan_re and not plan_re.search(plan):
                continue
            tc = int((p.get("testCase") or {}).get("id", 0))
            points_by_case.setdefault(tc, []).append({
                "test_case": tc,
                "outcome": _outcome(p),
                "plan": plan,
                "suite": (p.get("suite") or {}).get("name", ""),
                "tester": ident(p.get("assignedTo")),
                "last_updated": p.get("lastUpdatedDate"),
                "run_id": (p.get("lastTestRun") or {}).get("id"),
                "result_id": (p.get("lastResult") or {}).get("id"),
            })

    out = []
    for s in raw:
        f = s["fields"]
        rels = s.get("relations") or []
        story_bugs = []
        for r in rels:
            if r["rel"] in (CHILD, RELATED) and "/workItems/" in r["url"]:
                b = bugs.get(_id_from_url(r["url"]))
                if b:
                    bf = b["fields"]
                    story_bugs.append({
                        "id": b["id"], "title": bf.get("System.Title", ""), "state": bf.get("System.State", ""),
                        "severity": bf.get("Microsoft.VSTS.Common.Severity", ""),
                        "assignee": ident(bf.get("System.AssignedTo")), "created": bf.get("System.CreatedDate"),
                        "open": bf.get("System.State", "").lower() in OPEN_BUG_STATES,
                    })
        out.append({
            "id": s["id"],
            "type": f.get("System.WorkItemType", ""),
            "story_points": f.get("Microsoft.VSTS.Scheduling.StoryPoints"),
            "done_on": f.get("Microsoft.VSTS.Common.ResolvedDate") or f.get("Microsoft.VSTS.Common.ClosedDate"),
            "title": f.get("System.Title", ""),
            "state": f.get(F_STATE, ""),
            "points": [pt for tc in tested_by[s["id"]] for pt in points_by_case.get(tc, [])],
            "test_cases": tested_by[s["id"]],
            "bugs": story_bugs,
        })
    test_cases = collect_test_cases(client, all_cases, points_by_case, tested_by)
    return out, test_cases


def collect_test_cases(client, case_ids, points_by_case, tested_by, workers=8):
    """Test case work items plus, for each executed point, who ran it and what evidence was attached."""
    if not case_ids:
        return []
    stories_of = {}
    for sid, cases in tested_by.items():
        for tc in cases:
            stories_of.setdefault(tc, []).append(sid)

    executed = [pt for pts in points_by_case.values() for pt in pts
                if pt["outcome"] not in ("Not run", "In progress") and pt.get("run_id") and pt.get("result_id")]

    def run_detail(pt):
        result = client.test_result(pt["run_id"], pt["result_id"])
        steps = sum(len(i.get("attachments") or []) for i in result.get("iterationDetails") or [])
        return pt, {
            "run_id": int(pt["run_id"]), "result_id": int(pt["result_id"]), "outcome": pt["outcome"], "plan": pt["plan"],
            "run_by": ident(result.get("runBy")), "completed": result.get("completedDate"),
            "attachments_result": len(client.test_result_attachments(pt["run_id"], pt["result_id"])),
            "attachments_steps": steps,
        }

    runs = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for pt, run in pool.map(run_detail, executed):
            runs.setdefault(pt["test_case"], []).append(run)

    out = []
    for wi in client.work_items(case_ids, relations=True):
        f = wi["fields"]
        out.append({
            "id": wi["id"],
            "title": f.get("System.Title", ""),
            "state": f.get(F_STATE, ""),
            "priority": f.get("Microsoft.VSTS.Common.Priority"),
            "assignee": ident(f.get(F_ASSIGNED)),
            "attachments_wi": sum(1 for r in wi.get("relations") or [] if r["rel"] == "AttachedFile"),
            "stories": stories_of.get(wi["id"], []),
            "runs": sorted(runs.get(wi["id"], []), key=lambda r: r["completed"] or ""),
        })
    return out


def resolve_iterations(client, cfg, selector="current", team_filter=None, offset=0):
    """Just the sprint of each team (cheap) - used to find cached snapshots before collecting."""
    return {t.name: select_iteration(client, t.name, selector, offset) for t in _teams(cfg, team_filter)}


def _teams(cfg, team_filter):
    if not cfg.teams:
        raise AdoError("No teams configured - add team.1.name=... to ado.properties (run with --list-teams to see names)")
    teams = [t for t in cfg.teams if not team_filter or t.name.lower() == team_filter.lower()]
    if not teams:
        raise AdoError(f"Team '{team_filter}' is not configured")
    return teams


def collect(client, cfg, selector="current", team_filter=None, offset=0):
    team_snaps = [collect_team(client, t, selector, cfg, offset=offset) for t in _teams(cfg, team_filter)]
    start = min(datetime.fromisoformat(t["iteration"]["start"][:10]) for t in team_snaps)
    end = max(datetime.fromisoformat(t["iteration"]["finish"][:10]) for t in team_snaps) + timedelta(days=1)
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "org": client.org,
        "project": client.project,
        "selector": selector,
        "teams": team_snaps,
        "executions": collect_executions(client, start, end),
        "code": collect_code(client, start, end, cfg.repos_include),
    }
