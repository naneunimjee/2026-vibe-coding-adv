"""IT 뉴스레터 발행 작업: 소식 수집 → 거르기 → 분류·요약 → 호 파일 저장."""
from __future__ import annotations

import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
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
class Classified:
    """LLM이 분류한 후보 (상세 설계 2.1)."""

    cand: Candidate
    section: str  # "trend" | "issue" (BP-RANK-003)
    topic: str  # BP-RANK-005
    importance: int  # 1~5 (BP-RANK-007)


@dataclass
class Item:
    """저장할 소식 한 건. 원문 텍스트 필드가 없다 (BP-SRC-005). 형식은 데이터 설계서 3.2."""

    id: str
    section: str
    topic: str
    source: str
    published_at: datetime  # KST
    title: str
    summary: str
    url: str
    score: int
    reactions: str
    importance: int

    def to_json(self) -> dict:
        d = dict(self.__dict__)
        d["published_at"] = self.published_at.isoformat(timespec="seconds")
        return d


@dataclass
class RunLog:
    """실행 기록. 한 줄 형식은 `<오류 코드> <대상> <설명>` (API 설계 3.3)."""

    source_counts: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    excluded: Counter = field(default_factory=Counter)
    timings: dict[str, float] = field(default_factory=dict)  # 단계 이름 → 초
    source_seconds: dict[str, float] = field(default_factory=dict)
    llm_calls: list[dict] = field(default_factory=list)  # 호출마다 대상·시간·토큰 수

    def add(self, code: str, target: str, detail: str) -> None:
        self.errors.append(f"{code} {target} {detail}")
        self.excluded[code] += 1

    @contextmanager
    def timed(self, stage: str) -> Iterator[None]:
        """블록이 걸린 시간을 stage에 더한다. 예외가 나도 기록한다."""
        start = time.monotonic()
        try:
            yield
        finally:
            self.timings[stage] = self.timings.get(stage, 0.0) + time.monotonic() - start
