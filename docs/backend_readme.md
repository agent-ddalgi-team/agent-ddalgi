# 회사소개서 초안 백엔드 (C 담당)

저장소 루트에 있는 `backend/`가 이 문서의 대상이다.

회사 자료(TXT/MD)를 받아 작업 번호를 주고, 그 번호로 초안 결과를 조회하는 로컬 백엔드다.
**실행 모드는 서버 설정 `AGENT_MODE`로 정한다.** `mock`(기본)은 고정 Mock 결과, `llm`은 A의
`extract_company_info()`와 필요한 경우 `draft_profile()`을 실제 호출한다. 어느 모드든 현재 입력은 가짜 테스트 자료뿐이므로
결과는 `is_mock=true`(테스트 표시)이며, 실제 LLM 호출 여부는 `private_runs/<job_id>/run_meta.json`에 따로 남는다.

- 자세한 작업·검증 기록: [day1.md](day1.md), [day2.md](day2.md)
- 공통 연결 규격: [contracts/contract.md](../contracts/contract.md), [contracts/profile.schema.json](../contracts/profile.schema.json)
- 담당자 전달 자료: [handoff/](../handoff/)

## 폴더 구조

```
agent-ddalgi/                (저장소 루트)
├─ backend/      main.py(API·모드 분기), profile_builder.py(C: 최종 조립),
│                parsers.py(TXT/MD 추출), mock_agent.py(고정 Mock 로드)
│                agent.py(A: 추출·본문 생성), validators.py·document_generator.py(D: 검사·문서 출력)
├─ contracts/    공통 규격 문서와 결과 JSON 스키마(+day2_addendum.md)
├─ fixtures/     검증된 가짜 테스트 데이터(실제 기업 자료 아님, day2 변형 자료 포함)
├─ handoff/      A·B·D에게 전달할 예시(agent_input, 실제 API 응답, 추출 기록)
├─ scripts/      C 검증 스크립트(check_*, make_agent_input)
├─ docs/         day1.md·day2.md(작업·검증 기록), backend_readme.md(이 문서)
├─ requirements.txt, requirements-dev.txt, validate_fixtures.py
└─ .env.example  환경변수 이름만(실제 값은 .env에 두고 커밋하지 않음)
```

프론트엔드는 별도 저장소 `agent-ddalgi-team/agent-ddalgi-frontend`에서 관리한다.
`backend/agent.py`·`prompts/`·`backend/validators.py`·`backend/document_generator.py`는 현재 포함되어 있다.


실행 중 생기는 `private_runs/`(업로드 원본·추출 기록·서버 로그)는 저장소에 올리지 않는다.

## 설치 (Windows PowerShell)

저장소 폴더 안에서 가상환경을 만든다(`.venv/`는 커밋하지 않는다).

```powershell
# agent-ddalgi 저장소 루트에서 실행
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt   # 서버만 실행하려면 requirements.txt
```

`Activate.ps1`이 실행 정책에 막힐 수 있으므로 `.venv\Scripts\python.exe`를 직접 부른다.

- `requirements.txt`: fastapi, uvicorn, python-multipart, openai, python-dotenv, jsonschema, python-docx (서버 실행·DOCX 출력)
- `requirements-dev.txt`: 위 + httpx (검증 스크립트)
- 검증 환경: Python 3.12.10, Windows 11

### 실행 모드(.env)

`.env.example`을 `.env`로 복사한 뒤 값을 채운다(`.env`는 커밋하지 않는다).

- `AGENT_MODE=mock`(기본): 고정 Mock 결과. `llm`: A의 실제 추출 호출. 그 외 값이면 서버가 시작을 거부한다.
- `llm` 모드는 `OPENAI_API_KEY`·`OPENAI_MODEL`이 필요하다. 실패하면 작업이 `error`로 끝나며 **Mock으로 대체하지 않는다.**
- 기업 자료의 외부 LLM 사용 허용이 확인되기 전에는 어느 모드든 가짜 테스트 자료만 넣는다.

## 서버 실행

