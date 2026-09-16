"""Mock Agent: 실제 LLM을 호출하지 않고 동봉된 고정 Mock 결과를 반환한다.

contracts/contract.md 기준. is_mock=true인 테스트 데이터이며
실제 기업 분석 결과가 아니다. 값을 새로 쓰지 않고 fixtures 파일을 그대로 읽는다.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "mock_profile.json"
_cached: dict | None = None


def get_mock_profile() -> dict:
    """fixtures/mock_profile.json을 읽어 ProfileResult(dict)로 반환한다."""
    global _cached
    if _cached is None:
        _cached = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return copy.deepcopy(_cached)
