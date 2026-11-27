"""성능 기록: 단계별 시간, 호스트별 HTTP 통계, LLM 호출 시간·토큰, 실행 요약 줄."""
import io
import sys
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from newsletter import RunLog, config, http, llm, publish  # noqa: E402


class FakeResponse:
    status = 200
    headers = SimpleNamespace(get_content_charset=lambda: "utf-8", get_content_type=lambda: "text/html")

    def read(self):
        return b"ok"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class RunLogTimedTest(unittest.TestCase):
    def test_accumulates_and_records_on_error(self):
        log = RunLog()
        with mock.patch("newsletter.time.monotonic", side_effect=[0.0, 2.0, 10.0, 11.5]):
            with log.timed("collect"):
                pass
            with self.assertRaises(ValueError), log.timed("collect"):
                raise ValueError
        self.assertEqual(log.timings, {"collect": 3.5})


class HttpStatsTest(unittest.TestCase):
    def setUp(self):
        http.stats.clear()
        http._last_request_at.clear()
        self.addCleanup(http.stats.clear)
        self.addCleanup(http._last_request_at.clear)

    def test_counts_requests_and_interval_wait(self):
        with mock.patch.object(http.urllib.request, "urlopen", return_value=FakeResponse()), \
                mock.patch.object(http.time, "sleep") as sleep:
            http.get("https://export.arxiv.org/a")
            http.get("https://export.arxiv.org/b")  # arXiv는 3초 간격
        s = http.stats["export.arxiv.org"]
        self.assertEqual((s.requests, s.retries), (2, 0))
        self.assertAlmostEqual(s.waited, sleep.call_args.args[0])
        self.assertGreater(s.waited, 2.5)

    def test_retry_counts_wait(self):
        responses = [urllib.error.URLError("down"), FakeResponse()]
        with mock.patch.object(http.urllib.request, "urlopen", side_effect=responses), \
                mock.patch.object(http.time, "sleep"):
            http.get("https://example.com/x")
        s = http.stats["example.com"]
        self.assertEqual((s.requests, s.retries), (2, 1))
        self.assertGreaterEqual(s.waited, config.RETRY_DELAY)


class LlmRecordTest(unittest.TestCase):
    def call(self, resp):
        client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kw: resp))
        log = RunLog()
        with mock.patch.object(llm, "_client", client):
            llm.call_json("s", "u", {}, "low", log, "classify#1")
        return log.llm_calls

    def response(self, usage):
        cand = SimpleNamespace(finish_reason=SimpleNamespace(name="STOP"))
        return SimpleNamespace(text='{"a": 1}', candidates=[cand], prompt_feedback=None, usage_metadata=usage)

    def test_records_tokens(self):
        usage = SimpleNamespace(prompt_token_count=1200, candidates_token_count=300, thoughts_token_count=None)
        [call] = self.call(self.response(usage))
        self.assertEqual((call["target"], call["effort"], call["ok"]), ("classify#1", "low", True))
        self.assertEqual((call["in"], call["out"], call["thought"]), (1200, 300, 0))

    def test_missing_usage_is_zero(self):
        [call] = self.call(self.response(None))
        self.assertEqual((call["in"], call["out"], call["thought"]), (0, 0, 0))


class ReportTest(unittest.TestCase):
    def setUp(self):
        http.stats.clear()
        self.addCleanup(http.stats.clear)

    def test_performance_lines(self):
        log = RunLog()
        log.timings.update(collect=300.04, classify=38.2, total=412.3)
        http.stats["api.github.com"] = http.HostStats(requests=7, retries=1, seconds=4.2, waited=17.0)
        log.llm_calls += [
            {"target": "classify#1", "effort": "low", "seconds": 12.3, "ok": True, "in": 9000, "out": 800, "thought": 400},
            {"target": "hn:5", "effort": "medium", "seconds": 8.1, "ok": False, "in": 0, "out": 0, "thought": 0},
        ]
        self.assertEqual(publish.performance_lines(log), [
            "timing collect=300.0s classify=38.2s total=412.3s",
            "http api.github.com requests=7 retries=1 net=4.2s waited=17.0s",
            "llm calls=2 failed=1 seconds=20.4 tokens in=9000 out=800 thought=400 slowest=classify#1:12.3s,hn:5:8.1s",
        ])

    def test_report_prints_source_seconds(self):
        log = RunLog()
        log.source_counts["GeekNews"] = 20
        log.source_seconds["GeekNews"] = 3.21
        out = io.StringIO()
        with redirect_stdout(out):
            publish.report(log, None)
        self.assertIn("sources GeekNews=20 (3.2s)", out.getvalue())
        self.assertIn("timing ", out.getvalue())
        self.assertNotIn("llm ", out.getvalue())  # 호출이 없으면 줄을 내지 않는다


if __name__ == "__main__":
    unittest.main()
