"""IT 뉴스레터 발행 작업: 소식 수집 → 거르기 → 분류·요약 → 호 파일 저장."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from newsletter import config


@dataclass
class Candidate:
    """수집 후보. source_text는 메모리에만 두고 저장하지 않는다 (BP-SRC-005)."""

    id: str
    source: str
    title: str
    url: str
    published_at: datetime
    score: int
    source_text: str
    excerpt: str = field(init=False)

    def __post_init__(self) -> None:
        self.excerpt = self.source_text[: config.EXCERPT_CHARS]  # ADR-005


@dataclass
class RunLog:
    """실행 기록. 한 줄 형식은 `<오류 코드> <대상> <설명>` (API 설계 3.3)."""

    source_counts: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    excluded: Counter = field(default_factory=Counter)

    def add(self, code: str, target: str, detail: str) -> None:
        self.errors.append(f"{code} {target} {detail}")
        self.excluded[code] += 1
