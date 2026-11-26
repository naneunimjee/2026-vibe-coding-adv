"""후보 거르기: https 아닌 링크, 같은 소식, 최근 호에 실린 소식을 뺀다 (FR-002)."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from newsletter import Candidate, RunLog


def normalize_url(url: str) -> str:
    """BP-RANK-001: 소문자 호스트, utm_* 쿼리·조각(#) 제거, 경로 끝의 / 제거."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.startswith("utm_")]
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def apply(cands: list[Candidate], recent_urls: set[str], log: RunLog) -> list[Candidate]:
    """recent_urls는 최근 7개 호의 정규화 링크 집합이다 (BP-RANK-002). 입력 순서를 유지한다."""
    secure = []
    for c in cands:
        if c.url.startswith("https://"):
            secure.append(c)
        else:
            log.add("LINK_NOT_HTTPS", c.id, c.url)  # BP-SUM-004: https로 바꾸지 않고 제외

    # BP-RANK-001: 같은 소식이면 반응 수가 큰 쪽 하나만 남긴다
    best: dict[str, Candidate] = {}
    for c in secure:
        key = normalize_url(c.url)
        if key not in best or c.score > best[key].score:
            best[key] = c
    kept = []
    for c in secure:
        key = normalize_url(c.url)
        if best[key] is not c:
            log.add("DUPLICATE", c.id, f"same as {best[key].id}")
        elif key in recent_urls:
            log.add("RECENTLY_PUBLISHED", c.id, key)
        else:
            kept.append(c)
    return kept
