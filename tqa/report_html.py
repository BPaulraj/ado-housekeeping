"""Self-contained HTML report (no external dependencies, works offline)."""

from datetime import date
from html import escape

from . import classify as cls
from .analysis import gantt_rows

GROUP_CLASS = {g: "g-" + g.lower() for g in cls.GROUPS}


def _e(v):
    return escape(str(v)) if v is not None else ""


def _h(v):
    return f"{v:g}" if v else ""


def _pct(v):
    return f"{round(v * 100)}%" if v is not None else "–"


def _link(model, wid):
    from urllib.parse import quote
    return f'<a href="{model["org"]}/{quote(model["project"])}/_workitems/edit/{wid}" target="_blank">{wid}</a>'


def _status_chip(status):
    kind = {"Over-utilised": "bad", "Under-utilised / not logging": "warn", "Balanced": "ok"}.get(status, "muted")
    return f'<span class="chip {kind}">{_e(status)}</span>'


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2330;--muted:#6b7385;--line:#e3e6ec;--accent:#2f6fed;
--ok:#1f8a4c;--ok-bg:#e3f4ea;--warn:#a86400;--warn-bg:#fdf0d9;--bad:#b42318;--bad-bg:#fde4e1;
--off:#eceef2;--today:#fff6c9;
--g-design:#7b61ff;--g-execution:#2f6fed;--g-automation:#0f9d8a;--g-performance:#e2791c;--g-support:#8a93a6;--g-unclassified:#c2410c}
@media (prefers-color-scheme:dark){:root{--bg:#12151b;--card:#1b1f27;--ink:#e6e9ef;--muted:#99a1b3;--line:#2c323d;
--ok-bg:#15361f;--warn-bg:#3a2a0c;--bad-bg:#3d1611;--off:#262b35;--today:#3a3515;--ok:#5fd08e;--warn:#f0b35a;--bad:#ff8a7a}}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 "Segoe UI",system-ui,sans-serif;background:var(--bg);color:var(--ink)}
header{padding:20px 24px 8px}h1{margin:0;font-size:22px}h2{font-size:17px;margin:22px 0 10px}h3{margin:18px 0 6px;font-size:15px}
.sub{color:var(--muted)}main{padding:0 24px 40px}
nav{display:flex;gap:4px;flex-wrap:wrap;padding:8px 24px;position:sticky;top:0;background:var(--bg);z-index:5;border-bottom:1px solid var(--line)}
nav button{border:1px solid var(--line);background:var(--card);color:var(--ink);padding:7px 14px;border-radius:8px;cursor:pointer;font:inherit}
nav button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
section{display:none}section.on{display:block}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.card b{display:block;font-size:22px}.card span{color:var(--muted);font-size:12px}
.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%}th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:12px;color:var(--muted);font-weight:600;background:var(--card);position:sticky;top:0}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
a{color:var(--accent);text-decoration:none}
.chip{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;white-space:nowrap}
.ok{background:var(--ok-bg);color:var(--ok)}.warn{background:var(--warn-bg);color:var(--warn)}.bad{background:var(--bad-bg);color:var(--bad)}.muted{background:var(--off);color:var(--muted)}
.bar{display:flex;height:10px;border-radius:5px;overflow:hidden;min-width:140px;background:var(--off)}
.bar i{display:block;height:100%}
.legend{display:flex;gap:14px;flex-wrap:wrap;margin:8px 0;color:var(--muted);font-size:12px}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:5px;vertical-align:-2px}
.g-design{--g:var(--g-design)}.g-execution{--g:var(--g-execution)}.g-automation{--g:var(--g-automation)}
.g-performance{--g:var(--g-performance)}.g-support{--g:var(--g-support)}.g-unclassified{--g:var(--g-unclassified)}
.gantt td,.gantt th{border-right:1px solid var(--line);white-space:nowrap}
.gantt th.day{text-align:center;min-width:46px;font-weight:600}
.gantt th.day small{display:block;font-weight:400}
.gantt td.c{padding:3px 0;text-align:center;font-size:12px;font-variant-numeric:tabular-nums;border-right:none}
.gantt td.c span{display:block;height:22px;line-height:22px;background:color-mix(in srgb,var(--g) 30%,transparent);color:var(--ink)}
.gantt td.c span.s{border-radius:6px 0 0 6px}.gantt td.c span.e{border-radius:0 6px 6px 0}.gantt td.c span.s.e{border-radius:6px}
.gantt td.c span.h{background:var(--g);color:#fff;font-weight:600}
.gantt td.c span.open{border-right:3px dashed var(--g)}
.gantt td.c span.x{background:none;border:1px dashed var(--g);border-radius:6px;color:var(--g);font-weight:600}
.gantt td.off{background:repeating-linear-gradient(45deg,var(--off),var(--off) 5px,transparent 5px,transparent 10px);color:var(--muted);font-size:11px}
.gantt .today{background:var(--today)}
.gantt tr.tot td.c span{background:none;margin:0 3px}
.gantt tr.tot td.c span.ok{background:var(--ok-bg);color:var(--ok)}.gantt tr.tot td.c span.warn{background:var(--warn-bg);color:var(--warn)}
.gantt tr.tot td.c span.bad{background:var(--bad-bg);color:var(--bad)}
.gantt tr.tot td{background:var(--off);font-weight:600}
.gantt td.task{max-width:340px;overflow:hidden;text-overflow:ellipsis}
.person-pick{display:flex;gap:8px;align-items:center;margin:6px 0 12px}
select{font:inherit;padding:6px 10px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
.flags{color:var(--bad);font-size:12px}
.small{font-size:12px;color:var(--muted)}
.cgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px}
.ccard .chead{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.ccard .chead b{font-size:16px;display:inline}
.ccard dl{display:grid;grid-template-columns:100px 1fr;gap:4px 10px;margin:10px 0;font-size:13px}
.ccard dt{color:var(--muted);font-weight:600}.ccard dd{margin:0}
.obs{list-style:none;padding:8px 0 0;margin:0;border-top:1px solid var(--line);font-size:13px}
.obs li{padding:2px 0}.obs li.strength{color:var(--ok)}.obs li.watch{color:var(--warn)}
@media print{nav{display:none}section{display:block!important;page-break-after:always}}
"""

JS = """
function tab(id){document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('on',b.dataset.t===id));
document.querySelectorAll('main>section').forEach(s=>s.classList.toggle('on',s.id===id));}
function pick(k){document.querySelectorAll('.gperson').forEach(d=>d.style.display=(k==='*'||d.dataset.k===k)?'':'none');}
function filt(){document.querySelectorAll('#hyg tbody tr').forEach(r=>{
 const ok=['team','rule','person'].every(a=>{const f=document.getElementById('f-'+a).value;return !f||r.dataset[a]===f});r.style.display=ok?'':'none'});}
"""


def render(model, path):
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>Sprint Testing Insights</title><style>{CSS}</style></head><body>"]
    teams = model["teams"]
    iters = "; ".join(f"{t['name']}: {t['iteration']} ({t['start']:%d %b} – {t['finish']:%d %b}, day {t['elapsed']}/{len(t['days'])})" for t in teams)
    parts.append(f"<header><h1>Sprint Testing Insights</h1><div class='sub'>{_e(model['project'])} · as of {model['as_of']:%a %d %b %Y} · {_e(iters)}</div></header>")
    tabs = [("ov", "Overview"), ("gantt", "Tester Gantt"), ("util", "Utilisation"), ("contrib", "Contribution"), ("stories", "Stories"),
            ("tcs", "Test cases"), ("hyg", f"Hygiene ({len(model['findings'])})"), ("rules", "Rules & scope")]
    parts.append("<nav>" + "".join(f"<button data-t='{i}' onclick=\"tab('{i}')\" class='{'on' if n == 0 else ''}'>{_e(l)}</button>" for n, (i, l) in enumerate(tabs)) + "</nav><main>")
    parts.append(_overview(model))
    parts.append(_gantt(model))
    parts.append(_util(model))
    parts.append(_contribution(model))
    parts.append(_stories(model))
    parts.append(_test_cases(model))
    parts.append(_hygiene(model))
    parts.append(_rules(model))
    parts.append(f"</main><script>{JS}</script></body></html>")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))


def _legend():
    return "<div class='legend'>" + "".join(f"<span><i style='background:var(--g-{g.lower()})'></i>{g}</span>" for g in cls.GROUPS) + "</div>"


def _mix_bar(mix):
    total = sum(v for v in mix.values() if v > 0)
    if not total:
        return "<span class='small'>no effort</span>"
    segs = "".join(f"<i title='{g}: {mix[g]:g}h' style='width:{100 * mix[g] / total:.1f}%;background:var(--g-{g.lower()})'></i>"
                   for g in cls.GROUPS if mix.get(g, 0) > 0)
    return f"<div class='bar'>{segs}</div>"


def _overview(model):
    tasks = list(model["tasks"].values())
    people = [p for p in model["people"] if p["capacity"]]
    stories = model["stories"]
    open_st = [s for s in stories if not s["done"]]
    late = [s for s in open_st if s["timing"] in ("Late", "Not started")]
    high = sum(1 for f in model["findings"] if f["severity"] == "High")
    cap = sum(p["capacity_to_date"] for p in people)
    logged = sum(p["logged_to_date"] for p in people)
    cv = model["balance_cv"]
    bal = "–" if cv is None else ("Even" if cv < 0.15 else "Uneven" if cv < 0.3 else "Very uneven")
    cards = [
        (len(tasks), "testing tasks"), (sum(t["is_closed"] for t in tasks), "tasks closed"),
        (f"{logged:g}h / {cap:g}h", "logged vs capacity to date"), (_pct(logged / cap) if cap else "–", "team utilisation"),
        (bal, f"workload balance (CV {cv:.2f})" if cv is not None else "workload balance"),
        (f"{len(open_st)} / {len(stories)}", "stories open / in scope"), (len(late), "open stories late or not started"),
        (high, "high-severity hygiene issues"),
    ]
    out = ["<section id='ov' class='on'><h2>Sprint at a glance</h2><div class='cards'>"]
    out += [f"<div class='card'><b>{_e(v)}</b><span>{_e(l)}</span></div>" for v, l in cards]
    out.append("</div><h2>By team</h2><div class='wrap'><table><tr><th>Team</th><th>Sprint</th><th class='n'>Day</th><th class='n'>Tasks</th><th class='n'>Closed</th>"
               "<th class='n'>Effort h</th><th class='n'>Remaining h</th><th>Effort mix</th><th class='n'>Testers</th><th>Tester source</th><th class='n'>Excluded tasks</th></tr>")
    for t in model["teams"]:
        out.append(f"<tr><td>{_e(t['name'])}</td><td>{_e(t['iteration'])}</td><td class='n'>{t['elapsed']}/{len(t['days'])}</td>"
                   f"<td class='n'>{t['tasks']}</td><td class='n'>{t['tasks_closed']}</td><td class='n'>{t['effort']:g}</td>"
                   f"<td class='n'>{t['remaining']:g}</td><td>{_mix_bar(t['group_hours'])}</td><td class='n'>{t['testers'] or '–'}</td>"
                   f"<td>{_e(t['tester_source'])}</td><td class='n'>{t['excluded']}</td></tr>")
    out.append("</table></div>" + _legend())

    # when did testing start on stories
    buckets = {"Early": 0, "Mid": 0, "Late": 0, "Not started": 0}
    for s in stories:
        buckets[s["timing"]] += 1
    out.append("<h2>When did test execution start? (proxy for deployment to test)</h2><div class='cards'>")
    for k, v in buckets.items():
        out.append(f"<div class='card'><b>{v}</b><span>{k}{' (first third)' if k == 'Early' else ' (middle third)' if k == 'Mid' else ' (last third)' if k == 'Late' else ''}</span></div>")
    out.append("</div>")

    # hygiene by rule
    by_rule = {}
    for f in model["findings"]:
        by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1
    if by_rule:
        out.append("<h2>Hygiene issues by rule</h2><div class='wrap'><table><tr><th>Rule</th><th>Severity</th><th>Check</th><th class='n'>Count</th></tr>")
        for r, c in sorted(by_rule.items(), key=lambda x: -x[1]):
            sev, text = model["rules"][r].severity, model["rules"][r].title
            out.append(f"<tr><td>{r}</td><td>{_sev(sev)}</td><td>{_e(text)}</td><td class='n'>{c}</td></tr>")
        out.append("</table></div>")
    out.append("</section>")
    return "".join(out)


def _sev(s):
    return f"<span class='chip {'bad' if s == 'High' else 'warn' if s == 'Medium' else 'muted'}'>{s}</span>"


def _gantt(model):
    today = model["as_of"]
    people = [p for p in model["people"] if gantt_rows(model, p["key"])]
    out = ["<section id='gantt'><h2>Tester activity Gantt</h2>",
           "<p class='small'>Bar = task active span (first Active → Closed). Solid cells with numbers = hours logged that day "
           "(from Completed Work history). Dashed right edge = still open. Hatched = day off per sprint capacity. "
           "Dashed box = effort logged outside the active span.</p>"]
    out.append("<div class='person-pick'><label for='pp'>Tester</label><select id='pp' onchange='pick(this.value)'><option value='*'>All testers</option>")
    out += [f"<option value='{_e(p['key'])}'>{_e(p['name'])}</option>" for p in people]
    out.append("</select></div>" + _legend())

    for p in people:
        days = p["days"]
        rows = gantt_rows(model, p["key"])
        teams = ", ".join(f"{t['team']} ({t['capacity_per_day']:g}h/d)" for t in p["teams"]) or "no capacity set"
        out.append(f"<div class='gperson' data-k='{_e(p['key'])}'><h3>{_e(p['name'])} <span class='small'>· {_e(teams)} · "
                   f"logged {p['logged']:g}h of {p['capacity']:g}h capacity · {len(p['days_off'])} day(s) off</span></h3>")
        if not days:
            out.append("<p class='small'>Not in any team capacity for this sprint – showing no calendar.</p></div>")
            continue
        out.append("<div class='wrap'><table class='gantt'><tr><th>Task</th><th>Team</th><th>Activity</th><th>State</th><th class='n'>Est</th><th class='n'>Done</th><th class='n'>Rem</th>")
        for i, d in enumerate(days, 1):
            out.append(f"<th class='day{' today' if d == today else ''}'>D{i}<small>{d:%a %d}</small></th>")
        out.append("</tr>")
        for t in rows:
            mine = t["daily"].get(p["key"], {})
            s, e = t["span_start"], t["span_end"]
            flags = f" <span class='flags' title='{_e(', '.join(model['rules'][f].title for f in t['flags']))}'>⚑{len(t['flags'])}</span>" if t["flags"] else ""
            owner_note = "" if t["owner_key"] == p["key"] else f" <span class='small'>(owner: {_e(t['owner']['name'] if t['owner'] else '-')})</span>"
            out.append(f"<tr class='{GROUP_CLASS[t['group']]}'><td class='task' title='{_e(t['title'])}'>{_link(model, t['id'])} {_e(t['title'])}{owner_note}{flags}</td>"
                       f"<td>{_e(t['team'])}</td><td>{_e(t['label'])}</td><td>{_e(t['state'])}</td>"
                       f"<td class='n'>{_h(t['original'])}</td><td class='n'>{_h(t['completed'])}</td><td class='n'>{_h(t['remaining'])}</td>")
            vis_s = max(s, days[0]) if s else None
            vis_e = min(e, days[-1]) if e else None
            for d in days:
                h = round(mine.get(d, 0), 2)
                cls_today = " today" if d == today else ""
                in_span = vis_s and vis_e and vis_s <= d <= vis_e
                if d in p["days_off"] and not h:
                    out.append(f"<td class='c off{cls_today}'>OFF</td>")
                    continue
                if in_span:
                    k = ["h"] if h else []
                    if d == vis_s:
                        k.append("s")
                    if d == vis_e:
                        k.append("e")
                        if not t["is_closed"]:
                            k.append("open")
                    out.append(f"<td class='c{cls_today}'><span class='{' '.join(k)}'>{_h(h)}</span></td>")
                elif h:
                    out.append(f"<td class='c{cls_today}'><span class='x'>{_h(h)}</span></td>")
                else:
                    out.append(f"<td class='c{cls_today}'></td>")
            out.append("</tr>")
        # totals
        out.append("<tr class='tot'><td colspan='7'>Hours logged / capacity</td>")
        for d in days:
            h = round(p["daily_logged"].get(d, 0), 1)
            c = p["daily_capacity"].get(d, 0)
            if d in p["days_off"]:
                out.append(f"<td class='c off'>{_h(h) or 'OFF'}</td>")
                continue
            kind = "" if d > today else ("bad" if c and h > c * 1.2 else "warn" if c and h < c * 0.5 else "ok")
            out.append(f"<td class='c'><span class='chip {kind}'>{_h(h) or '0'}/{c:g}</span></td>")
        out.append("</tr></table></div></div>")
    out.append("</section>")
    return "".join(out)


def _util(model):
    out = ["<section id='util'><h2>Tester utilisation & balance</h2>",
           "<p class='small'>Utilisation = hours logged to date ÷ capacity to date (capacity per day × working days, minus days off). "
           "Plan load = original estimates of owned tasks ÷ full-sprint capacity. Switching = average distinct tasks worked per day.</p>",
           "<div class='wrap'><table><tr><th>Tester</th><th>Teams</th><th class='n'>Cap h/d</th><th class='n'>Days off</th><th class='n'>Capacity h</th>"
           "<th class='n'>Cap to date</th><th class='n'>Logged to date</th><th class='n'>Util</th><th class='n'>Plan load</th><th class='n'>Remaining h</th>"
           "<th class='n'>Tasks (closed)</th><th class='n'>Switching</th><th>Effort mix</th><th class='n'>Flags</th><th>Status</th></tr>"]
    for p in model["people"]:
        cpd = sum(t["capacity_per_day"] for t in p["teams"])
        out.append(f"<tr><td>{_e(p['name'])}</td><td>{_e(', '.join(t['team'] for t in p['teams']) or '-')}</td><td class='n'>{cpd:g}</td>"
                   f"<td class='n'>{len(p['days_off'])}</td><td class='n'>{p['capacity']:g}</td><td class='n'>{p['capacity_to_date']:g}</td>"
                   f"<td class='n'>{p['logged_to_date']:g}</td><td class='n'>{_pct(p['util'])}</td><td class='n'>{_pct(p['plan_load'])}</td>"
                   f"<td class='n'>{p['remaining']:g}</td><td class='n'>{p['tasks_total']} ({p['tasks_closed']})</td><td class='n'>{p['switching']:g}</td>"
                   f"<td>{_mix_bar(p['mix'])}</td><td class='n'>{p['flags']}</td><td>{_status_chip(p['status'])}</td></tr>")
    out.append("</table></div>" + _legend() + "</section>")
    return "".join(out)


def _stories(model):
    out = ["<section id='stories'><h2>Story test lifecycle</h2>",
           "<p class='small'>Test start = first activation of an execution task (manual, compatibility or automation execution / post-scripting). "
           "Progress = test points on test cases linked to the story via <i>Tested By</i>.</p>",
           "<div class='wrap'><table><tr><th>Story</th><th>Team</th><th>State</th><th>Test start</th><th>Timing</th><th class='n'>Test days</th>"
           "<th class='n'>Points</th><th>Outcome</th><th class='n'>Executed</th><th class='n'>Passed</th><th>Open bugs</th><th class='n'>QA effort h</th><th>Why not done / risks</th></tr>"]
    colours = {"Passed": "var(--ok)", "Failed": "var(--bad)", "Blocked": "var(--warn)", "In progress": "var(--accent)", "Not run": "var(--off)", "N/A": "var(--muted)"}
    for s in model["stories"]:
        tot = s["points_total"]
        bar = "<div class='bar'>" + "".join(
            f"<i title='{k}: {v}' style='width:{100 * v / tot:.1f}%;background:{colours.get(k, 'var(--muted)')}'></i>" for k, v in s["outcomes"].items()) + "</div>" if tot else "<span class='small'>none linked</span>"
        timing_kind = {"Early": "ok", "Mid": "muted", "Late": "warn", "Not started": "bad"}[s["timing"]]
        start = f"{s['test_start']:%a %d %b} (D{s['start_day']})" if s["test_start"] and s["start_day"] else (f"{s['test_start']:%d %b}" if s["test_start"] else "–")
        bugs = ", ".join(f"{_link(model, b['id'])} {_e((b['severity'] or '').split(' - ')[-1])}" for b in s["bugs_open"]) or "–"
        out.append(f"<tr><td>{_link(model, s['id'])} {_e(s['title'])}</td><td>{_e(s['team'])}</td><td>{_e(s['state'])}</td><td>{start}</td>"
                   f"<td><span class='chip {timing_kind}'>{s['timing']}</span></td><td class='n'>{s['test_days_left'] or '–'}</td><td class='n'>{tot}</td><td>{bar}</td>"
                   f"<td class='n'>{s['exec_pct'] if s['exec_pct'] is not None else '–'}{'%' if s['exec_pct'] is not None else ''}</td>"
                   f"<td class='n'>{s['pass_pct'] if s['pass_pct'] is not None else '–'}{'%' if s['pass_pct'] is not None else ''}</td>"
                   f"<td>{bugs}</td><td class='n'>{s['effort']:g}</td><td>{_e('; '.join(s['reasons'])) or ('<span class=\"chip ok\">Done</span>' if s['done'] else '')}</td></tr>")
    out.append("</table></div></section>")
    return "".join(out)


def _hygiene(model):
    fs = model["findings"]
    opts = lambda key: "".join(f"<option>{_e(v)}</option>" for v in sorted({f[key] for f in fs}))
    out = ["<section id='hyg'><h2>Work item hygiene</h2>",
           "<div class='person-pick'>"
           f"<select id='f-team' onchange='filt()'><option value=''>All teams</option>{opts('team')}</select>"
           f"<select id='f-person' onchange='filt()'><option value=''>All people</option>{opts('person')}</select>"
           f"<select id='f-rule' onchange='filt()'><option value=''>All rules</option>{opts('rule')}</select></div>",
           "<div class='wrap'><table><thead><tr><th>Severity</th><th>Rule</th><th>Check</th><th>Item</th><th>Team</th><th>Responsible</th><th>Detail</th></tr></thead><tbody>"]
    for f in fs:
        out.append(f"<tr data-team='{_e(f['team'])}' data-rule='{f['rule']}' data-person='{_e(f['person'])}'><td>{_sev(f['severity'])}</td><td>{f['rule']}</td>"
                   f"<td>{_e(f['text'])}</td><td><span class='small'>{_e(f.get('kind', 'Task'))}</span> {_link(model, f['task'])} {_e(f['title'])}</td><td>{_e(f['team'])}</td><td>{_e(f['person'])}</td><td>{_e(f['detail'])}</td></tr>")
    if not fs:
        out.append("<tr><td colspan='7'>No hygiene issues found 🎉</td></tr>")
    out.append("</tbody></table></div></section>")
    return "".join(out)


def _rules(model):
    out = ["<section id='rules'><h2>Hygiene rules</h2>",
           "<p class='small'>Defined in <code>tqa/rules.py</code>. Switch off or re-grade in ado.properties, "
           "e.g. <code>rule.H07.enabled=false</code>, <code>rule.H04.severity=High</code>.</p>",
           "<div class='wrap'><table><tr><th>Rule</th><th>Status</th><th>Severity</th><th>Check</th><th>Applies to</th><th>What it means</th><th class='n'>Findings</th></tr>"]
    counts = {}
    for f in model["findings"]:
        counts[f["rule"]] = counts.get(f["rule"], 0) + 1
    for r in model["rules"].values():
        status = "<span class='chip ok'>On</span>" if r.enabled else "<span class='chip muted'>Off</span>"
        out.append(f"<tr><td>{r.id}</td><td>{status}</td><td>{_sev(r.severity)}</td><td>{_e(r.title)}</td><td>{r.scope}</td>"
                   f"<td class='small'>{_e(r.description)}</td><td class='n'>{counts.get(r.id, 0)}</td></tr>")
    out.append("</table></div>")
    ex = model["excluded"]
    out.append(f"<h2>Excluded tasks – not tester work ({len(ex)})</h2>"
               "<p class='small'>Matched the QA naming/Activity but are owned by someone who is not in the tester list, "
               "and no tester logged effort on them. Check this list if a tester seems to be missing.</p>")
    if ex:
        out.append("<div class='wrap'><table><tr><th>Task</th><th>Team</th><th>State</th><th>Owner</th><th>Reason</th></tr>")
        out += [f"<tr><td>{_link(model, x['id'])} {_e(x['title'])}</td><td>{_e(x['team'])}</td><td>{_e(x['state'])}</td>"
                f"<td>{_e(x['owner'])}</td><td>{_e(x['reason'])}</td></tr>" for x in ex]
        out.append("</table></div>")
    out.append("</section>")
    return "".join(out)


def _test_cases(model):
    tcs = sorted(model["test_cases"], key=lambda t: (not t["flags"], t["team"], t["id"]))
    executed = [t for t in tcs if t["runs"]]
    cards = [(len(tcs), "test cases linked to sprint stories"), (len(executed), "executed"),
             (sum(1 for t in executed if t["attachments_total"] == 0), "executed without evidence"),
             (sum(1 for t in executed if t["state"].lower() in ("design",)), "executed while in Design"),
             (sum(1 for t in tcs if t["priority"] in (None, "")), "without priority")]
    out = ["<section id='tcs'><h2>Test cases</h2><div class='cards'>"]
    out += [f"<div class='card'><b>{v}</b><span>{_e(l)}</span></div>" for v, l in cards]
    out.append("</div><h2>Detail <span class='small'>(flagged first)</span></h2><div class='wrap'><table><tr><th>Test case</th><th>Team</th><th>Stories</th>"
               "<th>State</th><th class='n'>Priority</th><th class='n'>Runs</th><th>Last outcome</th><th>Executed by</th><th class='n'>Evidence</th><th>Flags</th></tr>")
    for t in tcs:
        last = t["runs"][-1]["outcome"] if t["runs"] else "–"
        flags = ", ".join(f"<span title='{_e(model['rules'][f].title)}'>{f}</span>" for f in t["flags"])
        out.append(f"<tr><td>{_link(model, t['id'])} {_e(t['title'])}</td><td>{_e(t['team'])}</td><td>{', '.join(_link(model, s) for s in t['stories'])}</td>"
                   f"<td>{_e(t['state'])}</td><td class='n'>{_e(t['priority']) or '–'}</td><td class='n'>{len(t['runs'])}</td><td>{_e(last)}</td>"
                   f"<td>{_e(', '.join(t['executors'])) or '–'}</td><td class='n'>{t['attachments_total'] if t['runs'] else '–'}</td>"
                   f"<td class='flags'>{flags}</td></tr>")
    out.append("</table></div></section>")
    return "".join(out)


def _sev_counts(sev):
    return ", ".join(f"{k.split(' - ')[-1]} {v}" for k, v in sev.items())


def _contribution(model):
    c = model["contribution"]
    people = {p["key"]: p for p in model["people"]}
    notes = []
    if not c["bug_reasons_maintained"]:
        notes.append("Resolved Reason is not maintained on bugs, so rejected-bug % is not shown.")
    if not c["has_code_data"]:
        notes.append("No Git repositories found, so commits and PRs are not shown.")
    dash = lambda v: "–" if v is None else f"{v:g}"
    out = ["<section id='contrib'><h2>Tester contribution</h2>",
           "<p class='small'>For balancing and coaching, not ranking. Read the numbers alongside each person's capacity "
           "and the kind of work they were given. " + " ".join(_e(n) for n in notes) + "</p><div class='cgrid'>"]
    for prof in c["people"]:
        p = people[prof["key"]]
        e, o, q, f, co = prof["effort"], prof["output"], prof["quality"], prof["flow"], prof["collaboration"]
        sev = o["bugs_by_severity"]
        retest = f" (median {dash(co['retest_turnaround_days_median'])} working days)" if co["bugs_retested"] else ""
        rows = [
            ("Effort", [f"{e['logged_to_date_h']:g}h of {p['capacity_to_date']:g}h ({dash(e['utilisation_pct'])}%)",
                        f"{e['days_off']} day(s) off"]),
            ("Output", [f"{o['test_cases_written']} TCs written · {o['test_cases_moved_to_ready']} moved to Ready",
                        f"{o['executions_manual']} manual + {o['executions_automated']} automated executions "
                        f"({o['distinct_test_cases_executed']} TCs)",
                        f"{o['bugs_raised']} bugs raised" + (f" ({_sev_counts(sev)})" if sev else ""),
                        f"{o['commits']} commits · {o['pull_requests']} PRs · {o['story_points_touched']:g} SP touched"]),
            ("Quality", [f"evidence on {dash(q['evidence_pct'])}% of executed TCs" if q["evidence_pct"] is not None else "no executed TCs linked to stories",
                         f"rejected bugs {dash(q['bugs_rejected_pct'])}%" if q["bugs_rejected_pct"] is not None else "rejected bugs: n/a",
                         f"{q['hygiene_findings']} hygiene findings"]),
            ("Flow", [f"{f['unplanned_tasks']} unplanned task(s) ({f['unplanned_h']:g}h) · {f['reassigned_tasks']} reassigned",
                      f"{f['avg_tasks_per_day']:g} tasks/day"]),
            ("Collaboration", [f"{co['reviews_for_others']} TC reviews for others · {co['pr_reviews']} PR reviews",
                               f"{co['support_h']:g}h support · {co['bugs_retested']} retests{retest}"]),
        ]
        out.append(f"<div class='card ccard'><div class='chead'><b>{_e(prof['name'])}</b>{_status_chip(p['status'])}</div>"
                   f"{_mix_bar(e['mix_h'])}<dl>")
        for label, vals in rows:
            out.append(f"<dt>{label}</dt><dd>{'<br>'.join(_e(v) for v in vals)}</dd>")
        out.append("</dl><ul class='obs'>")
        for ob in sorted(prof["observations"], key=lambda x: x["kind"] != "strength"):
            out.append(f"<li class='{ob['kind']}'>{'✓' if ob['kind'] == 'strength' else '•'} {_e(ob['text'])}</li>")
        if not prof["observations"]:
            out.append("<li class='small'>Nothing notable.</li>")
        out.append("</ul></div>")
    out.append("</div>" + _legend() + "</section>")
    return "".join(out)
