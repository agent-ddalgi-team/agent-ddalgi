"""draft_profile의 입력 검사·출력 검사·조립 연결을 OpenAI 호출 없이 확인한다.

정상 예시와 일부러 틀린 응답은 모두 가짜 Mock(fixtures/)에서 만든다. 파일은 저장하지 않는다.
실행(프로젝트 루트에서):
    .\\.venv\\Scripts\\python.exe scripts\\check_draft_rules.py

확인하는 것: supported_facts 입력 검사, 본문 섹션 대상 key 선정(company_name 제외),
모델용 출력 스키마, check_draft_sections의 거부 규칙, C의 build_draft_sections·D의
validate_draft와 실제로 맞물리는지.
확인하지 않는 것: 실제 LLM 호출, 문장의 의미가 근거와 맞는지(사람 검토).
"""
from __future__ import annotations
import copy
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.agent import (  # noqa: E402
    AgentError, AgentInputError, PLACEHOLDER_TEXTS, SECTION_ORDER, SECTION_TITLES,
    build_draft_output_schema, check_draft_sections, check_supported_facts, draft_section_keys,
)

failures: list[str] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'OK ' if condition else 'FAIL'}  {name}{f': {detail}' if detail else ''}")
    if not condition:
        failures.append(name)


def rejects(name: str, func, expected_rule: str) -> None:
    """func가 expected_rule로 거부하는지 본다. 통과해 버리면 실패로 센다."""
    try:
        func()
    except AgentError as exc:
        detail = json.dumps(exc.details, ensure_ascii=False)
        ok(name, exc.code == "INVALID_OUTPUT" and exc.rule == expected_rule,
           f"{exc.code} [{exc.rule}] {detail}")
        return
    except AgentInputError as exc:
        ok(name, exc.rule == expected_rule, f"[{exc.rule}] {exc.message}")
        return
    ok(name, False, "거부하지 않고 통과했다")


