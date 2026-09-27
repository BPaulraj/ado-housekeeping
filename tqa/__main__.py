"""CLI: python -m tqa [options]"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime

import hashlib

from . import analysis, digest, report_excel, report_html, report_trends, trends
from .ado_client import AdoClient, AdoError
from .collector import NotEnoughSprints, collect, resolve_iterations
from .config import load_config


def _json_default(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(type(o))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tqa", description="Sprint testing insights from Azure DevOps")
    ap.add_argument("--config", default="ado.properties")
    ap.add_argument("--iteration", default="current", help="'current', 'previous', or an iteration name/path")
    ap.add_argument("--team", help="only this configured team")
    ap.add_argument("--as-of", type=date.fromisoformat, help="analyse as if today were YYYY-MM-DD")
    ap.add_argument("--format", default="html,excel", help="html, excel or both")
    ap.add_argument("--out", help="output directory (default report.output.dir)")
    ap.add_argument("--from-snapshot", help="re-analyse a saved snapshot JSON instead of calling ADO")
    ap.add_argument("--demo", action="store_true", help="use built-in demo data")
    ap.add_argument("--list-teams", action="store_true", help="list ADO teams in the project and exit")
    ap.add_argument("--sprints", type=int, default=1, help="also build a trends report over the last N sprints (ending at --iteration)")
    ap.add_argument("--refresh", action="store_true", help="re-collect finished sprints instead of using the snapshot cache")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    out_dir = args.out or cfg.output_dir
    os.makedirs(out_dir, exist_ok=True)
    as_of = args.as_of

    try:
        if args.list_teams:
            client = AdoClient(cfg.org_url, cfg.project, cfg.pat)
            for t in sorted(client.list_teams(), key=lambda t: t["name"].lower()):
                tfv = client.team_field_values(t["name"])
                areas = ", ".join(v["value"] + (" (+children)" if v.get("includeChildren") else "") for v in tfv.get("values", []))
                print(f"{t['name']}\n    area: {areas}")
            return 0

        history = []   # oldest first; the last one is the sprint the main report is about
        if args.demo:
            from . import demo
            history = demo.history(args.sprints) if args.sprints > 1 else [demo.snapshot()]
            as_of = as_of or demo.AS_OF
        elif args.from_snapshot:
            with open(args.from_snapshot, encoding="utf-8") as fh:
                history = [json.load(fh)]
        else:
            client = AdoClient(cfg.org_url, cfg.project, cfg.pat)
            for offset in range(args.sprints - 1, -1, -1):
                try:
                    history.append(_collect_cached(client, cfg, args, out_dir, offset))
                except NotEnoughSprints as exc:
                    if offset == 0:
                        raise
                    print(f"Note     : {exc} - skipping sprint {offset} back")
    except AdoError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    snapshot = history[-1]

    sprint = "-".join(sorted({t["iteration"]["name"] for t in snapshot["teams"]}))
    stem = re.sub(r"[^\w.-]+", "_", f"{'demo_' if args.demo else ''}{sprint}_{datetime.now():%Y%m%d_%H%M}")

    if not (args.demo or args.from_snapshot) and args.sprints == 1:
        snap_dir = os.path.join(out_dir, "snapshots")
        os.makedirs(snap_dir, exist_ok=True)
        snap_path = os.path.join(snap_dir, stem + ".json")
        with open(snap_path, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh, indent=1, default=_json_default)
        print(f"Snapshot : {snap_path}")

    model = analysis.analyse(snapshot, cfg, as_of)
    formats = {f.strip().lower() for f in args.format.split(",")}
    if "html" in formats:
        path = os.path.join(out_dir, stem + ".html")
        report_html.render(model, path)
        print(f"HTML     : {path}")
    if formats & {"excel", "xlsx"}:
        path = os.path.join(out_dir, stem + ".xlsx")
        report_excel.render(model, path)
        print(f"Excel    : {path}")

    path = os.path.join(out_dir, stem + "_digest.json")
    digest.write(model, path)
    print(f"Digest   : {path}  (input for the Copilot prompts in .github/prompts)")

    if len(history) > 1:
        models = [analysis.analyse(snap, cfg, as_of) for snap in history[:-1]] + [model]
        tr = trends.build(models)
        tstem = re.sub(r"[^\w.-]+", "_", f"{'demo_' if args.demo else ''}trends_{tr['labels'][0]}_to_{tr['labels'][-1]}_{datetime.now():%Y%m%d_%H%M}")
        if "html" in formats:
            path = os.path.join(out_dir, tstem + ".html")
            report_trends.render_html(tr, model["project"], path)
            print(f"Trends   : {path}")
        if formats & {"excel", "xlsx"}:
            path = os.path.join(out_dir, tstem + ".xlsx")
            report_trends.render_excel(tr, path)
            print(f"Trends   : {path}")
        path = os.path.join(out_dir, tstem + "_digest.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(tr, fh, indent=1, default=_json_default)
        print(f"Trends   : {path}  (input for /trend-review)")
        print(f"Signals  : {len(tr['signals'])} across {len(tr['labels'])} sprints")

    high = sum(1 for f in model["findings"] if f["severity"] == "High")
    print(f"Done - {len(model['tasks'])} tasks, {len(model['stories'])} stories, {len(model['people'])} people, "
          f"{len(model['findings'])} hygiene findings ({high} high).")
    return 0


def _collect_cached(client, cfg, args, out_dir, offset):
    """Finished sprints don't change much, so their snapshot is cached; the open sprint is always collected fresh."""
    iterations = resolve_iterations(client, cfg, args.iteration, args.team, offset)
    names = "-".join(sorted({it["name"] for it in iterations.values()}))
    key = hashlib.sha1("|".join(f"{t}:{it['id']}" for t, it in sorted(iterations.items())).encode()).hexdigest()[:8]
    cache = os.path.join(out_dir, "snapshots", "cache", re.sub(r"[^\w.-]+", "_", f"{names}_{key}.json"))
    finished = all(date.fromisoformat(it["finish"][:10]) < date.today() for it in iterations.values())
    if finished and not args.refresh and os.path.exists(cache):
        print(f"Cached   : {names} ({cache})")
        with open(cache, encoding="utf-8") as fh:
            return json.load(fh)
    print(f"Collecting {names} from {cfg.org_url}/{cfg.project} ...")
    snap = collect(client, cfg, args.iteration, args.team, offset)
    if finished:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache, "w", encoding="utf-8") as fh:
            json.dump(snap, fh, indent=1, default=_json_default)
    return snap


if __name__ == "__main__":
    sys.exit(main())
