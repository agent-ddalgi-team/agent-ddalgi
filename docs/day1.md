> **폴더 이동 안내(2026-09-16):** 이 문서는 저장소 projects/02-company-profile/docs/day1.md로 복사된 사본이다.
> 아래 기록의 실행 폴더 C:\\Users\\user\\Documents\\Codex\\개발기준은 당시 원본 폴더 경로다.
> 저장소에서 실행할 때는 projects/02-company-profile에서 같은 상대경로 명령을 쓰고, 설치·실행은 같은 폴더의 README.md를 따른다.
> 기록에 나오는 private_runs/7e658ea0-.../extraction.json 예시는 저장소에서는 handoff/extraction_example.json으로 동봉했다(private_runs/는 Git 제외).

# 첫날(2026-09-15, 화) 작업 기록 — C 백엔드

기준 문서: 04_C_백엔드_AI작업기준.md (안내판 r1 / 공통 데이터 규격 v1.0)

## 작업 1 — 프로젝트 확인·부록 파일 복원·서버와 생성·조회 API

- **작업 번호:** C-1 (① 서버와 두 API부터 만들기)
- **기존 프로젝트 확인:** `Documents\Codex\geosan-agent-starter`는 A(Agent) 쪽 LangGraph 스타터로 확인. `backend/`·`contracts/contract.md` 구조의 기존 서버는 없음 → 문서 기본안(Python/FastAPI)으로 이 폴더(`Documents\Codex\개발기준`)에 새로 생성.
- **수정(생성) 파일:**
  - 부록 원문 복원: `contracts/contract.md`, `contracts/profile.schema.json`, `fixtures/mock_profile.json`, `fixtures/mock_job_ready.json`, `fixtures/mock_job_error.json`, `fixtures/mock_source_a.txt`, `fixtures/mock_source_b.txt`, `fixtures/agent_input_mock.json`, `prompts/extract.txt`, `prompts/draft.txt`, `validate_fixtures.py`
  - 백엔드: `backend/main.py`, `backend/mock_agent.py`, `backend/parsers.py`, `backend/__init__.py`, `.gitignore`
- **실행 명령:**
  - 의존성: `python -m pip install fastapi uvicorn python-multipart jsonschema`
  - 규격 검증: `python validate_fixtures.py` → PASS
  - 서버: `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`
- **직접 확인한 결과 (실제 실행):**
  - 시험1 가짜 TXT 2개 업로드 → 202, job_id(UUID)·queued 수신. PASS
  - 시험2 job_id 조회 → ready, result가 `fixtures/mock_profile.json`과 dict 완전 일치, profile.schema.json 검증 통과, `is_mock=true`. PASS
  - 시험4 빈 TXT → status=error, `NEEDS_TEXT_SOURCE`. 미지원 확장자(.pdf) → HTTP 415, `UNSUPPORTED_FILE`. PASS
  - 시험5 없는 작업 번호 → HTTP 404, `JOB_NOT_FOUND`. PASS
  - 문서 API → 실제 파일 생성 미구현이므로 성공을 반환하지 않고 409/`DOCUMENT_FAILED` 안내. PASS
  - 저장: `private_runs/<job_id>/S001.txt` 형식(서버 내부 저장명, 원본 이름은 표시용만). PASS
- **미실행 또는 실패:**
  - 시험6(B 화면 연동)은 아직 미실행. (시험3은 아래 작업 2에서 완료)
  - PDF/DOCX 파서, 실제 Agent 호출, 실제 문서 생성 미구현(첫날 범위 밖). Mock 결과는 테스트 데이터이며 실제 기업 분석이 아님.
  - 상한(파일 3개·10MB·40,000자)은 초기 제안값 그대로 적용. **팀 합의 여부 미확인.**
- **다음 담당자에게 전달할 것:**
  - B: 화면 주소 `http://127.0.0.1:8000/`, 생성 `POST /api/profiles`(FormData: files 1~3개, company_name_hint 선택), 조회 `GET /api/profiles/{job_id}`(약 1초 간격, ready/error에서 중단). 정상/오류 응답 예시는 `fixtures/mock_job_ready.json`·`mock_job_error.json`.
  - D: `backend/parsers.py`의 `extract_sources(stored_files)` 경계와 source_id(`S001`…)·locator(`N행`) 규칙.
  - A: agent_input 형태는 `fixtures/agent_input_mock.json` 기준(서버가 조립).
- **다음 작업:** ② source_units 검증(시험3) 마무리 → ③ B와 화면 연결(시험6).

## 작업 2 — 추출 기록 검증(시험3)과 서버 재검증

- **작업 번호:** C-2 (② 파일 검사·저장·TXT/MD 읽기 마무리)
- **수정 파일:** `backend/main.py`, `backend/parsers.py` 보강판 반영(추출 기록 저장 `private_runs/<job_id>/extraction.json`·`agent_input.json`, 422 대신 공통 오류 모양 400, BOM 제거·strict UTF-8 디코딩, frontend/ 정적 제공 준비). `docs/day1.md` 갱신.
- **실행 명령:** 서버 재기동 후 가짜 TXT 2개 업로드 → 조회 → 작업 폴더 기록 검증(Python).
- **직접 확인한 결과 (실제 실행):**
  - 시험3: `private_runs/<job_id>/extraction.json`에 source_id(S001·S002)·행 locator(`1행`…)·텍스트·manifest·sha256이 남음. `agent_input.json`이 `fixtures/agent_input_mock.json`과 **완전 일치**. PASS
  - files 누락 요청 → HTTP 400 + 공통 ErrorObject 모양(UNSUPPORTED_FILE 안내). PASS
  - 동시 POST 다발 시 BUSY 409 동작 확인(서버 로그).
- **미실행 또는 실패 / 주의:**
  - **주의(테스트 도구):** 이 PC의 Git Bash curl은 `-F "company_name_hint=테스트 회사"` 같은 명령줄 한글을 CP949로 보내 힌트가 깨져 저장된다. 서버 문제 아님 — 브라우저 FormData·Python 클라이언트(UTF-8)로는 정상. 한글 필드 테스트는 curl 명령줄로 하지 말 것.
  - 시험6(B 화면 연동) 미실행: `frontend/index.html`이 들어오면 같은 서버 `/`에서 제공되도록 준비됨(서버 재시작 필요).
- **다음 작업:** ③ B와 화면 연결(시험6) → 여유 시 ④ A의 extract_company_info 1회 호출 연동.

---

## 작업 3 — 시험3 원본 대조·파일 처리 조건 검증·B 연동 준비·인수인계 (최신 기준)