def main() -> int:
    mock = json.loads((ROOT / "fixtures/mock_profile.json").read_text(encoding="utf-8"))
    facts = json.loads((ROOT / "fixtures/day2_supported_facts.json").read_text(encoding="utf-8"))
    good = json.loads((ROOT / "fixtures/day2_draft_supported_example.json").read_text(encoding="utf-8"))
    keys = draft_section_keys(facts)

    print("== 1) 입력(supported_facts) 검사 ==")
    check_supported_facts(facts)
    ok("C의 실제 입력 예시를 통과시킨다", True, f"{len(facts)}건")
    check_supported_facts([])
    ok("빈 목록도 형식 오류가 아니다", True)
    rejects("배열이 아니면 거부", lambda: check_supported_facts({}), "supported_facts_type")
    rejects("키가 다르면 거부", lambda: check_supported_facts([{"field": "technology"}]),
            "supported_fact_shape")
    rejects("빈 문자열 거부",
            lambda: check_supported_facts([{"field": "technology", "fact_id": "F001", "text": " "}]),
            "supported_fact_field")
    rejects("company_info 항목이 아닌 field 거부",
            lambda: check_supported_facts([{"field": "없는항목", "fact_id": "F001", "text": "x"}]),
            "supported_fact_field_name")
    rejects("fact_id 중복 거부", lambda: check_supported_facts(
        [{"field": "technology", "fact_id": "F001", "text": "x"},
         {"field": "strengths", "fact_id": "F001", "text": "y"}]), "supported_fact_duplicate")

    print("\n== 2) 본문 섹션 대상 key ==")
    ok("company_name은 본문 섹션에서 제외", "company_name" not in keys, str(keys))
    ok("13개 섹션 순서를 따른다",
       list(keys) == [k for k in SECTION_ORDER if k in keys])
    ok("company_name만 supported면 빈 튜플",
       draft_section_keys([{"field": "company_name", "fact_id": "F001", "text": "x"}]) == ())

    print("\n== 3) 모델용 출력 스키마 ==")
    schema = build_draft_output_schema(keys)
    Draft202012Validator.check_schema(schema)
    ok("JSON Schema 문법 통과", True)
    ok("최상위가 object(strict 요구)", schema["type"] == "object")
    ok("key enum이 이번 섹션으로 한정",
       schema["$defs"]["draft_section"]["properties"]["key"]["enum"] == list(keys))
    dumped = json.dumps(schema)
    ok("strict가 받지 않는 키워드 제외", not any(w in dumped for w in ("minItems", "minLength", "allOf")))
    validator = Draft202012Validator(schema)
    ok("정상 예시가 모델용 스키마를 통과", not list(validator.iter_errors({"draft_sections": good})))

    print("\n== 4) 출력 검사(check_draft_sections) — 정상 ==")
    check_draft_sections(good, facts, keys)
    ok("C의 실제 출력 예시를 통과시킨다", True, f"{len(good)}개 섹션")
    ok("다른 섹션의 사실 참조 허용(F001을 company_summary에서 사용)",
       "F001" in good[0]["paragraphs"][0]["fact_ids"])

    print("\n== 5) 출력 검사 — 일부러 틀린 응답 거부 ==")

    def broken(mutate):
        data = copy.deepcopy(good)
        mutate(data)
        return lambda: check_draft_sections(data, facts, keys)

    rejects("배열이 아님", lambda: check_draft_sections({}, facts, keys), "draft_not_array")
    rejects("섹션에 title 없음", broken(lambda d: d[0].pop("title")), "section_shape")
    rejects("섹션에 없는 키 추가", broken(lambda d: d[0].update(extra=1)), "section_shape")
    rejects("문단 키가 다름", broken(lambda d: d[0]["paragraphs"][0].pop("fact_ids")), "paragraph_shape")
    rejects("섹션 누락", broken(lambda d: d.pop()), "section_keys")
    rejects("섹션 중복", broken(lambda d: d.append(copy.deepcopy(d[0]))), "section_keys")
    rejects("만들면 안 되는 key 생성",
            broken(lambda d: d[0].__setitem__("key", "technology")), "section_keys")
    rejects("company_name 단독 섹션 생성",
            broken(lambda d: d[0].__setitem__("key", "company_name")), "section_keys")
    rejects("제목이 공통 기준과 다름",
            broken(lambda d: d[0].__setitem__("title", "내 마음대로 제목")), "section_title")
    rejects("문단 없음", broken(lambda d: d[0].__setitem__("paragraphs", [])), "section_empty")
    rejects("text 빈 문자열",
            broken(lambda d: d[0]["paragraphs"][0].__setitem__("text", "   ")), "empty_value")
    rejects("서버 안내 문구를 본문으로 생성",
            broken(lambda d: d[0]["paragraphs"][0].__setitem__("text", "자료에서 확인되지 않음")),
            "placeholder_text")
    rejects("상충 항목 안내 문구를 본문으로 생성",
            broken(lambda d: d[0]["paragraphs"][0].__setitem__("text", "추가 확인 필요")),
            "placeholder_text")
    rejects("fact_ids 비어 있음",
            broken(lambda d: d[0]["paragraphs"][0].__setitem__("fact_ids", [])), "fact_ids_empty")
    rejects("fact_ids 중복",
            broken(lambda d: d[0]["paragraphs"][0].__setitem__("fact_ids", ["F001", "F001"])),
            "fact_ids_duplicate")
    rejects("없는 fact_id 참조",
            broken(lambda d: d[0]["paragraphs"][0].__setitem__("fact_ids", ["F999"])),
            "fact_ids_unknown")
    rejects("supported가 아닌 사실 참조(추출 결과의 conflict fact)",
            broken(lambda d: d[0]["paragraphs"][0].__setitem__("fact_ids", ["F004"])),
            "fact_ids_unknown")

    print("\n== 6) C 조립·D 검사와의 연결 ==")
    from backend import profile_builder, validators  # noqa: E402

    company_info = mock["company_info"]
    collected = profile_builder.collect_supported_facts(company_info)
    ok("C의 collect_supported_facts 결과를 그대로 받는다",
       check_supported_facts(collected) is None, f"{len(collected)}건")
    ok("그 입력의 섹션 대상이 예시와 같다", draft_section_keys(collected) == keys)

    sections = profile_builder.build_draft_sections(company_info, copy.deepcopy(good))
    ok("C의 build_draft_sections가 13개 섹션을 만든다", len(sections) == len(SECTION_ORDER))
    errors = validators.validate_draft(sections, company_info)
    ok("D의 validate_draft 통과", not errors, str(errors))

    subset_errors = validators.validate_draft(good, company_info, require_all_sections=False)
    ok("D의 부분집합 검사도 통과", not subset_errors, str(subset_errors))

    ok("안내 문구가 C·D와 같은 값", PLACEHOLDER_TEXTS == validators.PLACEHOLDER_TEXTS,
       str(sorted(PLACEHOLDER_TEXTS)))
    ok("섹션 제목이 C와 같은 값", SECTION_TITLES == profile_builder.SECTION_TITLES)

    print()
    if failures:
        print(f"FAIL {len(failures)}건: {', '.join(failures)}")
        return 1
    print("ALL OK")
    print("NOT CHECKED: 실제 LLM 호출, 문장의 의미가 근거와 맞는지(사람 검토 필요)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
