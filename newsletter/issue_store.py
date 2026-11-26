"""호 파일 읽기·검증·저장 (상세 설계 5.12, 데이터 설계서 3장). build.py도 validate를 쓴다."""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from newsletter import config
from newsletter.filtering import normalize_url

SECTIONS = ("trend", "issue")
TOPICS = ("AI", "개발 도구", "클라우드", "보안", "정책", "장애", "연구", "기타")
SOURCES = {"GeekNews": "gn", "Hacker News": "hn", "GitHub": "gh", "arXiv": "ax"}
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_all(data_dir: Path) -> list[dict]:
    """날짜 오름차순. JSON 파싱 실패는 예외로 둔다."""
    issues = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(data_dir).glob("*.json"))]
    return sorted(issues, key=lambda i: i["date"])


def next_identity(history: list[dict], today: date) -> tuple[int, str]:
    """같은 날짜를 다시 돌리면 같은 번호 (BP-PUB-005), 아니면 최대 번호 + 1 (BP-PUB-004)."""
    day = today.isoformat()
    for i in history:
        if i["date"] == day:
            return i["number"], day
    return max((i["number"] for i in history), default=0) + 1, day


def build_headline(items: list[dict], study: dict | None) -> tuple[str, str, str, int]:
    """대표 제목·강조어·한 줄 요약·읽는 시간을 규칙으로 만든다 (LLM을 쓰지 않음)."""
    counts = Counter(i["topic"] for i in items)
    top = max(counts.values())
    leaders = [t for t, n in counts.items() if n == top]
    word = items[0]["topic"] if items[0]["topic"] in leaders else leaders[0]
    trend = sum(i["section"] == "trend" for i in items)
    issue = len(items) - trend
    summary = f"트렌드 {trend}건, 이슈 {issue}건, 오늘의 공부 {1 if study else 0}개를 골랐어요."
    chars = sum(len(i["title"]) + len(i["summary"]) for i in items) + (len(study["summary"]) if study else 0)
    minutes = min(15, max(1, math.ceil(chars / 500)))  # 분당 약 500자
    return f"오늘은 {word} 소식이 가장 많았어요", word, summary, minutes


def save(issue: dict, data_dir: Path) -> Path:
    path = Path(data_dir) / f"{issue['date']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(issue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _str(v, lo: int, hi: int) -> bool:
    return isinstance(v, str) and lo <= len(v) <= hi


def _int(v, lo: int, hi: int | None = None) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= lo and (hi is None or v <= hi)


def _https(v) -> bool:
    return isinstance(v, str) and v.startswith("https://") and not re.search(r"\s", v)


def _time(v) -> bool:
    try:
        return isinstance(v, str) and datetime.fromisoformat(v).utcoffset() is not None
    except ValueError:
        return False


def validate(issue: dict, history: list[dict]) -> list[str]:
    """오류 메시지 목록. 비면 통과. history에 같은 날짜의 호가 있으면 그 호는 비교에서 뺀다 (덮어쓰기)."""
    e: list[str] = []
    tag = f"{issue.get('date')}"
    others = [h for h in history if h.get("date") != issue.get("date")]

    if issue.get("schema_version") != 1:
        e.append("schema_version must be 1")
    if not _int(issue.get("number"), 1):
        e.append("number must be int >= 1")
    elif any(h.get("number") == issue["number"] for h in others):
        e.append(f"number {issue['number']} already used")
    elif any(h.get("date") == issue.get("date") and h.get("number") != issue["number"] for h in history):
        e.append("same date must keep the same number")
    if not (isinstance(issue.get("date"), str) and DATE.match(issue["date"])):
        e.append("date must be YYYY-MM-DD")
    if not _time(issue.get("collected_at")):
        e.append("collected_at must be ISO 8601 with offset")
    if not _str(issue.get("headline"), 1, 60):
        e.append("headline 1~60")
    hl = issue.get("highlight")
    if not _str(hl, 1, 20) or not isinstance(issue.get("headline"), str) or hl not in issue["headline"]:
        e.append("highlight must be 1~20 and inside headline")
    if not _str(issue.get("summary"), 1, 120):
        e.append("summary 1~120")
    if not _int(issue.get("read_minutes"), 1, 15):
        e.append("read_minutes 1~15")

    items = issue.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= config.MAX_ITEMS:
        e.append("items 1~12")
        items = items if isinstance(items, list) else []
    if sum(isinstance(i, dict) and i.get("section") == "trend" for i in items) > config.MAX_TREND:
        e.append("trend <= 8")
    if sum(isinstance(i, dict) and i.get("section") == "issue" for i in items) > config.MAX_ISSUE:
        e.append("issue <= 4")
    ids, urls = set(), set()
    for n, it in enumerate(items):
        e += [f"items[{n}] {m}" for m in _item_errors(it)]
        if isinstance(it, dict):
            if it.get("id") in ids:
                e.append(f"items[{n}] duplicate id")
            ids.add(it.get("id"))
            key = normalize_url(it["url"]) if isinstance(it.get("url"), str) else None
            if key in urls:
                e.append(f"items[{n}] duplicate url")
            urls.add(key)

    if "study" not in issue:
        e.append("study is required (null if none)")
    elif issue["study"] is not None:
        e += [f"study {m}" for m in _study_errors(issue["study"], others)]
    return [f"{tag}: {m}" for m in e]


