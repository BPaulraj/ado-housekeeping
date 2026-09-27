"""Trends report across sprints: HTML (inline SVG, offline) and Excel."""

from html import escape

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .report_excel import _header, _table

SERIES = 4  # categorical slots validated for adjacent use; teams beyond 4 fold into the table only

CSS = """
:root{--bg:#f6f7f9;--card:#fcfcfb;--ink:#0b0b0b;--muted:#52514e;--line:#e3e6ec;--grid:#ecebe8;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;
--good:#0ca30c;--warning:#fab219;--serious:#ec835a;--critical:#d03b3b;--none:#eceef2}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){--bg:#12151b;--card:#1a1a19;--ink:#fff;--muted:#c3c2b7;
--line:#2c323d;--grid:#2a2a28;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--none:#262b35}}
:root[data-theme="dark"]{--bg:#12151b;--card:#1a1a19;--ink:#fff;--muted:#c3c2b7;--line:#2c323d;--grid:#2a2a28;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--none:#262b35}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 "Segoe UI",system-ui,sans-serif;background:var(--bg);color:var(--ink)}
header,main{padding:16px 24px}h1{margin:0;font-size:22px}h2{font-size:17px;margin:26px 0 10px}.sub,.small{color:var(--muted)}.small{font-size:12px}
.charts{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.card h3{margin:0 0 2px;font-size:14px}
.legend{display:flex;gap:14px;flex-wrap:wrap;margin:6px 0;color:var(--muted);font-size:12px}
.legend i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:6px;vertical-align:3px}
svg text{fill:var(--muted);font-size:11px}svg .lbl{fill:var(--ink);font-size:11px}
svg .grid{stroke:var(--grid);stroke-width:1}svg .axis{stroke:var(--line);stroke-width:1}
svg .ln{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
svg .pt{stroke:var(--card);stroke-width:2}svg .hit{fill:transparent}svg .hit:hover+.pt{r:6}
.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%}th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{font-size:12px;color:var(--muted);font-weight:600}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
td.cell{text-align:center;font-variant-numeric:tabular-nums}
.st{display:inline-block;min-width:74px;padding:2px 6px;border-radius:6px;font-size:12px;color:#0b0b0b}
.st.good{background:color-mix(in srgb,var(--good) 35%,transparent)}.st.warning{background:color-mix(in srgb,var(--warning) 45%,transparent)}
.st.critical{background:color-mix(in srgb,var(--critical) 35%,transparent)}.st.none{background:var(--none);color:var(--muted)}
@media (prefers-color-scheme:dark){.st{color:#fff}}
ul.sig{list-style:none;padding:0;margin:0}ul.sig li{display:grid;grid-template-columns:18px 120px 1fr;padding:6px 0;border-bottom:1px solid var(--line)}
.watch::before{content:"•";color:var(--serious)}.strength::before{content:"✓";color:var(--good)}
"""


def _e(v):
    return escape(str(v)) if v is not None else "–"


def _line_chart(title, subtitle, labels, series, unit=""):
    """Small multiple: one metric, one line per team, direct end labels + native hover tooltips."""
    w, h, l, r, t, b = 440, 190, 34, 92, 12, 26
    vals = [v for s in series.values() for v in s if v is not None]
    top = max(vals + [1])
    step = next(s for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000) if top / s <= 5)
    ymax = step * (int(top / step) + (0 if top % step == 0 else 1))
    x = lambda i: l + (w - l - r) * (i / (len(labels) - 1) if len(labels) > 1 else 0.5)
    y = lambda v: t + (h - t - b) * (1 - v / ymax)
    svg = [f"<svg viewBox='0 0 {w} {h}' width='100%' role='img' aria-label='{escape(title)}'>"]
    for g in range(0, ymax + 1, step):
        svg.append(f"<line class='grid' x1='{l}' x2='{w - r}' y1='{y(g):.1f}' y2='{y(g):.1f}'/>"
                   f"<text x='{l - 6}' y='{y(g) + 4:.1f}' text-anchor='end'>{g}</text>")
    for i, lab in enumerate(labels):
        svg.append(f"<text x='{x(i):.1f}' y='{h - 8}' text-anchor='middle'>{escape(lab.split(' / ')[0])}</text>")
    ends = []
    for n, (name, vs) in enumerate(list(series.items())[:SERIES], 1):
        pts = [(x(i), y(v), v, labels[i]) for i, v in enumerate(vs) if v is not None]
        if not pts:
            continue
        svg.append(f"<polyline class='ln' style='stroke:var(--s{n})' points='{' '.join(f'{px:.1f},{py:.1f}' for px, py, _, _ in pts)}'/>")
        for px, py, v, lab in pts:
            svg.append(f"<circle class='hit' cx='{px:.1f}' cy='{py:.1f}' r='10'><title>{escape(name)} · {escape(lab)}: {v:g}{unit}</title></circle>"
                       f"<circle class='pt' cx='{px:.1f}' cy='{py:.1f}' r='4' style='fill:var(--s{n})'/>")
        ends.append([pts[-1][1], pts[-1][0], name, pts[-1][2], n])
    ends.sort()
    for i in range(1, len(ends)):                       # keep end labels at least 13px apart
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + 13)
    for ly, lx, name, v, n in ends:
        svg.append(f"<line x1='{lx + 8:.1f}' x2='{lx + 18:.1f}' y1='{ly:.1f}' y2='{ly:.1f}' style='stroke:var(--s{n});stroke-width:2'/>"
                   f"<text class='lbl' x='{lx + 22:.1f}' y='{ly + 4:.1f}'>{escape(name)} {v:g}{unit}</text>")
    svg.append("</svg>")
    return f"<div class='card'><h3>{escape(title)}</h3><div class='small'>{escape(subtitle)}</div>{''.join(svg)}</div>"