```powershell
# agent-ddalgi 저장소 루트에서 실행
Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue   # 결과가 있으면 이미 실행 중
$env:AGENT_MODE="mock"   # 아래 HTTP 검증은 mock 서버 기준. 실제 호출 검증 때만 llm으로 변경
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

- 종료: 실행한 창에서 `Ctrl+C`. 백그라운드면 위 명령으로 PID를 확인한 뒤 `Stop-Process -Id <PID>`.
- 포트가 이미 쓰이면 `--port 8001`처럼 바꿔 실행한다.
- 127.0.0.1에만 바인딩한다. 외부 공개·LAN 공유용이 아니다.

## 주소와 API 문서

| 주소 | 내용 |
|---|---|
| `http://127.0.0.1:8000/` | 화면 자리. `frontend/index.html`(또는 `FRONTEND_DIR`)이 있으면 그 화면, 없으면 자리표시 페이지 |
| `http://127.0.0.1:8000/docs` | FastAPI 자동 API 문서(Swagger UI). 화면 요소를 CDN에서 받으므로 인터넷 연결이 필요하다 |
| `http://127.0.0.1:8000/redoc` | 같은 내용의 ReDoc 문서 |
| `http://127.0.0.1:8000/openapi.json` | OpenAPI 정의(인터넷 없이도 열린다) |

### API 요약

- `POST /api/profiles` — `multipart/form-data`. `files`(UTF-8 `.txt`/`.md` 1~3개, 같은 이름 반복), `company_name_hint`(선택). 성공 시 `202 {"job_id","status":"queued","result":null,"error":null}`
- `GET /api/profiles/{job_id}` — `{"job_id","status","result","error"}`. `ready`면 `result`에 완성 초안(mock 모드: 고정 Mock), `error`면 `error`에 오류 객체. llm 모드는 추출·본문 생성·조립·검사가 성공해야 `ready`가 된다. 추출 및 본문 생성의 시간 초과는 해당 단계의 `LLM_TIMEOUT`으로 끝난다.
- `POST /api/profiles/{job_id}/document` — 요청 본문 `{"format":"md"|"docx"}`. `ready` 결과로 실제 MD/DOCX 파일 바이트와 다운로드 헤더를 돌려준다. 모듈 미연결·지원하지 않는 형식·생성 실패는 `409 DOCUMENT_FAILED`이며 기존 `ready` 결과는 유지한다.
- 요청 자체가 잘못되면 HTTP 4xx/500 + `{"error": {...}}`. 접수 후 처리 실패는 조회에서 `status=error`로 구분한다. 실제 응답 예시는 `handoff/api_examples.json`, `handoff/api_examples_upload_storage.json`.

## 검증 실행

```powershell
# agent-ddalgi 저장소 루트에서 실행. HTTP 검증은 서버와 별도 PowerShell 창 사용
$env:AGENT_MODE="mock"   # .env가 llm이어도 내부 검증에서 실제 호출을 방지
.\.venv\Scripts\python.exe validate_fixtures.py                    # 가짜 fixtures 형식·인용 위치
.\.venv\Scripts\python.exe scripts\check_backend.py --offline       # 서버 없이 내부 시험 9개
.\.venv\Scripts\python.exe scripts\check_upload_storage.py --offline # 크기·저장 실패 처리 내부 시험 9개
.\.venv\Scripts\python.exe scripts\check_backend.py                 # mock HTTP + 내부 시험, 실제 MD/DOCX 다운로드 포함(handoff/api_examples.json을 새로 씀)
.\.venv\Scripts\python.exe scripts\check_upload_storage.py          # 서버 실행 중일 때 크기·저장 시험 16개
.\.venv\Scripts\python.exe scripts\make_agent_input.py              # A 전달용 agent_input 재생성
.\.venv\Scripts\python.exe scripts\check_profile_builder.py         # C 조립 모듈 픽스처 시험 11개
.\.venv\Scripts\python.exe scripts\check_llm_mode.py                # llm 모드 오류 경로 시험(실제 호출 없음)
.\.venv\Scripts\python.exe scripts\check_document_api.py             # 문서 API 연결부 시험 25개(시험용 대역 사용)
.\.venv\Scripts\python.exe scripts\check_llm_pipeline.py             # 실제 호출 차단, 가짜 Agent 결과로 조립·검사·오류 전달 6개
.\.venv\Scripts\python.exe scripts\test_validators.py               # 인용·본문 검사기
.\.venv\Scripts\python.exe scripts\test_document.py                 # 실제 MD/DOCX 생성과 오류 처리
.\.venv\Scripts\python.exe scripts\check_company_info_rules.py      # 추출 결과 규칙(실제 호출 없음)
.\.venv\Scripts\python.exe scripts\check_draft_rules.py             # 본문 규칙·조립 연결(실제 호출 없음)
.\.venv\Scripts\python.exe scripts\check_model_schema.py            # 모델용 JSON 스키마(실제 호출 없음)
```

