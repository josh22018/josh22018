#!/usr/bin/env python3
"""Save the last year of GitHub contributions to data/contributions.json.

Uses the GraphQL API when GITHUB_TOKEN is set (the Action provides one),
otherwise scrapes the public contributions calendar.
"""
import datetime as dt
import json
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USER = json.loads((ROOT / "config.json").read_text())["user"]

QUERY = """query($login:String!){user(login:$login){contributionsCollection{
  contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""


def via_graphql(token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    body = json.load(urllib.request.urlopen(req, timeout=30))
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    cal = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return [{"date": d["date"], "count": d["contributionCount"]}
            for w in cal["weeks"] for d in w["contributionDays"]]


def via_html():
    req = urllib.request.Request(f"https://github.com/users/{USER}/contributions",
                                 headers={"User-Agent": "profile-cards"})
    html = urllib.request.urlopen(req, timeout=30).read().decode()
    ids = dict(re.findall(r'data-date="(\d{4}-\d\d-\d\d)"[^>]*?id="([^"]+)"', html))
    ids.update({d: i for i, d in re.findall(r'id="([^"]+)"[^>]*?data-date="(\d{4}-\d\d-\d\d)"', html)})
    tips = {}
    for tid, label in re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', html):
        m = re.match(r"\s*(\d+|No) contribution", label)
        tips[tid] = 0 if (not m or m.group(1) == "No") else int(m.group(1))
    return [{"date": d, "count": tips.get(i, 0)} for d, i in sorted(ids.items())]


def main():
    token = os.environ.get("GITHUB_TOKEN")
    days = None
    if token:
        try:
            days = via_graphql(token)
        except Exception as e:  # fall back to the public page
            print("GraphQL failed, scraping instead:", e)
    if not days:
        days = via_html()
    if len(days) < 300:
        raise SystemExit(f"Only got {len(days)} days; refusing to overwrite the data file")
    out = {"user": USER, "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "total": sum(d["count"] for d in days), "days": days}
    (ROOT / "data" / "contributions.json").write_text(json.dumps(out, indent=1))
    print(f"{len(days)} days, {out['total']} contributions")


if __name__ == "__main__":
    main()