def _status_cell(row):
    if not row:
        return "<td class='cell'><span class='st none'>–</span></td>"
    kind, icon = {"Over-utilised": ("critical", "▲"), "Balanced": ("good", "●")}.get(
        row["status"], ("warning", "▼") if row["status"].startswith("Under") else ("none", "–"))
    util = f"{row['utilisation_pct']}%" if row["utilisation_pct"] is not None else "n/a"
    tip = f"{row['status']} · {row['logged_h']:g}h of {row['capacity_h']:g}h · {row['hygiene']} hygiene · main work {row['main_work'] or '–'}"
    return f"<td class='cell' title='{escape(tip)}'><span class='st {kind}'>{icon} {util}</span></td>"


def render_html(tr, project, path):
    labels, sprints, teams = tr["labels"], tr["sprints"], tr["teams"]
    team_series = lambda key: {name: [r[key] if r else None for r in rows] for name, rows in teams.items()}
    legend = "<div class='legend'>" + "".join(f"<span><i style='background:var(--s{n})'></i>{escape(name)}</span>"
                                             for n, name in enumerate(list(teams)[:SERIES], 1)) + "</div>"
    extra = f"<p class='small'>Only the first {SERIES} teams are charted; all teams are in the tables.</p>" if len(teams) > SERIES else ""
    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>Sprint Testing Trends</title><style>{CSS}</style></head><body>"
           f"<header><h1>Sprint Testing Trends</h1><div class='sub'>{escape(project)} · {len(labels)} sprints · "
           f"{escape(labels[0])} → {escape(labels[-1])} ({sprints[0]['start']:%d %b} – {sprints[-1]['finish']:%d %b %Y})</div></header><main>"]

    out.append("<h2>Signals across sprints</h2><div class='card'><ul class='sig'>")
    out += [f"<li class='{s['kind']}'><b>{escape(s['who'])}</b>{escape(s['text'])}</li>" for s in tr["signals"]]
    if not tr["signals"]:
        out.append("<li class='small'>No multi-sprint patterns detected.</li>")
    out.append("</ul></div>")

    out.append("<h2>By team</h2>" + legend + extra + "<div class='charts'>")
    out.append(_line_chart("Tester utilisation", "hours logged ÷ capacity, %", labels, team_series("utilisation_pct"), "%"))
    out.append(_line_chart("Testing started late or not at all", "% of stories (proxy for late deployment)", labels, team_series("late_start_pct"), "%"))
    out.append(_line_chart("Stories not done by sprint end", "count", labels, team_series("spillover")))
    out.append(_line_chart("Hygiene findings", "per 10 testing tasks", labels, team_series("hygiene_per_10_tasks")))
    out.append("</div>")

    out.append("<h2>Tester utilisation by sprint</h2><p class='small'>▲ over capacity · ● balanced · ▼ under 60% or not logging. "
               "Hover a cell for hours, hygiene and main work. For balancing and coaching, not ranking.</p>"
               "<div class='wrap'><table><tr><th>Tester</th>" + "".join(f"<th class='cell'>{escape(lb)}</th>" for lb in labels) + "</tr>")
    for t in tr["testers"].values():
        out.append(f"<tr><td>{escape(t['name'])}</td>" + "".join(_status_cell(r) for r in t["sprints"]) + "</tr>")
    out.append("</table></div>")

    cols = [("utilisation_pct", "Utilisation %"), ("balance_cv", "Balance CV"), ("stories", "Stories"), ("spillover", "Spillover"),
            ("late_start_pct", "Late start %"), ("avg_start_day", "Avg test start day"), ("hygiene", "Hygiene"),
            ("hygiene_high", "High"), ("executions", "Executions"), ("bugs_raised", "Bugs raised"),
            ("evidence_pct", "Evidence %"), ("unplanned_pct", "Unplanned %")]
    out.append("<h2>All teams – sprint by sprint</h2><div class='wrap'><table><tr><th>Sprint</th>"
               + "".join(f"<th class='n'>{c}</th>" for _, c in cols) + "<th>Work mix % (Design/Exec/Auto/Perf/Support)</th></tr>")
    for s in sprints:
        mix = s["mix_pct"]
        out.append(f"<tr><td>{escape(s['sprint'])}</td>" + "".join(f"<td class='n'>{_e(s[k])}</td>" for k, _ in cols)
                   + f"<td>{mix['Design']} / {mix['Execution']} / {mix['Automation']} / {mix['Performance']} / {mix['Support']}</td></tr>")
    out.append("</table></div></main></body></html>")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(out))


