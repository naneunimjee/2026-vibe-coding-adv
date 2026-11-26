"""출처 어댑터 4개의 공통 도구. 각 모듈은 fetch(window, log) -> list[Candidate]를 갖는다."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime

from newsletter import RunLog, http

ATOM = {"a": "http://www.w3.org/2005/Atom"}
# 출처 단위로 잡는 예외 (BP-ERROR-001: 출처 하나가 실패해도 나머지는 진행)
SOURCE_ERRORS = (http.FetchError, http.BlockedError, http.ParseError, ET.ParseError, KeyError, ValueError, TypeError)


def in_window(dt: datetime, window: tuple[datetime, datetime]) -> bool:
    start, end = window
    return start <= dt < end


def parse_time(value: str) -> datetime:
    """ISO 8601 시각 (끝의 Z 포함)을 시간대 있는 datetime으로."""
    return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))


def log_failure(log: RunLog, source: str, error: Exception) -> None:
    """API 설계 6.1의 수집 오류 코드로 기록한다."""
    if isinstance(error, http.BlockedError):
        code = "SOURCE_BLOCKED"
    elif isinstance(error, http.FetchError):
        code = "SOURCE_FETCH_FAILED"
    else:
        code = "SOURCE_PARSE_FAILED"
    log.add(code, source, str(error) or type(error).__name__)