- **작업 번호:** C-2 마무리, C-3(③ B와 화면 연결 — B 파일이 없어 준비까지만)
- **기준 문서 원본 위치:** `C:\Users\user\Downloads\04_C_백엔드_AI작업기준.md`
- 작업 2의 요약과 겹치는 부분은 이 절이 실행 근거를 포함한 최신 기록이다.

### 3-1. 서버 실행 상태 확인과 재시작

| 시점 | 확인 내용 |
|---|---|
| 시작 전 | `127.0.0.1:8000` 수신 프로세스 1개(PID 7828, `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`, `--reload` 없음). `GET /` 자리표시 페이지 응답 확인. 새로 띄우지 않음. |
| 코드 반영 | `--reload`가 없어 수정 코드가 반영되지 않으므로 PID 7828 종료 → 8000 포트 수신 0개 확인 → **같은 명령으로 1개만 재시작(PID 20192)**. |
| 재시작 영향 | 메모리에 있던 이전 작업은 사라짐(규격대로 조회 시 404 `JOB_NOT_FOUND`). `private_runs/`의 저장 파일은 그대로 남음. |
| 확인 시점 | 8000 포트 수신 프로세스는 PID 20192 하나. 서버 로그(`private_runs/server_stdout.log`, `server_stderr.log`)에 Traceback 없음. |

### 3-2. 수정 전 서버에서 직접 재현한 문제

가짜 데이터로 수정 전 서버(PID 7828)에 요청해 확인했다(탐침 스크립트는 작업용 임시 폴더에서 실행했고 프로젝트에는 넣지 않음).

| # | 요청 | 수정 전 결과 | 문제 |
|---|---|---|---|
| 1 | CP949(UTF-8 아님) 파일 + 정상 파일 | 202 → **ready** | 디코딩 실패를 경고만 남기고 성공 처리. 경고는 API에 보이지 않음 |
| 2 | 공백만 있는 파일 + 정상 파일 | 202 → **ready** | 빈 파일을 조용히 빼고 성공 처리 |
| 3 | 정상 파일 + 10MB+1바이트 파일 | 413은 맞음, **작업 폴더와 앞 파일이 남음** | 검사를 끝내기 전에 저장을 시작 |
| 4 | files 없이 company_name_hint만 | **422 `{"detail": ...}`** | 공통 오류 모양 `{"error": ErrorObject}`가 아님 |
| 5 | (코드 검토) `threading.Lock`을 쥔 채 `await f.read()` | 큰 파일 동시 업로드(6MB×3 + 소형 25건)를 5회 시도했으나 **재현 안 됨** | 이론상 이벤트 루프 전체가 멈출 수 있어 예방 차원에서 수정 |

### 3-3. 수정한 파일과 변경 이유

공개 API 주소·요청 필드·응답 JSON 키(`job_id`, `status`, `result`, `error`, ErrorObject 4개 키)는 **바꾸거나 추가하지 않았다.** 다른 담당자 파일과 부록 원문(contracts, fixtures, prompts, validate_fixtures.py)은 수정하지 않았다.

| 파일 | 변경 | 이유 |
|---|---|---|
| `backend/parsers.py` | UTF-8 strict 디코딩 실패 시 `UnsupportedEncoding` 예외. 빈 파일이나 공백만 있는 파일이 **하나라도** 있으면 `NeedsTextSource` 예외. 행 구분을 `\r\n`/`\r`/`\n`로 고정한 `split_lines()` 추가. 파일 맨 앞 BOM 제거(`utf-8-sig`). | 문제 1·2: 오류를 무시하고 성공 처리하지 않음. 행 번호 규칙을 코드로 고정해 D와 검증 코드가 같은 함수를 쓰게 함. |
| `backend/main.py` | ① 모든 파일의 개수·확장자·크기를 **저장 전에** 검사하고, 저장 중 예외가 나면 작업 폴더 삭제 ② `await`를 잠금 밖으로 이동 ③ 요청 형식 오류를 400 `{"error": ...}`로 응답 ④ UTF-8 실패 → `UNSUPPORTED_FILE`(stage `extracting`) ⑤ 추출 성공 시 `private_runs/<job_id>/extraction.json`, `agent_input.json` 저장(내부 기록, API 응답에는 미포함) ⑥ 예외 시 error를 먼저 채운 뒤 status=error로 바꾸고, stage는 예외가 난 단계로 기록 ⑦ 빈 `company_name_hint`는 null로 정리 ⑧ `frontend/index.html`(또는 환경변수 `FRONTEND_DIR`)이 있으면 서버 시작 시 `/`에서 정적 파일로 제공하고, 없으면 기존 자리표시 페이지 | 문제 3·4·5 수정, 추출 결과 보관, B 화면을 같은 서버·같은 origin에서 제공할 준비 |
| `scripts/check_backend.py` (신규) | HTTP 시험 28개 + 프로세스 내부 시험 9개. 실제 응답을 `handoff/api_examples.json`에 저장 | 시험 근거를 다시 실행할 수 있게 함 |
| `scripts/make_agent_input.py` (신규) | A 전달용 agent_input 생성(업로드 작업 기록 복사 또는 서버 없이 재생성) | A 인수인계 |
| `scripts/browser_api_check.mjs` (신규) | 헤드리스 Chrome에서 같은 origin의 `fetch`+`FormData`로 API 호출 검증 | B 화면 없이 할 수 있는 브라우저 쪽 연동 준비 확인 |
| `handoff/agent_input_example.json` (생성물) | A 전달용 가짜 agent_input | A 인수인계 |
| `handoff/api_examples.json` (생성물) | 실제 로컬 응답 예시 13종 | B 인수인계 |
| `docs/day1.md` | 작업 3 기록 추가(기존 작업 1·2 내용 유지) | — |

### 3-4. 실행 폴더·명령·주소

- 실행 폴더: `C:\Users\user\Documents\Codex\개발기준`
- 환경: Windows 11, Python 3.12.10, fastapi 0.141.1, uvicorn 0.51.0, httpx 0.28.1, Node v24.15.0, Chrome 153
- 서버 실행: `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`
- 서버 종료(PowerShell): `Get-NetTCPConnection -State Listen -LocalPort 8000`으로 PID를 확인한 뒤 `Stop-Process -Id <PID>`
- 주소: 화면 `http://127.0.0.1:8000/`, 생성 `POST http://127.0.0.1:8000/api/profiles`, 조회 `GET http://127.0.0.1:8000/api/profiles/{job_id}`
- 검증 명령(서버 실행 중):
  - `python scripts/check_backend.py` (서버 없이 내부 시험만 할 때: `--offline`)
  - `node scripts/browser_api_check.mjs`
  - `python validate_fixtures.py`
