"""원문 텍스트 추출 점검: 본문 → og:description → description → 빈 문자열 순서."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from newsletter.extract import page_text  # noqa: E402

LONG = "이 문장은 본문 문단으로 인정받을 만큼 충분히 길게 쓴 테스트용 문장이에요. 같은 내용을 반복해요."  # 41자 이상


def page(body: str = "", head: str = "") -> str:
    return f"<html><head>{head}</head><body>{body}</body></html>"


class PageTextTest(unittest.TestCase):
    def test_body_paragraphs_returned_when_long_enough(self):
        html = page("".join(f"<p>{LONG} {i}</p>" for i in range(10)))
        text = page_text(html)
        self.assertGreaterEqual(len(text), 500)
        self.assertEqual(len(text.splitlines()), 10)

    def test_skip_tags_and_short_lines_are_dropped(self):
        noise = (
            f"<nav><p>{LONG} 메뉴</p></nav>"
            f"<footer><li>{LONG} 푸터</li></footer>"
            "<script>var x = '아주 긴 스크립트 문자열이 여기에 들어가도 본문으로 치면 안 돼요';</script>"
            "<p>짧은 버튼 문구</p>"
        )
        html = page(noise + "".join(f"<p>{LONG} {i}</p>" for i in range(10)))
        text = page_text(html)
        self.assertNotIn("메뉴", text)
        self.assertNotIn("푸터", text)
        self.assertNotIn("스크립트", text)
        self.assertNotIn("짧은 버튼", text)

    def test_nested_and_unclosed_tags_split_into_lines(self):
        html = page(f"<ul><li><p>{LONG} 하나</p></li></ul><p>{LONG} 둘<p>{LONG} 셋")
        lines = page_text(page("".join(f"<p>{LONG} {i}</p>" for i in range(8))) + html).splitlines()
        self.assertTrue(any(line.endswith("하나") for line in lines))
        self.assertTrue(any(line.endswith("둘") for line in lines))
        self.assertTrue(any(line.endswith("셋") for line in lines))

    def test_og_description_used_when_body_short(self):
        og = "출처가 제공한 요약 설명이에요. " * 5
        html = page(f"<p>{LONG}</p>", f'<meta property="og:description" content="{og}">'
                                        '<meta name="description" content="다른 설명">')
        self.assertEqual(page_text(html), og.strip())

    def test_description_used_when_og_missing(self):
        desc = "메타 설명만 있는 페이지의 설명 문장이에요. " * 4
        html = page("", f'<meta name="description" content="{desc}">')
        self.assertEqual(page_text(html), desc.strip())

    def test_short_meta_ignored(self):
        html = page("", '<meta property="og:description" content="너무 짧은 설명">')
        self.assertEqual(page_text(html), "")

    def test_empty_when_nothing_usable(self):
        self.assertEqual(page_text("<html><body><div>스크립트로 그리는 페이지</div></body></html>"), "")


if __name__ == "__main__":
    unittest.main()
