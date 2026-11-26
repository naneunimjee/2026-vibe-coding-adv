"""요약·공부 글이 함께 쓰는 문체 검사 (BP-TEXT-001·002)."""
from __future__ import annotations

import re

BANNED = ("혁신적", "최고의", "차세대")
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")
SENTENCE_SPLIT = re.compile(r"(?<=[.?!])\s+")


def sentences(text: str) -> list[str]:
    return [s for s in SENTENCE_SPLIT.split(text.strip()) if s]


def is_haeyo(text: str) -> bool:
    """모든 문장이 '~요.' 또는 '~요?'로 끝나면 해요체로 본다."""
    parts = sentences(text)
    return bool(parts) and all(re.search(r"요[.?]$", s) for s in parts)


def has_banned(text: str) -> bool:
    return any(w in text for w in BANNED) or bool(EMOJI.search(text))
