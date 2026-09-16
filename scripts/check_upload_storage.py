"""파일 크기 검사(조각 읽기)와 저장 실패 처리 검증 — 가짜 데이터만 사용한다.

실행(개발기준 폴더):
    python scripts/check_upload_storage.py            # HTTP 시험(서버 127.0.0.1:8000 실행 중) + 내부 시험
    python scripts/check_upload_storage.py --offline  # 서버 없이 내부 시험만

- HTTP 시험은 실행 중인 서버에 업로드하므로 private_runs/에 새 작업 폴더가 생긴다.
- 내부 시험은 TestClient와 임시 폴더를 쓰고, 저장 실패는 테스트용 예외 주입으로만 만든다
  (실제 디스크를 채우거나 폴더 권한을 바꾸지 않는다).
- 기존 handoff/api_examples.json은 건드리지 않는다. 새 응답 예시는 handoff/api_examples_upload_storage.json에 저장한다.
PASS는 출력된 항목만 검사해 통과했다는 뜻이다.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import io
import json
import os
import pathlib
import sys
import tempfile
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_backend as cb  # noqa: E402  (공통 도우미·가짜 데이터 재사용)

check, part, upload, job_error, is_error_body, is_ready_mock = (
    cb.check, cb.part, cb.upload, cb.job_error, cb.is_error_body, cb.is_ready_mock)
LIMIT = cb.MAX_FILE_BYTES
FIXTURE_PARTS = [part("mock_source_a.txt", cb.SRC_A), part("mock_source_b.txt", cb.SRC_B)]
examples: dict[str, dict] = {}


def padded(total_bytes: int) -> bytes:
    """바이트는 크지만 추출 글자 수는 작은 파일: 내용 1행 + 나머지는 빈 행."""
    head = "회사명: 크기 시험 회사\n".encode("utf-8")
    return head + b"\n" * (total_bytes - len(head))


def http_checks() -> None:
    try:
        httpx.get(f"{cb.BASE}/", timeout=3)
    except httpx.HTTPError as exc:
        check("서버 응답(127.0.0.1:8000)", False, f"연결 실패: {exc}")
        return

    exact = padded(LIMIT)
    code, body, final, _ = upload([part("exact_10mb_padded.txt", exact)])
    ext = cb.load_json(cb.job_file(body, "extraction.json")) or {}
    stored = (ext.get("stored_files") or [{}])[0]
    check("크기 정확히 10MB(10,485,760B, 추출 글자 수는 상한 이내) → 202·ready, 저장 크기·sha256 일치(자르지 않음)",
          code == 202 and is_ready_mock(final) and stored.get("size_bytes") == LIMIT
          and stored.get("sha256") == hashlib.sha256(exact).hexdigest() and ext.get("total_chars", 0) < 100,
          f"job_id={body.get('job_id')} size={stored.get('size_bytes')} total_chars={ext.get('total_chars')}")

    code, body, final, dirs = upload([part("over_10mb_padded.txt", padded(LIMIT + 1))])
    check("크기 10MB+1B → 413 INPUT_TOO_LARGE(stage queued), 작업 폴더 미생성",
          code == 413 and is_error_body(body, "INPUT_TOO_LARGE") and body["error"]["stage"] == "queued" and dirs == [],
          f"new_dirs={dirs}")

    over = padded(LIMIT + 1)
    code, body, final, dirs = upload([part("good_1.txt", cb.GOOD), part("over.txt", over), part("good_3.txt", cb.GOOD)])
    examples["HTTP 413 INPUT_TOO_LARGE (3개 중 2번째 파일 10MB 초과)"] = {
        "request": "POST /api/profiles files=good_1.txt, over.txt(10MB+1B), good_3.txt", "http_status": code, "body": body}
    check("3개 중 2번째만 10MB 초과 → 413, 작업 폴더·앞 파일 저장 안 됨",
          code == 413 and is_error_body(body, "INPUT_TOO_LARGE") and dirs == [], f"new_dirs={dirs}")
    code, body, final, dirs = upload([part("good_1.txt", cb.GOOD), part("good_2.txt", cb.GOOD), part("over.txt", over)])
    check("3개 중 마지막만 10MB 초과 → 413, 작업 폴더·앞 파일 저장 안 됨",
          code == 413 and is_error_body(body, "INPUT_TOO_LARGE") and dirs == [], f"new_dirs={dirs}")

    chars_over = "\n".join(["가" * 100] * 400).encode("utf-8") + "\n나".encode("utf-8")  # 40,001자, 약 120KB
    code, body, final, _ = upload([part("chars_40001_small_bytes.txt", chars_over)])
    check("글자 수 제한은 별도: 120KB·40,001자 → 크기 통과(202) 후 error INPUT_TOO_LARGE(stage extracting)",
          code == 202 and job_error(final, "INPUT_TOO_LARGE", "extracting"), f"job_id={body.get('job_id')}")
    code, body, final, _ = upload([part("exact_10mb_text.txt", b"a" * LIMIT)])
    check("크기 정확히 10MB지만 글자 수 초과 → 413이 아니라 202 후 error INPUT_TOO_LARGE(stage extracting)",
          code == 202 and job_error(final, "INPUT_TOO_LARGE", "extracting"), f"job_id={body.get('job_id')}")

    code, body, final, _ = upload(FIXTURE_PARTS, hint="테스트 회사")
    check("크기 초과 실패 뒤 다음 정상 업로드 → 202·ready, result == Mock",
          code == 202 and is_ready_mock(final), f"job_id={body.get('job_id')}")


class CountingBytesIO(io.BytesIO):
    def __init__(self, data: bytes):
        super().__init__(data)
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        chunk = super().read(size)
        self.bytes_read += len(chunk)
        return chunk


def inprocess_checks() -> None:
    from fastapi.testclient import TestClient
    from starlette.datastructures import UploadFile

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["FRONTEND_DIR"] = str(Path(tmp) / "no_frontend")
        import backend.main as main
        main = importlib.reload(main)
        runs = Path(tmp) / "private_runs"
        main.PRIVATE_RUNS = runs
        client = TestClient(main.app)

        # ── 조각 읽기: 요청 정보(size)를 믿지 않고 실제 바이트로 판단 ──
        exact_io = CountingBytesIO(b"a" * LIMIT)
        got = asyncio.run(main._read_limited(UploadFile(file=exact_io, size=10**9, filename="x.txt"), LIMIT))
        check("_read_limited: 실제 10MB·size 정보는 1GB로 속임 → 전부 받음",
              got is not None and len(got) == LIMIT)
        big_io = CountingBytesIO(b"a" * (LIMIT * 2 + 5))
        got = asyncio.run(main._read_limited(UploadFile(file=big_io, size=1, filename="x.txt"), LIMIT))
        check("_read_limited: 실제 20MB·size 정보는 1B로 속임 → None, 읽기를 10MB+1조각 이내에서 중단",
              got is None and big_io.bytes_read <= LIMIT + main._READ_CHUNK_BYTES,
              f"bytes_read={big_io.bytes_read:,} / 파일 {LIMIT * 2 + 5:,}")

        secret = r"C:\secret\internal\path"
        leaks = ("secret", "Errno", "OSError", tmp.replace("\\", "\\\\"), tmp)

        def no_leak(text: str) -> bool:
            return not any(s in text for s in leaks)

        def under_runs(p: pathlib.Path) -> bool:
            return str(p).startswith(str(runs))

        def job_dirs() -> list[str]:
            return sorted(p.name for p in runs.iterdir() if p.is_dir()) if runs.exists() else []

        original_mkdir, original_write_bytes, original_write_text = (
            pathlib.Path.mkdir, pathlib.Path.write_bytes, pathlib.Path.write_text)

        def run_with(patch_name: str, fake, request):
            setattr(pathlib.Path, patch_name, fake)
            try:
                return request()
            finally:
                pathlib.Path.mkdir, pathlib.Path.write_bytes, pathlib.Path.write_text = (
                    original_mkdir, original_write_bytes, original_write_text)

        def recovery(label: str) -> None:
            r = client.post("/api/profiles", files=FIXTURE_PARTS)
            g = client.get(f"/api/profiles/{r.json()['job_id']}").json() if r.status_code == 202 else {}
            check(f"{label} 뒤 다음 정상 업로드 → 202·ready, result == Mock (BUSY 해제)",
                  r.status_code == 202 and g.get("status") == "ready" and g.get("result") == cb.MOCK_PROFILE,
                  f"POST {r.status_code}")

        # ── 폴더 생성 실패(요청 접수 실패) ──────────────────────────
        def fail_mkdir(self, *args, **kwargs):
            if under_runs(self):
                raise OSError(28, "No space left on device", secret)
            return original_mkdir(self, *args, **kwargs)

        before = job_dirs()
        r = run_with("mkdir", fail_mkdir, lambda: client.post("/api/profiles", files=FIXTURE_PARTS))
        examples["HTTP 500 INVALID_OUTPUT (업로드 파일 저장 실패, 예외 주입 시험)"] = {
            "request": "POST /api/profiles files=mock_source_a.txt,mock_source_b.txt (작업 폴더 생성 실패 주입)",
            "http_status": r.status_code, "body": r.json()}
        check("폴더 생성 실패 → 500 {error} INVALID_OUTPUT(stage queued, retryable=true), 예외·경로 미노출, 폴더 없음",
              r.status_code == 500 and is_error_body(r.json(), "INVALID_OUTPUT")
              and r.json()["error"]["stage"] == "queued" and r.json()["error"]["retryable"] is True
              and no_leak(r.text) and job_dirs() == before, r.text)
        recovery("폴더 생성 실패")

        # ── 2번째 파일 쓰기 실패(부분 파일 정리) ─────────────────────
        def fail_second_write(self, data):
            if under_runs(self) and self.name == "S002.txt":
                raise OSError(28, "No space left on device", secret)
            return original_write_bytes(self, data)

        before = job_dirs()
        r = run_with("write_bytes", fail_second_write, lambda: client.post("/api/profiles", files=FIXTURE_PARTS))
        check("2번째 파일 쓰기 실패 → 500 {error} INVALID_OUTPUT, 먼저 쓴 S001 포함 작업 폴더 삭제, 예외·경로 미노출",
              r.status_code == 500 and is_error_body(r.json(), "INVALID_OUTPUT") and no_leak(r.text)
              and job_dirs() == before, f"dirs_before={len(before)} dirs_after={len(job_dirs())}")
        recovery("파일 쓰기 실패")

        # ── 작업 등록 뒤 추출 기록 쓰기 실패(작업 error 종료) ─────────
        def fail_record_write(self, *args, **kwargs):
            if under_runs(self) and self.name.startswith("agent_input.json"):
                original_write_text(self, '{"partial": ', encoding="utf-8")  # 반쯤 쓴 파일을 남긴 뒤 실패
                raise OSError(28, "No space left on device", secret)
            return original_write_text(self, *args, **kwargs)

        def post_and_get():
            resp = client.post("/api/profiles", files=FIXTURE_PARTS)
            return resp, client.get(f"/api/profiles/{resp.json()['job_id']}")

        r, g = run_with("write_text", fail_record_write, post_and_get)
        body = g.json()
        job_dir = runs / r.json()["job_id"]
        leftovers = sorted(p.name for p in job_dir.iterdir()) if job_dir.exists() else []
        examples["GET error INVALID_OUTPUT (추출 기록 저장 실패, 예외 주입 시험)"] = {
            "request": f"GET /api/profiles/{r.json()['job_id']} (agent_input.json 쓰기 실패 주입)",
            "http_status": g.status_code, "body": body}
        check("추출 기록 쓰기 실패 → POST 202, GET 200 status=error INVALID_OUTPUT(extracting), result=null, 예외·경로 미노출",
              r.status_code == 202 and g.status_code == 200 and body["status"] == "error" and body["result"] is None
              and body["error"]["code"] == "INVALID_OUTPUT" and body["error"]["stage"] == "extracting"
              and no_leak(g.text), g.text)
        check("추출 기록 쓰기 실패 → extraction.json·agent_input.json·.tmp가 남지 않고 업로드 원본 S001·S002만 유지",
              leftovers == ["S001.txt", "S002.txt"], f"leftovers={leftovers}")
        recovery("추출 기록 쓰기 실패")

    os.environ.pop("FRONTEND_DIR", None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="서버 없이 내부 시험만")
    args = ap.parse_args()
    if not args.offline:
        print("== HTTP 시험: 실행 중인 서버 http://127.0.0.1:8000 ==")
        http_checks()
    print("== 내부 시험: TestClient·임시 폴더·예외 주입 ==")
    inprocess_checks()

    out = cb.ROOT / "handoff" / "api_examples_upload_storage.json"
    out.write_text(json.dumps({
        "note": "파일 크기 초과·저장 실패 응답 예시(가짜 데이터). 500·저장 실패 예시는 임시 폴더에서 예외를 주입한 내부 시험 응답이다.",
        "generated_by": "python scripts/check_upload_storage.py",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "examples": examples,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"      (응답 예시 저장: {out.relative_to(cb.ROOT)})")

    failed = [name for name, ok in cb.results if not ok]
    print(f"\n합계: PASS {len(cb.results) - len(failed)} / FAIL {len(failed)} — 위에 출력된 항목만 검사함")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
