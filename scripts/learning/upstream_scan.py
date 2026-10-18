"""Upstream discovery — the skill researches how to improve its own research.

Scans GitHub (new repos + watchlist releases), arXiv (fresh benchmark/method
papers) and produces a reviewable discovery report. NEVER auto-applies anything.
See references/learning-protocol.md §8.
"""

from __future__ import annotations

import os
import sys
import time

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from lib import http, paths, util  # noqa: E402

GITHUB_SEARCH = "https://api.github.com/search/repositories"
GITHUB_REPO = "https://api.github.com/repos"
ARXIV_API = "https://export.arxiv.org/api/query"

QUERIES = [
    "deep research agent",
    "research agent benchmark",
    "citation verification tool",
    "MCP server research",
]

NEED_KEYWORDS = [
    "research", "citation", "evidence", "fact", "verify", "verification",
    "benchmark", "search", "browser", "knowledge", "data",
]

PROPOSE_STARS = 300
PROPOSE_FRESH_DAYS = 90
WATCH_STARS = 80
WATCH_FRESH_DAYS = 180


def scan(write_report: bool = True, update_watchlist: bool = False) -> dict:
    period = util.today_iso()[:7]
    candidates: list[dict] = []
    watchlist_changes: list[dict] = []
    queries_run = 0
    repos_checked = 0

    if http.is_offline():
        result = {
            "period": period,
            "offline": True,
            "candidates": [],
            "scan": {"repos_checked": 0, "queries": 0, "watchlist_changes": []},
        }
        if write_report:
            result["written"] = _write_report(period, candidates, {"repos_checked": 0, "queries": 0,
                                                                   "watchlist_changes": []},
                                              offline=True)
        return result

    # 1) new repos from GitHub search
    for q in QUERIES:
        try:
            payload = http.get_json(
                GITHUB_SEARCH,
                params={"q": q, "sort": "updated", "order": "desc", "per_page": 5},
                headers={"Accept": "application/vnd.github+json"},
            )
            queries_run += 1
            for repo in payload.get("items", []) or []:
                repos_checked += 1
                cand = _repo_candidate(repo)
                if cand:
                    candidates.append(cand)
        except Exception as exc:  # noqa: BLE001
            candidates.append({
                "name": f"(github search failed: {q})",
                "what": f"{type(exc).__name__}", "why": "network/rate-limit",
                "where": "github", "cost": "n/a", "cost_note": "", "risk": "",
                "recommendation": "skip",
            })
        time.sleep(1.0)  # gentle on the keyless search rate limit

    # 2) fresh arXiv benchmark/method papers
    try:
        xml = http.get_text(
            ARXIV_API,
            params={"search_query": 'all:"deep research" AND all:agent',
                    "sortBy": "submittedDate", "sortOrder": "descending", "max_results": 5},
        )
        from connectors.arxiv import parse_feed

        for rec in parse_feed(xml):
            candidates.append({
                "name": util.truncate(rec["title"], 80),
                "what": "arXiv paper (fresh)", "why": "new method/benchmark adjacent to this skill",
                "where": rec["url"], "repo": None, "stars": None, "last_commit": rec.get("published"),
                "cost": "read-time only", "cost_note": "evaluate abstract first",
                "risk": "preprint (unreviewed)", "recommendation": "watch",
            })
    except Exception:
        pass

    # 3) watchlist release monitoring
    wl_path = paths.runtime_learning_dir() / "watchlist.json"
    watchlist = util.read_json(wl_path, {"schema": 1, "watch": []})
    new_wl = {"schema": 1, "watch": []}
    for entry in watchlist.get("watch", []):
        repo = entry.get("repo")
        if repo:
            repos_checked += 1
            try:
                rel = http.get_json(f"{GITHUB_REPO}/{repo}/releases/latest",
                                    headers={"Accept": "application/vnd.github+json"})
                tag = rel.get("tag_name")
                if tag and tag != entry.get("last_seen_release"):
                    watchlist_changes.append(
                        {"name": entry.get("name", repo), "change": f"new release {tag} ({rel.get('published_at', '')[:10]})"}
                    )
                    entry["last_seen_release"] = tag
            except Exception:
                pass
            time.sleep(0.5)
        new_wl["watch"].append(entry)
    if update_watchlist:
        util.write_json(wl_path, new_wl)

    written = _write_report(period, candidates, {
        "repos_checked": repos_checked,
        "queries": queries_run,
        "watchlist_changes": watchlist_changes,
    }) if write_report else None

    return {
        "period": period,
        "offline": False,
        "candidates": candidates,
        "scan": {"repos_checked": repos_checked, "queries": queries_run,
                 "watchlist_changes": watchlist_changes},
        "written": written,
        "recommend_propose": [c["name"] for c in candidates if c["recommendation"] == "propose"],
    }


def _repo_candidate(repo: dict) -> dict | None:
    name = repo.get("full_name", "")
    desc = (repo.get("description") or "").lower()
    if not name:
        return None
    stars = repo.get("stargazers_count", 0)
    pushed = (repo.get("pushed_at") or "")[:10]
    fresh_days = _days_since(pushed)
    keyword_hit = any(k in desc for k in NEED_KEYWORDS)
    if not keyword_hit and stars < WATCH_STARS:
        return None
    if stars >= PROPOSE_STARS and fresh_days is not None and fresh_days <= PROPOSE_FRESH_DAYS:
        rec = "propose"
    elif stars >= WATCH_STARS or (fresh_days is not None and fresh_days <= WATCH_FRESH_DAYS):
        rec = "watch"
    else:
        rec = "skip"
    return {
        "name": name,
        "what": util.truncate(repo.get("description") or "(no description)", 140),
        "why": "matches research/verification needs" if keyword_hit else "high-activity repo",
        "where": repo.get("html_url"),
        "repo": name,
        "stars": stars,
        "last_commit": pushed or None,
        "cost": "MCP/exe integration", "cost_note": "hours; needs eval",
        "risk": "unreviewed quality; check license",
        "recommendation": rec,
    }


def _days_since(iso_date: str) -> int | None:
    from datetime import date, datetime

    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (date.today() - d).days


def _write_report(period: str, candidates: list[dict], scan: dict, offline: bool = False) -> str:
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(paths.REPO_ROOT / "templates")), autoescape=False)
    tpl = env.get_template("discovery-report.md.j2")
    text = tpl.render(
        period=period,
        generated_at=util.utcnow_iso(),
        candidates=candidates,
        scan=scan,
    )
    out_dir = paths.runtime_learning_dir() / "discoveries"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{period}.md"
    util.atomic_write_text(out, text)
    return str(out)
