"""Excel workbook: Summary, Utilisation, Gantt (per tester), Stories, Hygiene, Tasks, Daily effort."""

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import classify as cls
from .analysis import gantt_rows

GROUP_FILL = {"Design": "7B61FF", "Execution": "2F6FED", "Automation": "0F9D8A",
              "Performance": "E2791C", "Support": "8A93A6", "Unclassified": "C2410C"}
GROUP_LIGHT = {"Design": "DDD6FF", "Execution": "D4E2FC", "Automation": "CDEFEA",
               "Performance": "FBE3CC", "Support": "E4E7EC", "Unclassified": "F8D9CB"}
HEAD = PatternFill("solid", fgColor="1D2330")
OFF = PatternFill("gray125", fgColor="C9CDD6")
TODAY = PatternFill("solid", fgColor="FFF6C9")
THIN = Border(*(Side(style="thin", color="E3E6EC"),) * 4)


def _fill(hex_):
    return PatternFill("solid", fgColor=hex_)


def _header(ws, row, values):
    for c, v in enumerate(values, 1):
        cell = ws.cell(row=row, column=c, value=v)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEAD
        cell.alignment = Alignment(vertical="center", wrap_text=True)


def _table(ws, headers, rows, widths=None):
    _header(ws, 1, headers)
    for r in rows:
        ws.append(r)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for i, w in enumerate(widths or [], 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _p(v):
    return round(v, 3) if v is not None else None


def render(model, path):
    wb = Workbook()
    link = lambda wid: f'{model["org"]}/{model["project"]}/_workitems/edit/{wid}'

    ws = wb.active
    ws.title = "Summary"
    _table(ws, ["Team", "Sprint", "Start", "Finish", "Day", "Sprint days", "Tasks", "Closed", "Effort h", "Remaining h"] + cls.GROUPS
           + ["Testers", "Tester source", "Excluded tasks"],
           [[t["name"], t["iteration"], t["start"], t["finish"], t["elapsed"], len(t["days"]), t["tasks"], t["tasks_closed"], t["effort"], t["remaining"]]
            + [t["group_hours"].get(g, 0) for g in cls.GROUPS] + [t["testers"], t["tester_source"], t["excluded"]] for t in model["teams"]],
           [18, 22, 12, 12, 6, 10, 8, 8, 10, 12] + [12] * len(cls.GROUPS) + [8, 28, 10])

    ws = wb.create_sheet("Utilisation")
    _table(ws, ["Tester", "Teams", "Capacity h/day", "Days off", "Capacity h", "Capacity to date", "Logged to date", "Utilisation",
                "Plan load", "Remaining h", "Tasks", "Closed", "Avg tasks/day", "Flags", "Status"] + [f"{g} h" for g in cls.GROUPS],
           [[p["name"], ", ".join(t["team"] for t in p["teams"]), sum(t["capacity_per_day"] for t in p["teams"]), len(p["days_off"]),
             p["capacity"], p["capacity_to_date"], p["logged_to_date"], _p(p["util"]), _p(p["plan_load"]), p["remaining"],
             p["tasks_total"], p["tasks_closed"], p["switching"], p["flags"], p["status"]] + [p["mix"].get(g, 0) for g in cls.GROUPS]
            for p in model["people"]],
           [24, 26, 10, 8, 10, 10, 10, 10, 10, 10, 7, 7, 9, 7, 24] + [11] * len(cls.GROUPS))
    for row in ws.iter_rows(min_row=2, min_col=8, max_col=9):
        for c in row:
            c.number_format = "0%"

    _gantt_sheet(wb.create_sheet("Gantt"), model)

    ws = wb.create_sheet("Contribution")
    cols = [("effort", "utilisation_pct", "Utilisation %"), ("effort", "logged_to_date_h", "Logged h"),
            ("output", "test_cases_written", "TCs written"), ("output", "test_cases_moved_to_ready", "TCs to Ready"),
            ("output", "executions_manual", "Manual executions"), ("output", "executions_automated", "Automated executions"),
            ("output", "distinct_test_cases_executed", "Distinct TCs executed"), ("output", "bugs_raised", "Bugs raised"),
            ("output", "commits", "Commits"), ("output", "pull_requests", "PRs"), ("output", "story_points_touched", "SP touched"),
            ("quality", "evidence_pct", "Evidence %"), ("quality", "bugs_rejected_pct", "Rejected bugs %"),
            ("quality", "self_moved_to_ready", "Own TCs moved to Ready"), ("quality", "hygiene_findings", "Hygiene findings"),
            ("flow", "unplanned_tasks", "Unplanned tasks"), ("flow", "unplanned_h", "Unplanned h"), ("flow", "reassigned_tasks", "Reassigned"),
            ("flow", "avg_tasks_per_day", "Tasks/day"), ("collaboration", "reviews_for_others", "TC reviews for others"),
            ("collaboration", "pr_reviews", "PR reviews"), ("collaboration", "support_h", "Support h"),
            ("collaboration", "bugs_retested", "Bugs retested"), ("collaboration", "retest_turnaround_days_median", "Retest median (working days)")]
    _table(ws, ["Tester"] + [c[2] for c in cols] + ["Strengths", "Worth discussing"],
           [[p["name"]] + [p[g][k] for g, k, _ in cols]
            + ["\n".join(o["text"] for o in p["observations"] if o["kind"] == "strength"),
               "\n".join(o["text"] for o in p["observations"] if o["kind"] == "watch")]
            for p in model["contribution"]["people"]],
           [22] + [11] * len(cols) + [45, 60])
    for row in ws.iter_rows(min_row=2, min_col=len(cols) + 2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    ws = wb.create_sheet("Stories")
    _table(ws, ["ID", "Type", "Title", "Team", "State", "Test start", "Start day", "Timing", "Test days", "Points", "Executed %",
                "Passed %", "Passed", "Failed", "Blocked", "Not run", "Open bugs", "QA effort h", "Why not done / risks"],
           [[s["id"], s["type"], s["title"], s["team"], s["state"], s["test_start"], s["start_day"], s["timing"], s["test_days_left"],
             s["points_total"], s["exec_pct"], s["pass_pct"], s["outcomes"].get("Passed", 0), s["outcomes"].get("Failed", 0),
             s["outcomes"].get("Blocked", 0), s["outcomes"].get("Not run", 0), len(s["bugs_open"]), s["effort"], "; ".join(s["reasons"])]
            for s in model["stories"]],
           [8, 11, 50, 16, 11, 12, 8, 11, 8, 7, 9, 9, 7, 7, 7, 7, 8, 9, 60])
    _hyperlinks(ws, link)

    ws = wb.create_sheet("Test cases")
    _table(ws, ["ID", "Title", "Team", "Stories", "State", "Priority", "Runs", "Last outcome", "Executed by", "Evidence attachments", "Flags"],
           [[t["id"], t["title"], t["team"], ", ".join(map(str, t["stories"])), t["state"], t["priority"], len(t["runs"]),
             t["runs"][-1]["outcome"] if t["runs"] else "", ", ".join(t["executors"]), t["attachments_total"], ", ".join(t["flags"])]
            for t in sorted(model["test_cases"], key=lambda t: (not t["flags"], t["team"], t["id"]))],
           [8, 50, 16, 12, 10, 8, 6, 12, 26, 10, 14])
    _hyperlinks(ws, link)

    ws = wb.create_sheet("Hygiene")
    _table(ws, ["Severity", "Rule", "Check", "Item type", "Item", "Title", "Team", "Responsible", "Detail"],
           [[f["severity"], f["rule"], f["text"], f.get("kind", "Task"), f["task"], f["title"], f["team"], f["person"], f["detail"]]
            for f in model["findings"]],
           [9, 6, 44, 10, 8, 50, 16, 22, 50])
    _hyperlinks(ws, link, col=5)

    ws = wb.create_sheet("Rules")
    counts = {}
    for f in model["findings"]:
        counts[f["rule"]] = counts.get(f["rule"], 0) + 1
    _table(ws, ["Rule", "Enabled", "Severity", "Check", "Scope", "Description", "Findings"],
           [[r.id, "Yes" if r.enabled else "No", r.severity, r.title, r.scope, r.description, counts.get(r.id, 0)]
            for r in model["rules"].values()], [7, 8, 9, 44, 7, 80, 9])

    ws = wb.create_sheet("Excluded (non-tester)")
    _table(ws, ["Task", "Title", "Team", "State", "Owner", "Reason"],
           [[x["id"], x["title"], x["team"], x["state"], x["owner"], x["reason"]] for x in model["excluded"]],
           [8, 50, 16, 10, 24, 34])
    _hyperlinks(ws, link)

    ws = wb.create_sheet("Tasks")
    _table(ws, ["ID", "Title", "Team", "Owner", "State", "Activity field", "Type", "Group", "Parent", "Original", "Completed", "Remaining",
                "Started", "Closed", "Effort updates", "Owner comments", "Flags"],
           [[t["id"], t["title"], t["team"], t["owner"]["name"] if t["owner"] else "", t["state"], t["activity_field"], t["label"], t["group"],
             t["parent"], t["original"], t["completed"], t["remaining"], t["span_start"], t["closed_on"], t["effort_updates"],
             t["owner_comments"], ", ".join(t["flags"])] for t in model["tasks"].values()],
           [8, 50, 16, 22, 10, 12, 24, 12, 8, 8, 9, 9, 11, 11, 8, 8, 16])
    _hyperlinks(ws, link)

    ws = wb.create_sheet("Daily effort")
    rows = []
    for t in model["tasks"].values():
        for who, per_day in t["daily"].items():
            for d, h in sorted(per_day.items()):
                rows.append([d, who, t["id"], t["title"], t["team"], t["label"], t["group"], round(h, 2)])
    _table(ws, ["Date", "Person", "Task", "Title", "Team", "Type", "Group", "Hours"], sorted(rows, key=lambda r: (r[0], r[1] or "")),
           [12, 28, 8, 50, 16, 24, 12, 8])

    for sheet in wb.worksheets:
        for row in sheet.iter_rows():
            for c in row:
                if hasattr(c.value, "year") and not c.number_format.startswith("d"):
                    c.number_format = "dd-mmm-yy"
    wb.save(path)


def _hyperlinks(ws, link, col=1):
    for row in ws.iter_rows(min_row=2, min_col=col, max_col=col):
        c = row[0]
        if isinstance(c.value, int):
            c.hyperlink = link(c.value)
            c.font = Font(color="2F6FED", underline="single")


def _gantt_sheet(ws, model):
    today = model["as_of"]
    fixed = ["Task", "Title", "Team", "Activity", "State", "Est", "Done", "Rem"]
    widths = [8, 44, 14, 24, 9, 6, 6, 6]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    max_days = max((len(p["days"]) for p in model["people"]), default=0)
    for i in range(max_days):
        ws.column_dimensions[get_column_letter(len(fixed) + 1 + i)].width = 7.5
    r = 1
    for p in model["people"]:
        rows = gantt_rows(model, p["key"])
        if not rows or not p["days"]:
            continue
        days = p["days"]
        ws.cell(row=r, column=1, value=f"{p['name']}  ·  logged {p['logged']:g}h of {p['capacity']:g}h  ·  {len(p['days_off'])} day(s) off").font = Font(bold=True, size=12)
        r += 1
        _header(ws, r, fixed + [f"D{i}\n{d:%a %d}" for i, d in enumerate(days, 1)])
        ws.row_dimensions[r].height = 30
        r += 1
        for t in rows:
            mine = t["daily"].get(p["key"], {})
            vals = [t["id"], t["title"], t["team"], t["label"], t["state"], t["original"] or None, t["completed"] or None, t["remaining"] or None]
            for c, v in enumerate(vals, 1):
                ws.cell(row=r, column=c, value=v).border = THIN
            s, e = t["span_start"], t["span_end"]
            for i, d in enumerate(days):
                cell = ws.cell(row=r, column=len(fixed) + 1 + i)
                cell.border = THIN
                cell.alignment = Alignment(horizontal="center")
                h = round(mine.get(d, 0), 2)
                if h:
                    cell.value = h
                if d in p["days_off"] and not h:
                    cell.fill, cell.value = OFF, "OFF"
                    cell.font = Font(color="8A93A6", size=8)
                elif s and e and s <= d <= e:
                    cell.fill = _fill(GROUP_FILL[t["group"]] if h else GROUP_LIGHT[t["group"]])
                    if h:
                        cell.font = Font(color="FFFFFF", bold=True)
                elif h:
                    cell.font = Font(color=GROUP_FILL[t["group"]], bold=True)
                if d == today and cell.fill.fill_type is None:
                    cell.fill = TODAY
            ws.cell(row=r, column=1).hyperlink = f'{model["org"]}/{model["project"]}/_workitems/edit/{t["id"]}'
            r += 1
        ws.cell(row=r, column=2, value="Hours logged / capacity").font = Font(bold=True)
        for i, d in enumerate(days):
            cell = ws.cell(row=r, column=len(fixed) + 1 + i)
            cell.alignment = Alignment(horizontal="center")
            if d in p["days_off"]:
                cell.value, cell.fill = "OFF", OFF
            else:
                cell.value = f"{round(p['daily_logged'].get(d, 0), 1):g}/{p['daily_capacity'].get(d, 0):g}"
            cell.font = Font(bold=True, size=9)
        r += 3
    ws.freeze_panes = ws.cell(row=1, column=len(fixed) + 1)