- 참고: 내부 시험 실행 시 `StarletteDeprecationWarning`(httpx 관련 경고)이 출력되지만 결과에는 영향이 없다. 한글 필드는 curl 명령줄 대신 브라우저나 Python으로 시험한다(작업 2 주의 참고).

### 3-5. 시험 결과(실제 실행)

**PASS가 뜻하는 범위:** 아래 표에 적힌 항목을 가짜 데이터로 실제 검사해 통과했다는 뜻뿐이다. 실제 기업 자료, 결과 내용의 사실성, 실제 Agent/LLM 호출, PDF/DOCX, 문서 파일 생성, B 화면 표시는 검사하지 않았다. 원문 행 대조는 표에 적힌 가짜 파일에만 했다. 서비스 전체가 성공했다는 뜻이 아니다.

| 시험 | 결과 | 근거(실행 명령·확인 방법) |
|---|---|---|
| 시험1 가짜 TXT 2개 업로드 | **통과** | `check_backend.py`: 202, `status=queued`, `result`·`error`=null, UUID job_id |
| 시험2 job_id 조회 | **통과** | 200 ready, 응답 키 4개, `result`가 `fixtures/mock_profile.json`과 dict 완전 일치, `is_mock=true` |
| 시험3 source_units — 추적 | **통과** | 작업 `7e658ea0-298b-413f-9319-fa77394eab53`의 `extraction.json`: S001→`mock_source_a.txt`, S002→`mock_source_b.txt`. `source_manifest`와 `stored_files`의 이름이 같고, 저장 파일 바이트·sha256이 원본 fixtures와 같음 |
| 시험3 source_units — 원본 대조 | **통과** | 원본 바이트에서 파서와 다른 방법(개행 통일 후 분할)으로 기대값을 만들어 비교. 7개 unit의 source_id·locator·text가 누락·추가 없이 일치(S001 1~5행, S002 1~2행) |
| 시험3 빈 줄 때문에 번호가 달라지지 않는지 | **통과** | 빈 줄·공백 행·CRLF·BOM·마지막 개행 없음이 섞인 가짜 TXT → `1행, 4행, 7행, 8행`(원본 행 번호 그대로). 기대값을 코드에 직접 적어 비교했고, BOM은 text에 섞이지 않음 |
| 시험3 `extract_sources` 반환 구조 | **통과** | 직접 호출하면 목록 3개로 된 튜플을 반환. unit 키 `{source_id, locator, text}`, manifest 키 `{source_id, file_name, document_date}`, `document_date=None`, warnings는 문자열 목록(현재 빈 목록) |
| 시험3 추출 결과 보관 | **통과(보완 후)** | 수정 전에는 메모리에만 있어서 밖에서 확인할 수 없었고 재시작하면 사라짐 → 이제 `private_runs/<job_id>/extraction.json`, `agent_input.json`에 저장. 공개 API 키는 추가하지 않음 |
| 시험3 agent_input | **통과** | 키는 `schema_version`·`company_name_hint`·`source_units` 세 개뿐이고, source_units는 추출 기록과 같으며, 부록 `fixtures/agent_input_mock.json`과 완전 일치 |
| 시험3 Mock과 업로드 추출 결과 구분 | **통과** | ready의 `result.sources`는 Mock 고정값(`mock_source_a.txt`, `mock_source_b.txt`) 그대로. 다른 이름의 파일을 올려도 Mock sources·evidence를 업로드 manifest로 바꾸지 않음(코드 주석에 명시) |
| 시험4 MD 정상 처리 | **통과** | 가짜 `company_test.md` → ready, 저장명 `S001.md`, `# 제목`·`- 목록`·`[링크](...)`를 원본 행 그대로 보존(1·3·4·6·7행), hint 전달 |
| 시험4 공백만 있는 파일 / 0바이트 | **통과** | error `NEEDS_TEXT_SOURCE`(extracting), result=null, agent_input 미생성 |
| 시험4 정상 + 공백 파일 | **통과(수정 후)** | 수정 전 ready → 수정 후 error `NEEDS_TEXT_SOURCE` |
| 시험4 UTF-8 디코딩 실패 | **통과(수정 후)** | CP949 단독, 정상+CP949, UTF-8 중간에 잘못된 바이트가 든 파일 3가지 모두 error `UNSUPPORTED_FILE`(extracting). 대체 문자로 바꿔 성공 처리하지 않음 |
| 시험4 파일 개수 초과 | **통과** | 4개 → 400 `INPUT_TOO_LARGE`, 작업 폴더 생성 안 됨 |
| 시험4 파일당 크기 초과 | **통과(수정 후)** | 정상+10MB+1바이트 → 413 `INPUT_TOO_LARGE`, 작업 폴더·앞 파일 저장 안 됨. 정확히 10MB는 크기 검사를 통과한 뒤 글자 수 초과로 error |
| 시험4 추출 텍스트 총량 초과 | **통과** | 정확히 40,000자 → ready(`total_chars=40000`). 40,001자 → error `INPUT_TOO_LARGE`(extracting), agent_input 미생성, 저장 원본은 자르지 않은 바이트 그대로 |
| 시험4 미지원 확장자 | **통과** | 정상+.pdf → 415 `UNSUPPORTED_FILE`, 작업 폴더 생성 안 됨 |
| 시험4 files 없음 | **통과(수정 후)** | 400 `{"error": {code: UNSUPPORTED_FILE, ...}}` (수정 전에는 422 `detail`) |
| 처리 중 예외 → error 종료 | **통과(내부 시험)** | TestClient·임시 폴더에서 추출 함수와 Mock 로드를 각각 강제로 실패시킴 → status=error, result=null, `INVALID_OUTPUT`, 예외 메시지·내부 경로 미노출. 실행 중인 서버에서 예외를 일으킨 시험은 아님 |
| 실패 후 다음 정상 작업 | **통과** | HTTP: 여러 오류 뒤 가짜 TXT 2개 → ready. 내부 시험: 강제 예외 뒤 → ready(BUSY로 막히지 않음) |
| 시험5 없는 작업 번호 | **통과** | 404 `JOB_NOT_FOUND` |
| 동시 업로드 | **통과** | 약 5MB 파일 4건 동시 → `[409, 202, 409, 409]`. 서버가 멈추지 않고 모두 응답했고, 409는 `BUSY` 모양 |
| 문서 API | **통과** | 409 `DOCUMENT_FAILED`, 성공을 반환하지 않음 |
| 화면 제공 방식 | **통과(연결 방식만)** | 내부 시험: 임시 `index.html`/`app.js`를 `FRONTEND_DIR`로 지정하면 `/`와 `/app.js`를 제공하고 API가 우선함(POST 202 → GET ready, 404 JSON). 폴더가 없으면 자리표시 페이지. 임시 파일은 시험용이며 B 화면이 아님 |
| 브라우저 fetch 연동 준비 | **통과(API 호출만)** | `browser_api_check.mjs`: HeadlessChrome 153, origin `http://127.0.0.1:8000`, FormData(`files` 반복, `company_name_hint`), Content-Type 수동 지정 없음. 정상 2회 ready(result==Mock), UTF-8 아님→error `UNSUPPORTED_FILE`, 공백→error `NEEDS_TEXT_SOURCE`, .pdf→415, files 없음→400, 없는 작업→404. 7/7 |
| `validate_fixtures.py` | **통과(부록 Mock 범위만)** | JSON Schema, 부록 Mock의 인용 위치, fact_id 중복, 초안 연결, API 예시 일치만 검사 |
| **시험6 B 화면에서 반복 실행** | **미실행** | B 프론트 파일이 프로젝트와 사용자 폴더에 없음(3-8 참고). 대체 화면을 만들지 않음 |
| 합계 | `check_backend.py` 37/37, `browser_api_check.mjs` 7/7 | 위에 적힌 항목만 해당 |

