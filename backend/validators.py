"""검증기 — D 담당. 본문과 최종 결과가 근거 규칙을 지키는지 확인하고 '오류 목록'만 돌려준다.

경계(contracts/day2_addendum.md §8):
    validate_draft(draft_sections, company_info) -> list[str]
    validate_profile_result(profile, source_units) -> list[str]

원칙
- 잘못을 자동으로 고치지 않는다. 문제를 사람이 읽을 오류 문자열로만 모아 돌려준다(통과 시 빈 목록).
- 성공 플래그(validation.*)를 여기서 만들지 않는다. 서버(main.py)가 이 목록이 비어야만 True로 바꾼다.
- A의 추출 검사(check_company_info)와 역할이 겹치지 않게 한다. 여기서는 '조립된 본문·최종 결과'의
  참조·근거 연결을 본다(모델 원응답 형식 검사는 A 몫).
- 순수 JSON 스키마 모양 검사는 C의 profile_builder.schema_errors()가 담당한다(main.py에서 별도로 부름).
  여기서는 스키마로 표현 못 하는 의미 검사(근거가 실제 원문의 그 위치에 있는지 등)를 한다.

기준 자료(계약이 정한 authority)
- 14개 필드 키: contracts/profile.schema.json
- 13개 본문 섹션의 순서·고정 안내 문구: fixtures/mock_profile.json
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
_SCHEMA = json.loads((ROOT / "contracts" / "profile.schema.json").read_text(encoding="utf-8"))
_MOCK = json.loads((ROOT / "fixtures" / "mock_profile.json").read_text(encoding="utf-8"))

# 14개 필드 키(스키마 required 순서)와, 본문이 될 수 있는 13개 섹션 키(Mock 순서, company_name 제외).
FIELD_KEYS: tuple[str, ...] = tuple(_SCHEMA["properties"]["company_info"]["required"])
SECTION_ORDER: tuple[str, ...] = tuple(s["key"] for s in _MOCK["draft_sections"])
# 근거 없는 문단에 허용되는 고정 안내 문구(Mock에서 fact_ids=[]인 문단의 text로 정의).
PLACEHOLDER_TEXTS: frozenset[str] = frozenset(
    p["text"] for s in _MOCK["draft_sections"] for p in s["paragraphs"] if not p["fact_ids"]
)

FIELD_STATUSES = {"supported", "conflict", "needs_confirmation", "not_found"}
QUESTION_STATUSES = {"conflict", "needs_confirmation", "not_found"}
FINAL_REQUIRED_KEYS = (
    "schema_version", "is_mock", "company_info", "draft_sections",
    "needs_confirmation", "sources", "validation",
)


# --------------------------------------------------------------------------
# company_info에서 사실 색인 만들기 (여러 검사에서 공통으로 씀)
# --------------------------------------------------------------------------
def _index_facts(company_info: Any, errors: list[str]) -> dict[str, str]:
    """fact_id -> 그 사실이 속한 필드의 status. 전역 fact_id 중복도 함께 잡는다."""
    status_by_fact: dict[str, str] = {}
    if not isinstance(company_info, dict):
        errors.append("company_info가 객체가 아닙니다.")
        return status_by_fact
    for key, field in company_info.items():
        if not isinstance(field, dict):
            errors.append(f"company_info.{key} 형식이 잘못되었습니다.")
            continue
        status = field.get("status")
        for fact in field.get("facts", []) or []:
            fid = fact.get("fact_id") if isinstance(fact, dict) else None
            if not fid:
                errors.append(f"company_info.{key}에 fact_id 없는 사실이 있습니다.")
                continue
            if fid in status_by_fact:
                errors.append(f"fact_id가 전역에서 중복됩니다: {fid}")
            status_by_fact[fid] = status
    return status_by_fact


# --------------------------------------------------------------------------
# ① 본문 검사
# --------------------------------------------------------------------------
def validate_draft(
    draft_sections: Any,
    company_info: Any,
    require_all_sections: bool = True,
) -> list[str]:
    """조립된 본문(draft_sections)이 근거 규칙을 지키는지 검사한다.

    require_all_sections=True(기본, C 조립 결과): 13개 본문 섹션이 Mock 순서대로 모두 있어야 한다.
    require_all_sections=False: A가 supported 부분집합만 시험할 때. 순서·누락은 보지 않는다.
    """
    errors: list[str] = []
    status_by_fact = _index_facts(company_info, errors)
    supported_ids = {fid for fid, st in status_by_fact.items() if st == "supported"}

    if not isinstance(draft_sections, list):
        errors.append("draft_sections가 배열이 아닙니다.")
        return errors

    seen_keys: list[str] = []
    for i, section in enumerate(draft_sections):
        where = f"draft_sections[{i}]"
        if not isinstance(section, dict):
            errors.append(f"{where} 형식이 잘못되었습니다.")
            continue
        key = section.get("key")
        if key not in FIELD_KEYS:
            errors.append(f"{where}: 알 수 없는 key {key!r}")
        elif key not in SECTION_ORDER:
            errors.append(f"{where}: 본문 섹션이 될 수 없는 key {key!r}(단독 섹션 금지)")
        else:
            if key in seen_keys:
                errors.append(f"{where}: key가 중복됩니다: {key}")
            seen_keys.append(key)

        if not section.get("title"):
            errors.append(f"{where}: title이 없습니다.")

        paragraphs = section.get("paragraphs")
        if not isinstance(paragraphs, list) or not paragraphs:
            errors.append(f"{where}: paragraphs가 비어 있습니다.")
            continue

        for j, para in enumerate(paragraphs):
            pw = f"{where}.paragraphs[{j}]"
            if not isinstance(para, dict):
                errors.append(f"{pw} 형식이 잘못되었습니다.")
                continue
            text = para.get("text")
            fact_ids = para.get("fact_ids")
            if not isinstance(text, str) or not text.strip():
                errors.append(f"{pw}: text가 비어 있습니다.")
            if not isinstance(fact_ids, list):
                errors.append(f"{pw}: fact_ids가 배열이 아닙니다.")
                continue
            if len(set(fact_ids)) != len(fact_ids):
                errors.append(f"{pw}: 한 문단 안에서 fact_ids가 중복됩니다.")
            if not fact_ids:
                # 근거 없는 문단은 정확히 두 고정 안내 문구 중 하나여야 한다.
                if isinstance(text, str) and text not in PLACEHOLDER_TEXTS:
                    errors.append(f"{pw}: 근거(fact_ids) 없는 문단인데 허용된 안내 문구가 아닙니다.")
            else:
                for fid in fact_ids:
                    if fid not in status_by_fact:
                        errors.append(f"{pw}: 존재하지 않는 fact_id 참조: {fid}")
                    elif fid not in supported_ids:
                        errors.append(f"{pw}: supported가 아닌 사실을 본문에 사용: {fid}")

    if require_all_sections and not errors:
        # 조립 결과는 13개 섹션이 Mock 순서와 정확히 같아야 한다(누락·순서 어긋남·추가 금지).
        if tuple(seen_keys) != SECTION_ORDER:
            errors.append(
                "본문 섹션의 구성/순서가 기준(13개)과 다릅니다. "
                f"기대={list(SECTION_ORDER)} / 실제={seen_keys}"
            )
    return errors


# --------------------------------------------------------------------------
# ② 최종 결과 검사 — 근거가 실제 원문에 있는지까지
# --------------------------------------------------------------------------
def _index_source_units(source_units: Any) -> dict[tuple[str, str], str]:
    """(source_id, locator) -> 그 위치의 원문 text. 인용이 실제로 그 자리에 있는지 볼 때 쓴다."""
    index: dict[tuple[str, str], str] = {}
    for unit in source_units or []:
        if isinstance(unit, dict) and "source_id" in unit and "locator" in unit:
            index[(unit["source_id"], unit["locator"])] = unit.get("text", "")
    return index


def validate_profile_result(profile: Any, source_units: Any) -> list[str]:
    """최종 ProfileResult가 근거 규칙을 지키는지 검사한다(스키마 모양은 profile_builder가 별도 검사).

    - 필수 키 존재, 사실/출처 ID 유일성
    - evidence.source_id가 sources 목록에 있는지
    - (source_id, locator)가 실제 추출 원문(source_units)에 있는지
    - evidence.quote가 그 위치의 원문에 실제로 들어 있는지
    - needs_confirmation 항목의 field/status/question 기본 규칙
    """
    errors: list[str] = []
    if not isinstance(profile, dict):
        return ["profile이 객체가 아닙니다."]

    for key in FINAL_REQUIRED_KEYS:
        if key not in profile:
            errors.append(f"최종 결과에 필수 키가 없습니다: {key}")

    company_info = profile.get("company_info")
    status_by_fact = _index_facts(company_info, errors)  # 전역 fact_id 중복도 여기서 잡힘

    # 출처 목록 색인
    sources = profile.get("sources")
    source_ids: set[str] = set()
    if not isinstance(sources, list) or not sources:
        errors.append("sources 목록이 비어 있습니다.")
    else:
        for s in sources:
            sid = s.get("source_id") if isinstance(s, dict) else None
            if not sid:
                errors.append("sources에 source_id 없는 항목이 있습니다.")
            elif sid in source_ids:
                errors.append(f"sources의 source_id가 중복됩니다: {sid}")
            else:
                source_ids.add(sid)

    unit_index = _index_source_units(source_units)

    # 각 사실의 evidence가 실제 원문과 연결되는지
    if isinstance(company_info, dict):
        for key, field in company_info.items():
            if not isinstance(field, dict):
                continue
            for fact in field.get("facts", []) or []:
                if not isinstance(fact, dict):
                    continue
                fid = fact.get("fact_id", "?")
                evidence = fact.get("evidence", [])
                if not evidence:
                    errors.append(f"사실 {fid}에 근거(evidence)가 없습니다.")
                for ev in evidence or []:
                    if not isinstance(ev, dict):
                        errors.append(f"사실 {fid}의 evidence 형식이 잘못되었습니다.")
                        continue
                    sid = ev.get("source_id")
                    locator = ev.get("locator")
                    quote = ev.get("quote", "")
                    if sid not in source_ids:
                        errors.append(f"사실 {fid}의 근거가 sources에 없는 자료를 가리킵니다: {sid}")
                    origin = unit_index.get((sid, locator))
                    if origin is None:
                        errors.append(f"사실 {fid}의 근거 위치가 원문에 없습니다: {sid} {locator}")
                    elif not quote or quote not in origin:
                        errors.append(f"사실 {fid}의 인용이 원문 위치와 일치하지 않습니다: {sid} {locator}")

    # needs_confirmation 기본 규칙(enum·필수는 스키마가 보지만, 빈 질문/supported 혼입을 여기서 한 번 더)
    nc = profile.get("needs_confirmation", [])
    if isinstance(nc, list):
        for i, item in enumerate(nc):
            if not isinstance(item, dict):
                errors.append(f"needs_confirmation[{i}] 형식이 잘못되었습니다.")
                continue
            if item.get("field") not in FIELD_KEYS:
                errors.append(f"needs_confirmation[{i}]: 알 수 없는 field {item.get('field')!r}")
            if item.get("status") not in QUESTION_STATUSES:
                errors.append(f"needs_confirmation[{i}]: 확인 질문에 올 수 없는 status {item.get('status')!r}")
            if not (isinstance(item.get("question"), str) and item["question"].strip()):
                errors.append(f"needs_confirmation[{i}]: question이 비어 있습니다.")
    else:
        errors.append("needs_confirmation이 배열이 아닙니다.")

    return errors


# main.py는 list(...)로 감싸 쓰므로 Iterable 반환도 안전하지만, 위 두 함수는 list를 돌려준다.
__all__ = ["validate_draft", "validate_profile_result"]
