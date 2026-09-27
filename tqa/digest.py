"""Compact JSON digest of an analysed sprint.

Written next to every report as <stem>_digest.json. It is the input for the
GitHub Copilot prompts in .github/prompts (sprint summary, tester nudges,
classification tuning, closing-comment review) - Copilot reads this file
instead of calling ADO or parsing the HTML report.
"""

import json
from datetime import date

MAX_COMMENT = 300


def _pct(v):
    return round(v * 100) if v is not None else None


def build(model):
    by_person = {}
    for f in model["findings"]:
        by_person.setdefault(f["person"], []).append(
            {"rule": f["rule"], "severity": f["severity"], "check": f["text"], "item_type": f.get("kind", "Task"),
             "item": f["task"], "title": f["title"], "detail": f["detail"]})
    by_rule = {}
    for f in model["findings"]:
        r = by_rule.setdefault(f["rule"], {"check": f["text"], "severity": f["severity"], "count": 0})
        r["count"] += 1

    tcs = model["test_cases"]
    executed = [t for t in tcs if t["runs"]]
    tasks = model["tasks"].values()
    return {
        "meta": {"project": model["project"], "as_of": model["as_of"], "generated": model["generated"],
                 "workload_balance_cv": round(model["balance_cv"], 2) if model["balance_cv"] is not None else None},
        "teams": [{
            "name": t["name"], "sprint": t["iteration"], "start": t["start"], "finish": t["finish"],
            "day": t["elapsed"], "sprint_days": len(t["days"]), "tasks": t["tasks"], "tasks_closed": t["tasks_closed"],
            "effort_h": t["effort"], "remaining_h": t["remaining"], "effort_by_group_h": t["group_hours"],
            "testers": t["testers"], "tester_source": t["tester_source"], "excluded_non_tester_tasks": t["excluded"],
        } for t in model["teams"]],
        "testers": [{
            "name": p["name"], "teams": [x["team"] for x in p["teams"]], "capacity_h": p["capacity"],
            "capacity_to_date_h": p["capacity_to_date"], "logged_to_date_h": p["logged_to_date"],
            "utilisation_pct": _pct(p["util"]), "plan_load_pct": _pct(p["plan_load"]), "remaining_h": p["remaining"],
            "days_off": len(p["days_off"]), "tasks": p["tasks_total"], "tasks_closed": p["tasks_closed"],
            "avg_tasks_per_day": p["switching"], "effort_mix_h": p["mix"], "status": p["status"], "hygiene_findings": p["flags"],
        } for p in model["people"]],
        "stories": [{
            "id": s["id"], "title": s["title"], "team": s["team"], "state": s["state"], "done": s["done"],
            "test_start_timing": s["timing"], "test_start_day": s["start_day"], "sprint_days": s["sprint_len"],
            "executed_pct": s["exec_pct"], "passed_pct": s["pass_pct"], "test_points": s["points_total"],
            "open_bugs": [{"id": b["id"], "severity": b["severity"]} for b in s["bugs_open"]],
            "qa_effort_h": s["effort"], "why_not_done": s["reasons"],
        } for s in model["stories"]],
        "contribution": {
            "note": "For balancing and coaching, not ranking.",
            "bug_reasons_maintained": model["contribution"]["bug_reasons_maintained"],
            "has_code_data": model["contribution"]["has_code_data"],
            "people": [{k: v for k, v in p.items() if k != "key"} for p in model["contribution"]["people"]],
        },
        "test_cases": {
            "linked": len(tcs), "executed": len(executed),
            "executed_without_evidence": sum(1 for t in executed if t["attachments_total"] == 0),
            "without_priority": sum(1 for t in tcs if t["priority"] in (None, "")),
            "flagged": sum(1 for t in tcs if t["flags"]),
        },
        "hygiene": {"total": len(model["findings"]), "by_rule": by_rule, "by_person": by_person},
        "rules": [{"id": r.id, "check": r.title, "severity": r.severity, "scope": r.scope, "enabled": r.enabled,
                   "meaning": r.description} for r in model["rules"].values()],
        "unclassified_task_titles": sorted({t["title"] for t in tasks if t["code"] == "UN"}),
        "classified_examples": sorted({(t["label"], t["title"]) for t in tasks if t["code"] != "UN"})[:60],
        "closing_comments": [{
            "task": t["id"], "title": t["title"], "type": t["label"], "owner": t["owner"]["name"] if t["owner"] else None,
            "completed_h": t["completed"], "comment": t["owner_last_comment"][:MAX_COMMENT],
        } for t in tasks if t["is_closed"] and t["owner_last_comment"]],
    }


def write(model, path):
    def default(o):
        if isinstance(o, date):
            return o.isoformat()
        if isinstance(o, (set, tuple)):
            return list(o)
        raise TypeError(type(o))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(build(model), fh, indent=1, default=default)
