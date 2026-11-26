"""거르기 점검: SRS FR-002 수용 기준과 링크 정규화 규칙."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from newsletter import Candidate, RunLog  # noqa: E402
from newsletter.filtering import apply, normalize_url  # noqa: E402

NOW = datetime(2026, 11, 26, tzinfo=timezone.utc)


def cand(id: str, url: str, score: int = 0) -> Candidate:
    return Candidate(id=id, source="Hacker News", title=id, url=url, published_at=NOW, score=score, source_text="")


class NormalizeUrlTest(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(normalize_url("https://Example.COM/a/?utm_source=x&utm_medium=y"), "https://example.com/a")
        self.assertEqual(normalize_url("https://example.com/a?id=3&utm_campaign=z#top"), "https://example.com/a?id=3")
        self.assertEqual(normalize_url("https://example.com/"), "https://example.com")

    def test_geeknews_feed_link_matches_clean_link(self):
        self.assertEqual(
            normalize_url("https://news.hada.io/topic?id=37886&utm_source=geeknews&utm_medium=rss"),
            normalize_url("https://news.hada.io/topic?id=37886"),
        )


class ApplyTest(unittest.TestCase):
    def test_fr002_ac1_duplicate_keeps_higher_score(self):
        log = RunLog()
        kept = apply([cand("gn:1", "https://example.com/a?utm_source=x", 30),
                      cand("hn:2", "https://example.com/a/", 412)], set(), log)
        self.assertEqual([c.id for c in kept], ["hn:2"])
        self.assertEqual(kept[0].score, 412)
        self.assertEqual(log.excluded["DUPLICATE"], 1)

    def test_fr002_ac2_http_link_excluded_and_logged(self):
        log = RunLog()
        self.assertEqual(apply([cand("hn:1", "http://example.org/post")], set(), log), [])
        self.assertEqual(log.errors, ["LINK_NOT_HTTPS hn:1 http://example.org/post"])

    def test_fr002_ac3_recently_published_excluded(self):
        log = RunLog()
        recent = {normalize_url("https://example.com/old")}
        kept = apply([cand("hn:1", "https://example.com/old/?utm_source=hn"), cand("hn:2", "https://example.com/new")],
                     recent, log)
        self.assertEqual([c.id for c in kept], ["hn:2"])
        self.assertEqual(log.excluded["RECENTLY_PUBLISHED"], 1)

    def test_order_is_kept_and_nothing_excluded_when_clean(self):
        log = RunLog()
        cands = [cand("a", "https://a.example.com"), cand("b", "https://b.example.com"), cand("c", "https://c.example.com")]
        self.assertEqual(apply(cands, set(), log), cands)
        self.assertEqual(log.errors, [])


if __name__ == "__main__":
    unittest.main()
