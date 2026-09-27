"""Loads ado.properties (key=value) into a typed Config."""

import os
from dataclasses import dataclass, field


@dataclass
class TeamConfig:
    name: str
    area_path: str = ""
    testers: list = field(default_factory=list)       # team-specific tester emails


@dataclass
class Config:
    org_url: str
    project: str
    pat: str
    teams: list = field(default_factory=list)
    testers: list = field(default_factory=list)       # tester emails valid for every team
    tester_activities: list = field(default_factory=lambda: ["testing"])  # capacity activities that mark a tester
    tester_exclude: list = field(default_factory=list)  # never treat these people as testers
    rule_overrides: dict = field(default_factory=dict)  # {"H05": {"enabled": False, "severity": "High"}}
    output_dir: str = "reports"
    testplan_filter: str = ""                          # regex on test plan name, blank = all plans
    timezone: str = ""                                 # IANA name, blank = machine local time
    over_util: float = 1.10                            # > 110% of capacity = over-utilised
    under_util: float = 0.60                           # < 60% of capacity = under-utilised
    stale_days: int = 2                                # active task with no effort update for N working days
    max_daily_hours: float = 10.0                      # effort logged in one day above this is suspicious
    estimate_overrun: float = 2.0                      # completed > N x original estimate
    testcase_design_states: list = field(default_factory=lambda: ["design"])  # not-ready test case states
    repos_include: str = ""                            # regex on repo name for commits/PRs, blank = all repos
    rejected_bug_reasons: list = field(default_factory=lambda: list(REJECTED_BUG_REASONS))


def load_properties(path):
    props = {}
    if not os.path.exists(path):
        return props
    with open(path, encoding="utf-8-sig") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line[0] in "#!" or "=" not in line:
                continue
            key, value = line.split("=", 1)
            props[key.strip()] = value.strip()
    return props


REJECTED_BUG_REASONS = ("as designed", "cannot reproduce", "duplicate", "obsolete", "won't fix",
                        "rejected", "not a bug", "by design")


def _list(value):
    return [v.strip().lower() for v in value.split(",") if v.strip()]


def testers_for(cfg, team_name, members):
    """Who counts as a tester in a team, and how that was decided.

    1. Explicit lists (team.N.testers + testers) - most reliable.
    2. Otherwise, sprint-capacity members whose activity is one of tester.activities.
    testers.exclude always wins.
    """
    team = next((t for t in cfg.teams if t.name.lower() == team_name.lower()), None)
    explicit = set(cfg.testers) | set(team.testers if team else [])
    if explicit:
        keys, source = explicit, "configured list"
    else:
        keys = {m["unique"] for m in members
                if any(a["name"].lower() in cfg.tester_activities and a["capacity_per_day"] > 0 for a in m["activities"])}
        source = f"capacity activity ({', '.join(cfg.tester_activities)})"
    return keys - set(cfg.tester_exclude), source


def load_config(path="ado.properties"):
    p = load_properties(path)
    pat = os.environ.get("ADO_PAT") or p.get("ado.pat", "")

    teams = []
    i = 1
    while f"team.{i}.name" in p:
        name = p[f"team.{i}.name"]
        if name:
            teams.append(TeamConfig(name=name, area_path=p.get(f"team.{i}.area", ""),
                                    testers=_list(p.get(f"team.{i}.testers", ""))))
        i += 1

    overrides = {}
    for key, value in p.items():
        parts = key.split(".")
        if len(parts) == 3 and parts[0] == "rule" and parts[2] in ("enabled", "severity") and parts[1][:1].isupper():
            rid = parts[1].upper()
            overrides.setdefault(rid, {})[parts[2]] = value.lower() not in ("false", "no", "0", "off") if parts[2] == "enabled" else value.capitalize()

    def num(key, default, cast=float):
        return cast(p[key]) if p.get(key) else default

    return Config(
        org_url=p.get("ado.org.url", "").rstrip("/"),
        project=p.get("ado.project", ""),
        pat=pat,
        teams=teams,
        testers=_list(p.get("testers", "")),
        tester_activities=_list(p.get("tester.activities", "Testing")),
        tester_exclude=_list(p.get("testers.exclude", "")),
        rule_overrides=overrides,
        output_dir=p.get("report.output.dir", "reports"),
        testplan_filter=p.get("report.testplan.filter", ""),
        timezone=p.get("report.timezone", ""),
        over_util=num("rule.util.over", 1.10),
        under_util=num("rule.util.under", 0.60),
        stale_days=num("rule.stale.days", 2, int),
        max_daily_hours=num("rule.max.daily.hours", 10.0),
        estimate_overrun=num("rule.estimate.overrun", 2.0),
        testcase_design_states=_list(p.get("rule.testcase.design.states", "Design")),
        repos_include=p.get("report.repos.include", ""),
        rejected_bug_reasons=_list(p.get("report.bug.rejected.reasons", "")) or list(REJECTED_BUG_REASONS),
    )
