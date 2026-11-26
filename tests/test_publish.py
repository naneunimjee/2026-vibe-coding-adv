"""호 저장·검증과 발행 진입점 점검 (FR-001-AC4, FR-002-AC4, FR-007). 네트워크·Gemini는 가짜로 바꾼다."""
import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from newsletter import Candidate, classify, clock, issue_store, llm, publish, summarize  # noqa: E402
from newsletter import study as study_mod  # noqa: E402
from sample_data import issue, item, study, three_issues  # noqa: E402


class ValidateTest(unittest.TestCase):
    def test_samples_are_valid(self):
        history = []
        for i in three_issues():
            self.assertEqual(issue_store.validate(i, history), [])
            history.append(i)

    def test_fr007_ac4_javascript_link_fails(self):
        bad = three_issues()[0]
        bad["items"][0]["url"] = "javascript:alert(1)"
        self.assertTrue(any("url must be https" in e for e in issue_store.validate(bad, [])))

    def test_duplicates_against_history(self):
        a, b, _ = three_issues()
        b["number"] = 1
        b["study"]["slug"] = "vector-database"
        errors = issue_store.validate(b, [a])
        self.assertTrue(any("number 1 already used" in e for e in errors))
        self.assertTrue(any("slug vector-database already used" in e for e in errors))

    def test_field_rules(self):
        i = three_issues()[0]
        i["items"][1]["reactions"] = "댓글 3개"  # score 0이면 빈 문자열
        i["items"][0]["id"] = "gn:1"  # 출처 코드 불일치 + 중복 id
        i["study"]["points"] = i["study"]["points"][:2]
        i["highlight"] = "없는 말"
        errors = "\n".join(issue_store.validate(i, []))
        for expected in ("reactions", "id must be", "duplicate id", "points exactly 3", "highlight"):
            self.assertIn(expected, errors)

    def test_study_null_allowed_but_required(self):
        i = three_issues()[2]
        self.assertEqual(issue_store.validate(i, []), [])
        del i["study"]
        self.assertTrue(issue_store.validate(i, []))


class IdentityTest(unittest.TestCase):
    def test_fr007_ac1_next_number(self):
        self.assertEqual(issue_store.next_identity(three_issues(), date(2026, 11, 26)), (4, "2026-11-26"))
        self.assertEqual(issue_store.next_identity([], date(2026, 11, 26)), (1, "2026-11-26"))

    def test_fr007_ac2_same_day_same_number(self):
        self.assertEqual(issue_store.next_identity(three_issues(), date(2026, 11, 24)), (2, "2026-11-24"))

    def test_headline(self):
        items = [item("hn:1", topic="보안"), item("hn:2", topic="AI"), item("hn:3", "issue", topic="AI")]
        headline, word, summary, minutes = issue_store.build_headline(items, None)
        self.assertEqual((headline, word), ("오늘은 AI 소식이 가장 많았어요", "AI"))
        self.assertEqual(summary, "트렌드 2건, 이슈 1건, 오늘의 공부 0개를 골랐어요.")
        self.assertEqual(minutes, 1)
        # 동률이면 주요 소식(첫 항목)의 주제
        self.assertEqual(issue_store.build_headline(items[:2], None)[1], "보안")


NOW = datetime(2026, 11, 26, 8, 0, tzinfo=clock.KST)


def fake_llm(system, user, schema, effort, log, target):
    if schema is classify.SCHEMA:
        ids = [line.split('"')[1] for line in user.splitlines() if line.startswith("<candidate ")]
        return {"results": [{"id": i, "section": "trend", "topic": "AI", "importance": 3} for i in ids]}
    if schema is summarize.SCHEMA:
        return {"title": "소식 제목이에요", "summary": "첫 문장이에요. 두 번째 문장이에요."}
    if schema is study_mod.CANDIDATES_SCHEMA:
        return {"candidates": []}
    raise AssertionError(target)


class PublishTest(unittest.TestCase):
    def run_publish(self, history, cands, argv=()):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        data_dir = Path(tmp.name)
        for i in history:
            issue_store.save(i, data_dir)
        fetches = [mock.patch.object(m, "fetch", return_value=cands if n == 0 else []) for n, (_, m) in enumerate(publish.SOURCES)]
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test", "DATA_DIR": str(data_dir)}), \
                mock.patch.object(llm, "init"), mock.patch.object(llm, "call_json", side_effect=fake_llm), \
                mock.patch.object(clock, "now_kst", return_value=NOW), \
                mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            for f in fetches:
                f.start()
                self.addCleanup(f.stop)
            code = publish.main(list(argv))
        return code, data_dir

    def cand(self, id, url):
        return Candidate(id=id, source="Hacker News", title=id, url=url, published_at=NOW - timedelta(hours=1),
                         score=5, source_text="원문에만 있는 비밀 문장이에요.")

    def test_saves_issue_without_source_text(self):
        code, data_dir = self.run_publish(three_issues(), [self.cand("hn:9", "https://example.com/new")])
        self.assertEqual(code, 0)
        saved = json.loads((data_dir / "2026-11-26.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["number"], 4)
        self.assertIsNone(saved["study"])
        self.assertNotIn("원문에만 있는 비밀 문장", json.dumps(saved, ensure_ascii=False))  # FR-001-AC4

    def test_fr002_ac4_link_from_8_issues_ago_is_kept(self):
        history = []
        for n in range(1, 9):
            day = f"2026-11-{17 + n:02d}"
            history.append(issue(n, day, [item(f"hn:{n}", url=f"https://example.com/old{n}")], None))
        cands = [self.cand("hn:91", "https://example.com/old1"), self.cand("hn:92", "https://example.com/old2")]
        code, data_dir = self.run_publish(history, cands)
        self.assertEqual(code, 0)
        saved = json.loads((data_dir / "2026-11-26.json").read_text(encoding="utf-8"))
        self.assertEqual([i["id"] for i in saved["items"]], ["hn:91"])  # 8개 호 전은 남고 7개 호 전은 빠짐

    def test_fr007_ac3_no_items_exit_2_and_no_file(self):
        code, data_dir = self.run_publish(three_issues(), [])
        self.assertEqual(code, 2)
        self.assertFalse((data_dir / "2026-11-26.json").exists())

    def test_dry_run_does_not_save(self):
        code, data_dir = self.run_publish([], [self.cand("hn:9", "https://example.com/new")], ["--dry-run"])
        self.assertEqual(code, 0)
        self.assertEqual(list(data_dir.glob("*.json")), [])

    def test_config_missing_exit_1(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}), mock.patch("sys.stderr"):
            self.assertEqual(publish.main([]), 1)


if __name__ == "__main__":
    unittest.main()
