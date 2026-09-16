"""D 문서 출력기 점검 — LLM 없이 Mock으로 MD/DOCX를 실제로 만들어 확인한다.

실행(프로젝트 최상위, backend/가 보이는 폴더에서):
    python -m scripts.test_document

정상 결과:
    - private_runs/day2/mock_output/회사소개서_초안.md 생성
    - private_runs/day2/mock_output/회사소개서_초안.docx 생성 (python-docx 있을 때)
    - 아래 작은 실패 사례가 모두 '기대한 오류'로 걸림(05_D 시험 목록: 없는 fact_id·상충 참조·
      빈 fact_ids 임의 문장은 test_validators가, 여기서는 형식·본문·저장 실패를 담당)
파일을 직접 열어 한글·본문·확인 질문·근거가 맞는지 눈으로 확인한 뒤 C에게 함수·실행법을 전달한다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.document_generator import DocumentRenderError, render_document  # noqa: E402

OUTPUT_DIR = ROOT / "private_runs" / "day2" / "mock_output"
MOCK_PROFILE = ROOT / "fixtures" / "mock_profile.json"


def _load_mock() -> dict:
    return json.loads(MOCK_PROFILE.read_text(encoding="utf-8"))


def _expect_error(label: str, func, code: str | None = None) -> bool:
    """func가 DocumentRenderError를 내면 통과. code를 주면 오류 코드까지 일치해야 통과."""
    try:
        func()
    except DocumentRenderError as exc:
        if code is not None and exc.code != code:
            print(f"  실패 {label} -> 오류 코드가 {code}가 아니라 {exc.code}")
            return False
        print(f"  OK  {label} -> 기대한 오류: {exc.code}")
        return True
    print(f"  실패 {label} -> 오류가 나야 하는데 통과함")
    return False


def main() -> int:
    profile = _load_mock()

    print("[1] 정상 Mock으로 MD/DOCX 생성")
    md_path = render_document(profile, OUTPUT_DIR, format="md")
    print(f"  OK  MD  -> {md_path}")
    try:
        docx_path = render_document(profile, OUTPUT_DIR, format="docx")
        print(f"  OK  DOCX-> {docx_path}")
    except DocumentRenderError as exc:
        print(f"  주의 DOCX 미생성: {exc}")

    print("[2] 걸러야 하는 작은 사례")
    passed = True
    passed &= _expect_error("지원하지 않는 형식(pdf)", lambda: render_document(profile, OUTPUT_DIR, format="pdf"),
                            code="unsupported_format")
    passed &= _expect_error("draft_sections 없음", lambda: render_document({"draft_sections": []}, OUTPUT_DIR, "md"),
                            code="bad_profile")
    passed &= _expect_error("본문 text 비어 있음", lambda: render_document(
        {"draft_sections": [{"title": "t", "paragraphs": [{"text": ""}]}], "sources": [], "company_info": {}},
        OUTPUT_DIR, "md",
    ), code="bad_profile")
    passed &= _expect_error("profile이 dict 아님", lambda: render_document("not a dict", OUTPUT_DIR, "md"),
                            code="bad_profile")

    # 저장 불가 폴더: 일반 '파일' 아래 경로를 출력 폴더로 주면 폴더를 만들 수 없다(mkdir 실패 → save_failed).
    blocker = OUTPUT_DIR.parent / "_blocker_file"
    blocker.parent.mkdir(parents=True, exist_ok=True)
    blocker.write_text("x", encoding="utf-8")
    try:
        passed &= _expect_error("저장 불가 폴더(파일 아래 경로)",
                                lambda: render_document(profile, blocker / "sub", "md"),
                                code="save_failed")
    finally:
        blocker.unlink(missing_ok=True)

    print()
    print("전체 통과" if passed else "일부 실패 — 위 로그 확인")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())