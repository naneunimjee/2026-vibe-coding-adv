"""선정·정렬 점검: SRS FR-004 수용 기준과 BP-RANK-006~008."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from newsletter import Candidate, Classified  # noqa: E402
from newsletter.ranking import select  # noqa: E402

BASE = datetime(2026, 11, 26, tzinfo=timezone.utc)


def item(id: str, section: str = "trend", importance: int = 3, score: int = 0, hours: int = 0) -> Classified:
    c = Candidate(id=id, source="GitHub", title=id, url=f"https://example.com/{id}",
                  published_at=BASE + timedelta(hours=hours), score=score, source_text="")
    return Classified(cand=c, section=section, topic="기타", importance=importance)


def ids(items):
    return [c.cand.id for c in items]


class SelectTest(unittest.TestCase):
    def test_fr004_ac1_trend_capped_at_8(self):
        trends = [item(f"t{i}", importance=1 + i % 5, score=i) for i in range(15)]
        issues = [item("i1", "issue"), item("i2", "issue")]
        selected = select(trends + issues)
        self.assertEqual(len(selected), 10)
        self.assertEqual(sum(c.section == "trend" for c in selected), 8)
        self.assertEqual(sum(c.section == "issue" for c in selected), 2)

    def test_issue_capped_at_4_and_total_at_12(self):
        selected = select([item(f"t{i}") for i in range(10)] + [item(f"i{i}", "issue") for i in range(6)])
        self.assertEqual(len(selected), 12)
        self.assertEqual(sum(c.section == "issue" for c in selected), 4)

    def test_fr004_ac2_same_importance_higher_score_first(self):
        self.assertEqual(ids(select([item("low", score=96), item("high", score=214)])), ["high", "low"])

    def test_fr004_ac3_few_items_all_kept(self):
        self.assertEqual(len(select([item("a"), item("b", "issue"), item("c")])), 3)

    def test_sort_key_importance_then_score_then_newest(self):
        selected = select([
            item("old", importance=4, score=10, hours=0),
            item("new", importance=4, score=10, hours=5),
            item("top", "issue", importance=5, score=1),
            item("popular", importance=4, score=50),
        ])
        # BP-RANK-008: 첫 항목이 주요 소식
        self.assertEqual(ids(selected), ["top", "popular", "new", "old"])

    def test_capped_items_are_the_lowest_ranked(self):
        trends = [item(f"t{i}", importance=5 if i < 8 else 1) for i in range(10)]
        self.assertEqual(sorted(ids(select(trends))), sorted(f"t{i}" for i in range(8)))

    def test_empty(self):
        self.assertEqual(select([]), [])


if __name__ == "__main__":
    unittest.main()