### 3-6. A에게 넘길 agent_input

- **위치:** `handoff/agent_input_example.json` (가짜 자료)
- **만든 방법(실제 실행):** 서버에 가짜 TXT 2개(`mock_source_a.txt`, `mock_source_b.txt`, hint `테스트 회사`)를 업로드 → 서버가 추출 직후 `private_runs/7e658ea0-298b-413f-9319-fa77394eab53/agent_input.json` 저장 → `python scripts/make_agent_input.py --job 7e658ea0-298b-413f-9319-fa77394eab53`로 복사
- **다시 만드는 방법:**
  - 서버로 만들기: 서버 실행 → 가짜 TXT 2개 업로드(`python scripts/check_backend.py` 출력 마지막에 복사 명령이 나옴) → `python scripts/make_agent_input.py --job <job_id>`
  - 서버 없이 만들기: `python scripts/make_agent_input.py` (fixtures TXT를 같은 파서로 직접 추출)
  - 두 방법의 결과 파일이 바이트 단위로 같고, 부록 `fixtures/agent_input_mock.json`과도 같음을 확인
- **모양:** `{"schema_version": "1.0", "company_name_hint": "테스트 회사" 또는 null, "source_units": [{"source_id", "locator", "text"}]}` — 키 세 개만
- **A가 알아야 할 것:**
  - 첫 반환은 `company_info` 객체(추출 중간 결과)이며 최종 ProfileResult가 아니다. C는 이를 ready 응답으로 포장하지 않는다.
  - `sources`·`is_mock`·`validation`은 서버가 채운다. evidence의 source_id·locator에는 source_units에 실제로 있는 값만 쓸 수 있다.
  - 현재 서버는 A 함수를 호출하지 않는다(ready 결과는 고정 Mock).

### 3-7. D가 이어받을 것

- **파서 함수:** `backend/parsers.py`
  - `extract_sources(stored_files) -> (source_units, source_manifest, warnings)`
  - `split_lines(text) -> list[str]` — 행 번호의 기준. 근거 인용 검사(`validate_company_info`)도 이 함수로 행을 나눠야 locator와 같은 행을 가리킨다.
  - 예외: `UnsupportedEncoding`(서버가 `UNSUPPORTED_FILE`로 응답), `NeedsTextSource`(`NEEDS_TEXT_SOURCE`). 문제 파일이 하나라도 있으면 작업 전체를 error로 끝낸다(건너뛰고 성공 처리하지 않음).
- **저장 파일 정보(stored_files):** 서버가 만든다. `{"source_id": "S001", "stored_path": "<절대경로>\\private_runs\\<job_id>\\S001.txt", "display_name": "원본이름.txt"}`. 저장명은 `S00N` + 소문자 확장자이며, 원본 이름은 표시용으로만 쓴다.
- **자료 ID 규칙:** 한 작업 안에서 업로드 순서대로 `S001`, `S002`, `S003`. 작업이 다르면 같은 ID가 다른 파일일 수 있으므로 `job_id`와 함께 추적한다.
- **행 위치 규칙(TXT/MD):**
  - `locator = "N행"`. N은 1부터 시작하는 원본 행 번호이고, 행 구분은 `\r\n`, `\r`, `\n`만 인정한다.
  - 빈 행이나 공백만 있는 행은 unit을 만들지 않지만 번호는 센다.
  - `text`는 행 앞뒤 공백만 제거한다. 행 내부는 바꾸거나 자르지 않고, 파일 맨 앞 BOM만 제거한다.
  - MD도 같은 규칙을 쓴다(마크다운 기호를 해석하거나 지우지 않음).
  - 추출 텍스트 총량 = 모든 unit `text`의 글자 수 합(바이트 아님, 빈 행 제외).
  - 참고: `validate_fixtures.py`는 `str.splitlines()`를 쓴다. 동봉 가짜 TXT에서는 결과가 같지만, `\x0c`·`\u2028` 같은 특수 구분 문자가 있는 파일에서는 행 번호가 달라질 수 있다.
- **추출 예시:** `private_runs/7e658ea0-298b-413f-9319-fa77394eab53/extraction.json`(`stored_files`의 크기·sha256, `source_manifest`, `warnings`, `source_units`, `total_chars`, 상한값 포함). 서버 없이 볼 예시는 `handoff/agent_input_example.json`.
- **PDF/DOCX:** 미구현. 추가할 때 같은 반환 모양을 지키고, locator 규칙(예: 쪽·문단)은 팀과 새로 정해야 한다.
- **문서 규격(아직 미연결):** `render_document(profile, output_dir, format)`는 실제 출력 파일 Path를 반환한다. 연결 전까지 문서 API는 409 `DOCUMENT_FAILED`.

### 3-8. B 화면 연동 상태

- **B 파일 확인 결과: 없음.**
  - `개발기준` 폴더에는 html/js/css가 없다.
  - `Documents`·`Downloads`·`Desktop`을 검색하니 `Documents\ChatGPT\geosan-agent-starter\ui\static\index.html`·`app.js`가 있었다. 하지만 “거산케미칼 방문 준비 시연” 화면이고 `/api/action`·`/api/session`을 호출한다. `/api/profiles`·`files`·`company_name_hint`를 쓰지 않으므로 **B의 회사소개서 화면이 아니라고 판단**했다. 수정하거나 연결하지 않았다.
  - 대체 화면을 만들지 않았고, **B 연동은 완료되지 않았다(시험6 미실행)**.
- **백엔드 쪽 준비 완료:** 화면 제공 방식 구현과 내부 시험, 브라우저 fetch 검증(3-5), 실제 응답 예시 저장(`handoff/api_examples.json`)

#### B에게 전달할 내용

