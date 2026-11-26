"""테스트용 호 데이터. 데이터 설계서 3장 규칙을 지키는 최소 예시 (링크는 example.com)."""
from __future__ import annotations

import copy


def item(id: str, section: str = "trend", topic: str = "AI", source: str = "Hacker News", score: int = 10,
         url: str | None = None, published_at: str = "2026-11-25T05:10:00+09:00") -> dict:
    return {
        "id": id,
        "section": section,
        "topic": topic,
        "source": source,
        "published_at": published_at,
        "title": f"{id} 소식 제목",
        "summary": "첫 문장이에요. 두 번째 문장이에요.",
        "url": url or f"https://example.com/{id.replace(':', '/')}",
        "score": score,
        "reactions": f"포인트 {score:,}점" if score and source == "Hacker News" else ("스타 {:,}개".format(score) if score and source == "GitHub" else ""),
        "importance": 3,
    }


def study(slug: str, title: str) -> dict:
    wiki = f"https://ko.wikipedia.org/wiki/{slug}"
    return {
        "slug": slug,
        "title": title,
        "summary": f"{title}을 짧게 정의한 문장이에요.",
        "read_minutes": 3,
        "points": ["첫 요점이에요", "두 번째 요점이에요", "세 번째 요점이에요"],
        "sections": [
            {"heading": "무엇인가요", "paragraphs": ["설명 문장이에요. " * 30]},
            {"heading": "왜 쓰나요", "paragraphs": ["이유를 설명해요. " * 35], "code": "print('hi')"},
        ],
        "references": [{"title": f"위키백과: {title}", "url": wiki}, {"title": "관련 소식", "url": "https://example.com/news"}],
        "wikipedia": {"lang": "ko", "title": title, "url": wiki},
    }


def issue(number: int, date: str, items: list[dict], study_: dict | None) -> dict:
    return {
        "schema_version": 1,
        "number": number,
        "date": date,
        "collected_at": f"{date}T08:00:00+09:00",
        "headline": "오늘은 AI 소식이 가장 많았어요",
        "highlight": "AI",
        "summary": "트렌드 2건, 이슈 1건, 오늘의 공부 1개를 골랐어요.",
        "read_minutes": 2,
        "items": items,
        "study": study_,
    }


def three_issues() -> list[dict]:
    """번호 1~3. 최신 호(3)는 공부가 없다 (BP-ERROR-004 확인용)."""
    return copy.deepcopy([
        issue(1, "2026-11-23", [item("hn:1", score=96), item("gn:1", "issue", "보안", "GeekNews", 0)], study("vector-database", "벡터 데이터베이스")),
        issue(2, "2026-11-24", [item("gh:o/r", source="GitHub", score=3120), item("hn:2", "issue", "장애")], study("canary-release", "카나리 배포")),
        issue(3, "2026-11-25", [item("hn:3", score=412, url="https://example.com/sample/open-llm-server"), item("ax:2611.00001", topic="연구", source="arXiv", score=0, published_at="2026-11-24T23:40:00+09:00")], None),
    ])
