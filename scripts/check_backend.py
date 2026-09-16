"""C 백엔드 첫날 검증 — 가짜 데이터만 사용한다.

실행(개발기준 폴더):
    python scripts/check_backend.py            # HTTP 시험(서버 127.0.0.1:8000 실행 중) + 프로세스 내부 시험
    python scripts/check_backend.py --offline  # 서버 없이 프로세스 내부 시험만

PASS는 출력된 각 항목을 실제로 검사해 통과했다는 뜻뿐이다.
검사하지 않는 것: 실제 기업 자료·결과 내용의 사실성, 실제 Agent/LLM, PDF/DOCX, 문서 생성, B 화면 표시.
HTTP 시험은 실제 응답을 handoff/api_examples.json에 저장한다(B 전달용 예시).
시험 중 만든 작업 폴더는 private_runs/ 아래에 남는다(가짜 데이터).
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib
import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIX = ROOT / "fixtures"
RUNS = ROOT / "private_runs"
BASE = "http://127.0.0.1:8000"
MAX_FILE_BYTES = 10 * 1024 * 1024

MOCK_PROFILE = json.loads((FIX / "mock_profile.json").read_text(encoding="utf-8"))
MOCK_AGENT_INPUT = json.loads((FIX / "agent_input_mock.json").read_text(encoding="utf-8"))
SRC_A = (FIX / "mock_source_a.txt").read_bytes()
SRC_B = (FIX / "mock_source_b.txt").read_bytes()
GOOD = "회사명: 정상 시험 회사\n공정 수: 1개\n".encode("utf-8")
CP949 = "회사명: 인코딩 시험 회사\n".encode("cp949")

ENVELOPE_KEYS = {"job_id", "status", "result", "error"}
ERROR_KEYS = {"code", "stage", "message", "retryable"}
AGENT_INPUT_KEYS = {"schema_version", "company_name_hint", "source_units"}

results: list[tuple[str, bool]] = []
examples: dict[str, dict] = {}


def check(name: str, ok: object, detail: str = "") -> bool:
    ok = bool(ok)
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    return ok


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def part(name: str, data: bytes, mime: str = "text/plain") -> tuple:
    return ("files", (name, data, mime))


def expected_units(source_id: str, raw: bytes) -> list[dict]:
    """파서 코드를 쓰지 않고 원본 바이트에서 기대값을 만든다(개행 통일 후 \\n 분할)."""
    text = raw.decode("utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return [
        {"source_id": source_id, "locator": f"{n}행", "text": line.strip()}
        for n, line in enumerate(lines, start=1)
        if line.strip()
    ]


def units_match(units: list[dict], raw_by_id: dict[str, bytes]) -> tuple[bool, str]:
    expected = [u for sid, raw in raw_by_id.items() for u in expected_units(sid, raw)]
    if units == expected:
        return True, f"unit {len(units)}개 일치"
    return False, f"expected={expected} actual={units}"


def run_dirs() -> set[str]:
    return {p.name for p in RUNS.iterdir()} if RUNS.exists() else set()


def poll(job_id: str, timeout: float = 30) -> tuple[int, dict]:
    deadline = time.time() + timeout
    while True:
        g = httpx.get(f"{BASE}/api/profiles/{job_id}", timeout=10)
        body = g.json()
        if g.status_code != 200 or body["status"] in ("ready", "error") or time.time() > deadline:
            return g.status_code, body
        time.sleep(0.2)


def upload(parts: list, hint: str | None = None):
    before = run_dirs()
    data = {"company_name_hint": hint} if hint is not None else None
    r = httpx.post(f"{BASE}/api/profiles", files=parts, data=data, timeout=120)
    body = r.json()
    final = poll(body["job_id"]) if r.status_code == 202 else None
    return r.status_code, body, final, sorted(run_dirs() - before)


def job_file(body: dict, name: str) -> Path:
    return RUNS / body.get("job_id", "-") / name


def load_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def is_error_body(body: dict, code: str) -> bool:
    return set(body) == {"error"} and set(body["error"]) == ERROR_KEYS and body["error"]["code"] == code


def job_error(final, code: str, stage: str) -> bool:
    if not final:
        return False
    status, body = final
    return (
        status == 200 and set(body) == ENVELOPE_KEYS and body["status"] == "error"
        and body["result"] is None and set(body["error"] or {}) == ERROR_KEYS
        and body["error"]["code"] == code and body["error"]["stage"] == stage
    )


def is_ready_mock(final) -> bool:
    return bool(final) and final[0] == 200 and final[1]["status"] == "ready" and final[1]["result"] == MOCK_PROFILE


def example(name: str, request: str, status: int, body: dict) -> None:
    examples[name] = {"request": request, "http_status": status, "body": body}


def http_checks() -> None:
    try:
        httpx.get(f"{BASE}/", timeout=3)
    except httpx.HTTPError as exc:
        check("서버 응답(127.0.0.1:8000)", False, f"연결 실패: {exc}")
        return

    # ── 시험 1·2·3: 동봉 가짜 TXT 2개 ─────────────────────────────
    code, body, final, _ = upload([part("mock_source_a.txt", SRC_A), part("mock_source_b.txt", SRC_B)],
                                  hint="테스트 회사")
    example("POST 202 정상 접수", "POST /api/profiles files=mock_source_a.txt,mock_source_b.txt company_name_hint=테스트 회사",
            code, body)
    ok_uuid = False
    try:
        ok_uuid = str(uuid.UUID(body.get("job_id", ""))) == body.get("job_id")
    except ValueError:
        pass
    check("시험1 가짜 TXT 2개 업로드 → 202, queued, result·error=null, UUID job_id",
          code == 202 and set(body) == ENVELOPE_KEYS and body["status"] == "queued"
          and body["result"] is None and body["error"] is None and ok_uuid)
    if code != 202:
        return
    first_job = body["job_id"]
    g_status, g = final
    example("GET ready (고정 Mock 결과)", f"GET /api/profiles/{first_job}", g_status, g)
    check("시험2 조회 → 200 ready, 키 4개, result == fixtures/mock_profile.json, is_mock=true",
          g_status == 200 and set(g) == ENVELOPE_KEYS and g["status"] == "ready" and g["error"] is None
          and g["result"] == MOCK_PROFILE and g["result"]["is_mock"] is True)
    check("시험3 Mock result.sources는 고정값 유지(업로드 source_manifest로 교체하지 않음)",
          g["result"] is not None and g["result"]["sources"] == MOCK_PROFILE["sources"])

    ext = load_json(job_file(body, "extraction.json"))
    ai = load_json(job_file(body, "agent_input.json"))
    if not check("시험3 추출 기록 보관: private_runs/<job_id>/extraction.json, agent_input.json",
                 ext is not None and ai is not None):
        return
    job_dir = RUNS / first_job
    stored = {s["source_id"]: s for s in ext["stored_files"]}
    check("시험3 source_id 추적: S001→mock_source_a.txt, S002→mock_source_b.txt (manifest·저장 바이트·sha256)",
          ext["source_manifest"] == [
              {"source_id": "S001", "file_name": "mock_source_a.txt", "document_date": None},
              {"source_id": "S002", "file_name": "mock_source_b.txt", "document_date": None},
          ]
          and (job_dir / "S001.txt").read_bytes() == SRC_A and (job_dir / "S002.txt").read_bytes() == SRC_B
          and stored["S001"]["sha256"] == sha256(SRC_A) and stored["S002"]["sha256"] == sha256(SRC_B)
          and stored["S001"]["display_name"] == "mock_source_a.txt"
          and stored["S002"]["display_name"] == "mock_source_b.txt")
    ok, detail = units_match(ext["source_units"], {"S001": SRC_A, "S002": SRC_B})
    check("시험3 source_units의 source_id·locator·text가 원본 행과 일치(누락·추가 없음)", ok, detail)
    check("시험3 warnings=[] 이고 total_chars = text 길이 합",
          ext["warnings"] == [] and ext["total_chars"] == sum(len(u["text"]) for u in ext["source_units"]),
          f"total_chars={ext['total_chars']}")
    check("시험3 agent_input 키 = schema_version·company_name_hint·source_units, 값이 추출 기록과 같음",
          set(ai) == AGENT_INPUT_KEYS and ai["schema_version"] == "1.0"
          and ai["company_name_hint"] == "테스트 회사" and ai["source_units"] == ext["source_units"])
    check("시험3 업로드로 만든 agent_input == fixtures/agent_input_mock.json(부록 원문)", ai == MOCK_AGENT_INPUT)

    # ── 빈 줄·공백 행·CRLF·BOM ─────────────────────────────────────
    crafted = ("\ufeff회사명: 빈 줄 시험 회사\n\n   \n사업 분야: 시험 사업 B\r\n\r\n\t\n"
               "  공정 수: 5개  \n마지막 줄(개행 없음)").encode("utf-8")
    code, body, final, _ = upload([part("blank_lines_test.txt", crafted)])
    ext = load_json(job_file(body, "extraction.json")) or {}
    literal = [
        {"source_id": "S001", "locator": "1행", "text": "회사명: 빈 줄 시험 회사"},
        {"source_id": "S001", "locator": "4행", "text": "사업 분야: 시험 사업 B"},
        {"source_id": "S001", "locator": "7행", "text": "공정 수: 5개"},
        {"source_id": "S001", "locator": "8행", "text": "마지막 줄(개행 없음)"},
    ]
    check("시험3 빈 줄·공백 행·CRLF·BOM 파일 → 원본 기준 1·4·7·8행 유지, BOM이 text에 섞이지 않음",
          is_ready_mock(final) and ext.get("source_units") == literal
          and units_match(literal, {"S001": crafted})[0],
          f"actual={[(u['locator'], u['text']) for u in ext.get('source_units', [])]}")

    # ── MD 정상 처리 ───────────────────────────────────────────────
    md = ("# 시험 회사 소개\n\n- 사업 분야: 시험 사업 C\n- 공정 수: 2개\n\n## 참고\n"
          "[자료 링크](https://example.invalid/)\n").encode("utf-8")
    code, body, final, _ = upload([part("company_test.md", md, "text/markdown")], hint="시험 회사")
    ext = load_json(job_file(body, "extraction.json")) or {}
    ai = load_json(job_file(body, "agent_input.json")) or {}
    md_literal = [
        {"source_id": "S001", "locator": "1행", "text": "# 시험 회사 소개"},
        {"source_id": "S001", "locator": "3행", "text": "- 사업 분야: 시험 사업 C"},
        {"source_id": "S001", "locator": "4행", "text": "- 공정 수: 2개"},
        {"source_id": "S001", "locator": "6행", "text": "## 참고"},
        {"source_id": "S001", "locator": "7행", "text": "[자료 링크](https://example.invalid/)"},
    ]
    check("MD 정상 → 202·ready, 저장명 S001.md, 마크다운 기호 포함 원본 행 그대로, hint 전달",
          code == 202 and is_ready_mock(final) and ext.get("stored_files", [{}])[0].get("stored_name") == "S001.md"
          and ext.get("source_manifest") == [{"source_id": "S001", "file_name": "company_test.md", "document_date": None}]
          and ext.get("source_units") == md_literal and ai.get("company_name_hint") == "시험 회사")

    # ── 빈 파일 ────────────────────────────────────────────────────
    code, body, final, _ = upload([part("blank_only.txt", " \n\t\n\r\n\u3000\n".encode("utf-8"))])
    if final:
        example("GET error NEEDS_TEXT_SOURCE (공백만 있는 파일)", f"GET /api/profiles/{body['job_id']}", *final)
    check("공백만 있는 파일 → error NEEDS_TEXT_SOURCE(extracting), agent_input 미생성",
          code == 202 and job_error(final, "NEEDS_TEXT_SOURCE", "extracting")
          and not job_file(body, "agent_input.json").exists())
    code, body, final, _ = upload([part("zero.txt", b"")])
    check("0바이트 파일 → error NEEDS_TEXT_SOURCE", code == 202 and job_error(final, "NEEDS_TEXT_SOURCE", "extracting"))
    code, body, final, _ = upload([part("good.txt", GOOD), part("blank.txt", b"  \n\n")])
    check("정상 + 공백 파일 → ready로 넘기지 않고 error NEEDS_TEXT_SOURCE",
          code == 202 and job_error(final, "NEEDS_TEXT_SOURCE", "extracting"))

    # ── UTF-8 디코딩 실패 ──────────────────────────────────────────
    code, body, final, _ = upload([part("cp949.txt", CP949)])
    if final:
        example("GET error UNSUPPORTED_FILE (UTF-8 아님)", f"GET /api/profiles/{body['job_id']}", *final)
    check("CP949 파일 → error UNSUPPORTED_FILE(extracting), agent_input 미생성",
          code == 202 and job_error(final, "UNSUPPORTED_FILE", "extracting")
          and not job_file(body, "agent_input.json").exists())
    code, body, final, _ = upload([part("good.txt", GOOD), part("cp949.txt", CP949)])
    check("정상 + CP949 → 디코딩 오류를 무시하고 ready 처리하지 않음(error UNSUPPORTED_FILE)",
          code == 202 and job_error(final, "UNSUPPORTED_FILE", "extracting"))
    broken = "회사명: 중간 깨짐\n".encode("utf-8") + b"\xff\xfe" + "공정 수: 1개\n".encode("utf-8")
    code, body, final, _ = upload([part("broken.txt", broken)])
    check("UTF-8 중간에 잘못된 바이트 → 대체 문자로 성공 처리하지 않음(error UNSUPPORTED_FILE)",
          code == 202 and job_error(final, "UNSUPPORTED_FILE", "extracting"))

    # ── 상한(팀 합의 전 제안값) ─────────────────────────────────────
    code, body, final, dirs = upload([part(f"f{i}.txt", GOOD) for i in range(1, 5)])
    example("HTTP 400 INPUT_TOO_LARGE (파일 4개)", "POST /api/profiles files×4", code, body)
    check("파일 4개 → 400 INPUT_TOO_LARGE, 작업 폴더 미생성", code == 400 and is_error_body(body, "INPUT_TOO_LARGE") and dirs == [])

    code, body, final, dirs = upload([part("good.txt", GOOD), part("over_10mb.txt", b"a" * (MAX_FILE_BYTES + 1))])
    example("HTTP 413 INPUT_TOO_LARGE (파일당 10MB 초과)", "POST /api/profiles files=good.txt, over_10mb.txt(10MB+1B)", code, body)
    check("정상 + 10MB+1바이트 → 413 INPUT_TOO_LARGE, 작업 폴더·앞 파일 저장 안 됨",
          code == 413 and is_error_body(body, "INPUT_TOO_LARGE") and dirs == [], f"new_dirs={dirs}")

    code, body, final, _ = upload([part("exact_10mb.txt", b"a" * MAX_FILE_BYTES)])
    check("정확히 10MB → 크기 검사 통과(202) 후 추출 글자 수 초과로 error INPUT_TOO_LARGE(extracting)",
          code == 202 and job_error(final, "INPUT_TOO_LARGE", "extracting"))

    exact = "\n".join(["가" * 100] * 400).encode("utf-8")  # 40,000자(120,399바이트)
    over = exact + "\n나".encode("utf-8")                   # 40,001자
    code, body, final, _ = upload([part("chars_40000.txt", exact)])
    ext = load_json(job_file(body, "extraction.json")) or {}
    check("추출 텍스트 정확히 40,000자 → ready, total_chars=40000",
          is_ready_mock(final) and ext.get("total_chars") == 40_000, f"total_chars={ext.get('total_chars')}")
    code, body, final, _ = upload([part("chars_40001.txt", over)])
    if final:
        example("GET error INPUT_TOO_LARGE (추출 텍스트 40,000자 초과)", f"GET /api/profiles/{body['job_id']}", *final)
    check("추출 텍스트 40,001자 → error INPUT_TOO_LARGE(extracting), 잘라서 진행하지 않음(agent_input 미생성·저장 원본 그대로)",
          code == 202 and job_error(final, "INPUT_TOO_LARGE", "extracting")
          and not job_file(body, "agent_input.json").exists()
          and job_file(body, "S001.txt").read_bytes() == over)

    # ── 기타 HTTP 오류 ─────────────────────────────────────────────
    r = httpx.post(f"{BASE}/api/profiles", files={"company_name_hint": (None, "테스트 회사")}, timeout=10)
    example("HTTP 400 UNSUPPORTED_FILE (files 없음)", "POST /api/profiles company_name_hint만", r.status_code, r.json())
    check("files 없이 요청 → 400 + {error} 공통 모양(422 detail 아님)",
          r.status_code == 400 and is_error_body(r.json(), "UNSUPPORTED_FILE"))

    code, body, final, dirs = upload([part("good.txt", GOOD), part("report.pdf", b"%PDF-1.4 fake", "application/pdf")])
    example("HTTP 415 UNSUPPORTED_FILE (.pdf)", "POST /api/profiles files=good.txt, report.pdf", code, body)
    check(".pdf 포함 → 415 UNSUPPORTED_FILE, 작업 폴더 미생성",
          code == 415 and is_error_body(body, "UNSUPPORTED_FILE") and dirs == [])

    missing = str(uuid.uuid4())
    r = httpx.get(f"{BASE}/api/profiles/{missing}", timeout=10)
    example("HTTP 404 JOB_NOT_FOUND", f"GET /api/profiles/{missing}", r.status_code, r.json())
    check("없는 작업 번호 → 404 JOB_NOT_FOUND", r.status_code == 404 and is_error_body(r.json(), "JOB_NOT_FOUND"))

    r = httpx.post(f"{BASE}/api/profiles/{first_job}/document", json={"format": "md"}, timeout=10)
    example("HTTP 409 DOCUMENT_FAILED (문서 API 미구현)", f"POST /api/profiles/{first_job}/document format=md",
            r.status_code, r.json())
    check("문서 API → 성공을 반환하지 않고 409 DOCUMENT_FAILED",
          r.status_code == 409 and is_error_body(r.json(), "DOCUMENT_FAILED"))

    # ── 동시 업로드(1MB 초과 파일은 디스크 임시파일에서 읽음) ─────────
    big = ("동시 요청 시험 줄\n" * 200_000).encode("utf-8")  # 약 5MB

    def post_big(_: int) -> httpx.Response:
        return httpx.post(f"{BASE}/api/profiles", files=[part("concurrent.txt", big)], timeout=30)

    try:
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            responses = list(pool.map(post_big, range(4)))
        statuses = [r.status_code for r in responses]
        hung = False
    except httpx.HTTPError as exc:
        responses, statuses, hung = [], [type(exc).__name__], True
    for r in responses:
        if r.status_code == 202:
            poll(r.json()["job_id"])
        elif r.status_code == 409 and "HTTP 409 BUSY" not in examples:
            example("HTTP 409 BUSY (진행 중 작업 있음)", "POST /api/profiles (다른 작업 처리 중)", r.status_code, r.json())
    check("동시 업로드 4건 → 서버가 멈추지 않고 모두 응답(202 또는 409 BUSY)",
          not hung and set(statuses) <= {202, 409} and 202 in statuses
          and all(r.status_code != 409 or is_error_body(r.json(), "BUSY") for r in responses),
          f"statuses={statuses}")

    # ── 실패 후 다음 정상 작업 ──────────────────────────────────────
    code, body, final, _ = upload([part("mock_source_a.txt", SRC_A), part("mock_source_b.txt", SRC_B)], hint="테스트 회사")
    ai = load_json(job_file(body, "agent_input.json"))
    check("여러 오류 뒤 다음 정상 작업 → ready, result == Mock, agent_input == 부록 원문",
          code == 202 and is_ready_mock(final) and ai == MOCK_AGENT_INPUT, f"job_id={body.get('job_id')}")
    print(f"      (A 전달용 복사 명령: python scripts/make_agent_input.py --job {body.get('job_id')})")


def inprocess_checks() -> None:
    from fastapi.testclient import TestClient

    from backend import parsers

    # ── extract_sources 반환 구조 ──────────────────────────────────
    stored = [
        {"source_id": "S001", "stored_path": FIX / "mock_source_a.txt", "display_name": "mock_source_a.txt"},
        {"source_id": "S002", "stored_path": str(FIX / "mock_source_b.txt"), "display_name": "mock_source_b.txt"},
    ]
    returned = parsers.extract_sources(stored)
    su, sm, w = returned
    check("P1 extract_sources → (source_units, source_manifest, warnings) 세 목록 반환",
          isinstance(returned, tuple) and len(returned) == 3 and all(isinstance(x, list) for x in returned))
    check("P1 unit 키={source_id,locator,text}, manifest 키={source_id,file_name,document_date}, warnings=문자열 목록",
          all(set(u) == {"source_id", "locator", "text"} for u in su)
          and all(set(m) == {"source_id", "file_name", "document_date"} for m in sm)
          and all(isinstance(x, str) for x in w))
    check("P1 직접 호출 source_units == fixtures/agent_input_mock.json source_units, document_date=None",
          su == MOCK_AGENT_INPUT["source_units"] and all(m["document_date"] is None for m in sm))

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["FRONTEND_DIR"] = str(Path(tmp) / "no_frontend")
        import backend.main as main
        main = importlib.reload(main)
        main.PRIVATE_RUNS = Path(tmp) / "private_runs"
        client = TestClient(main.app)
        files = [part("mock_source_a.txt", SRC_A), part("mock_source_b.txt", SRC_B)]

        # ── 처리 중 예외 → error 종료, 다음 작업 가능 ──────────────
        original_extract = main.parsers.extract_sources

        def boom(_stored_files):
            raise RuntimeError(r"boom C:\secret\internal\path 원문노출금지")

        main.parsers.extract_sources = boom
        try:
            r = client.post("/api/profiles", files=files)
            g = client.get(f"/api/profiles/{r.json()['job_id']}").json()
        finally:
            main.parsers.extract_sources = original_extract
        text = json.dumps(g, ensure_ascii=False)
        check("P2 추출 중 예외 → status=error, result=null, INVALID_OUTPUT(extracting), 내부 메시지·경로 미노출",
              r.status_code == 202 and g["status"] == "error" and g["result"] is None
              and g["error"]["code"] == "INVALID_OUTPUT" and g["error"]["stage"] == "extracting"
              and "boom" not in text and "secret" not in text, text)

        original_mock = main.get_mock_profile

        def mock_boom():
            raise ValueError("mock load failed")

        main.get_mock_profile = mock_boom
        try:
            r = client.post("/api/profiles", files=files)
            g = client.get(f"/api/profiles/{r.json()['job_id']}").json()
        finally:
            main.get_mock_profile = original_mock
        check("P2 Mock 결과 붙이는 중 예외 → status=error(INVALID_OUTPUT), 진행 중 상태로 남지 않음",
              g["status"] == "error" and g["result"] is None and g["error"]["code"] == "INVALID_OUTPUT")

        r = client.post("/api/profiles", files=files)
        g = client.get(f"/api/profiles/{r.json()['job_id']}").json()
        check("P2 예외 뒤 다음 정상 작업 → 202·ready, result == Mock (BUSY로 막히지 않음)",
              r.status_code == 202 and g["status"] == "ready" and g["result"] == MOCK_PROFILE)

        check("P3 frontend/index.html 없음 → '/'는 자리표시 페이지",
              "아직 연결되지 않았습니다" in client.get("/").text)

        # ── 화면 제공 방식(임시 index.html로 연결 방식만 확인. B 화면 아님) ──
        fe = Path(tmp) / "serving_check"
        fe.mkdir()
        (fe / "index.html").write_text("<!doctype html><title>serving-check</title>SERVING-CHECK-ONLY", encoding="utf-8")
        (fe / "app.js").write_text("// serving check only\n", encoding="utf-8")
        os.environ["FRONTEND_DIR"] = str(fe)
        try:
            main = importlib.reload(main)
            main.PRIVATE_RUNS = Path(tmp) / "private_runs"
            c = TestClient(main.app)
            root_text = c.get("/").text
            js = c.get("/app.js")
            r = c.post("/api/profiles", files=files)
            g = c.get(f"/api/profiles/{r.json()['job_id']}").json()
            nf = c.get(f"/api/profiles/{uuid.uuid4()}")
            check("P3 FRONTEND_DIR에 index.html 있음 → '/'와 같은 폴더 파일(app.js)을 같은 서버에서 제공",
                  "SERVING-CHECK-ONLY" in root_text and js.status_code == 200)
            check("P3 화면 연결 상태에서도 API 우선: POST 202 → GET ready, 없는 작업 404 JSON",
                  r.status_code == 202 and g["status"] == "ready" and g["result"] == MOCK_PROFILE
                  and nf.status_code == 404 and is_error_body(nf.json(), "JOB_NOT_FOUND"))
        finally:
            os.environ.pop("FRONTEND_DIR", None)
            importlib.reload(main)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="서버 없이 프로세스 내부 시험만")
    args = ap.parse_args()

    if not args.offline:
        print("== HTTP 시험: 실행 중인 서버 http://127.0.0.1:8000 ==")
        http_checks()
        if examples:
            out = ROOT / "handoff" / "api_examples.json"
            out.parent.mkdir(exist_ok=True)
            out.write_text(json.dumps({
                "note": "로컬 서버 실제 응답(가짜 데이터). ready의 result는 고정 Mock(is_mock=true)이며 업로드 자료 분석 결과가 아님.",
                "generated_by": "python scripts/check_backend.py",
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "examples": examples,
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"      (응답 예시 저장: {out.relative_to(ROOT)})")

    print("== 프로세스 내부 시험: TestClient·임시 폴더 ==")
    inprocess_checks()

    failed = [name for name, ok in results if not ok]
    print(f"\n합계: PASS {len(results) - len(failed)} / FAIL {len(failed)} — 위에 출력된 항목만 검사함")
    print("검사하지 않음: 실제 기업 자료·결과 사실성, 실제 Agent/LLM, PDF/DOCX, 문서 파일 생성, B 화면 표시·동작")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