FILLS = {"Over-utilised": "F5C4C4", "Balanced": "C6EBC6"}


def render_excel(tr, path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Sprints"
    keys = ["utilisation_pct", "balance_cv", "stories", "spillover", "late_start_pct", "avg_start_day", "hygiene",
            "hygiene_high", "hygiene_per_10_tasks", "executions", "bugs_raised", "evidence_pct", "unplanned_pct"]
    _table(ws, ["Sprint", "Start", "Finish"] + keys + [f"{g} %" for g in tr["sprints"][0]["mix_pct"]],
           [[s["sprint"], s["start"], s["finish"]] + [s[k] for k in keys] + list(s["mix_pct"].values()) for s in tr["sprints"]],
           [16, 11, 11] + [12] * (len(keys) + 6))

    ws = wb.create_sheet("Teams")
    tkeys = ["utilisation_pct", "stories", "spillover", "late_start_pct", "hygiene_per_10_tasks", "automation_pct"]
    rows = [[name, tr["labels"][i]] + [r[k] for k in tkeys] for name, rs in tr["teams"].items() for i, r in enumerate(rs) if r]
    _table(ws, ["Team", "Sprint"] + tkeys, rows, [18, 16] + [14] * len(tkeys))

    ws = wb.create_sheet("Tester utilisation")
    _header(ws, 1, ["Tester"] + tr["labels"])
    for r, t in enumerate(tr["testers"].values(), 2):
        ws.cell(row=r, column=1, value=t["name"])
        for c, row in enumerate(t["sprints"], 2):
            cell = ws.cell(row=r, column=c, value=f"{row['utilisation_pct']}% {row['status']}" if row and row["utilisation_pct"] is not None
                           else (row["status"] if row else "–"))
            cell.alignment = Alignment(horizontal="center")
            if row:
                fill = FILLS.get(row["status"], "FBE3B0" if row["status"].startswith("Under") else None)
                if fill:
                    cell.fill = PatternFill("solid", fgColor=fill)
    ws.column_dimensions["A"].width = 24
    for c in range(2, len(tr["labels"]) + 2):
        ws.column_dimensions[ws.cell(row=1, column=c).column_letter].width = 26

    ws = wb.create_sheet("Tester detail")
    dkeys = ["utilisation_pct", "status", "logged_h", "capacity_h", "hygiene", "executions", "bugs_raised",
             "reviews_for_others", "main_work", "main_work_pct", "unplanned_h"]
    rows = [[t["name"], tr["labels"][i]] + [r[k] for k in dkeys] for t in tr["testers"].values() for i, r in enumerate(t["sprints"]) if r]
    _table(ws, ["Tester", "Sprint"] + dkeys, rows, [22, 16] + [13] * len(dkeys))

    ws = wb.create_sheet("Signals")
    _table(ws, ["Kind", "Who", "Signal"], [[s["kind"], s["who"], s["text"]] for s in tr["signals"]], [10, 20, 90])
    for sheet in wb.worksheets:
        for row in sheet.iter_rows():
            for c in row:
                if hasattr(c.value, "year"):
                    c.number_format = "dd-mmm-yy"
    ws["A1"].font = Font(bold=True, color="FFFFFF")
    wb.save(path)
