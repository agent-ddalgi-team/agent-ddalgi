"""C 백엔드 — 회사소개서 초안 생성·조회 API (수요일: Mock/LLM 모드 분리).

contracts/contract.md v1.0 기준.
- 127.0.0.1 단일 프로세스, 동시 작업 한 건, 작업 상태는 메모리 보관(서버 재시작 시 소멸 → 404 재생성 안내).
- POST /api/profiles: TXT/MD 수신·제한 검사·private_runs/<job_id>/ 저장·작업 번호 발급.
- GET /api/profiles/{job_id}: 작업별 결과 조회.
- POST /api/profiles/{job_id}/document: D의 render_document가 연결되기 전이므로 성공을 반환하지 않는다.
- 실행 모드(AGENT_MODE, .env 또는 환경변수, 서버 시작 시 1회 결정. 요청으로 바꿀 수 없음):
  - mock(기본): 첫날과 같은 고정 Mock 결과(is_mock=true). 실제 기업 분석이 아님.
  - llm: analyzing에서 A의 extract_company_info()를 실제 호출한다. 실패하면 error로 끝내며
    Mock으로 대체하지 않는다. drafting은 A의 draft_profile, validating은 D의 검사 모듈이
    연결되어야 진행되고, 없으면 중간 결과만 기록하고 error로 끝낸다(중간 결과로 ready 금지).
- 작업 폴더 기록(내부, 공개 API 응답에 넣지 않음): extraction.json, agent_input.json,
  company_info.json(LLM 추출 중간 결과), run_meta.json(모드·실제 호출 여부), result.json(최종).

실행: cd projects/02-company-profile && .venv\\Scripts\\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import shutil
import threading
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend import parsers, profile_builder
from backend.mock_agent import get_mock_profile

ROOT = Path(__file__).resolve().parent.parent
PRIVATE_RUNS = ROOT / "private_runs"

load_dotenv(ROOT / ".env")
FRONTEND_DIR = Path(os.environ.get("FRONTEND_DIR") or ROOT / "frontend")

# 실행 모드는 서버 설정으로만 정한다. 요청 JSON으로 바꾸는 API는 만들지 않는다.
AGENT_MODE = (os.environ.get("AGENT_MODE") or "mock").strip().lower()
if AGENT_MODE not in {"mock", "llm"}:
    # 오설정을 조용히 mock으로 대체하면 실제 분석처럼 보일 수 있어 서버 시작을 중단한다.
    raise RuntimeError(f"AGENT_MODE는 mock 또는 llm이어야 합니다(현재: {AGENT_MODE!r}). .env를 수정해 주세요.")

# 기업 자료의 외부 LLM 사용 허용이 확인되기 전이므로 입력은 가짜 테스트 자료뿐이고,
# 결과의 is_mock은 항상 true다(테스트 데이터 표시). 실제 LLM 호출 여부는 run_meta.json에 따로 남긴다.
RESULT_IS_MOCK = True

logger = logging.getLogger(__name__)

# 아래 세 상한은 contract.md의 초기 제안값이며 팀 합의 전이다(docs/day1.md 기록).
MAX_FILES = 3
MAX_FILE_BYTES = 10 * 1024 * 1024  # 파일당 10MB
MAX_TOTAL_CHARS = 40_000           # source_units text 글자 수 합계. 초과 시 조용히 자르지 않고 오류.
ALLOWED_EXTENSIONS = {".txt", ".md"}  # PDF/DOCX는 첫날 미구현
SCHEMA_VERSION = "1.0"

app = FastAPI(title="회사소개서 초안 백엔드 (첫날·Mock)")

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

ACTIVE_STATUSES = {"queued", "extracting", "analyzing", "drafting", "validating"}


def _error(code: str, stage: str, message: str, retryable: bool = False) -> dict:
    return {"code": code, "stage": stage, "message": message, "retryable": retryable}


def _error_response(status_code: int, error: dict) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": error})


def _job_envelope(job: dict) -> dict:
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "result": job["result"],
        "error": job["error"],
    }


@app.exception_handler(RequestValidationError)
async def _request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI 기본 422 {"detail": ...} 대신 공통 오류 모양으로 답한다. 받은 입력값은 되돌려주지 않는다.
    return _error_response(
        400,
        _error("UNSUPPORTED_FILE", "queued",
               f"요청 형식이 올바르지 않습니다. files 필드로 TXT/MD 파일을 1~{MAX_FILES}개 보내 주세요."),
    )


_READ_CHUNK_BYTES = 1024 * 1024


async def _read_limited(upload: UploadFile, limit: int) -> bytes | None:
    """실제로 읽은 바이트 수를 세며 limit까지만 받는다. 넘으면 읽기를 멈추고 None을 돌려준다.

    Content-Length나 UploadFile.size 같은 요청 정보로 판단하지 않는다.
    한 파일에 쓰는 메모리는 limit + 한 조각(1MB)을 넘지 않는다.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(_READ_CHUNK_BYTES):
        total += len(chunk)
        if total > limit:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


