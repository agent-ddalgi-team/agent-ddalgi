"""D 검사기 점검 — 가짜 픽스처로 정상/실패 사례를 확인한다.

실행(프로젝트 최상위):
    python -m scripts.test_validators

정상 결과: 정상 조립 결과는 오류 0개, 아래 고장 낸 사례들은 각각 기대한 오류가 잡힘 → '전체 통과'.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import parsers, profile_builder, validators  # noqa: E402

FIX = ROOT / "fixtures"
results: list[bool] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail and not ok else ""))


def load(name: str):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def build_source_units() -> list[dict]:
    stored = [
        {"source_id": "S001", "stored_path": FIX / "mock_source_a.txt", "display_name": "mock_source_a.txt"},
        {"source_id": "S002", "stored_path": FIX / "mock_source_b.txt", "display_name": "mock_source_b.txt"},
    ]
    units, _manifest, _warn = parsers.extract_sources(stored)
    return units


def main() -> int:
    mock = load("mock_profile.json")
    company_info = mock["company_info"]
    manifest = mock["sources"]
    generated = load("day2_draft_supported_example.json")
    source_units = build_source_units()

    # 정상 조립 결과
    profile = profile_builder.assemble_profile(company_info, generated, manifest, is_mock=True)

    print("[A] 정상 결과 — 오류 0개여야 함")
    d_errors = validators.validate_draft(profile["draft_sections"], company_info)
    check("validate_draft 통과", d_errors == [], f"errors={d_errors}")
    p_errors = validators.validate_profile_result(profile, source_units)
    check("validate_profile_result 통과", p_errors == [], f"errors={p_errors}")

    print("[B] validate_draft가 잡아야 할 것")
    # 1) 없는 fact_id 참조
    bad = copy.deepcopy(profile)
    bad["draft_sections"][0]["paragraphs"][0]["fact_ids"] = ["F999"]
    check("없는 fact_id 참조 → 오류", validators.validate_draft(bad["draft_sections"], company_info) != [])
    # 2) supported 아닌 사실 참조 (F004는 conflict 상태)
    bad = copy.deepcopy(profile)
    bad["draft_sections"][0]["paragraphs"][0]["fact_ids"] = ["F004"]
    check("supported 아닌 사실 참조 → 오류", validators.validate_draft(bad["draft_sections"], company_info) != [])
    # 3) 근거 없는데 안내 문구 아님
    bad = copy.deepcopy(profile)
    for sec in bad["draft_sections"]:
        if sec["paragraphs"][0]["fact_ids"] == []:
            sec["paragraphs"][0]["text"] = "근거 없이 지어낸 문장"
            break
    check("근거 없는 임의 문장 → 오류", validators.validate_draft(bad["draft_sections"], company_info) != [])
    # 4) 섹션 하나 누락 → 순서/구성 오류
    bad = copy.deepcopy(profile)
    bad["draft_sections"] = bad["draft_sections"][:-1]
    check("섹션 누락(12개) → 오류", validators.validate_draft(bad["draft_sections"], company_info) != [])
    # 5) 부분집합 모드에서는 누락을 문제 삼지 않음
    subset = [s for s in profile["draft_sections"] if s["key"] in ("company_summary", "business_areas")]
    check("부분집합 모드(require_all_sections=False) 통과",
          validators.validate_draft(subset, company_info, require_all_sections=False) == [])
    # 6) 전역 fact_id 중복
    dup_info = copy.deepcopy(company_info)
    dup_info["business_areas"]["facts"][0]["fact_id"] = "F001"  # company_name과 충돌
    check("전역 fact_id 중복 → 오류", validators.validate_draft(profile["draft_sections"], dup_info) != [])

    print("[C] validate_profile_result가 잡아야 할 것")
    # 7) 인용이 원문과 다름
    bad = copy.deepcopy(profile)
    bad["company_info"]["company_name"]["facts"][0]["evidence"][0]["quote"] = "원문에 없는 인용"
    check("원문에 없는 인용 → 오류", validators.validate_profile_result(bad, source_units) != [])
    # 8) 근거 위치가 원문에 없음
    bad = copy.deepcopy(profile)
    bad["company_info"]["company_name"]["facts"][0]["evidence"][0]["locator"] = "999행"
    check("없는 근거 위치 → 오류", validators.validate_profile_result(bad, source_units) != [])
    # 9) sources에 없는 자료를 근거가 가리킴
    bad = copy.deepcopy(profile)
    bad["company_info"]["company_name"]["facts"][0]["evidence"][0]["source_id"] = "S999"
    check("sources 밖 자료 참조 → 오류", validators.validate_profile_result(bad, source_units) != [])
    # 10) source_units가 비면 근거 위치를 확인할 수 없음 → 오류
    check("source_units 없음 → 오류", validators.validate_profile_result(profile, []) != [])

    print()
    ok = all(results)
    print("전체 통과" if ok else f"실패 {results.count(False)}건")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
