"""빌드 결과 점검: 6페이지·404가 생기고, 사이트 안 링크가 모두 실제 파일을 가리키는지 (FR-016)."""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
from newsletter import issue_store  # noqa: E402
from sample_data import three_issues  # noqa: E402

PAGES = [
    "index.html",
    "trends/index.html",
    "issues/index.html",
    "study/canary-release/index.html",
    "archive/index.html",
    "about/index.html",
    "404.html",
]


def write_issues(data_dir: Path, issues: list[dict]) -> None:
    for i in issues:
        issue_store.save(i, data_dir)


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = Path(cls.tmp.name) / "issues"
        write_issues(cls.data, three_issues())
        cls.out = Path(cls.tmp.name) / "site"
        build.build(cls.out, data_dir=cls.data, site_url="https://example.test")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_pages_exist(self):
        for page in PAGES:
            self.assertTrue((self.out / page).is_file(), page)

    def test_internal_links_resolve(self):
        for html in self.out.rglob("*.html"):
            for href in re.findall(r'(?:href|src)="(/[^"#?]*)"', html.read_text(encoding="utf-8")):
                target = self.out / href.lstrip("/")
                if href.endswith("/"):
                    target = target / "index.html"
                self.assertTrue(target.is_file(), f"{html.relative_to(self.out)} → {href}")

    def test_every_issue_and_study_has_a_page(self):
        for issue in three_issues():
            self.assertTrue((self.out / f"issue/{issue['number']}/index.html").is_file())
            if issue["study"]:
                self.assertTrue((self.out / f"study/{issue['study']['slug']}/index.html").is_file())

    def test_news_links_to_original(self):
        home = self.read("index.html")
        self.assertIn("원문 보기", home)
        self.assertIn('href="https://example.com/sample/open-llm-server"', home)
        self.assertNotIn("공유하기", home)  # ISSUE-06

    def test_bp_error_004_latest_without_study_shows_previous(self):
        home = self.read("index.html")
        self.assertIn('href="/study/canary-release/"', home)  # 최신 호(3)는 공부가 없음 → 직전 공부

    def test_time_and_reactions(self):
        home = self.read("index.html")
        self.assertIn("arXiv · 11월 24일 23:40", home)  # 호 날짜와 다른 날 (BP-TEXT-004)
        self.assertIn("Hacker News · 05:10 · 포인트 412점", home)
        self.assertNotIn("arXiv · 11월 24일 23:40 ·", home)  # 반응 없으면 생략

    def test_empty_issue_states(self):
        self.assertNotIn("오늘은 트렌드 소식이 없어요", self.read("trends/index.html"))
        self.assertNotIn("최근에 올라온 이슈가 없어요", self.read("issues/index.html"))

    def test_study_license_and_pager(self):
        page = self.read("study/canary-release/index.html")
        self.assertIn("CC BY-SA 4.0", page)
        self.assertIn("https://ko.wikipedia.org/wiki/canary-release", page)
        self.assertIn('href="/study/vector-database/"', page)  # 이전 주제만

    def test_about_notice(self):
        self.assertIn("보증하거나 운영하지 않아요", self.read("about/index.html"))

    def test_404(self):
        self.assertIn("페이지를 찾을 수 없어요", self.read("404.html"))

    def test_tokens_css_has_dark_theme(self):
        css = self.read("static/tokens.css")
        self.assertIn("--accent: var(--blue-500);", css)
        self.assertIn("prefers-color-scheme: dark", css)

    def test_feed_uses_site_url(self):
        self.assertIn("<link>https://example.test/issue/3/</link>", self.read("feed.xml"))


class BuildGuardTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.data = self.root / "issues"

    def test_invalid_issue_fails_build(self):
        issues = three_issues()
        issues[0]["items"][0]["url"] = "javascript:alert(1)"
        write_issues(self.data, issues)
        with self.assertRaises(SystemExit):
            build.build(self.root / "site", data_dir=self.data)

    def test_empty_trends_and_issues(self):
        issues = three_issues()
        for i in issues:
            for it in i["items"]:
                it["section"] = "issue" if i["number"] == 3 else "trend"
        issues[2]["items"] = issues[2]["items"][:1]
        for i in issues[:2]:
            i["summary"] = "트렌드만 있어요."
        write_issues(self.data, issues)
        build.build(self.root / "site", data_dir=self.data)
        self.assertIn("오늘은 트렌드 소식이 없어요", (self.root / "site/trends/index.html").read_text(encoding="utf-8"))
        issues[2]["items"][0]["section"] = "trend"
        write_issues(self.data, issues)
        build.build(self.root / "site", data_dir=self.data)
        self.assertIn("최근에 올라온 이슈가 없어요", (self.root / "site/issues/index.html").read_text(encoding="utf-8"))

    def test_refuses_repo_root_and_foreign_folder(self):
        write_issues(self.data, three_issues())
        with self.assertRaises(SystemExit):
            build.build(build.ROOT, data_dir=self.data)
        other = self.root / "mine"
        other.mkdir()
        (other / "notes.txt").write_text("x")
        with self.assertRaises(SystemExit):
            build.build(other, data_dir=self.data)
        self.assertTrue((other / "notes.txt").exists())

    def test_fr015_ac2_site_url_required_in_production(self):
        with mock.patch.dict(os.environ, {"SITE_URL": "http://localhost:8000"}), self.assertRaises(SystemExit):
            build.site_url_from_env(production=True)
        with mock.patch.dict(os.environ, {"SITE_URL": "https://it-newsletter.pages.dev/", "CI": ""}):
            self.assertEqual(build.site_url_from_env(production=True), "https://it-newsletter.pages.dev")


if __name__ == "__main__":
    unittest.main()
