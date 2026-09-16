"""C 조립 모듈(backend/profile_builder.py) 검사 — 고정 픽스처(가짜 데이터)만 사용한다.

실행(프로젝트 루트에서):
    .\\.venv\\Scripts\\python.exe scripts\\check_profile_builder.py

확인하는 것:
- supported 사실 수집 결과가 day2 전달 규격(fixtures/day2_supported_facts.json)과 일치.
- Mock company_info + day2 supported 본문 예시로 조립한 결과가 기존 Mock의 13개 섹션
  순서·제목·안내 문구와 일치하고, 공통 스키마를 통과.
- supported 본문 누락·엉뚱한 fact_id 참조 시 보충 없이 오류.
확인하지 않는 것: 실제 LLM 호출, A의 draft_profile, D의 검사·문서 생성.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import profile_builder as pb  # noqa: E402

FIXTURES = ROOT / "fixtures"
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


mock_profile = load("mock_profile.json")
company_info = mock_profile["company_info"]
manifest = mock_profile["sources"]  # source_id/file_name/document_date — 파서 manifest와 같은 키

# 1) supported 사실 수집이 day2 전달 규격과 일치하는가
expected_supported = load("day2_supported_facts.json")
actual_supported = pb.collect_supported_facts(company_info)
check("collect_supported_facts == day2_supported_facts.json", actual_supported == expected_supported,
      f"actual={json.dumps(actual_supported, ensure_ascii=False)}")

# 2) 조립 결과가 기존 Mock의 섹션 순서·제목·안내 문구와 일치하는가
generated = load("day2_draft_supported_example.json")
profile = pb.assemble_profile(company_info, generated, manifest, is_mock=True)
check("draft_sections == mock_profile의 13개 섹션", profile["draft_sections"] == mock_profile["draft_sections"])
check("sources == mock_profile.sources", profile["sources"] == mock_profile["sources"])
check("validation 플래그는 검사 전 False", profile["validation"] == {
    "schema_valid": False, "evidence_links_valid": False, "human_review_required": True})

mock_nc = [(q["field"], q["status"]) for q in mock_profile["needs_confirmation"]]
actual_nc = [(q["field"], q["status"]) for q in profile["needs_confirmation"]]
check("needs_confirmation의 field·status 목록이 Mock과 일치", actual_nc == mock_nc)
check("모든 질문이 비어 있지 않은 문장", all(
    isinstance(q["question"], str) and q["question"].strip() for q in profile["needs_confirmation"]))

check("조립 결과가 공통 스키마 통과", pb.schema_errors(profile) == [],
      "; ".join(pb.schema_errors(profile)[:3]))

# 3) supported가 하나도 없으면 LLM 없이 안내 문구만으로 조립된다
empty_info = {key: {"status": "not_found", "facts": []} for key in pb.COMPANY_INFO_KEYS}
empty_profile = pb.assemble_profile(empty_info, [], manifest, is_mock=True)
check("supported 없음: 13개 섹션 전부 고정 안내 문구",
      len(empty_profile["draft_sections"]) == 13
      and all(s["paragraphs"] == [{"text": pb.NOT_FOUND_TEXT, "fact_ids": []}]
              for s in empty_profile["draft_sections"]))
check("supported 없음: 질문 14개·스키마 통과",
      len(empty_profile["needs_confirmation"]) == 14 and pb.schema_errors(empty_profile) == [])

# 4) supported 항목의 생성 본문이 없으면 보충하지 않고 오류
try:
    pb.assemble_profile(company_info, [], manifest, is_mock=True)
    check("supported 본문 누락 시 오류", False, "오류가 나지 않음")
except pb.ProfileAssemblyError:
    check("supported 본문 누락 시 오류", True)

# 5) supported가 아닌 fact_id를 참조하면 오류
bad = copy.deepcopy(generated)
bad[0]["paragraphs"][0]["fact_ids"] = ["F999"]
try:
    pb.assemble_profile(company_info, bad, manifest, is_mock=True)
    check("모르는 fact_id 참조 시 오류", False, "오류가 나지 않음")
except pb.ProfileAssemblyError:
    check("모르는 fact_id 참조 시 오류", True)

print()
if failures:
    print(f"FAIL {len(failures)}건: {', '.join(failures)}")
    sys.exit(1)
print("profile_builder 검사 모두 PASS (가짜 픽스처 기준. 실제 LLM·D 검사와는 무관)")