def _item_errors(it) -> list[str]:
    if not isinstance(it, dict):
        return ["must be object"]
    e = []
    code = SOURCES.get(it.get("source"))
    if code is None:
        e.append("source")
    if not (isinstance(it.get("id"), str) and code and it["id"].startswith(code + ":") and len(it["id"]) > len(code) + 1):
        e.append("id must be <code>:<id>")
    if it.get("section") not in SECTIONS:
        e.append("section")
    if it.get("topic") not in TOPICS:
        e.append("topic")
    if not _time(it.get("published_at")):
        e.append("published_at")
    if not _str(it.get("title"), 1, 100):
        e.append("title 1~100")
    if not _str(it.get("summary"), 1, config.SUMMARY_MAX_CHARS):
        e.append("summary 1~200")
    if not _https(it.get("url")):
        e.append("url must be https")
    if not _int(it.get("score"), 0):
        e.append("score >= 0")
    r = it.get("reactions")
    if not _str(r, 0, 30) or (it.get("score") == 0 and r != ""):
        e.append("reactions 0~30, empty when score 0")
    if not _int(it.get("importance"), 1, 5):
        e.append("importance 1~5")
    return e


def _study_errors(s, others: list[dict]) -> list[str]:
    if not isinstance(s, dict):
        return ["must be object or null"]
    e = []
    slug = s.get("slug")
    if not (isinstance(slug, str) and SLUG.match(slug) and len(slug) <= 60):
        e.append("slug format")
    elif any((h.get("study") or {}).get("slug") == slug for h in others):
        e.append(f"slug {slug} already used")
    if not _str(s.get("title"), 1, 40):
        e.append("title 1~40")
    if not _str(s.get("summary"), 1, 80):
        e.append("summary 1~80")
    if not _int(s.get("read_minutes"), 1, 10):
        e.append("read_minutes 1~10")
    pts = s.get("points")
    if not (isinstance(pts, list) and len(pts) == 3 and all(_str(p, 1, 60) for p in pts)):
        e.append("points exactly 3, each 1~60")
    secs = s.get("sections")
    total = 0
    if not (isinstance(secs, list) and 2 <= len(secs) <= 4):
        e.append("sections 2~4")
        secs = secs if isinstance(secs, list) else []
    for sec in secs:
        paras = sec.get("paragraphs") if isinstance(sec, dict) else None
        if not (isinstance(sec, dict) and _str(sec.get("heading"), 1, 30) and isinstance(paras, list) and paras
                and all(isinstance(p, str) for p in paras) and isinstance(sec.get("code", ""), str)):
            e.append("section heading 1~30, paragraphs 1+")
            continue
        total += sum(len(p) for p in paras)
    if not config.STUDY_BODY_MIN <= total <= config.STUDY_BODY_MAX:
        e.append(f"body {total} chars, must be 600~1500")
    refs = s.get("references")
    if not (isinstance(refs, list) and refs and all(isinstance(r, dict) and _str(r.get("title"), 1, 100) and _https(r.get("url")) for r in refs)):
        e.append("references 1+, each title 1~100 and https url")
        refs = []
    w = s.get("wikipedia")
    if not (isinstance(w, dict) and w.get("lang") in ("ko", "en") and isinstance(w.get("title"), str) and _https(w.get("url"))):
        e.append("wikipedia lang/title/url")
    elif not refs or refs[0].get("url") != w["url"]:
        e.append("first reference must be the wikipedia page")
    return e
