r"""POST /api/profiles/{job_id}/document 연결 지점 확인 (서버를 따로 켜지 않고 TestClient로 검사).

D의 backend/document_generator 유무와 무관하게, 모듈 부재는 명시적으로 재현하고
**시험 전용 임시 대역**을 sys.modules에 잠깐 끼워 넣어 C의 API 쪽 처리도 확인한다.
대역은 이 파일 안에만 있고 backend/에 저장하지 않는다. 실제 문서 생성 기능(D 소유)이 아니며,
이 검사가 통과해도 문서 생성 기능이 준비되었다는 뜻이 아니다.

실행(프로젝트 루트에서):
    .\.venv\Scripts\python.exe scripts\check_document_api.py
"""
from __future__ import annotations

import os
import threading
import time
import sys
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# 이 검사는 문서 API만 본다. .env가 llm으로 바뀌어도 여기서는 mock 경로로 고정한다.
os.environ["AGENT_MODE"] = "mock"

import backend  # noqa: E402
from backend import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

FIXTURES = ROOT / "fixtures"
results: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    results.append((bool(ok), label))
    print(f"{'PASS' if ok else 'FAIL'}: {label}")


def install_stub(func) -> None:
    """시험용 대역을 backend.document_generator 자리에 임시로 올린다."""
    module = types.ModuleType("backend.document_generator")
    module.render_document = func
    sys.modules["backend.document_generator"] = module
    setattr(backend, "document_generator", module)


def remove_stub() -> None:
    sys.modules.pop("backend.document_generator", None)
    if hasattr(backend, "document_generator"):
        delattr(backend, "document_generator")


def make_ready_job(client: TestClient) -> str:
    files = [
        ("files", ("mock_source_a.txt", (FIXTURES / "mock_source_a.txt").read_bytes(), "text/plain")),
        ("files", ("mock_source_b.txt", (FIXTURES / "mock_source_b.txt").read_bytes(), "text/plain")),
    ]
    res = client.post("/api/profiles", files=files, data={"company_name_hint": "테스트 회사"})
    assert res.status_code == 202, res.text
    job_id = res.json()["job_id"]
    assert client.get(f"/api/profiles/{job_id}").json()["status"] == "ready"
    return job_id


def error_code(res) -> str | None:
    try:
        return res.json()["error"]["code"]
    except Exception:
        return None


