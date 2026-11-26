"""arXiv 공식 API (OUT-07)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlencode

from newsletter import Candidate, RunLog, config, http
from newsletter.sources import ATOM, SOURCE_ERRORS, in_window, log_failure, parse_time

API = "https://export.arxiv.org/api/query"
SOURCE = "arXiv"
ARXIV_ID = re.compile(r"arxiv\.org/abs/(.+?)(?:v\d+)?$")


def fetch(window: tuple[datetime, datetime], log: RunLog) -> list[Candidate]:
    try:
        xml = http.get(query_url(), accept="application/atom+xml").text
        cands = parse(xml)
    except SOURCE_ERRORS as e:
        log_failure(log, "arxiv", e)
        return []
    return [c for c in cands if in_window(c.published_at, window)]


def query_url() -> str:
    query = urlencode({
        "search_query": " OR ".join(f"cat:{c}" for c in config.ARXIV_CATEGORIES),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": config.ARXIV_MAX_RESULTS,
    })
    return f"{API}?{query}"


def parse(xml: str) -> list[Candidate]:
    root = ET.fromstring(xml)
    return [_to_candidate(entry) for entry in root.findall("a:entry", ATOM)]


def _to_candidate(entry: ET.Element) -> Candidate:
    # <id>는 http://arxiv.org/abs/<번호>v<n> 형식 → 버전을 뺀 번호만 (CHK-02)
    number = ARXIV_ID.search(entry.findtext("a:id", "", ATOM).strip()).group(1)
    title = " ".join(entry.findtext("a:title", "", ATOM).split())
    abstract = " ".join(entry.findtext("a:summary", "", ATOM).split())
    return Candidate(
        id=f"ax:{number}",
        source=SOURCE,
        title=title,
        url=f"https://arxiv.org/abs/{number}",
        published_at=parse_time(entry.findtext("a:published", "", ATOM)),
        score=0,
        source_text=f"{title}\n\n{abstract}",
    )
