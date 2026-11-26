"""출처 4곳 파싱 점검: 저장해 둔 응답 예시(fixtures)만 쓰고 네트워크는 쓰지 않는다."""
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from newsletter import RunLog, http  # noqa: E402
from newsletter.sources import arxiv, geeknews, github, hackernews  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
KST = timezone(timedelta(hours=9))
WINDOW = (datetime(2026, 11, 25, 9, 0, tzinfo=KST), datetime(2026, 11, 26, 12, 0, tzinfo=KST))
ARTICLE_HTML = "<html><body>" + "<p>" + "원문 본문 문단이에요. " * 50 +"</p></body></html>"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fake_network(routes: dict):
    """URL 앞부분이 맞는 경로의 값을 돌려준다. 값이 예외면 그 예외를 던진다."""

    def find(url):
        for prefix, value in routes.items():
            if url.startswith(prefix):
                if isinstance(value, Exception):
                    raise value
                return value
        raise AssertionError(f"예상하지 못한 요청: {url}")

    def get(url, accept="*/*", headers=None):
        value = find(url)
        if isinstance(value, http.Response):
            return value
        return http.Response(200, "text/plain", value)

    def get_json(url, headers=None):
        return find(url)

    return mock.patch.multiple(http, get=get, get_json=get_json)


class GeekNewsTest(unittest.TestCase):
    def test_entries_in_window_become_candidates(self):
        log = RunLog()
        with fake_network({geeknews.FEED_URL: fixture("geeknews.xml")}):
            cands = geeknews.fetch(WINDOW, log)
        self.assertEqual([c.id for c in cands], ["gn:10002"])
        c = cands[0]
        self.assertEqual(c.source, "GeekNews")
        self.assertTrue(c.url.startswith("https://news.hada.io/topic?id=10002"))
        self.assertEqual(c.score, 0)
        self.assertEqual(c.published_at, datetime(2026, 11, 26, 8, 30, tzinfo=KST))
        self.assertEqual(c.source_text, "예시 빌드 도구가 1.0을 냈습니다. 설정 파일 없이 & 바로 실행")
        self.assertEqual(log.errors, [])

    def test_broken_feed_is_logged_and_skipped(self):
        log = RunLog()
        with fake_network({geeknews.FEED_URL: "<feed>깨진"}):
            self.assertEqual(geeknews.fetch(WINDOW, log), [])
        self.assertTrue(log.errors[0].startswith("SOURCE_PARSE_FAILED geeknews"))


class HackerNewsTest(unittest.TestCase):
    def routes(self, **overrides):
        data = json.loads(fixture("hackernews.json"))
        routes = {f"{hackernews.API}/topstories.json": data["topstories"]}
        for item_id, item in data["items"].items():
            routes[f"{hackernews.API}/item/{item_id}.json"] = item
        routes["https://blog.example.com/post"] = http.Response(200, "text/html", ARTICLE_HTML)
        routes["https://api.github.com/repos/owner/tool/readme"] = "# Tool README"
        routes.update(overrides)
        return routes

    def test_stories_in_window_become_candidates(self):
        log = RunLog()
        with fake_network(self.routes()):
            cands = {c.id: c for c in hackernews.fetch(WINDOW, log)}
        # job(4)과 수집 기간 밖(5)은 빠진다
        self.assertEqual(sorted(cands), ["hn:1", "hn:2", "hn:3", "hn:6"])
        self.assertEqual(cands["hn:1"].score, 412)
        self.assertIn("원문 본문 문단이에요.", cands["hn:1"].source_text)

    def test_text_post_uses_item_page_and_text(self):
        with fake_network(self.routes()):
            c = {c.id: c for c in hackernews.fetch(WINDOW, RunLog())}["hn:2"]
        self.assertEqual(c.url, "https://news.ycombinator.com/item?id=2")
        self.assertEqual(c.source_text, "Question & details")

    def test_github_repo_link_uses_readme_api(self):
        with fake_network(self.routes()):
            c = {c.id: c for c in hackernews.fetch(WINDOW, RunLog())}["hn:3"]
        self.assertEqual(c.source_text, "# Tool README")

    def test_http_link_is_not_requested(self):
        # fake_network에 http:// 경로가 없으므로 요청하면 AssertionError가 난다
        with fake_network(self.routes()):
            c = {c.id: c for c in hackernews.fetch(WINDOW, RunLog())}["hn:6"]
        self.assertEqual(c.source_text, "")

    def test_blocked_original_gives_empty_text(self):
        routes = self.routes(**{"https://blog.example.com/post": http.BlockedError("403")})
        with fake_network(routes):
            c = {c.id: c for c in hackernews.fetch(WINDOW, RunLog())}["hn:1"]
        self.assertEqual(c.source_text, "")

    def test_non_html_original_gives_empty_text(self):
        routes = self.routes(**{"https://blog.example.com/post": http.Response(200, "application/pdf", "%PDF")})
        with fake_network(routes):
            c = {c.id: c for c in hackernews.fetch(WINDOW, RunLog())}["hn:1"]
        self.assertEqual(c.source_text, "")

    def test_rate_limited_top_list_skips_source(self):
        log = RunLog()
        with fake_network({f"{hackernews.API}/topstories.json": http.BlockedError("429")}):
            self.assertEqual(hackernews.fetch(WINDOW, log), [])
        self.assertTrue(log.errors[0].startswith("SOURCE_BLOCKED hackernews"))


