"""Maps a testing task to an activity code using its title.

Rules are evaluated top-down; the first match wins, so more specific
patterns (e.g. 'evidence review') must come before generic ones ('review').
Tune the regexes to your team's naming convention.
"""

import re

ACTIVITIES = {
    "TD": ("Test case design", "Design"),
    "TR": ("Test case review & rework", "Design"),
    "TE": ("Test case execution", "Execution"),
    "ER": ("Test evidence review", "Execution"),
    "RT": ("Bug retest", "Execution"),
    "CT": ("Compatibility execution", "Execution"),
    "AP": ("Automation pre-scripting", "Automation"),
    "AS": ("Automation post-scripting", "Automation"),
    "AE": ("Automation execution", "Automation"),
    "AC": ("Automation commit & push", "Automation"),
    "PD": ("Performance / JMeter design", "Performance"),
    "PE": ("Performance execution", "Performance"),
    "SD": ("Support to Dev", "Support"),
    "SO": ("Support to other teams", "Support"),
    "UN": ("Unclassified", "Unclassified"),
}

GROUPS = ["Design", "Execution", "Automation", "Performance", "Support", "Unclassified"]

# Codes whose start marks "story is testable / deployed to test"
EXECUTION_START_CODES = {"TE", "CT", "AE", "AS", "PE"}

_RULES = [
    ("SD", r"support.*\bdev"),
    ("SO", r"support"),
    ("RT", r"\bre-?test"),
    ("ER", r"evidence"),
    ("CT", r"compatib|cross[- ]?browser|cross[- ]?device"),
    ("PD", r"(jmeter|perf|performance|load).*(design|script)|(design|script).*(jmeter|perf|performance|load)"),
    ("PE", r"jmeter|performance|\bperf\b|load test|stress test|soak"),
    ("AC", r"commit|\bpush\b|pull request|\bpr\b"),
    ("AP", r"pre[- ]?script|pre[- ]?deploy"),
    ("AS", r"post[- ]?script|post[- ]?deploy"),
    ("AE", r"auto(mation)?\b.*(exec|run)|auto ?qa|automation"),
    ("TR", r"review|rework"),
    ("TD", r"design|test case (creation|writing|prep)|scenario"),
    ("TE", r"exec|run|\bqa\b|test"),
]
_COMPILED = [(code, re.compile(rx, re.I)) for code, rx in _RULES]


def classify(title):
    for code, rx in _COMPILED:
        if rx.search(title or ""):
            return code
    return "UN"


def label(code):
    return ACTIVITIES[code][0]


def group(code):
    return ACTIVITIES[code][1]
