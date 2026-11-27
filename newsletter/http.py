"""모든 외부 HTTP 요청의 공통 규칙: https만, 호스트별 간격, 1회 재시도 (ADR-006)."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from newsletter import config

BLOCKED_STATUSES = {403, 404, 429}


class FetchError(Exception):
    """연결 실패, 시간 초과, 서버 오류가 재시도 후에도 계속될 때."""


class BlockedError(Exception):
    """403·404·429: 재시도해도 소용없는 거절."""


class ParseError(Exception):
    """응답을 기대한 형식으로 읽을 수 없을 때."""


@dataclass
class Response:
    status: int
    content_type: str
    text: str


@dataclass
class HostStats:
    """호스트별 성능 기록. 네트워크 시간과 규칙 때문에 기다린 시간을 나눠 센다."""

    requests: int = 0
    retries: int = 0
    seconds: float = 0.0  # 요청을 보내고 응답을 다 받기까지
    waited: float = 0.0  # 호스트 간격(HOST_MIN_INTERVAL)과 재시도 대기


_last_request_at: dict[str, float] = {}
stats: dict[str, HostStats] = {}


def get(url: str, accept: str = "*/*", headers: dict[str, str] | None = None) -> Response:
    if not url.startswith("https://"):
        raise ValueError(f"https 주소만 요청할 수 있어요: {url}")
    host = urlsplit(url).hostname or ""
    request_headers = {"User-Agent": config.USER_AGENT, "Accept": accept, **(headers or {})}
    try:
        return _request(url, host, request_headers)
    except FetchError:
        s = stats.setdefault(host, HostStats())
        s.retries += 1
        s.waited += config.RETRY_DELAY
        time.sleep(config.RETRY_DELAY)
        return _request(url, host, request_headers)


def get_json(url: str, headers: dict[str, str] | None = None) -> Any:
    response = get(url, accept="application/json", headers=headers)
    try:
        return json.loads(response.text)
    except json.JSONDecodeError as e:
        raise ParseError(f"JSON이 아니에요: {url}") from e


def _request(url: str, host: str, headers: dict[str, str]) -> Response:
    s = stats.setdefault(host, HostStats())
    s.waited += _wait_for_host(host)
    s.requests += 1
    start = time.monotonic()
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=config.HTTP_TIMEOUT) as resp:
            body = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return Response(
                status=resp.status,
                content_type=resp.headers.get_content_type(),
                text=body.decode(charset, errors="replace"),
            )
    except urllib.error.HTTPError as e:
        if e.code in BLOCKED_STATUSES:
            raise BlockedError(f"{e.code}: {url}") from e
        raise FetchError(f"{e.code}: {url}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        # SSL 인증서 오류도 URLError로 오며 재시도 대상이다 (상세 설계 5.3, 부록 D CHK-02)
        raise FetchError(f"{type(e).__name__}: {url}") from e
    finally:
        _last_request_at[host] = time.monotonic()
        s.seconds += _last_request_at[host] - start


def _wait_for_host(host: str) -> float:
    """같은 호스트의 직전 요청과 간격을 맞춘다. 기다린 초를 돌려준다."""
    last = _last_request_at.get(host)
    if last is None:
        return 0.0
    remaining = _min_interval(host) - (time.monotonic() - last)
    if remaining > 0:
        time.sleep(remaining)
        return remaining
    return 0.0


def _min_interval(host: str) -> float:
    for key, seconds in config.HOST_MIN_INTERVAL.items():
        if key != "*" and (host == key or host.endswith("." + key)):
            return seconds
    return config.HOST_MIN_INTERVAL["*"]