- **한 컴퓨터에서 함께 실행하는 방법**
  1. B 화면 파일을 `C:\Users\user\Documents\Codex\개발기준\frontend\`에 넣는다(`frontend\index.html` 필수). 파일을 옮기지 않으려면 서버 실행 전에 PowerShell에서 `$env:FRONTEND_DIR="B 화면 폴더 경로"`를 지정한다.
  2. 개발기준 폴더에서 `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`를 한 번만 실행한다. 이미 떠 있으면 종료한 뒤 다시 실행한다(화면 파일은 서버 시작 시에만 인식).
  3. 브라우저에서 `http://127.0.0.1:8000/`를 연다. 화면과 API가 같은 origin이므로 CORS 설정이 필요 없다.
- **화면 제공 방식:** 폴더 안 파일을 그대로 정적 파일로 제공한다(`/` → `index.html`, `/app.js` → `frontend/app.js`). 빌드 도구(Vite 등)를 쓰면 다른 포트의 개발 서버가 아니라 **빌드 결과 폴더**를 넣는다. `/api/`로 시작하는 경로에는 화면 파일을 두지 않는다.
- **API 주소(상대 경로로 호출):** `POST /api/profiles`, `GET /api/profiles/{job_id}` (다른 호스트·포트를 코드에 적지 않음)
- **요청 필드:** `multipart/form-data`
  - `files`: 파일 1~3개. 같은 이름으로 반복해서 `append`한다. 첫날은 UTF-8 `.txt`/`.md`만 받는다.
  - `company_name_hint`: 선택 문자열(빈 값이면 서버가 null로 처리)
  - `fetch`에 `Content-Type`을 직접 지정하지 않는다(브라우저가 boundary를 설정).
- **조회 규칙:** 202에서 받은 `job_id`로 약 1초 간격으로 GET한다. `status`가 `ready` 또는 `error`이면 멈춘다. HTTP 상태가 200이 아니면(`404` 등) 멈추고 `error.message`를 표시한다. 진행 상태는 `queued`→`extracting`까지만 실제로 나타난다(분석 단계 연출 없음).
- **표시 규칙:** `result.is_mock === true`이면 “테스트 데이터”를 표시한다. 결과 내용은 고정 Mock이며 업로드한 파일을 분석한 것이 아니다. 화면을 닫아도 서버 작업은 취소되지 않는다.
- **실제 응답 예시:** `handoff/api_examples.json` (2026-09-15 로컬 실행 결과. `python scripts/check_backend.py`를 다시 실행하면 새 job_id로 다시 저장됨)
  - 정상 접수 `202`: `{"job_id": "25f092fd-3972-4d54-a0a9-68a3d2ddeff1", "status": "queued", "result": null, "error": null}`
  - 정상 조회 `200`: `{"job_id": "25f092fd-…", "status": "ready", "result": { fixtures/mock_profile.json과 동일 }, "error": null}`
  - 작업 실패 `200`: `{"job_id": "291beeef-8e96-49f8-b825-688ef0e8cc53", "status": "error", "result": null, "error": {"code": "UNSUPPORTED_FILE", "stage": "extracting", "message": "cp949.txt: UTF-8로 읽을 수 없는 파일입니다. UTF-8로 저장한 TXT/MD를 사용해 주세요.", "retryable": false}}`
  - 그 밖의 작업 실패(`200`, status=error): `NEEDS_TEXT_SOURCE`(빈 파일), `INPUT_TOO_LARGE`(추출 텍스트 40,000자 초과)
  - HTTP 오류(본문은 `{"error": ErrorObject}`): `400 INPUT_TOO_LARGE`(파일 4개), `400 UNSUPPORTED_FILE`(files 없음), `413 INPUT_TOO_LARGE`(10MB 초과), `415 UNSUPPORTED_FILE`(.pdf), `404 JOB_NOT_FOUND`, `409 BUSY`, `409 DOCUMENT_FAILED`