한글 출력이 깨지면 실행 전에 `$env:PYTHONUTF8="1"`을 설정한다.
`check_llm_mode.py`는 `.env` 또는 `OPENAI_API_KEY`가 있으면 설정 누락 검사를 건너뛴다.
`check_llm_pipeline.py`는 Agent 결과를 가짜 값으로 대체하고 SDK 호출도 차단하므로 키 설정과 무관하게 실제 호출하지 않는다.
일부 검증은 `handoff/`의 응답 예시를 갱신하고 `private_runs/`에 가짜 작업·문서를 만든다.

실제 LLM 검증은 별도로 `AGENT_MODE=llm`, `OPENAI_API_KEY`, `OPENAI_MODEL`을 설정한 서버에서
`scripts/check_llm_job.py`를 실행한다. 한 작업에서 추출과 본문 생성 호출이 일어날 수 있다.
이 스크립트의 성공 판정은 중간 추출 결과 기준이므로 최종 `ready`·본문 품질·문서까지 보장하지 않는다.

PASS는 각 스크립트가 출력한 항목만 검사해 통과했다는 뜻이며, 실제 기업 자료·사실성·실제 LLM 호출은 검사하지 않는다.

## 구현 범위 (현재 코드 기준; day1.md·day2.md는 당시 작업 기록)

**구현·검증 완료**
- TXT/MD 수신, 개수·확장자·크기 검사, `private_runs/<job_id>/`에 저장, 작업 번호 발급
- UTF-8 추출(`extract_sources`): 자료 ID `S001…`, 위치 `N행`(원본 행 번호 유지), 추출 기록과 `agent_input.json` 저장
- 조회 API의 상태·결과·오류, 공통 오류 객체, 예외 발생 시 `status=error` 종료, 동시 작업 1건 제한(BUSY)
- 파일당 10MB는 1MB씩 읽으며 누적 바이트로 검사하고, 추출 텍스트 40,000자 초과는 자르지 않고 오류 처리
- 저장 실패 시 부분 파일 정리와 공통 오류 응답

**수요일 추가(docs/day2.md)**
- `AGENT_MODE=mock|llm` 분기, llm 모드에서 A의 `extract_company_info()` 실제 호출 경로 연결
- C 조립 모듈 `backend/profile_builder.py`(supported 수집·13개 섹션 조립·질문·출처·스키마 검사)
- 실행 기록 `run_meta.json`(모드·실제 호출 여부), 중간 추출 결과 `company_info.json`
- A의 `draft_profile()` 본문 생성과 D의 `validate_draft`/`validate_profile_result` 연결.
- 문서 API와 D의 `render_document` 연결(실제 파일·작업 폴더 내부·확장자·0바이트 검사, 스레드풀 실행).
  Mock 결과의 실제 MD/DOCX 생성·다운로드·본문/부록 내용은 HTTP 검증으로 확인한다.

**별도 검증 또는 구현이 필요한 것**
- 실제 LLM 호출의 성공·본문 품질·사실성(가짜 응답을 사용한 연결부 시험으로 대체할 수 없음)
- PDF/DOCX 입력 파싱, DB, 배포
- MD/DOCX 문서의 시각적 레이아웃·Word에서의 표시(자동 내용 검사와 별개)
- 브라우저 클릭 흐름 시험(B와 함께): 화면 렌더링·정적 제공까지만 확인됨

**팀 합의 전 제안값**: 파일 3개·파일당 10MB·추출 텍스트 40,000자, 규격에 없는 경우의 오류 코드 배정. 자세한 내용은 docs/day1.md 3-9·5-4.

## 화면(B) 연결

`frontend/index.html`을 이 폴더 안에 두거나, 서버 실행 전에 `$env:FRONTEND_DIR="화면 폴더 경로"`를 지정한 뒤 서버를 시작하면 같은 주소에서 화면이 제공된다. 자세한 전달 사항은 docs/day1.md 3-8.
