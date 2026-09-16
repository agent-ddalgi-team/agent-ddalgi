"""C 조립 모듈 — 최종 ProfileResult를 한곳에서 조립한다 (수요일 r2 제안: backend/profile_builder.py).

경계(contracts/contract.md, contracts/day2_addendum.md 기준):
- collect_supported_facts: A의 extract_company_info() 반환값에서 supported 사실만
  A의 draft_profile() 입력 모양([{"field","fact_id","text"}])으로 모은다.
- build_draft_sections: A가 반환한 supported 본문 + 고정 안내 문구로 13개 본문 섹션을
  기존 Mock(fixtures/mock_profile.json)의 순서·제목 그대로 조립한다.
- build_needs_confirmation: status != supported 항목의 확인 질문을 코드로 작성한다(LLM 재호출 없음).
  질문에는 facts에 있는 텍스트만 쓰고 없는 수치·고객명을 새로 넣지 않는다.
- build_sources: 실제 파서의 source_manifest를 sources 3개 필드로 변환한다.
- assemble_profile: 위를 묶어 공통 JSON v1.0 모양을 만든다. validation 플래그는 False로 두고,
  실제 검사(D + 스키마)를 통과한 뒤에만 서버가 True로 바꾼다.

절대 하지 않기: Mock 전체를 복사한 뒤 일부만 교체하기. supported 섹션의 생성 문단이
없으면 안내 문구로 메우지 않고 ProfileAssemblyError를 낸다.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_PATH = ROOT / "contracts" / "profile.schema.json"
_MOCK_PROFILE_PATH = ROOT / "fixtures" / "mock_profile.json"

SCHEMA_VERSION = "1.0"

# 14개 키 순서는 공통 스키마의 required 순서를 그대로 쓴다(직접 나열하지 않음).
_PROFILE_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
COMPANY_INFO_KEYS: tuple[str, ...] = tuple(_PROFILE_SCHEMA["properties"]["company_info"]["required"])

# 13개 본문 섹션의 순서·제목은 기존 Mock에서 가져와 고정한다(임의 변경 금지).
_MOCK_SECTIONS: list[dict] = json.loads(_MOCK_PROFILE_PATH.read_text(encoding="utf-8"))["draft_sections"]
SECTION_ORDER: tuple[str, ...] = tuple(s["key"] for s in _MOCK_SECTIONS)
SECTION_TITLES: dict[str, str] = {s["key"]: s["title"] for s in _MOCK_SECTIONS}
# 질문 문구에 쓰는 항목 이름. 본문 섹션이 없는 company_name만 별도로 정한다.
FIELD_TITLES: dict[str, str] = {"company_name": "회사명", **SECTION_TITLES}

NOT_FOUND_TEXT = "자료에서 확인되지 않음"
NEEDS_CONFIRMATION_TEXT = "추가 확인 필요"


class ProfileAssemblyError(Exception):
    """조립 규칙 위반. 서버(main.py)가 INVALID_OUTPUT으로 변환한다. 자동 보정하지 않는다."""


def collect_supported_facts(company_info: dict[str, Any]) -> list[dict]:
    """status=supported인 항목의 사실만 [{"field","fact_id","text"}]로 모은다(14개 키 순서).

    field는 A에게 전달하는 내부 참고 값이며 최종 fact 객체에는 넣지 않는다.
    """
    supported: list[dict] = []
    for key in COMPANY_INFO_KEYS:
        field = company_info[key]
        if field["status"] != "supported":
            continue
        for fact in field["facts"]:
            supported.append({"field": key, "fact_id": fact["fact_id"], "text": fact["text"]})
    return supported


def _supported_fact_ids(company_info: dict[str, Any]) -> set[str]:
    return {
        fact["fact_id"]
        for key in COMPANY_INFO_KEYS
        if company_info[key]["status"] == "supported"
        for fact in company_info[key]["facts"]
    }


def build_draft_sections(company_info: dict[str, Any], generated_sections: list[dict]) -> list[dict]:
    """13개 본문 섹션을 Mock 순서·제목대로 조립한다.

    - supported 항목: A(draft_profile)가 생성한 그 key의 문단을 쓴다. 없으면 오류(보충 금지).
    - conflict / needs_confirmation 항목: 고정 문구 "추가 확인 필요", fact_ids=[].
    - not_found 항목: 고정 문구 "자료에서 확인되지 않음", fact_ids=[].
    generated_sections가 비어 있어도 supported 항목이 없으면 정상 조립한다(안내 문구만).
    """
    by_key: dict[str, dict] = {}
    for section in generated_sections:
        key = section.get("key")
        if key not in SECTION_ORDER:
            raise ProfileAssemblyError(f"본문 섹션이 아닌 key가 생성 결과에 있습니다: {key!r}")
        if key in by_key:
            raise ProfileAssemblyError(f"생성 결과에 같은 key가 두 번 있습니다: {key}")
        if company_info[key]["status"] != "supported":
            raise ProfileAssemblyError(f"supported가 아닌 항목의 본문이 생성 결과에 있습니다: {key}")
        by_key[key] = section

    allowed_ids = _supported_fact_ids(company_info)
    sections: list[dict] = []
    for key in SECTION_ORDER:
        status = company_info[key]["status"]
        title = SECTION_TITLES[key]
        if status == "supported":
            generated = by_key.pop(key, None)
            if generated is None:
                # 사실이 있는데 생성 문단이 없으면 성공으로 보충하지 않고 멈춘다.
                raise ProfileAssemblyError(f"supported 항목 '{key}'의 생성 본문이 없습니다.")
            paragraphs = []
            for i, paragraph in enumerate(generated.get("paragraphs") or []):
                text = paragraph.get("text")
                fact_ids = paragraph.get("fact_ids")
                if not isinstance(text, str) or not text.strip():
                    raise ProfileAssemblyError(f"'{key}' 생성 문단 {i}의 text가 비어 있습니다.")
                if not isinstance(fact_ids, list) or not fact_ids:
                    raise ProfileAssemblyError(f"'{key}' 생성 문단 {i}에 fact_ids가 없습니다.")
                if len(set(fact_ids)) != len(fact_ids):
                    raise ProfileAssemblyError(f"'{key}' 생성 문단 {i}의 fact_ids가 중복됩니다.")
                unknown = [fid for fid in fact_ids if fid not in allowed_ids]
                if unknown:
                    raise ProfileAssemblyError(
                        f"'{key}' 생성 문단 {i}이(가) supported가 아닌 fact_id를 참조합니다: {', '.join(unknown)}"
                    )
                paragraphs.append({"text": text, "fact_ids": list(fact_ids)})
            if not paragraphs:
                raise ProfileAssemblyError(f"supported 항목 '{key}'의 생성 문단이 비어 있습니다.")
            sections.append({"key": key, "title": title, "paragraphs": paragraphs})
        elif status == "not_found":
            sections.append({"key": key, "title": title,
                             "paragraphs": [{"text": NOT_FOUND_TEXT, "fact_ids": []}]})
        else:  # conflict / needs_confirmation
            sections.append({"key": key, "title": title,
                             "paragraphs": [{"text": NEEDS_CONFIRMATION_TEXT, "fact_ids": []}]})

    if by_key:
        raise ProfileAssemblyError(f"조립에 쓰이지 않은 생성 섹션이 남았습니다: {', '.join(by_key)}")
    return sections


def build_needs_confirmation(company_info: dict[str, Any]) -> list[dict]:
    """status != supported인 14개 항목마다 코드로 확인 질문을 만든다(세 번째 LLM 호출 없음)."""
    questions: list[dict] = []
    for key in COMPANY_INFO_KEYS:
        field = company_info[key]
        status = field["status"]
        if status == "supported":
            continue
        title = FIELD_TITLES[key]
        texts = [fact["text"] for fact in field["facts"]]
        if status == "not_found":
            question = f"{title} 정보를 제공하거나 해당 사항 없음을 확인해 주세요."
        elif status == "conflict":
            question = f"자료마다 {title} 내용이 다릅니다({' / '.join(texts)}). 실제 값은 무엇인가요?"
        else:  # needs_confirmation
            question = f"{title}의 '{', '.join(texts)}' 표현에 대한 구체적인 기준과 적용 조건은 무엇인가요?"
        questions.append({"field": key, "status": status, "question": question})
    return questions


def build_sources(source_manifest: list[dict]) -> list[dict]:
    """파서의 source_manifest를 sources 3개 필드로 변환한다. 작성일을 모르면 null 유지(업로드 시각 금지)."""
    return [
        {"source_id": item["source_id"], "file_name": item["file_name"], "document_date": item["document_date"]}
        for item in source_manifest
    ]


def assemble_profile(
    company_info: dict[str, Any],
    generated_sections: list[dict],
    source_manifest: list[dict],
    is_mock: bool,
) -> dict[str, Any]:
    """공통 JSON v1.0 모양의 최종 결과를 조립한다.

    validation은 schema_valid=False, evidence_links_valid=False로 시작한다.
    실제 검사(D의 본문/최종 검사 + 스키마 검사)를 통과한 뒤에만 서버가 True로 바꾼다.
    is_mock은 '테스트 데이터 여부'를 서버 설정이 정하는 값이며 실제 LLM 호출 증거가 아니다.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "is_mock": is_mock,
        "company_info": copy.deepcopy(company_info),
        "draft_sections": build_draft_sections(company_info, generated_sections),
        "needs_confirmation": build_needs_confirmation(company_info),
        "sources": build_sources(source_manifest),
        "validation": {
            "schema_valid": False,
            "evidence_links_valid": False,
            "human_review_required": True,
        },
    }


def schema_errors(profile: dict[str, Any]) -> list[str]:
    """contracts/profile.schema.json으로 최종 결과를 검사해 오류 문자열 목록을 돌려준다(통과 시 빈 목록)."""
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(_PROFILE_SCHEMA)
    return [
        f"{'/'.join(str(p) for p in error.absolute_path) or '(root)'}: {error.message}"
        for error in validator.iter_errors(profile)
    ]
