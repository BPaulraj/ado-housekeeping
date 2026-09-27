"""Self-check for rule and code changes: python -m tqa.selfcheck

Used by developers and by the GitHub Copilot /add-rule prompt to verify a change.
Exit code 0 = OK (warnings allowed), 1 = a problem that must be fixed.
"""

import re
import sys
import tempfile
import traceback

from . import analysis, demo, digest, report_excel, report_html, report_trends, trends
from . import rules as hygiene
from .config import load_config


def main():
    errors, warnings = [], []

    # 1. Rule registry is well formed
    for rid, r in sorted(hygiene.REGISTRY.items()):
        if not re.fullmatch(r"H\d{2,3}", rid):
            errors.append(f"{rid}: id must look like H19")
        if r.severity not in hygiene.SEVERITIES:
            errors.append(f"{rid}: severity '{r.severity}' must be one of {hygiene.SEVERITIES}")
        if r.scope not in hygiene.SCOPES:
            errors.append(f"{rid}: scope '{r.scope}' must be one of {hygiene.SCOPES}")
        if not r.description:
            errors.append(f"{rid}: add a docstring - it is shown in the report as 'What it means'")
        if not r.title or len(r.title) > 70:
            errors.append(f"{rid}: title must be 1-70 characters")

    # 2. Analysis + every renderer run end to end on demo data
    cfg = load_config()
    cfg.rule_overrides = {}  # check every rule, even ones switched off locally
    model = None
    try:
        model = analysis.analyse(demo.snapshot(), cfg, demo.AS_OF)
        with tempfile.TemporaryDirectory() as tmp:
            report_html.render(model, f"{tmp}/r.html")
            report_excel.render(model, f"{tmp}/r.xlsx")
            digest.write(model, f"{tmp}/d.json")
            models = [analysis.analyse(s, cfg, demo.AS_OF) for s in demo.history(4)]
            tr = trends.build(models)
            report_trends.render_html(tr, "Demo", f"{tmp}/t.html")
            report_trends.render_excel(tr, f"{tmp}/t.xlsx")
            if not tr["signals"]:
                warnings.append("trends: demo history produced no signals")
    except Exception:
        errors.append("demo run failed:\n" + traceback.format_exc())

    # 3. Every rule is exercised by the demo data
    if model:
        counts = {}
        for f in model["findings"]:
            counts[f["rule"]] = counts.get(f["rule"], 0) + 1
        print(f"{'Rule':6} {'Scope':9} {'Sev':7} {'Demo hits':>9}  Check")
        for rid, r in sorted(hygiene.REGISTRY.items()):
            n = counts.get(rid, 0)
            print(f"{rid:6} {r.scope:9} {r.severity:7} {n:>9}  {r.title}")
            if n == 0:
                warnings.append(f"{rid}: no demo finding - add a case to tqa/demo.py that should trigger it")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print("SELFCHECK " + ("FAILED" if errors else "OK"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