def main_check() -> int:
    remove_stub()
    with TestClient(main.app) as client:
        job_id = make_ready_job(client)
        job_dir = main.PRIVATE_RUNS / job_id

        res = client.post("/api/profiles/없는작업/document", json={"format": "md"})
        check(res.status_code == 404 and error_code(res) == "JOB_NOT_FOUND", "없는 작업 → 404 JOB_NOT_FOUND")

        # ready가 아닌 작업: 조립 없이 상태만 만들어 확인한다.
        main._jobs["pending-job"] = {"job_id": "pending-job", "status": "analyzing", "result": None, "error": None}
        res = client.post("/api/profiles/pending-job/document", json={"format": "md"})
        check(res.status_code == 409 and error_code(res) == "DOCUMENT_FAILED", "ready 아님 → 409 DOCUMENT_FAILED")

        # 1) 실제 D 모듈이 설치되어 있어도 미연결 오류 경로를 확실히 재현한다.
        with patch.dict(sys.modules, {"backend.document_generator": None}):
            res = client.post(f"/api/profiles/{job_id}/document", json={"format": "md"})
        check(res.status_code == 409 and error_code(res) == "DOCUMENT_FAILED", "D 모듈 없음 → 409 DOCUMENT_FAILED")
        check(error_code(res) == "DOCUMENT_FAILED"
              and "아직 연결되지 않았습니다" in res.json()["error"]["message"], "안내 문구가 미연결 상태를 알린다")

        # 2) 형식 값 검사 (대역이 없어도 형식부터 막는다)
        for body, label in (({"format": "pdf"}, "미지원 형식 pdf"), ({}, "format 없음"), (None, "JSON 본문 없음")):
            res = client.post(f"/api/profiles/{job_id}/document", json=body) if body is not None else \
                client.post(f"/api/profiles/{job_id}/document")
            check(res.status_code == 409 and error_code(res) == "DOCUMENT_FAILED", f"{label} → 409 DOCUMENT_FAILED")

        # 3) 대역 성공: 실제 파일 바이트와 헤더를 확인한다.
        def render_ok(profile, output_dir, fmt):
            # 시험용 대역. 실제 문서 내용이 아니다.
            path = Path(output_dir) / f"회사소개서_초안.{fmt}"
            path.write_text("# 시험용 임시 파일(실제 문서 아님)\n", encoding="utf-8")
            return path

        install_stub(render_ok)
        res = client.post(f"/api/profiles/{job_id}/document", json={"format": "md"})
        check(res.status_code == 200, "대역 성공 → 200")
        check(res.headers.get("content-type") == "text/markdown; charset=utf-8", "Content-Type: text/markdown; charset=utf-8")
        disposition = res.headers.get("content-disposition", "")
        check("attachment" in disposition and "%ED%9A%8C%EC%82%AC" in disposition,
              "Content-Disposition: attachment + 회사소개서 파일명")
        produced_path = job_dir / "documents" / "회사소개서_초안.md"
        check(produced_path.is_file() and res.content == produced_path.read_bytes(),
              "응답이 실제 생성 파일의 바이트")
        check(produced_path.is_file(), "파일이 작업 폴더 안(documents/)에 생성됨")
        check(client.get(f"/api/profiles/{job_id}").json()["status"] == "ready", "문서 요청 후에도 ready 유지")

        # 4) 대역이 예외를 던지면 DOCUMENT_FAILED로 바꾸고 ready는 유지한다.
        def render_raises(profile, output_dir, fmt):
            raise RuntimeError("시험용 실패")

        install_stub(render_raises)
        res = client.post(f"/api/profiles/{job_id}/document", json={"format": "md"})
        check(res.status_code == 409 and error_code(res) == "DOCUMENT_FAILED", "생성 예외 → 409 DOCUMENT_FAILED")
        check("시험용 실패" not in res.text, "내부 예외 문구를 응답에 노출하지 않음")
        body = client.get(f"/api/profiles/{job_id}").json()
        check(body["status"] == "ready" and body["result"] is not None, "생성 실패 후에도 result·ready 유지")

        # 5) 작업 폴더 밖 경로 / 요청과 다른 형식은 성공으로 받지 않는다.
        outside = ROOT / "private_runs" / "시험용_폴더밖.md"

        def render_outside(profile, output_dir, fmt):
            outside.write_text("바깥 파일\n", encoding="utf-8")
            return outside

        install_stub(render_outside)
        res = client.post(f"/api/profiles/{job_id}/document", json={"format": "md"})
        check(res.status_code == 409 and error_code(res) == "DOCUMENT_FAILED", "작업 폴더 밖 경로 → 409 DOCUMENT_FAILED")
        outside.unlink(missing_ok=True)

        def render_wrong_suffix(profile, output_dir, fmt):
            path = Path(output_dir) / "회사소개서_초안.txt"
            path.write_text("형식 불일치\n", encoding="utf-8")
            return path

        install_stub(render_wrong_suffix)
        res = client.post(f"/api/profiles/{job_id}/document", json={"format": "md"})
        check(res.status_code == 409 and error_code(res) == "DOCUMENT_FAILED", "요청 형식과 다른 파일 → 409 DOCUMENT_FAILED")


        # 6) 빈 파일(0바이트)은 성공으로 내려보내지 않는다.
        def render_empty(profile, output_dir, fmt):
            path = Path(output_dir) / f"회사소개서_초안.{fmt}"
            path.write_bytes(b"")
            return path

        install_stub(render_empty)
        res = client.post(f"/api/profiles/{job_id}/document", json={"format": "md"})
        check(res.status_code == 409 and error_code(res) == "DOCUMENT_FAILED",
              "빈 파일(0바이트) → 409 DOCUMENT_FAILED")
        body = client.get(f"/api/profiles/{job_id}").json()
        check(body["status"] == "ready" and body["result"] is not None, "빈 파일 거부 후에도 result·ready 유지")

        # 7) 경로가 아닌 값을 돌려줘도 500이 아니라 공통 문서 오류로 끝난다.
        def render_not_a_path(profile, output_dir, fmt):
            return {"file": "경로가 아님"}

        install_stub(render_not_a_path)
        res = client.post(f"/api/profiles/{job_id}/document", json={"format": "md"})
        check(res.status_code == 409 and error_code(res) == "DOCUMENT_FAILED",
              "경로가 아닌 반환값 → 409 DOCUMENT_FAILED(500 아님)")

        # 8) 느린 문서 생성 중에도 상태 조회가 막히지 않는다(스레드풀 연결 확인).
        SLOW_SECONDS = 1.5

        def render_slow(profile, output_dir, fmt):
            time.sleep(SLOW_SECONDS)
            path = Path(output_dir) / f"느린_시험용.{fmt}"
            path.write_text("느린 생성 시험용 임시 파일" + chr(10), encoding="utf-8")
            return path

        install_stub(render_slow)
        slow_result: dict = {}

        def run_slow() -> None:
            started = time.monotonic()
            r = client.post(f"/api/profiles/{job_id}/document", json={"format": "md"})
            slow_result["status_code"] = r.status_code
            slow_result["elapsed"] = time.monotonic() - started

        worker = threading.Thread(target=run_slow)
        worker.start()
        time.sleep(0.3)  # 문서 생성이 진행 중인 시점에 상태를 조회한다.
        poll_started = time.monotonic()
        polled = client.get(f"/api/profiles/{job_id}").json()
        poll_elapsed = time.monotonic() - poll_started
        worker.join(timeout=SLOW_SECONDS + 10)

        check(not worker.is_alive() and slow_result.get("status_code") == 200, "느린 문서 생성 → 200")
        check(slow_result.get("elapsed", 0) >= SLOW_SECONDS, f"문서 요청이 실제로 {SLOW_SECONDS}초 걸렸다")
        check(polled["status"] == "ready", "생성 중 상태 조회가 응답함")
        check(poll_elapsed < 0.5, f"생성 중 상태 조회가 막히지 않음({poll_elapsed:.2f}초 < 0.5초)")

        remove_stub()

    passed = sum(1 for ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} PASS")
    print("NOT CHECKED: D의 실제 render_document, 실제 MD/DOCX 내용, 사람이 파일을 열어 본 확인")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main_check())
