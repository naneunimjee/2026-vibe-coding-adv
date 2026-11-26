"""Gemini 호출 하나의 공통 처리 (상세 설계 5.7). 다른 모듈은 google.genai를 직접 쓰지 않는다."""
from __future__ import annotations

import json

from google import genai
from google.genai import errors, types

from newsletter import RunLog, config

REFUSED = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"}

_client: genai.Client | None = None


class LlmError(Exception):
    """SDK가 재시도한 뒤에도 API 오류가 난 경우."""


class LlmUnavailable(Exception):
    """한 단계의 모든 호출이 LlmError로 실패한 경우 (종료 코드 4)."""


def init(api_key: str) -> None:
    global _client
    # retry_options가 없으면 SDK는 재시도하지 않는다. 비워 두면 5회, 408·429·5xx.
    _client = genai.Client(api_key=api_key, http_options=types.HttpOptions(retry_options=types.HttpRetryOptions()))


def call_json(system: str, user: str, schema: dict, effort: str, log: RunLog, target: str) -> dict | None:
    """구조화 출력으로 dict를 받는다. 거절·형식 오류는 기록하고 None. API 오류는 LlmError."""
    try:
        resp = _client.models.generate_content(
            model=config.MODEL,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_json_schema=schema,
                thinking_config=types.ThinkingConfig(thinking_level=effort),
                max_output_tokens=16000,
            ),
        )
    except errors.APIError as e:
        raise LlmError(f"{e.code} {e.status}") from e

    feedback = resp.prompt_feedback
    finish = resp.candidates[0].finish_reason if resp.candidates else None
    finish_name = getattr(finish, "name", str(finish))
    if (feedback and feedback.block_reason) or finish_name in REFUSED:
        log.add("LLM_REFUSED", target, finish_name)
        return None
    try:
        data = json.loads(resp.text or "")
    except ValueError:
        data = None
    if finish_name == "MAX_TOKENS" or not isinstance(data, dict):
        log.add("LLM_INVALID_OUTPUT", target, f"finish={finish_name}")
        return None
    return data