class GitHubTest(unittest.TestCase):
    def routes(self, readme=None):
        return {
            f"{github.API}/search/repositories": json.loads(fixture("github_search.json")),
            f"{github.API}/repos/owner/fast-tool/readme": readme if readme is not None else "README " * 1000,
            f"{github.API}/repos/owner/no-desc/readme": http.BlockedError("404"),
        }

    def test_repos_in_window_become_candidates(self):
        log = RunLog()
        with fake_network(self.routes()):
            cands = {c.id: c for c in github.fetch(WINDOW, log)}
        self.assertEqual(sorted(cands), ["gh:owner/fast-tool", "gh:owner/no-desc"])
        c = cands["gh:owner/fast-tool"]
        self.assertEqual(c.title, "owner/fast-tool: A fast example CLI tool")
        self.assertEqual(c.score, 3120)
        self.assertEqual(c.url, "https://github.com/owner/fast-tool")
        self.assertTrue(c.source_text.startswith("A fast example CLI tool\n\nREADME"))
        self.assertLessEqual(len(c.source_text), len("A fast example CLI tool\n\n") + 4000)
        self.assertEqual(len(c.excerpt), 1000)

    def test_missing_description_and_readme(self):
        with fake_network(self.routes()):
            c = {c.id: c for c in github.fetch(WINDOW, RunLog())}["gh:owner/no-desc"]
        self.assertEqual(c.title, "owner/no-desc")
        self.assertEqual(c.source_text, "")

    def test_search_query(self):
        query = parse_qs(urlsplit(github.search_url(WINDOW[0])).query)
        self.assertEqual(query["q"], ["created:>=2026-11-25 stars:>=50"])
        self.assertEqual(query["per_page"], ["10"])

    def test_fetch_failure_skips_source(self):
        log = RunLog()
        with fake_network({f"{github.API}/search/repositories": http.FetchError("timeout")}):
            self.assertEqual(github.fetch(WINDOW, log), [])
        self.assertTrue(log.errors[0].startswith("SOURCE_FETCH_FAILED github"))


class ArxivTest(unittest.TestCase):
    def test_entries_in_window_become_candidates(self):
        log = RunLog()
        with fake_network({arxiv.API: fixture("arxiv.xml")}):
            cands = arxiv.fetch(WINDOW, log)
        self.assertEqual([c.id for c in cands], ["ax:2611.00001"])
        c = cands[0]
        self.assertEqual(c.url, "https://arxiv.org/abs/2611.00001")
        self.assertEqual(c.title, "An Example Paper About Testing")
        self.assertEqual(c.source_text, "An Example Paper About Testing\n\nThis abstract is made up for tests.")
        self.assertEqual(c.published_at, datetime(2026, 11, 25, 23, 50, tzinfo=timezone.utc))

    def test_query_url(self):
        query = parse_qs(urlsplit(arxiv.query_url()).query)
        self.assertEqual(query["search_query"], ["cat:cs.AI OR cat:cs.CL OR cat:cs.LG OR cat:cs.SE"])
        self.assertEqual(query["sortBy"], ["submittedDate"])
        self.assertEqual(query["max_results"], ["20"])


if __name__ == "__main__":
    unittest.main()
