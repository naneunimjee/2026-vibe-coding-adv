"""GitHub 공식 검색 API와 README API (OUT-05~06)."""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode

from newsletter import Candidate, RunLog, config, http
from newsletter.sources import SOURCE_ERRORS, in_window, log_failure, parse_time

API = "https://api.github.com"
SOURCE = "GitHub"


def fetch(window: tuple[datetime, datetime], log: RunLog) -> list[Candidate]:
    try:
        repos = http.get_json(search_url(window[0]))["items"]
    except SOURCE_ERRORS as e:
        log_failure(log, "github", e)
        return []
    cands = []
    for repo in repos:
        try:
            published_at = parse_time(repo["created_at"])
        except SOURCE_ERRORS as e:
            log_failure(log, f"github {repo.get('full_name')}", e)
            continue
        if in_window(published_at, window):
            cands.append(_to_candidate(repo, published_at))
    return cands


def search_url(start: datetime) -> str:
    created = start.astimezone(timezone.utc).date().isoformat()
    query = urlencode({
        "q": f"created:>={created} stars:>={config.GITHUB_MIN_STARS}",
        "sort": "stars",
        "order": "desc",
        "per_page": config.GITHUB_MAX_REPOS,
    })
    return f"{API}/search/repositories?{query}"


def _to_candidate(repo: dict, published_at: datetime) -> Candidate:
    full_name = repo["full_name"]
    description = (repo.get("description") or "").strip()
    return Candidate(
        id=f"gh:{full_name}",
        source=SOURCE,
        title=f"{full_name}: {description}" if description else full_name,
        url=repo["html_url"],
        published_at=published_at,
        score=repo.get("stargazers_count", 0),
        source_text=f"{description}\n\n{_readme(full_name)}".strip(),
    )


def _readme(full_name: str) -> str:
    try:
        text = http.get(f"{API}/repos/{full_name}/readme", accept="application/vnd.github.raw").text
    except (http.FetchError, http.BlockedError):
        return ""  # README가 없거나 못 받으면 설명만 쓴다
    return text[: config.README_MAX_CHARS]
