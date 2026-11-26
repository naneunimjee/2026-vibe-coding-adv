"""GeekNews Atom 피드 (OUT-01)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

from newsletter import Candidate, RunLog, http
from newsletter.extract import plain_text
from newsletter.sources import ATOM, SOURCE_ERRORS, in_window, log_failure, parse_time

FEED_URL = "https://news.hada.io/rss/news"
SOURCE = "GeekNews"


def fetch(window: tuple[datetime, datetime], log: RunLog) -> list[Candidate]:
    try:
        xml = http.get(FEED_URL, accept="application/atom+xml").text
        cands = parse(xml)
    except SOURCE_ERRORS as e:
        log_failure(log, "geeknews", e)
        return []
    return [c for c in cands if in_window(c.published_at, window)]


def parse(xml: str) -> list[Candidate]:
    root = ET.fromstring(xml)
    return [_to_candidate(entry) for entry in root.findall("a:entry", ATOM)]


def _to_candidate(entry: ET.Element) -> Candidate:
    # BP-SRC-007: 원문 링크는 피드가 주는 GeekNews 토론 페이지 주소
    link = entry.find("a:link", ATOM).attrib["href"]
    entry_id = entry.findtext("a:id", "", ATOM) or link
    topic_id = parse_qs(urlsplit(entry_id).query)["id"][0]
    published = entry.findtext("a:published", "", ATOM) or entry.findtext("a:updated", "", ATOM)
    return Candidate(
        id=f"gn:{topic_id}",
        source=SOURCE,
        title=entry.findtext("a:title", "", ATOM).strip(),
        url=link,
        published_at=parse_time(published),
        score=0,
        source_text=plain_text(entry.findtext("a:content", "", ATOM)),
    )
