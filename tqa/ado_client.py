"""Thin Azure DevOps REST client (read-only)."""

import time
from datetime import timedelta
from urllib.parse import quote

import requests

API = "7.1"


class AdoError(RuntimeError):
    pass


class AdoClient:
    def __init__(self, org_url, project, pat, timeout=60):
        if not (org_url and project and pat):
            raise AdoError("ado.org.url, ado.project and a PAT (ADO_PAT env var or ado.pat) are required")
        self.org = org_url.rstrip("/")
        self.project = project
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = ("", pat)
        self.session.headers.update({"Accept": "application/json"})

    # ---- plumbing -------------------------------------------------------
    def _request(self, method, url, params=None, json=None, api=API):
        params = dict(params or {})
        params.setdefault("api-version", api)
        for attempt in range(5):
            try:
                resp = self.session.request(method, url, params=params, json=json, timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout):
                if attempt == 4:
                    raise AdoError(f"Cannot reach {self.org} - check network/VPN")
                time.sleep(2 ** attempt)
                continue
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(int(resp.headers.get("Retry-After", 2 ** attempt)))
                continue
            if resp.status_code == 203 or "text/html" in resp.headers.get("Content-Type", ""):
                raise AdoError("Authentication failed - check the PAT (needs Work Items: Read, Test Management: Read, Project & Team: Read, Code: Read)")
            if not resp.ok:
                raise AdoError(f"{method} {url} -> {resp.status_code}: {resp.text[:400]}")
            return resp
        raise AdoError(f"{method} {url} failed after retries")

    def get(self, url, params=None, api=API):
        return self._request("GET", url, params=params, api=api).json()

    def post(self, url, body, params=None, api=API):
        return self._request("POST", url, params=params, json=body, api=api).json()

    def _proj(self, path):
        return f"{self.org}/{quote(self.project)}/_apis/{path}"

    def _team(self, team, path):
        return f"{self.org}/{quote(self.project)}/{quote(team, safe='')}/_apis/{path}"

    # ---- teams & sprints ------------------------------------------------
    def list_teams(self):
        url = f"{self.org}/_apis/projects/{quote(self.project)}/teams"
        return self.get(url, {"$top": 500})["value"]

    def team_iterations(self, team, timeframe=None):
        params = {"$timeframe": timeframe} if timeframe else {}
        return self.get(self._team(team, "work/teamsettings/iterations"), params)["value"]

    def team_settings(self, team):
        return self.get(self._team(team, "work/teamsettings"))

    def team_field_values(self, team):
        return self.get(self._team(team, "work/teamsettings/teamfieldvalues"))

    def capacities(self, team, iteration_id):
        data = self.get(self._team(team, f"work/teamsettings/iterations/{iteration_id}/capacities"))
        # 7.1 returns {"teamMembers": [...]}; older versions return {"value": [...]}
        return data.get("teamMembers", data.get("value", []))

    def team_days_off(self, team, iteration_id):
        return self.get(self._team(team, f"work/teamsettings/iterations/{iteration_id}/teamdaysoff")).get("daysOff", [])

    # ---- work items -----------------------------------------------------
    def wiql(self, team, query):
        data = self.post(self._team(team, "wit/wiql"), {"query": query})
        return [w["id"] for w in data.get("workItems", [])]

    def work_items(self, ids, fields=None, relations=False):
        out = []
        ids = list(ids)
        for i in range(0, len(ids), 200):
            body = {"ids": ids[i:i + 200], "errorPolicy": "Omit"}
            if relations:
                body["$expand"] = "Relations"
            elif fields:
                body["fields"] = fields
            data = self.post(self._proj("wit/workitemsbatch"), body)
            out.extend(w for w in data.get("value", []) if w)
        return out

    def revisions(self, wid):
        out, skip = [], 0
        while True:
            page = self.get(self._proj(f"wit/workItems/{wid}/revisions"), {"$top": 200, "$skip": skip})["value"]
            out.extend(page)
            if len(page) < 200:
                return out
            skip += 200

    def comments(self, wid):
        out, token = [], None
        while True:
            params = {"$top": 200}
            if token:
                params["continuationToken"] = token
            data = self.get(self._proj(f"wit/workItems/{wid}/comments"), params, api="7.1-preview.4")
            out.extend(data.get("comments", []))
            token = data.get("continuationToken")
            if not token:
                return out

    # ---- test plans -----------------------------------------------------
    def test_plan_names(self):
        out, token = {}, None
        while True:
            params = {"continuationToken": token} if token else {}
            resp = self._request("GET", self._proj("testplan/plans"), params=params)
            out.update({str(p["id"]): p["name"] for p in resp.json().get("value", [])})
            token = resp.headers.get("x-ms-continuationtoken")
            if not token:
                return out

    def test_points_for_cases(self, test_case_ids):
        out = []
        ids = list(test_case_ids)
        for i in range(0, len(ids), 100):
            body = {"pointsFilter": {"testcaseIds": ids[i:i + 100]}}
            skip = 0
            while True:
                page = self.post(self._proj("test/points"), body, params={"$top": 1000, "$skip": skip}).get("points", [])
                out.extend(page)
                if len(page) < 1000:
                    break
                skip += 1000
        return out

    def test_result(self, run_id, result_id):
        """Result with step (iteration) details - carries runBy, completedDate and step attachments."""
        return self.get(self._proj(f"test/Runs/{run_id}/Results/{result_id}"), {"detailsToInclude": "Iterations"})

    def test_result_attachments(self, run_id, result_id):
        return self.get(self._proj(f"test/Runs/{run_id}/Results/{result_id}/attachments"), api="7.1-preview.1").get("value", [])

    def test_plans(self):
        """All test plans with their area path (used to attribute executions to a team)."""
        out, token = [], None
        while True:
            params = {"continuationToken": token} if token else {}
            resp = self._request("GET", self._proj("testplan/plans"), params=params)
            out.extend(resp.json().get("value", []))
            token = resp.headers.get("x-ms-continuationtoken")
            if not token:
                return out

    def test_runs(self, start, end):
        """Runs updated between two datetimes; ADO allows at most 7 days per query, so chunk."""
        out, seen, lo = [], set(), start
        while lo < end:
            hi = min(lo + timedelta(days=7), end)
            skip = 0
            while True:
                page = self.get(self._proj("test/runs"), {"minLastUpdatedDate": lo.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                          "maxLastUpdatedDate": hi.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                          "$top": 100, "$skip": skip})["value"]   # max 100 here
                out.extend(r for r in page if r["id"] not in seen)
                seen.update(r["id"] for r in page)
                if len(page) < 100:
                    break
                skip += 100
            lo = hi
        return out

    def run_results(self, run_id):
        out, skip = [], 0
        while True:
            page = self.get(self._proj(f"test/Runs/{run_id}/results"), {"$top": 1000, "$skip": skip})["value"]
            out.extend(page)
            if len(page) < 1000:
                return out
            skip += 1000

    # ---- git ------------------------------------------------------------
    def repositories(self):
        return self.get(self._proj("git/repositories"))["value"]

    def commits(self, repo_id, start, end):
        out, skip = [], 0
        while True:
            page = self.get(self._proj(f"git/repositories/{repo_id}/commits"), {
                "searchCriteria.fromDate": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "searchCriteria.toDate": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "searchCriteria.$top": 1000, "searchCriteria.$skip": skip})["value"]
            out.extend(page)
            if len(page) < 1000:
                return out
            skip += 1000

    def pull_requests_since(self, start):
        """Project PRs (any status) created on/after start. Newest first, so stop paging once older."""
        out, skip = [], 0
        while True:
            page = self.get(self._proj("git/pullrequests"), {"searchCriteria.status": "all", "$top": 200, "$skip": skip})["value"]
            fresh = [p for p in page if p.get("creationDate", "") >= start.strftime("%Y-%m-%dT%H:%M:%S")]
            out.extend(fresh)
            if len(page) < 200 or len(fresh) < len(page):
                return out
            skip += 200

    def web_url(self, wid):
        return f"{self.org}/{quote(self.project)}/_workitems/edit/{wid}"
