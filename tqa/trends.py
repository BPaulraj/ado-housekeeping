"""Sprint-over-sprint trends from several analysed sprints (oldest first).

Same principle as the single-sprint report: numbers are computed here, the
renderers only format them, and the purpose is balancing and coaching.
"""

import statistics

GROUPS = ["Design", "Execution", "Automation", "Performance", "Support", "Unclassified"]


def _pct(a, b):
    return round(100 * a / b) if b else None


def _sprint_row(model):
    teams = model["teams"]
    stories = model["stories"]
    effort = sum(t["effort"] for t in teams)
    group_h = {g: sum(t["group_hours"].get(g, 0) for t in teams) for g in GROUPS}
    late = [s for s in stories if s["timing"] in ("Late", "Not started")]
    cap = sum(t["capacity_to_date"] for t in teams)
    logged = sum(t["logged_to_date"] for t in teams)
    tasks = sum(t["tasks"] for t in teams)
    contrib = model["contribution"]["people"]
    executed = [tc for tc in model["test_cases"] if tc["runs"]]
    return {
        "sprint": " / ".join(sorted({t["iteration"] for t in teams})),
        "start": min(t["start"] for t in teams), "finish": max(t["finish"] for t in teams),
        "utilisation_pct": _pct(logged, cap), "logged_h": round(logged, 1), "capacity_h": round(cap, 1),
        "balance_cv": round(model["balance_cv"], 2) if model["balance_cv"] is not None else None,
        "stories": len(stories), "spillover": sum(1 for s in stories if not s["done_by_end"]),
        "late_start_pct": _pct(len(late), len(stories)),
        "avg_start_day": round(statistics.mean(s["start_day"] for s in stories if s["start_day"]), 1)
        if any(s["start_day"] for s in stories) else None,
        "hygiene": len(model["findings"]),
        "hygiene_high": sum(1 for f in model["findings"] if f["severity"] == "High"),
        "hygiene_per_10_tasks": round(10 * len(model["findings"]) / tasks, 1) if tasks else None,
        "executions": sum(p["output"]["executions_manual"] + p["output"]["executions_automated"] for p in contrib),
        "bugs_raised": sum(p["output"]["bugs_raised"] for p in contrib),
        "evidence_pct": _pct(sum(1 for tc in executed if tc["attachments_total"]), len(executed)),
        "mix_pct": {g: _pct(h, effort) or 0 for g, h in group_h.items()},
        "unplanned_pct": _pct(sum(t["unplanned_h"] for t in teams), effort),
        "rule_counts": _count(f["rule"] for f in model["findings"]),
    }


def _team_row(model, team):
    stories = [s for s in model["stories"] if s["team"] == team["name"]]
    return {
        "utilisation_pct": _pct(team["logged_to_date"], team["capacity_to_date"]),
        "spillover": sum(1 for s in stories if not s["done_by_end"]), "stories": len(stories),
        "late_start_pct": _pct(sum(1 for s in stories if s["timing"] in ("Late", "Not started")), len(stories)),
        "hygiene_per_10_tasks": round(10 * sum(1 for f in model["findings"] if f["team"] == team["name"]) / team["tasks"], 1)
        if team["tasks"] else None,
        "automation_pct": _pct(team["group_hours"].get("Automation", 0), team["effort"]),
    }


def _tester_row(model, p, prof):
    mix = {g: h for g, h in p["mix"].items() if h > 0}
    total = sum(mix.values())
    top = max(mix.items(), key=lambda kv: kv[1]) if mix else (None, 0)
    return {
        "utilisation_pct": round(p["util"] * 100) if p["util"] is not None else None, "status": p["status"],
        "logged_h": p["logged_to_date"], "capacity_h": p["capacity_to_date"], "teams": [t["team"] for t in p["teams"]],
        "hygiene": p["flags"], "executions": prof["output"]["executions_manual"] + prof["output"]["executions_automated"],
        "bugs_raised": prof["output"]["bugs_raised"], "reviews_for_others": prof["collaboration"]["reviews_for_others"],
        "main_work": top[0], "main_work_pct": _pct(top[1], total), "unplanned_h": prof["flow"]["unplanned_h"],
    }


def _count(items):
    out = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return out


