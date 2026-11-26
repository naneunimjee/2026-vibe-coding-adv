"""발행 작업의 환경 변수와 규칙 상수."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

VERSION = "0.1"
MODEL = "claude-opus-5-5"  # ADR-004
USER_AGENT = f"IT-Newsletter/{VERSION} (+https://github.com/naneunimjee/2026-vibe-coding-adv)"
HTTP_TIMEOUT = 20  # 초, API 설계 1.1
RETRY_DELAY = 5  # 초, API 설계 1.1
MAX_ITEMS, MAX_TREND, MAX_ISSUE = 12, 8, 4  # BP-RANK-006
RECENT_ISSUES_FOR_DEDUP = 7  # BP-RANK-002
RECENT_ISSUES_FOR_STUDY = 30  # BP-STUDY-002
SUMMARY_MAX_CHARS = 200  # BP-SUM-002
STUDY_BODY_MIN, STUDY_BODY_MAX = 600, 1500  # BP-STUDY-005
SOURCE_TEXT_MAX_CHARS = 20000  # 요약 입력 상한 (약 6천 토큰)
EXCERPT_CHARS = 1000  # 분류 입력 (ADR-005)
# 호스트별 최소 요청 간격(초). 키는 호스트 끝부분과 비교하고, 없으면 "*" 값을 쓴다.
HOST_MIN_INTERVAL = {
    "hacker-news.firebaseio.com": 0.2,
    "api.github.com": 2,
    "export.arxiv.org": 3,
    "wikipedia.org": 1,
    "*": 1,
}
DEFAULT_DATA_DIR = "data/issues"


@dataclass(frozen=True)
class Config:
    api_key: str
    data_dir: Path


def load() -> Config:
    """환경 변수를 읽는다. ANTHROPIC_API_KEY가 없으면 CONFIG_MISSING으로 종료 코드 1."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("CONFIG_MISSING: ANTHROPIC_API_KEY", file=sys.stderr)
        raise SystemExit(1)
    return Config(api_key=api_key, data_dir=Path(os.environ.get("DATA_DIR", DEFAULT_DATA_DIR)))
