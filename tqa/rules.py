"""Work-item hygiene rules.

HOW TO ADD A RULE
-----------------
1. Pick the next free id (e.g. "H15") and write a function decorated with @rule.
2. Return None when the item is fine. Return a string (the detail shown in the
   report, may be "") for one finding, or a list of strings for several.
   To blame someone other than the item's owner, return (detail, person) where
   person is an identity dict {"name", "unique"} (e.g. the tester who ran a test).
3. That's it - the rule appears in the report's Rules tab and runs automatically.
4. Run `python -m tqa.selfcheck` - it fails if a rule crashes and warns if no demo
   data exercises it (add a case to tqa/demo.py).

    @rule("H15", "Medium", "Execution task closed on a weekend")
    def closed_on_weekend(t, ctx):
        if t["closed_on"] and t["closed_on"].weekday() >= 5:
            return f"closed {t['closed_on']:%a %d-%b}"

Task rules receive the analysed task dict `t` (see analysis.py for its fields) and
a `ctx` with: cfg, as_of, sprint_days, elapsed, wd_between(a, b), people.
Test case rules (scope="testcase") receive the analysed test case dict.
Story rules (scope="story") receive the story dict and return a list of
(task_dict, detail) pairs - the findings are raised against those tasks.

SWITCHING RULES OFF / CHANGING SEVERITY (ado.properties)
--------------------------------------------------------
    rule.H07.enabled=false
    rule.H04.severity=High
"""

from dataclasses import dataclass
from typing import Callable

ACTIVE_STATES = {"active", "in progress", "doing", "committed"}
NEW_STATES = {"new", "to do", "proposed"}
SEVERITIES = ("High", "Medium", "Low")


@dataclass
class Rule:
    id: str
    severity: str
    title: str
    scope: str
    check: Callable
    description: str = ""
    enabled: bool = True


REGISTRY = {}


def rule(rule_id, severity, title, scope="task"):
    def deco(fn):
        REGISTRY[rule_id] = Rule(rule_id, severity, title, scope, fn, " ".join((fn.__doc__ or "").split()))
        return fn
    return deco


def effective(cfg):
    """Rules with ado.properties overrides applied, in id order."""
    out = {}
    for rid in sorted(REGISTRY):
        base = REGISTRY[rid]
        o = cfg.rule_overrides.get(rid, {})
        sev = o.get("severity", base.severity)
        out[rid] = Rule(base.id, sev if sev in SEVERITIES else base.severity, base.title, base.scope,
                        base.check, base.description, o.get("enabled", True))
    return out


SCOPES = ("task", "testcase", "story")


def run(rules, scope, item, ctx):
    """Yields (rule, item, detail, person) for every enabled rule of the scope that fires.
    person is None unless the rule named someone other than the item's owner."""
    for r in rules.values():
        if not r.enabled or r.scope != scope:
            continue
        result = r.check(item, ctx)
        if result is None:
            continue
        if scope == "story":
            for task, detail in result:
                yield r, task, detail, None
        else:
            for one in (result if isinstance(result, list) else [result]):
                detail, person = one if isinstance(one, tuple) else (one, None)
                yield r, item, detail, person


# ============================================================ task rules ===

@rule("H01", "High", "Closed without an owner comment in Discussion")
def no_owner_comment(t, ctx):
    """Every closed task must carry a Discussion comment from its owner summarising the work."""
    if t["is_closed"] and t["owner"] and t["owner_comments"] == 0:
        return f"{t['comments']} comment(s), none by owner" if t["comments"] else "no comments"


@rule("H02", "High", "Closed with no Completed Work captured")
def no_completed_work(t, ctx):
    """Completed Work must record the time actually spent."""
    if t["is_closed"] and t["completed"] <= 0:
        return ""


@rule("H03", "Medium", "Closed with Remaining Work not zero")
def remaining_on_close(t, ctx):
    """Remaining Work left on a closed task distorts the sprint burndown."""
    if t["is_closed"] and t["remaining"] > 0:
        return f"remaining {t['remaining']:g}h"


@rule("H04", "Medium", "Completed Work far from Original Estimate")
def estimate_mismatch(t, ctx):
    """Completed is at least rule.estimate.overrun x the estimate (or that far below it)."""
    if t["is_closed"] and t["original"] > 0 and t["completed"] > 0:
        ratio = t["completed"] / t["original"]
        if ratio >= ctx.cfg.estimate_overrun or ratio <= 1 / ctx.cfg.estimate_overrun:
            return f"estimate {t['original']:g}h vs completed {t['completed']:g}h"


@rule("H05", "Medium", "Effort not updated daily (logged in one go)")
def logged_in_one_go(t, ctx):
    """A multi-day task whose Completed Work changed only once."""
    if t["is_closed"] and t["effort_updates"] <= 1 and t["completed"] > 0:
        span = ctx.wd_between(t["span_start"], t["closed_on"])
        if span >= 1:
            return f"{t['completed']:g}h logged in a single update over {span + 1} days"