@app.post("/api/profiles", status_code=202)
async def create_profile(
    background_tasks: BackgroundTasks,
    files: list[UploadFile],
    company_name_hint: str | None = Form(default=None),
):
    # 저장 전에 모든 파일을 검사한다. 하나라도 걸리면 작업 폴더·파일을 만들지 않는다.
    if not files or len(files) > MAX_FILES:
        return _error_response(
            400, _error("INPUT_TOO_LARGE", "queued", f"파일은 1~{MAX_FILES}개만 받을 수 있습니다.")
        )

    for f in files:
        if Path(f.filename or "").suffix.lower() not in ALLOWED_EXTENSIONS:
            return _error_response(
                415,
                _error("UNSUPPORTED_FILE", "queued",
                       "첫날은 UTF-8 TXT/MD만 받습니다. PDF/DOCX는 아직 지원하지 않습니다."),
            )

    uploads: list[tuple[str, str, bytes]] = []  # (확장자, 표시용 원본 이름, 내용)
    for index, f in enumerate(files, start=1):
        content = await _read_limited(f, MAX_FILE_BYTES)
        if content is None:
            return _error_response(
                413, _error("INPUT_TOO_LARGE", "queued", "파일당 10MB를 넘을 수 없습니다.")
            )
        uploads.append(
            (Path(f.filename or "").suffix.lower(), Path(f.filename or f"file_{index}").name, content)
        )

    hint = (company_name_hint or "").strip() or None

    # 잠금 안에서는 await하지 않는다. threading.Lock을 쥔 채 이벤트 루프를 넘기면
    # 동시에 들어온 다른 요청이 잠금을 기다리며 루프 전체를 멈춘다.
    with _jobs_lock:
        if any(j["status"] in ACTIVE_STATUSES for j in _jobs.values()):
            return _error_response(
                409, _error("BUSY", "queued", "이미 진행 중인 작업이 있습니다. 완료 후 다시 시도해 주세요.", True)
            )

        job_id = str(uuid.uuid4())
        job_dir = PRIVATE_RUNS / job_id
        stored_files: list[dict] = []
        created = False
        try:
            job_dir.mkdir(parents=True)
            created = True
            for index, (suffix, display_name, content) in enumerate(uploads, start=1):
                source_id = f"S{index:03d}"  # 업로드 순서대로 서버가 부여
                stored_path = job_dir / f"{source_id}{suffix}"  # 서버 내부 저장명. 원본 이름은 표시용.
                stored_path.write_bytes(content)
                stored_files.append(
                    {"source_id": source_id, "stored_path": str(stored_path), "display_name": display_name}
                )
        except Exception:
            # 폴더 생성·파일 쓰기 실패: 이 요청이 만든 폴더만 지우고 공통 오류로 답한다.
            # 작업을 등록하기 전이므로 BUSY 상태도 남지 않는다. 예외 내용·경로는 응답에 넣지 않는다.
            if created:
                shutil.rmtree(job_dir, ignore_errors=True)
            return _error_response(
                500,
                _error("INVALID_OUTPUT", "queued", "업로드 파일을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.", True),
            )

        _jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "result": None,
            "error": None,
            "company_name_hint": hint,
            "stored_files": stored_files,
        }

    background_tasks.add_task(_process_job, job_id)
    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "status": "queued", "result": None, "error": None},
    )


def _fail(job: dict, error: dict) -> None:
    # 조회 쪽이 status=error인데 error=null인 순간을 보지 않도록 error를 먼저 채운다.
    job["result"] = None
    job["error"] = error
    job["status"] = "error"


