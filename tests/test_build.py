"""빌드 결과 점검: 6페이지가 생기고, 사이트 안 링크가 모두 실제 파일을 가리키는지."""
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build  # noqa: E402

PAGES = [
    "index.html",
    "trends/index.html",
    "issues/index.html",
    "study/vector-database/index.html",
    "archive/index.html",
    "about/index.html",
]


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        build.build(cls.out, site_url="https://example.test")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_six_pages_exist(self):
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
        for issue in build.load_issues(build.ROOT / "data" / "issues"):
            self.assertTrue((self.out / f"issue/{issue['number']}/index.html").is_file())
            self.assertTrue((self.out / f"study/{issue['study']['slug']}/index.html").is_file())

    def test_news_links_to_original(self):
        home = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertIn("원문 보기", home)
        self.assertIn('href="https://example.com/sample/open-llm-server"', home)

    def test_tokens_css_has_dark_theme(self):
        css = (self.out / "static/tokens.css").read_text(encoding="utf-8")
        self.assertIn("--accent: var(--blue-500);", css)
        self.assertIn("prefers-color-scheme: dark", css)

    def test_feed_uses_site_url(self):
        feed = (self.out / "feed.xml").read_text(encoding="utf-8")
        self.assertIn("<link>https://example.test/issue/128/</link>", feed)


if __name__ == "__main__":
    unittest.main()
