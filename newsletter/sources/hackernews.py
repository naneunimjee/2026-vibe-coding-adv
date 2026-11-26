"""Hacker News 공식 API (OUT-02~04)."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from newsletter import Candidate, RunLog, config, http
from newsletter.extract import page_text, plain_text
from newsletter.sources import SOURCE_ERRORS, in_window, log_failure

API = "https://hacker-news.firebaseio.com/v0"
ITEM_PAGE = "https://news.ycombinator.com/item?id={id}"
SOURCE = "Hacker News"
GITHUB_REPO_HOME = re.compile(r"^https://github\.com/([^/?#]+)/([^/?#]+)/?$")


def fetch(window: tuple[datetime, datetime], log: RunLog) -> list[Candidate]:
    try:
        top_ids = http.get_json(f"{API}/topstories.json")[: config.HN_TOP_STORIES]
    except SOURCE_ERRORS as e:
        log_failure(log, "hackernews", e)
        return []
    cands = []
    for item_id in top_ids:
        try:
            item = http.get_json(f"{API}/item/{item_id}.json")
        except SOURCE_ERRORS as e:
            log_failure(log, f"hackernews item {item_id}", e)
            continue
        if not item or item.get("type") != "story":
            continue
        published_at = datetime.fromtimestamp(item["time"], tz=timezone.utc)
        if not in_window(published_at, window):
            continue  # 수집 기간 밖이면 원문(OUT-04)을 요청하지 않는다
        cands.append(_to_candidate(item, published_at))
    return cands


def _to_candidate(item: dict, published_at: datetime) -> Candidate:
    url = item.get("url")
    if url:
        source_text = _original_text(url)
    else:
        url = ITEM_PAGE.format(id=item["id"])
        source_text = plain_text(item.get("text", ""))
    return Candidate(
        id=f"hn:{item['id']}",
        source=SOURCE,
        title=item.get("title", "").strip(),
        url=url,
        published_at=published_at,
        score=item.get("score", 0),
        source_text=source_text,
    )


def _original_text(url: str) -> str:
    """원문 본문. 못 얻으면 "" → 요약 단계에서 ORIGINAL_UNAVAILABLE로 제외."""
    if not url.startswith("https://"):
        return ""  # BP-SUM-004: 필터 단계에서 LINK_NOT_HTTPS로 제외
    try:
        repo = GITHUB_REPO_HOME.match(url)
        if repo:
            # 저장소 첫 화면은 스크립트로 그려져 본문을 못 얻으므로 README API를 쓴다 (CHK-04)
            owner, name = repo.groups()
            return http.get(f"https://api.github.com/repos/{owner}/{name}/readme",
                            accept="application/vnd.github.raw").text
        response = http.get(url, accept="text/html")
    except (http.FetchError, http.BlockedError):
        return ""
    if "html" not in response.content_type:
        return ""
    return page_text(response.text)
