"""선정·정렬: 분류별 건수 상한 안에서 중요도 순으로 고른다 (FR-004)."""
from __future__ import annotations

from newsletter import Classified, config


def select(classified: list[Classified]) -> list[Classified]:
    """결과의 첫 항목이 주요 소식이다 (BP-RANK-008). 상한 밖은 버린다 (OVER_LIMIT은 호출한 쪽이 기록)."""
    ranked = _sorted(classified)
    trend = [c for c in ranked if c.section == "trend"][: config.MAX_TREND]  # BP-RANK-006
    issue = [c for c in ranked if c.section == "issue"][: config.MAX_ISSUE]  # BP-RANK-006
    return _sorted(trend + issue)[: config.MAX_ITEMS]


def _sorted(items: list[Classified]) -> list[Classified]:
    # BP-RANK-007: 중요도 → 반응 수 → 발행 시각, 모두 큰 값이 앞
    return sorted(items, key=lambda c: (c.importance, c.cand.score, c.cand.published_at), reverse=True)