def build(models):
    """models: analysed sprints, oldest first."""
    sprints = [_sprint_row(m) for m in models]
    labels = [s["sprint"] for s in sprints]

    team_names = sorted({t["name"] for m in models for t in m["teams"]})
    teams = {name: [next((_team_row(m, t) for t in m["teams"] if t["name"] == name), None) for m in models]
             for name in team_names}

    testers = {}
    for i, m in enumerate(models):
        profs = {c["key"]: c for c in m["contribution"]["people"]}
        for p in m["people"]:
            entry = testers.setdefault(p["key"], {"name": p["name"], "sprints": [None] * len(models)})
            entry["sprints"][i] = _tester_row(m, p, profs[p["key"]])

    return {"labels": labels, "sprints": sprints, "teams": teams,
            "testers": dict(sorted(testers.items(), key=lambda kv: kv[1]["name"].lower())),
            "signals": _signals(labels, sprints, teams, testers)}


def _streak(values, test):
    """How many of the most recent values pass test, counting back until one fails."""
    n = 0
    for v in reversed(values):
        if v is None or not test(v):
            break
        n += 1
    return n


def _signals(labels, sprints, teams, testers):
    out = []
    add = lambda kind, who, text: out.append({"kind": kind, "who": who, "text": text})
    n = len(labels)
    if n < 2:
        return out

    for t in testers.values():
        rows = t["sprints"]
        status = [r["status"] if r else None for r in rows]
        over = _streak(status, lambda s: s == "Over-utilised")
        under = _streak(status, lambda s: s.startswith("Under"))
        if over >= 2:
            add("watch", t["name"], f"Over capacity for the last {over} sprints - sustained overload, rebalance next sprint")
        if under >= 2:
            add("watch", t["name"], f"Under 60% of capacity for the last {under} sprints - check for blockers or unlogged work")
        hyg = [r["hygiene"] for r in rows if r]
        if len(hyg) >= 3:
            before = statistics.mean(hyg[:-1])
            if before >= 2 and hyg[-1] <= before * 0.7:
                add("strength", t["name"], f"Hygiene findings down to {hyg[-1]} from an average of {before:.1f}")
            elif hyg[-1] >= 3 and hyg[-1] >= before * 1.5:
                add("watch", t["name"], f"Hygiene findings up to {hyg[-1]} from an average of {before:.1f}")
        recent = [r for r in rows[-3:] if r]
        if len(recent) == 3 and len({r["main_work"] for r in recent}) == 1 and all((r["main_work_pct"] or 0) >= 90 for r in recent):
            add("watch", t["name"], f"{recent[0]['main_work']} was 90%+ of their hours for 3 sprints - rotation or growth opportunity?")

    for name, rows in teams.items():
        spill = [r["spillover"] if r else None for r in rows]
        streak = _streak(spill, lambda v: v > 0)
        if streak >= 3:
            add("watch", name, f"Stories spilled over in each of the last {streak} sprints")
        late = [r["late_start_pct"] for r in rows if r and r["late_start_pct"] is not None]
        if len(late) >= 3 and late[-1] >= 40 and late[-1] > late[0]:
            add("watch", name, f"Late/not-started testing rose from {late[0]}% to {late[-1]}% of stories - raise deployment timing with the team")

    cv = [s["balance_cv"] for s in sprints if s["balance_cv"] is not None]
    if len(cv) >= 3 and cv[-1] > cv[-2] > cv[-3] and cv[-1] >= 0.15:
        add("watch", "All testers", f"Workload balance getting more uneven 3 sprints running (CV {cv[-3]} → {cv[-1]})")
    auto = [s["mix_pct"]["Automation"] for s in sprints]
    if n >= 3 and auto[-1] - auto[0] >= 5:
        add("strength", "All testers", f"Automation share of hours up from {auto[0]}% to {auto[-1]}%")
    elif n >= 3 and auto[0] - auto[-1] >= 5:
        add("watch", "All testers", f"Automation share of hours down from {auto[0]}% to {auto[-1]}%")
    ev = [s["evidence_pct"] for s in sprints if s["evidence_pct"] is not None]
    if len(ev) >= 2 and ev[-1] < 80:
        add("watch", "All testers", f"Evidence attached on {ev[-1]}% of executed test cases last sprint")
    return out