- **B에게 받아야 할 것**
  1. 화면 폴더 전체: `index.html`과 거기서 참조하는 JS·CSS·이미지(빌드 도구를 쓰면 빌드 결과 폴더). `개발기준\frontend\`에 넣거나 폴더 경로를 알려 준다.
  2. 빌드 도구 사용 여부와 빌드 명령(쓰는 경우), 확인에 쓸 브라우저
  3. 화면이 호출하는 API 주소·필드 이름이 위 규격과 같은지 B의 확인. 다르면 C가 B 파일을 고치지 않고, 대상 파일과 이유를 정리해 B에게 요청한다.
- **B 파일 도착 후 C가 할 일(남은 작업):** `frontend\`에 배치하거나 `FRONTEND_DIR` 지정 → 서버 재시작 → 실제 브라우저에서 ① 가짜 TXT 2개 선택 → POST → GET → result 표시 ② ready/error에서 조회 중단 ③ HTTP 오류(.pdf 415, 없는 작업 404) 표시 ④ “테스트 데이터”·`is_mock=true` 표시 ⑤ 반복 실행을 확인하고 시험6을 기록한다.

### 3-9. 팀 결정이 필요한 것

1. **상한값:** 파일 3개·파일당 10MB·추출 텍스트 40,000자는 **팀 합의 전 제안값**이다(코드 주석과 `extraction.json`의 `limits.note`에도 기록). 합의되면 `backend/main.py` 상단 상수만 바꾸면 된다.
2. **오류 코드 배정(C 제안, 규격에 명시 없음):** files 없음·요청 형식 오류 → 400 `UNSUPPORTED_FILE` / UTF-8 실패 → `UNSUPPORTED_FILE`(stage `extracting`) / 파일 0개·4개 이상 → 400 `INPUT_TOO_LARGE` / 예상하지 못한 내부 예외 → `INVALID_OUTPUT`(`retryable=true`). 규격에 범용 내부 오류 코드가 없어 임시로 배정했다.
3. **여러 파일 중 하나만 문제일 때:** 현재는 작업 전체를 error로 끝낸다. 문제 파일만 빼고 진행하려면 사용자에게 경고를 보여 줄 방법이 먼저 필요하다(현재 API에는 warnings 키가 없음).
4. **오류 메시지에 원본 파일 이름 포함:** 사용자가 올린 이름만 넣고 내부 경로·원문은 넣지 않는다. 이 방식이 괜찮은지 확인이 필요하다.
5. **행 구분 규칙:** `\r\n`/`\r`/`\n`만 행으로 본다(3-7 참고). 근거 검증 코드도 같은 규칙을 쓸지 D와 확인이 필요하다.

### 3-10. 추가하지 않은 것 · 임시 자료

- 실제 Agent 호출, PDF/DOCX 파싱, 문서 파일 생성, DB, 배포는 추가하지 않았다. ready 결과는 계속 고정 Mock(`is_mock=true`)이다.
- `private_runs/`에는 오늘 시험에 쓴 가짜 작업 폴더가 남아 있다(확인 시점 85개, 서버 로그 파일 2개 별도). 모두 가짜 데이터이며 Git 제외 대상이다. 위 근거 기록(`7e658ea0-…`)을 확인한 뒤 보관 정책에 따라 지운다(아직 삭제하지 않음).

---

## 작업 4 — 백엔드 마무리: 완료 상태 대조·의존성·실행 방법·연결 자료

- **작업 번호:** C-4 (백엔드 범위만. 프론트 파일·화면 디자인·브라우저 화면 시험 제외)
- **범위 밖(추가하지 않음):** 실제 Agent 호출, PDF/DOCX 파싱, 문서 생성, DB, 배포

### 4-1. 완료 상태 대조 결과

- `backend/main.py`·`parsers.py`·`mock_agent.py`는 작업 3 검증(4:06) 이후 바뀌지 않았다. 실행 중인 서버(PID 20192)는 이 코드로 기동한 상태다.
- 생성·조회 API, TXT/MD 검사·저장·추출, 작업 상태와 오류 처리를 3-5 시험 기록과 대조했다. **새로 고쳐야 할 명확한 결함은 없어 코드를 수정하지 않았다.** HTTP 시험도 다시 실행하지 않았다(다시 실행하면 `handoff/api_examples.json`의 job_id가 바뀌어 이 문서의 참조와 어긋난다).
- 알려진 한계(첫날 범위에서 유지, 수정하지 않음):
  - 파일당 10MB 검사는 업로드 파일을 메모리로 읽은 뒤에 한다. 매우 큰 파일은 거절되기 전에 메모리를 쓴다.
  - POST 처리 중 디스크 쓰기 같은 예상하지 못한 예외가 나면 작업 폴더는 지우지만, 응답은 FastAPI 기본 500이다(`{"error": ...}` 모양 아님).
  - 작업 상태는 메모리에만 있다. 서버를 재시작하면 404 `JOB_NOT_FOUND`로 재업로드를 안내한다(규격대로).

### 4-2. 의존성·설치·실행 (Windows PowerShell 기준)

기존 의존성 관리 파일이 없어 새로 만들었다. 코드가 실제로 import하는 패키지만 넣고 검증한 버전으로 고정했다.

| 파일 | 내용 | 용도 |
|---|---|---|
| `requirements.txt` | `fastapi==0.141.1`, `uvicorn==0.51.0`, `python-multipart==0.0.32` | 서버 실행 |
| `requirements-dev.txt` | `-r requirements.txt` + `httpx==0.28.1`, `jsonschema==4.26.0` | `scripts/check_backend.py`, `validate_fixtures.py` |

- 필요 환경: Python 3.12(검증 3.12.10). 검증 스크립트 외 추가 도구는 필요 없다. `scripts/browser_api_check.mjs`(Node·Chrome)는 선택 항목이며 이번 범위에서 제외했다.
- 실행 폴더: `C:\Users\user\Documents\Codex\개발기준`
- 설치(처음 한 번):
  ```powershell
  cd C:\Users\user\Documents\Codex\개발기준
  python -m venv .venv
  .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt   # 서버만 필요하면 requirements.txt
  ```
  활성화 스크립트(`Activate.ps1`)가 실행 정책에 막힐 수 있으므로 `.venv\Scripts\python.exe`를 직접 부른다. `.venv/`는 `.gitignore`에 추가했다.
- 서버 실행(8000 포트에 이미 떠 있지 않은지 먼저 확인):
  ```powershell
  Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue   # 결과가 없을 때만 실행
  .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
  ```
  종료: 창에서 Ctrl+C. 백그라운드로 떠 있으면 위 명령으로 PID를 확인한 뒤 `Stop-Process -Id <PID>`.
- 백엔드 검증 명령:
  ```powershell
  .\.venv\Scripts\python.exe scripts\check_backend.py --offline   # 서버 불필요: 파서 구조·예외 처리·화면 제공 방식(9개)
  .\.venv\Scripts\python.exe validate_fixtures.py                 # 부록 Mock 형식·인용 위치만
  .\.venv\Scripts\python.exe scripts\check_backend.py             # 서버 실행 중: HTTP 28개 + 내부 9개. handoff\api_examples.json 새로 저장
  .\.venv\Scripts\python.exe scripts\make_agent_input.py          # A 전달용 agent_input 재생성
  ```
- **설치 목록 검증(실제 실행):** 작업용 임시 폴더에 빈 가상환경을 만들어 `requirements-dev.txt`만 설치했다. 그 환경에서 `check_backend.py --offline` 9/9 PASS, `validate_fixtures.py` PASS, `make_agent_input.py` 결과가 `handoff/agent_input_example.json`과 바이트 일치했고, `backend.main` import와 uvicorn 0.51.0 로드도 확인했다. 기존 서버와 겹치지 않도록 새 환경으로 HTTP 서버는 띄우지 않았다(HTTP 28개 시험은 작업 3에서 기존 환경으로 통과).
- 참고: 고정하지 않은 하위 패키지는 새 환경에서 starlette 1.6.0, pydantic 2.13.5로, 기존 환경은 starlette 1.3.1, pydantic 2.13.4였다. 두 조합 모두 내부 시험을 통과했다. 내부 시험 때 나오는 `StarletteDeprecationWarning`은 결과에 영향이 없다.

### 4-3. 백엔드 연결 자료 확인

기존 자료를 재사용했다. `handoff/api_examples.json`(4:06)과 `handoff/agent_input_example.json`(4:07)은 현재 코드(4:02)로 만든 실제 실행 결과다.

**POST /api/profiles** — `multipart/form-data`
- 요청 필드: `files`(1~3개, 같은 이름 반복, UTF-8 `.txt`/`.md`), `company_name_hint`(선택 문자열, 빈 값은 null)
- 정상 응답 202: `{"job_id": "<서버 UUID>", "status": "queued", "result": null, "error": null}` — 예시 `api_examples.json` › `POST 202 정상 접수`

**GET /api/profiles/{job_id}** — 응답 키는 항상 `job_id`, `status`, `result`, `error` 네 개

| status | result | error | 근거 |
|---|---|---|---|
| `queued`, `extracting` | null | null | 코드상 모양. 브라우저 조회 기록에서 `extracting` 관측(3-5). `analyzing`·`drafting`·`validating`은 현재 쓰지 않음(단계 연출 없음) |
| `ready` | `fixtures/mock_profile.json`과 같은 고정 Mock(`is_mock=true`) | null | `api_examples.json` › `GET ready (고정 Mock 결과)` |
| `error` | null | ErrorObject | `api_examples.json` › `GET error …` 3종 |

**HTTP 요청 오류와 작업 처리 오류의 구분**

| 구분 | 언제 | 응답 | 코드(예시 파일 항목) |
|---|---|---|---|
| HTTP 요청 오류 | 요청을 받는 즉시 거절. 작업·job_id·저장 폴더를 만들지 않음 | HTTP 4xx + 본문 `{"error": ErrorObject}` | 400 `INPUT_TOO_LARGE`(파일 4개 이상) · 400 `UNSUPPORTED_FILE`(files 없음·요청 형식 오류) · 413 `INPUT_TOO_LARGE`(파일당 10MB 초과) · 415 `UNSUPPORTED_FILE`(.txt/.md 아님) · 409 `BUSY`(진행 중 작업 있음) · 404 `JOB_NOT_FOUND`(없는 작업 조회) · 409 `DOCUMENT_FAILED`(문서 API 미구현) |
| 작업 처리 오류 | POST는 202로 접수된 뒤 추출 중 실패 | GET이 HTTP 200 + `status: "error"`, `result: null`, `error: ErrorObject` | `UNSUPPORTED_FILE`(UTF-8 디코딩 실패) · `NEEDS_TEXT_SOURCE`(빈 파일·공백만 있는 파일) · `INPUT_TOO_LARGE`(추출 텍스트 40,000자 초과) · `INVALID_OUTPUT`(예상하지 못한 내부 예외, `retryable: true`) |

화면 쪽 처리 기준: HTTP 상태가 2xx가 아니면 `error.message`를 표시하고 멈춘다. 200이면 `status`를 보고 `ready`/`error`에서 멈춘다.

**A — agent_input:** `handoff/agent_input_example.json`. 키는 `schema_version`·`company_name_hint`·`source_units` 세 개뿐이다. 생성 방법은 3-6과 같다(`scripts/make_agent_input.py`, 업로드 작업 기록 복사는 `--job <job_id>`). 이번에 빈 가상환경에서 다시 만들어 바이트 일치를 확인했다.

**D — extract_sources:** 입력 `stored_files`(`source_id`·`stored_path`·`display_name`), 반환 `(source_units, source_manifest, warnings)`, 예외 `UnsupportedEncoding`·`NeedsTextSource`, 자료 ID `S001`~(업로드 순서), 위치 `N행`(원본 행 번호, `\r\n`/`\r`/`\n` 기준, 빈 행은 번호만 셈)은 3-7이 최신이며 코드 docstring과 일치한다. 추출 예시는 `private_runs/7e658ea0-298b-413f-9319-fa77394eab53/extraction.json`이다(Git 제외 폴더이므로 전달할 때는 파일을 따로 복사).

**제안 상태 유지:** 상한값 3개·10MB·40,000자, 규격에 없는 경우의 오류 코드 배정, 여러 파일 중 하나만 문제일 때 전체 error 처리, 오류 메시지의 원본 파일명 포함, 행 구분 규칙은 모두 **팀 합의 전 C 제안**이다(3-9). 이번 작업에서 바꾸지 않았다.

### 4-4. 백엔드 완료 보고

- **완료한 백엔드 기능:** `POST /api/profiles`(검사·저장·작업 번호 발급), `GET /api/profiles/{job_id}`(상태·고정 Mock result·오류), TXT/MD UTF-8 추출(`extract_sources`)과 추출 기록 저장, 공통 오류 모양과 예외 시 error 종료, 동시 작업 1건 제한(BUSY), 문서 API의 규격 응답(성공 미반환), `frontend/` 정적 제공 준비
- **이번에 변경한 파일:** `requirements.txt`(신규), `requirements-dev.txt`(신규), `.gitignore`(`.venv/` 추가), `docs/day1.md`(작업 4 추가). 백엔드 코드는 변경하지 않음
- **실행·검증 근거:** 작업 3의 HTTP 28 + 내부 9 = 37/37 PASS(현재 코드와 같은 코드). 이번에 빈 가상환경에서 내부 시험 9/9, `validate_fixtures.py` PASS, agent_input 재생성 바이트 일치를 확인. 가짜 데이터로 적힌 항목만 검사했으며 실제 기업 자료·Agent·화면은 검사하지 않음
- **다른 담당자에게 전달할 파일:**
  - A: `handoff/agent_input_example.json`, `scripts/make_agent_input.py`
  - B: `handoff/api_examples.json`, 이 문서 3-8·4-3
  - D: `backend/parsers.py`, `private_runs/7e658ea0-298b-413f-9319-fa77394eab53/extraction.json`(복사해서 전달), 이 문서 3-7
  - 공통: `requirements.txt`, `requirements-dev.txt`, 이 문서 4-2
- **남은 백엔드 작업:**
  1. B 화면 파일이 오면 `frontend/`에 배치하고 서버를 재시작해 연결(시험6은 B 참여 필요)
  2. 팀 합의 결과(3-9)를 상수·오류 코드에 반영
  3. A의 `extract_company_info` 연결과 `validate_company_info` 등 검증 함수 연결(첫날 이후 범위)
  4. D의 `render_document` 연결 후 문서 API 구현(첫날 이후 범위)
  5. 시험 종료 후 `private_runs/` 가짜 작업 폴더 정리

---

## 작업 5 — 파일 크기 조각 검사·저장 실패 공통 오류 보완

- **작업 번호:** C-5. 4-1에 남긴 한계 두 가지(크기 검사 전 전체를 메모리로 읽음, 저장 실패 시 기본 500)를 보완했다. 그 밖의 API 규격과 동작은 유지했다.
- **범위 밖(추가하지 않음):** 프론트 파일·화면 시험, 실제 Agent, PDF/DOCX, 문서 생성, DB, 배포

### 5-1. 수정 파일

| 파일 | 변경 |
|---|---|
| `backend/main.py` | ① `_read_limited()`: 업로드를 1MB씩 읽으며 **실제 누적 바이트**를 세고, 10MB를 넘는 순간 읽기를 멈춘다. Content-Length나 `UploadFile.size`는 쓰지 않는다. 기존 413 `INPUT_TOO_LARGE`(stage `queued`) 응답은 그대로다 ② 작업 폴더 생성·파일 쓰기 실패: 이 요청이 만든 폴더만 지우고 **HTTP 500 `{"error": INVALID_OUTPUT, stage queued, retryable true}`**로 응답한다. 작업 등록 전이라 BUSY가 남지 않는다 ③ 추출 기록(`extraction.json`, `agent_input.json`)은 임시 파일에 쓴 뒤 교체한다. 쓰기에 실패하면 두 기록과 `.tmp`를 지우고 작업을 **status=error `INVALID_OUTPUT`(stage `extracting`)**으로 끝낸다. 업로드 원본(S00N)은 다른 error 작업과 같이 유지한다. 응답에는 예외 내용·경로를 넣지 않는다 |
| `scripts/check_upload_storage.py` (신규) | 이번 변경만 검증: 실행 중인 서버 HTTP 7개 + 내부 시험(TestClient·임시 폴더·예외 주입) 9개 |
| `handoff/api_examples_upload_storage.json` (신규) | 새 응답 예시 3종: 413(3개 중 2번째 초과), 500 저장 실패, GET error 추출 기록 저장 실패. 500·기록 실패 예시는 예외를 주입한 내부 시험에서 받은 응답이다 |

기존 `handoff/api_examples.json`(4:06), `handoff/agent_input_example.json`(4:07), `scripts/check_backend.py`, 이전 작업 폴더와 로그는 수정하지 않았다.

### 5-2. 실제 실행 명령

```powershell
cd C:\Users\user\Documents\Codex\개발기준
python -c "import backend.main"                        # 수정 코드 import 확인
# 서버 재시작: 기존 PID 20192 종료 → 8000 수신 0개 확인 → 같은 명령으로 1개만 기동(PID 6576)
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000   # 로그: private_runs\server_run2_stdout.log, server_run2_stderr.log
python scripts\check_backend.py --offline               # 기존 내부 시험 회귀 확인(handoff 파일 안 씀)
python scripts\check_upload_storage.py                  # 이번 변경 검증(서버 실행 중). 서버 없이: --offline
```

### 5-3. 검증 결과(2026-09-15 실제 실행)

`check_upload_storage.py` **16/16 PASS**, `check_backend.py --offline` **9/9 PASS**. 재시작한 서버 로그(`server_run2_*`)에 Traceback 없음.

| 시험 | 결과 | 근거 |
|---|---|---|
| 크기 정확히 10MB(10,485,760B, 1행+빈 행으로 추출 글자 수 13자) | 통과 | HTTP 202 → ready(Mock). 저장 크기·sha256이 보낸 파일과 같음(자르지 않음). job `cda1efd6-5aaa-4a8e-845a-1d3f33512b51` |
| 크기 10MB+1B | 통과 | HTTP 413 `INPUT_TOO_LARGE`(stage queued), 작업 폴더 생성 안 됨 |
| 3개 중 2번째만 10MB 초과 / 마지막만 초과 | 통과 | 둘 다 413, 작업 폴더·앞 파일 저장 안 됨 |
| 크기와 글자 수 제한 구분 | 통과 | 120KB·40,001자 → 202 후 error `INPUT_TOO_LARGE`(stage **extracting**), job `63b1396e-…`. 정확히 10MB지만 글자 수 초과 → 413이 아니라 202 후 error(stage extracting), job `df5ad57a-…`. 크기 초과는 stage **queued**의 HTTP 413으로 구분됨 |
| 요청 정보를 믿지 않는 조각 읽기 | 통과(내부) | size 정보를 1GB로 속인 실제 10MB → 전부 받음. size 정보를 1B로 속인 실제 20MB → 거절, 실제로 읽은 양 11,534,336B(10MB+1조각)에서 중단 |
| 폴더 생성 실패(예외 주입) | 통과(내부) | HTTP 500 `{"error": {"code": "INVALID_OUTPUT", "stage": "queued", "retryable": true}}`, 예외 문구·경로 미노출, 작업 폴더 없음 |
| 2번째 파일 쓰기 실패(예외 주입) | 통과(내부) | HTTP 500 `INVALID_OUTPUT`, 먼저 쓴 S001을 포함한 작업 폴더 삭제 |
| 작업 등록 뒤 추출 기록 쓰기 실패(반쯤 쓴 `.tmp`를 남기고 실패하도록 주입) | 통과(내부) | POST 202 → GET 200 status=error `INVALID_OUTPUT`(stage extracting), result=null, 미노출. 작업 폴더에는 `S001.txt`, `S002.txt`만 남고 `extraction.json`·`agent_input.json`·`.tmp`는 없음 |
| 각 실패 뒤 다음 정상 업로드와 Mock 조회 | 통과 | HTTP: 크기 초과 뒤 202 → ready(result==Mock), job `240a3b0f-386a-4806-924f-2846f81e2ef0`. 내부: 폴더 생성·파일 쓰기·기록 쓰기 실패 뒤 각각 202 → ready(BUSY 해제) |

- 저장 실패는 임시 폴더에서 `pathlib.Path.mkdir`·`write_bytes`·`write_text`에 테스트용 예외를 주입해서만 확인했다. 실제 디스크를 채우거나 폴더 권한을 바꾸지 않았다.
- HTTP 시험으로 `private_runs/`에 가짜 작업 폴더 4개가 새로 생겼다(86 → 90). 위 job_id가 이번 실행의 새 근거이며, 작업 3·4의 job_id와 예시 파일은 이전 실행 근거로 그대로 둔다.

### 5-4. 연결 자료 변경점

- 4-3 “HTTP 요청 오류” 표에 **500 `INVALID_OUTPUT`(stage queued, retryable true) — 업로드 파일 저장 실패**가 추가된다. 예시는 `handoff/api_examples_upload_storage.json`에 있다.
- 4-3 “작업 처리 오류”의 `INVALID_OUTPUT`에 **추출 기록 저장 실패**(message “추출 결과를 저장하지 못했습니다…”)가 포함된다.
- 저장 실패에 `INVALID_OUTPUT`을 쓰는 것은 기존 코드를 재사용한 **C 제안**이다. 규격에 범용 내부·저장 오류 코드가 없기 때문이며, 팀 합의 전이다(3-9의 2번에 추가).

### 5-5. 남은 한계

- Starlette(python-multipart)는 핸들러가 실행되기 전에 요청 본문 전체를 자체 임시 파일로 받는다. 이번 보완은 서버가 메모리로 읽고 `private_runs`에 저장하는 양을 제한할 뿐, 네트워크로 받는 요청 전체 크기는 제한하지 않는다. 그 임시 파일은 Starlette가 관리하며 따로 검증하지 않았다.
- 한 요청의 메모리 사용은 파일당 최대 10MB, 3개면 약 30MB다.
- 부분 폴더를 지우는 작업 자체가 실패하면(`ignore_errors`) 폴더가 남을 수 있다. 이 경우는 시험하지 않았다.
- 저장 실패 처리는 예외 주입으로만 확인했고 실제 디스크 부족·권한 오류로는 확인하지 않았다.
- 작업 상태는 계속 메모리에만 있고(재시작 시 404), 상한값 3개·10MB·40,000자와 오류 코드 배정은 팀 합의 전 제안값이다.
