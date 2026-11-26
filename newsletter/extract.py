"""HTML 원문 페이지에서 요약 입력으로 쓸 텍스트를 뽑는다 (CHK-04)."""
from __future__ import annotations

from html.parser import HTMLParser

SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript", "svg", "form", "button"}
TEXT_TAGS = {"p", "li", "pre", "blockquote"}
MIN_LINE_CHARS = 41  # 40자 이하 줄은 메뉴·버튼 문구로 보고 버린다
MIN_BODY_CHARS = 500
MIN_META_CHARS = 80


def page_text(html: str) -> str:
    """본문 문단 → og:description → description 순서로 찾고, 모두 부족하면 ""."""
    parser = _PageParser()
    parser.feed(html)
    parser.close()
    body = "\n".join(parser.lines)
    if len(body) >= MIN_BODY_CHARS:
        return body
    # BP-SUM-001: 본문을 못 얻으면 출처가 준 요약(메타 설명)을 쓴다
    for key in ("og:description", "description"):
        value = parser.meta.get(key, "")
        if len(value) >= MIN_META_CHARS:
            return value
    return ""  # → ORIGINAL_UNAVAILABLE


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.meta: dict[str, str] = {}
        self._skip_depth = 0
        self._text_depth = 0
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "meta":
            self._read_meta(dict(attrs))
        elif tag in SKIP_TAGS:
            self._skip_depth += 1
        elif tag in TEXT_TAGS:
            self._flush()
            self._text_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in TEXT_TAGS:
            self._flush()
            self._text_depth = max(0, self._text_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._text_depth and not self._skip_depth:
            self._buffer.append(data)

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self) -> None:
        line = " ".join("".join(self._buffer).split())
        self._buffer = []
        if len(line) >= MIN_LINE_CHARS:
            self.lines.append(line)

    def _read_meta(self, attrs: dict[str, str | None]) -> None:
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        content = (attrs.get("content") or "").strip()
        if key in ("og:description", "description") and content and key not in self.meta:
            self.meta[key] = content
