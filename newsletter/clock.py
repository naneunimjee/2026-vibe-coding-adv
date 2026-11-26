"""한국 시간(KST) 변환과 수집 기간 계산."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
DEFAULT_WINDOW = timedelta(hours=24)  # BP-PUB-006: 직전 호가 없으면 최근 24시간


def now_kst() -> datetime:
    return datetime.now(KST)


def to_kst(dt: datetime) -> datetime:
    """UTC나 다른 시간대의 시각을 KST로 바꾼다 (BP-TEXT-004)."""
    return dt.astimezone(KST)


def collect_window(latest_issue: dict | None, now: datetime) -> tuple[datetime, datetime]:
    """BP-PUB-006: 직전 호의 수집 시작 시각부터 지금까지. 직전 호가 없으면 최근 24시간."""
    if latest_issue is None:
        return now - DEFAULT_WINDOW, now
    return datetime.fromisoformat(latest_issue["collected_at"]), now


def issue_date(now: datetime) -> date:
    """호 날짜는 KST 기준 날짜다."""
    return to_kst(now).date()