def _write_json(path: Path, data: object) -> None:
    # 임시 파일에 다 쓴 뒤 교체한다. 쓰는 중에 실패해도 반쯤 쓴 JSON이 남지 않는다.
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _save_extraction_record(job: dict) -> None:
    """추출 결과를 작업 폴더에 남긴다(내부 기록). 공개 API 응답에는 포함하지 않는다."""
    job_dir = PRIVATE_RUNS / job["job_id"]
    stored = []
    for item in job["stored_files"]:
        data = Path(item["stored_path"]).read_bytes()
        stored.append(
            {
                "source_id": item["source_id"],
                "stored_name": Path(item["stored_path"]).name,
                "display_name": item["display_name"],
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    record_paths = (job_dir / "extraction.json", job_dir / "agent_input.json")
    try:
        _write_json(
            record_paths[0],
            {
                "job_id": job["job_id"],
                "limits": {
                    "max_files": MAX_FILES,
                    "max_file_bytes": MAX_FILE_BYTES,
                    "max_total_chars": MAX_TOTAL_CHARS,
                    "note": "팀 합의 전 제안값",
                },
                "total_chars": job["total_chars"],
                "stored_files": stored,
                "source_manifest": job["source_manifest"],
                "warnings": job["warnings"],
                "source_units": job["source_units"],
            },
        )
        _write_json(record_paths[1], job["agent_input"])
    except Exception:
        # 두 기록 중 하나만 남지 않게 지운다. 업로드 원본(S00N 파일)은 작업 입력이므로 유지한다.
        for path in record_paths:
            path.unlink(missing_ok=True)
        raise


def _process_job(job_id: str) -> None:
    """저장된 파일에서 실제로 텍스트를 추출·기록한 뒤, 첫날은 고정 Mock 결과를 붙인다.

    분석 단계를 타이머로 연출하지 않는다. 모든 예외를 error로 끝내 영구 진행 중 상태를 막는다.
    """
    job = _jobs.get(job_id)
    if job is None:
        return
    try:
        job["status"] = "extracting"
        source_units, source_manifest, warnings = parsers.extract_sources(job["stored_files"])
        total_chars = sum(len(u["text"]) for u in source_units)
        job["total_chars"] = total_chars
        if total_chars > MAX_TOTAL_CHARS:
            _fail(job, _error(
                "INPUT_TOO_LARGE", "extracting",
                f"추출 텍스트가 상한({MAX_TOTAL_CHARS:,}자)을 넘었습니다. 내용을 나눠 다시 시도해 주세요.",
            ))
            return

        job["source_units"] = source_units
        job["source_manifest"] = source_manifest
        job["warnings"] = warnings
        job["agent_input"] = {
            "schema_version": SCHEMA_VERSION,
            "company_name_hint": job["company_name_hint"],
            "source_units": source_units,
        }
        try:
            _save_extraction_record(job)
        except Exception:
            # 조회 가능한 작업이 이미 있으므로 HTTP 오류가 아니라 작업을 error로 끝낸다.
            _fail(job, _error("INVALID_OUTPUT", "extracting",
                              "추출 결과를 저장하지 못했습니다. 잠시 후 다시 업로드해 주세요.", True))
            return

        if AGENT_MODE == "llm":
            _run_llm_job(job)
        else:
            # mock 모드: 실제 Agent 호출 없이 고정 Mock 결과(is_mock=true)를 그대로 붙인다.
            # Mock의 sources·evidence는 동봉 가짜 TXT 기준 고정값이다. 업로드 자료의
            # source_manifest로 바꿔 끼우지 않는다(업로드 추출 결과는 위 기록 파일에만 둔다).
            _write_run_meta(job, llm_called=False, note="고정 Mock 결과(fixtures/mock_profile.json). 실제 LLM 호출 없음.")
            job["result"] = get_mock_profile()
            job["status"] = "ready"
    except parsers.UnsupportedEncoding as exc:
        _fail(job, _error("UNSUPPORTED_FILE", "extracting", str(exc)))
    except parsers.NeedsTextSource as exc:
        _fail(job, _error("NEEDS_TEXT_SOURCE", "extracting", str(exc)))
    except profile_builder.ProfileAssemblyError:
        # supported 본문 누락·잘못된 fact_id 참조 등. Mock 문단으로 보충하지 않고 오류로 끝낸다.
        logger.exception("본문 조립 실패: %s", job_id)
        _fail(job, _error("INVALID_OUTPUT", "drafting", "생성된 본문이 조립 규칙을 지키지 않았습니다."))
    except Exception:
        # 내부 경로·원문을 오류에 노출하지 않는다.
        stage = job["status"] if job["status"] in ACTIVE_STATUSES else "extracting"
        _fail(job, _error("INVALID_OUTPUT", stage, "작업 처리 중 오류가 발생했습니다.", True))


def _write_run_meta(job: dict, llm_called: bool, note: str) -> None:
    """실행 모드·실제 LLM 호출 여부를 작업 폴더에 남긴다(내부 기록, 최종 JSON에는 새 키를 넣지 않음)."""
    try:
        _write_json(PRIVATE_RUNS / job["job_id"] / "run_meta.json", {
            "job_id": job["job_id"],
            "agent_mode": AGENT_MODE,
            "llm_called": llm_called,
            "input_kind": "fake_test_data",  # 기업 자료 사용 허용 확인 전: 가짜 테스트 자료만 사용
            "result_is_mock": RESULT_IS_MOCK,
            "note": note,
            "written_at": datetime.datetime.now().isoformat(timespec="seconds"),
        })
    except Exception:
        # 실행 기록 실패로 작업 자체를 죽이지 않는다. 상세는 서버 로그로만 남긴다.
        logger.exception("run_meta.json 기록 실패: %s", job["job_id"])


def _run_llm_job(job: dict) -> None:
    """llm 모드: A의 extract_company_info()를 실제 호출한다. 어떤 실패도 Mock으로 대체하지 않는다.

    A의 draft_profile()과 D의 검사 모듈이 아직 없으므로, 지금은 추출 중간 결과까지 기록하고
    drafting 단계에서 error로 끝난다(중간 결과만으로 ready를 만들지 않는다).
    """
    job_dir = PRIVATE_RUNS / job["job_id"]
    # openai 의존성은 llm 모드에서만 필요하므로 여기서 불러온다.
    from backend import agent

    job["status"] = "analyzing"
    try:
        company_info = agent.extract_company_info(job["agent_input"])
    except agent.AgentError as exc:
        _write_run_meta(job, llm_called=True, note=f"extract_company_info 실패: {exc.code}[{exc.rule}]")
        retryable = exc.code == "LLM_TIMEOUT"
        _fail(job, _error(exc.code, "analyzing", exc.message, retryable))
        return
    except agent.AgentInputError as exc:
        _write_run_meta(job, llm_called=False, note=f"agent_input 형식 오류: {exc.rule}")
        _fail(job, _error("INVALID_OUTPUT", "analyzing", "Agent 입력 형식이 계약과 다릅니다. 서버 로그를 확인해 주세요."))
        return
    except RuntimeError:
        # agent.call_openai: .env의 OPENAI_API_KEY/OPENAI_MODEL 미설정. 키 값은 어디에도 남기지 않는다.
        _write_run_meta(job, llm_called=False, note="LLM 설정 누락(.env의 OPENAI_API_KEY/OPENAI_MODEL)")
        _fail(job, _error("INVALID_OUTPUT", "analyzing",
                          "LLM 설정이 없습니다. .env의 OPENAI_API_KEY와 OPENAI_MODEL을 확인해 주세요.", True))
        return
    except Exception:
        # 그 밖의 OpenAI API 오류(키·권한·모델명·한도·연결). 상세는 서버 로그로만 남긴다.
        logger.exception("OpenAI 호출 실패: %s", job["job_id"])
        _write_run_meta(job, llm_called=True, note="OpenAI 호출 실패(상세는 서버 로그)")
        _fail(job, _error("INVALID_OUTPUT", "analyzing", "AI 호출에 실패했습니다. 잠시 후 다시 시도해 주세요.", True))
        return

    # 중간 추출 결과는 별도 기록만 한다. 이 값만으로 ready로 바꾸지 않는다.
    _write_json(job_dir / "company_info.json", company_info)
    _write_run_meta(job, llm_called=True, note="extract_company_info 실제 호출 성공. 중간 결과 company_info.json 기록.")
    job["company_info"] = company_info
    supported_facts = profile_builder.collect_supported_facts(company_info)

    job["status"] = "drafting"
    if supported_facts and not hasattr(agent, "draft_profile"):
        # A의 본문 생성 함수가 아직 없다. 성공하는 가짜 함수로 메우지 않고 여기서 멈춘다.
        _fail(job, _error("INVALID_OUTPUT", "drafting",
                          "본문 생성 기능이 아직 연결되지 않았습니다. 추출 결과는 저장했지만 초안을 완성할 수 없습니다."))
        return
    # supported 사실이 하나도 없으면 본문 생성을 억지로 호출하지 않고 안내 문구만으로 조립한다.
    generated_sections = agent.draft_profile(supported_facts) if supported_facts else []
    profile = profile_builder.assemble_profile(
        company_info, generated_sections, job["source_manifest"], is_mock=RESULT_IS_MOCK
    )

    job["status"] = "validating"
    try:
        from backend import validators  # D 소유(신규/재사용). C가 대신 구현하지 않는다.
    except ImportError:
        _fail(job, _error("INVALID_OUTPUT", "validating",
                          "본문·최종 결과 검사 기능이 아직 연결되지 않았습니다. 검사 전 결과는 ready로 내보내지 않습니다."))
        return
    errors = list(validators.validate_draft(profile["draft_sections"], company_info))
    errors += list(validators.validate_profile_result(profile, job["source_units"]))
    if errors:
        logger.error("검사 실패 %s: %s", job["job_id"], errors)
        _fail(job, _error("INVALID_OUTPUT", "validating", "생성된 초안이 검사를 통과하지 못했습니다."))
        return
    profile["validation"]["evidence_links_valid"] = True
    schema_problems = profile_builder.schema_errors(profile)
    if not schema_problems:
        profile["validation"]["schema_valid"] = True
        schema_problems = profile_builder.schema_errors(profile)  # 플래그 반영 후 최종 재확인
    if schema_problems:
        logger.error("스키마 검사 실패 %s: %s", job["job_id"], schema_problems)
        _fail(job, _error("INVALID_OUTPUT", "validating", "최종 결과가 공통 스키마를 통과하지 못했습니다."))
        return

    _write_json(job_dir / "result.json", profile)
    job["result"] = profile
    job["status"] = "ready"


@app.get("/api/profiles/{job_id}")
def get_profile(job_id: str):
    job = _jobs.get(job_id)
    if job is None:
        return _error_response(
            404,
            _error("JOB_NOT_FOUND", "queued",
                   "작업을 찾을 수 없습니다. 서버가 재시작되었을 수 있으니 파일을 다시 업로드해 주세요."),
        )
    return _job_envelope(job)


# 형식별 Content-Type. 실제 내려보내는 파일 이름은 D가 만든 파일 이름을 그대로 쓴다.
DOCUMENT_MEDIA_TYPES: dict[str, str] = {
    "md": "text/markdown; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _document_failed(message: str) -> JSONResponse:
    # 문서만 실패한 경우다. 작업의 result와 ready 상태는 그대로 둔다(오류 JSON을 파일로 저장하지 않음).
    return _error_response(409, _error("DOCUMENT_FAILED", "rendering", message))


def _check_document_file(produced: object, output_dir: Path, fmt: str) -> tuple[Path | None, str | None]:
    """D가 돌려준 값이 내려보내도 되는 파일인지 본다. (파일 경로, 문제 설명)을 돌려준다.

    문제 설명은 서버 로그용이며 응답에는 넣지 않는다. 경로 확인·크기 조회 중 생긴 파일 오류도
    문제로 취급한다(예외를 그대로 올려 500을 내지 않는다). 파일 시스템을 만지므로 스레드풀에서 부른다.
    """
    if not isinstance(produced, (str, os.PathLike)):
        return None, f"반환값이 파일 경로가 아닙니다({type(produced).__name__})"
    try:
        resolved = Path(produced).resolve()
        if not resolved.is_file():
            return None, "실제 파일이 아닙니다"
        if output_dir.resolve() not in resolved.parents:
            return None, "작업 폴더 밖의 경로입니다"
        if resolved.suffix.lower() != f".{fmt}":
            return None, f"요청한 형식(.{fmt})과 확장자가 다릅니다"
        if resolved.stat().st_size == 0:
            # 내용이 없는 파일을 성공으로 내려보내면 사람이 열어 보기 전까지 실패를 모른다.
            return None, "빈 파일(0바이트)입니다"
    except OSError as exc:
        return None, f"파일을 확인하지 못했습니다({type(exc).__name__})"
    return resolved, None


@app.post("/api/profiles/{job_id}/document")
async def create_document(job_id: str, request: Request):
    """서버가 보관한 같은 job_id의 최종 결과를 D의 render_document에 넘겨 실제 파일만 돌려준다.

    D의 backend/document_generator.py가 없으면 지금처럼 409 DOCUMENT_FAILED로 끝난다.
    실제로 만들어진 비어 있지 않은 파일인 경우에만 성공(파일 바이트)을 반환한다.
    클라이언트가 보낸 profile·파일 경로·파일명은 받지 않는다.
    어떤 실패든 작업의 result와 ready 상태는 그대로 둔다(문서만 실패).
    """
    job = _jobs.get(job_id)
    if job is None:
        return _error_response(
            404, _error("JOB_NOT_FOUND", "rendering", "작업을 찾을 수 없습니다.")
        )
    if job["status"] != "ready":
        return _document_failed("ready 상태의 초안이 없어 문서를 만들 수 없습니다.")

    try:
        body = await request.json()
    except Exception:
        body = None
    requested = body.get("format") if isinstance(body, dict) else None
    fmt = requested.strip().lower() if isinstance(requested, str) else ""
    if fmt not in DOCUMENT_MEDIA_TYPES:
        return _document_failed(
            f"문서 형식은 {' 또는 '.join(DOCUMENT_MEDIA_TYPES)} 중 하나여야 합니다."
        )

    try:
        from backend import document_generator  # D 소유(신규/재사용). C가 대신 구현하지 않는다.
    except ImportError:
        return _document_failed(
            "문서 생성 기능이 아직 연결되지 않았습니다. 규격만 합의된 상태입니다."
        )

    # 출력은 이 작업 폴더 안으로 한정한다.
    output_dir = PRIVATE_RUNS / job_id / "documents"
    try:
        # D의 render_document는 동기 함수다. 파일 만들기·저장이 오래 걸려도 같은 시간에 들어온
        # 다른 요청(상태 조회 등)이 멈추지 않도록 스레드풀에서 실행한다.
        await run_in_threadpool(output_dir.mkdir, parents=True, exist_ok=True)
        produced = await run_in_threadpool(document_generator.render_document, job["result"], output_dir, fmt)
    except Exception:
        # D가 던진 예외를 약속된 DOCUMENT_FAILED로 바꾼다. 상세는 서버 로그에만 남긴다.
        logger.exception("문서 생성 실패 %s (%s)", job_id, fmt)
        return _document_failed("문서를 만들지 못했습니다. 잠시 후 다시 시도해 주세요.")

    resolved, problem = await run_in_threadpool(_check_document_file, produced, output_dir, fmt)
    if problem is not None:
        logger.error("문서 생성 결과를 내보낼 수 없습니다 %s (%s): %s", job_id, fmt, problem)
        return _document_failed("문서를 만들지 못했습니다. 잠시 후 다시 시도해 주세요.")
    return FileResponse(resolved, media_type=DOCUMENT_MEDIA_TYPES[fmt], filename=resolved.name)


# 화면은 API 경로를 모두 등록한 뒤 연결해야 API가 우선한다.
if (FRONTEND_DIR / "index.html").is_file():
    # B 화면: 같은 서버·같은 origin에서 정적 파일로 제공한다. 파일을 넣은 뒤 서버를 재시작해야 반영된다.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        # B 화면 파일이 들어오기 전까지의 자리표시 페이지.
        return (
            "<!doctype html><meta charset='utf-8'>"
            "<title>회사소개서 초안 서버 (테스트)</title>"
            "<h1>회사소개서 초안 백엔드 — 테스트 데이터</h1>"
            "<p>B 화면(frontend/index.html)이 아직 연결되지 않았습니다. "
            "파일을 넣은 뒤 서버를 재시작하면 이 주소에서 제공됩니다.</p>"
            "<p>API: POST /api/profiles, GET /api/profiles/{job_id}</p>"
        )