@rule("H06", "Medium", "Active task with no effort update recently")
def stale_active(t, ctx):
    """Active task whose Completed Work has not changed for rule.stale.days working days."""
    if t["state"].lower() in ACTIVE_STATES:
        last = t["last_effort"] or t["activated"]
        gap = ctx.wd_between(last, ctx.as_of)
        if gap >= ctx.cfg.stale_days:
            return f"last effort update {last:%d-%b}, {gap} working day(s) ago" if last else "never updated"


@rule("H07", "Low", "Closed by someone other than the owner")
def closed_by_other(t, ctx):
    """The owner should close their own task."""
    cb, owner = t["closed_by"], t["owner"]
    if t["is_closed"] and cb and owner and cb["unique"] != owner["unique"]:
        return f"closed by {cb['name']}"


@rule("H08", "Low", "Task has no parent story")
def no_parent(t, ctx):
    """Testing tasks should hang under the story (or bug) they test."""
    if not t["parent"]:
        return ""


@rule("H09", "Low", "Activity / title convention not followed")
def convention(t, ctx):
    """Activity must be Testing, the title must contain 'QA' / 'Auto QA', and the title must identify the activity type."""
    bits = []
    if t["activity_field"] != "Testing":
        bits.append(f"Activity='{t['activity_field'] or 'blank'}'")
    if "qa" not in t["title"].lower():
        bits.append("title lacks 'QA'")
    if t["code"] == "UN":
        bits.append("activity type not recognised from title")
    return "; ".join(bits) if bits else None


@rule("H10", "Medium", "Effort logged on a day off")
def effort_on_day_off(t, ctx):
    """Hours recorded on a date marked as a day off in sprint capacity."""
    out = []
    for who, per_day in t["daily"].items():
        p = ctx.people.get(who)
        for d, h in sorted(per_day.items()):
            if p and h > 0 and d in p["days_off"]:
                out.append(f"{h:g}h on {d:%a %d-%b}")
    return out or None


@rule("H11", "Low", "Unusually high effort logged in one day")
def high_daily_effort(t, ctx):
    """More than rule.max.daily.hours logged on one task in a single day."""
    out = [f"{h:g}h on {d:%a %d-%b}" for per_day in t["daily"].values() for d, h in sorted(per_day.items())
           if h > ctx.cfg.max_daily_hours]
    return out or None


@rule("H13", "Low", "Task not assigned")
def unassigned(t, ctx):
    """Every testing task needs an owner."""
    if not t["owner"]:
        return ""


@rule("H14", "Medium", "Task still New but sprint more than half over")
def not_started_late(t, ctx):
    """Planned testing work that has not started by mid-sprint."""
    if t["state"].lower() in NEW_STATES and len(ctx.elapsed) > len(ctx.sprint_days) / 2:
        return ""


# =========================================================== story rules ===

@rule("H12", "High", "Execution tasks closed but test points not run", scope="story")
def closed_but_not_run(s, ctx):
    """All execution tasks of a story are closed while its test points are still not executed."""
    exec_tasks = [t for t in s["task_objs"] if t["is_exec"]]
    if exec_tasks and all(t["is_closed"] for t in exec_tasks) and s["points_total"] and s["executed"] < s["points_total"]:
        detail = f"story {s['id']}: {s['points_total'] - s['executed']} of {s['points_total']} not run"
        return [(t, detail) for t in exec_tasks]
    return None


@rule("H15", "Medium", "Evidence reviewed by the tester who executed it", scope="story")
def self_review(s, ctx):
    """Test evidence review must be done by someone other than the tester who executed the tests (four-eyes check)."""
    executors = {t["owner_key"] for t in s["task_objs"] if t["code"] in ("TE", "CT") and t["owner_key"]}
    executors |= {r["run_by"]["unique"] for tc in s["tc_objs"] for r in tc["runs"] if r["run_by"]}
    return [(t, f"story {s['id']}: reviewer also executed its tests")
            for t in s["task_objs"] if t["code"] == "ER" and t["owner_key"] in executors] or None


# ======================================================== test case rules ===

@rule("H16", "High", "Test case executed while still in Design", scope="testcase")
def executed_in_design(tc, ctx):
    """A test case must be Ready (reviewed) before it is executed. States treated as not ready: rule.testcase.design.states."""
    if tc["runs"] and tc["state"].lower() in ctx.cfg.testcase_design_states:
        last = tc["runs"][-1]
        return (f"state '{tc['state']}' but executed {len(tc['runs'])} time(s), last {last['outcome']}", last["run_by"])


@rule("H17", "High", "Executed test case has no evidence attached", scope="testcase")
def no_evidence(tc, ctx):
    """An executed test case needs evidence: an attachment on the test result, a test step, or the test case itself."""
    if tc["runs"] and tc["attachments_total"] == 0:
        last = tc["runs"][-1]
        return (f"{len(tc['runs'])} run(s), last {last['outcome']} - no result, step or work item attachments", last["run_by"])


@rule("H18", "Medium", "Test case priority not set", scope="testcase")
def no_priority(tc, ctx):
    """Every test case needs a Priority so execution can be ordered and risk-based coverage reported."""
    if tc["priority"] in (None, ""):
        return ""
