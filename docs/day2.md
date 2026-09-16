# 수요일(2026-09-16) 작업 기록 — C 백엔드

기준 문서: `docs/04_C_수요일_업무서.md` + `contracts/day2_addendum.md`(실행안 r2) / 공통 데이터 규격 v1.0 유지
(첫 기록에 적었던 `docs/04_C_수요일_AI작업기준.md`는 **실제로 없는 경로**였다. 16:27에 원본
`Downloads\04_C_수요일_업무서.md`를 기준 폴더 `docs/`로 복사해 경로를 맞췄다. `docs/04_C_백엔드_AI작업기준.md`는
화요일(2026-09-15 / 안내판 r1) 기준이며 수요일 기준으로 대체하지 않는다.)
통합 기준 폴더: `Documents\Codex\final-project\projects\02-company-profile` (Git, 커밋 d9c4072 이후 작업)

## 작업 1 — 공용 코드 수령·통합 기준 폴더 확정

- **받은 것:** `Downloads\FINAL_geosan_공용기준_0916.zip`(공용 코드), `거산케미칼_수요일_4인_실행자료.zip`(수요일 기준·day2 픽스처).
- **비교 결과(폴더 덮어쓰기 없이 diff로 차이만 확인):**
  - `backend/main.py`, `backend/parsers.py`, `contracts/*`, `fixtures/mock_*`: 공용본과 로컬본 **완전 동일** → 로컬 유지.
  - 공용본에만 있음 → 가져옴: A의 `backend/agent.py`, 강화된 `prompts/extract.txt`(정성적 납기 표현 needs_confirmation 분류 등 2개 규칙 추가), A 스크립트 5개(`test_agent.py`, `check_model_schema.py`, `check_company_info_rules.py`, `check_openai_extract.py`, `test_openai_connection.py`), B의 `frontend/`(index.html, app.js, api.js).
  - 수요일 실행자료에서 가져옴: `contracts/day2_addendum.md`, `fixtures/day2_*`(supported_facts, draft_supported_example, variant_source_a/b, 테스트데이터 사용법).
  - 로컬이 최신이라 유지: `README.md`, `docs/day1.md`, `handoff/*`(이후 검증에서 재생성됨), `.env.example`.
- **하지 않은 것:** `contracts/`·`requirements*`·`prompts/`·`scripts/` 폴더째 덮어쓰기, 다른 담당자 파일 재구현, `.env`/`.venv` 공유.

## 작업 2 — 의존성·서버 환경

- **수정 파일:** `requirements.txt`(openai==3.14.0, python-dotenv==1.2.3, jsonschema==4.26.0 추가), `.env.example`(AGENT_MODE·OPENAI_API_KEY·OPENAI_MODEL 이름 추가, 값 없음).
- **실행:** 프로젝트 전용 `.venv` 신규 생성(Python 3.12.10) 후 `pip install -r requirements-dev.txt` 완료.
- **주의:** 이 PC에 `.env` 파일은 아직 없음(키 값은 만들지 않았고 어디에도 기록하지 않음).

## 작업 3 — 기존 Mock 흐름 재검증 (실제 실행)

| 검증 | 명령 | 결과 |
|---|---|---|
| 픽스처 규격 | `validate_fixtures.py` | PASS |
| 내부 시험 | `scripts/check_backend.py --offline` | 9/9 PASS |
| HTTP 시험(서버 127.0.0.1:8000 실행) | `scripts/check_backend.py` | 37/37 PASS, `handoff/api_examples.json` 재생성 |
| 업로드·저장 시험 | `scripts/check_upload_storage.py` | 16/16 PASS |
| A 오프라인 검사 | `scripts/check_model_schema.py`, `check_company_info_rules.py` | ALL PASS(이 PC 환경에서 A 코드 동작 확인) |
| B 화면 제공 | 브라우저로 `http://127.0.0.1:8000/` 접속 | B 화면 렌더링 확인(파일 선택·생성·상태·결과 영역), `/app.js` 200 |

- **미실시:** B와 함께하는 브라우저 클릭 흐름(가짜 TXT 2개 선택→202→ready 표시). 화면 제공까지만 확인했고 사람 클릭 시험은 남음.

## 작업 4 — 실제 호출 경로 연결 (AGENT_MODE=mock|llm)

- **수정 파일:** `backend/main.py`
  - `.env`의 `AGENT_MODE` 읽기(mock 기본). **오설정이면 서버 시작 거부**(조용히 mock 대체 금지).
  - llm 모드: `analyzing`에서 A의 `extract_company_info(agent_input)` 실제 호출. 중간 결과는 `private_runs/<job_id>/company_info.json`에 기록(이 값만으로 ready 금지).
  - 실행 기록 `run_meta.json`: agent_mode·llm_called·input_kind(가짜 자료)·is_mock. 테스트 표시(is_mock=true)와 실제 호출 여부를 분리 기록.
  - 오류 매핑: AgentError→해당 code(LLM_TIMEOUT만 retryable), .env 미설정→INVALID_OUTPUT(키 값 미노출), 기타 OpenAI 예외→INVALID_OUTPUT(상세는 서버 로그만). **어떤 실패도 Mock으로 대체하지 않음.** 실패 시 잠금 해제되어 다음 작업 수신 가능.
  - `draft_profile`(A)·`backend/validators`(D)가 없으면 각각 drafting/validating 단계에서 error로 종료. 준비되면 코드 수정 없이(모듈 존재 확인) 자동 연결.
  - mock 모드는 기존 첫날 경로 그대로(고정 Mock, is_mock=true) + run_meta 기록만 추가.
- **신규 파일(C 소유, r2 제안 채택):** `backend/profile_builder.py`
  - `collect_supported_facts` → day2 전달 규격, `build_draft_sections` → Mock의 13개 섹션 순서·제목 고정, supported는 A 문단만 사용(누락 시 오류, Mock 보충 금지), not_found="자료에서 확인되지 않음"/conflict·needs_confirmation="추가 확인 필요"(fact_ids=[]).
  - `build_needs_confirmation`(코드 생성 질문, facts에 있는 텍스트만 사용), `build_sources`(manifest 3필드, 날짜 모르면 null), `assemble_profile`(validation 플래그는 검사 전 False), `schema_errors`(jsonschema).
- **검증(실제 실행):**
  - `scripts/check_profile_builder.py` **11/11 PASS**: supported 수집=day2 규격 일치, 조립 결과=기존 Mock 13개 섹션과 일치·스키마 통과, supported 본문 누락/모르는 fact_id 참조 시 오류.
  - `scripts/check_llm_mode.py` **7/7 PASS**: AGENT_MODE 오설정 시 시작 거부, llm 모드+설정 없음→error(INVALID_OUTPUT/analyzing)·result null(Mock 대체 없음)·run_meta 기록·**실패 후 다음 작업 202 수신(BUSY 해제)**, 조회 응답 정상.

## 작업 번호별 실행 단계(오늘 실측 기준)

- mock 모드: queued → extracting(실제 추출·기록) → ready(고정 Mock). run_meta: llm_called=false.
- llm 모드(현재, .env 없음): queued → extracting → analyzing → **error**(LLM 설정 없음, retryable). run_meta: llm_called=false.
- llm 모드(키 설정 후 예상): analyzing(실제 호출)까지 성공 → company_info.json 기록 → drafting에서 error("본문 생성 기능 미연결") — draft_profile 도착 전까지의 의도된 동작. **실제 호출 성공은 아직 미확인.**

## 문서 형식별 상태

- MD: **여전히 409 DOCUMENT_FAILED**(D의 `backend/document_generator.py` 없음). 다만 아래 작업 7에서
  서버 쪽 연결 지점을 만들어 두어, D 모듈이 들어오면 C 코드 수정 없이 실제 파일 응답으로 바뀐다.
- DOCX: 같음(409). 형식 목록에는 넣었지만 실제 생성기는 없음.
- 어느 형식도 실제 파일을 만든 적이 없고, 사람이 파일을 열어 본 확인도 없음.

## 남은 의존성·다음 연결 지점

1. **A:** `draft_profile(supported_facts)` 함수 — 입출력 예시 전달 완료(`handoff/day2_전달사항.md`). 도착 시 `backend/agent.py`에 추가만 하면 서버가 자동 호출.
2. **A/사용자:** llm 모드 실제 호출 시험용 `.env`(OPENAI_API_KEY·OPENAI_MODEL) — 이 PC 미설정. 설정 후 가짜 TXT로 `analyzing` 실제 호출 확인 필요.
3. **D:** `backend/validators.py`(validate_draft·validate_profile_result), `backend/document_generator.py`(render_document)
   — 두 모듈 모두 서버가 자동으로 찾아 쓰는 연결 지점이 준비됨(파일만 넣으면 됨). 기대 입출력·예외 처리는 `handoff/day2_전달사항.md`.
4. **B:** 통합 기준 PC 브라우저 클릭 흐름 시험(서버 실행 중, 화면 제공 확인됨).
5. LLM 실행 중 상태 조회가 멈추지 않는지는 구조상 보장(BackgroundTasks 스레드풀)이나, 실제 느린 호출로는 미확인 → 키 설정 후 실측.

## 오늘 지킨 기준

공통 JSON v1.0·API 3개 경로 무변경, 다른 담당자 파일 재구현 없음(A draft_profile·D 모듈을 가짜로 만들지 않음), LLM 실패의 Mock 대체 없음, 중간 추출 결과로 ready 처리 없음, 가짜 자료만 사용(is_mock=true 유지, 실제 호출 여부는 run_meta 별도 기록), API 키 미기록·미커밋, 문서 API는 실제 파일 생성 전 성공 없음.

---

# 이어받은 세션(16:05~) — 환경 점검과 C 단독 진행분

## 작업 5 — 작업 경로·가상환경·서버 상태 확인 (실제 실행)

| 확인 | 결과 |
|---|---|
| 작업 폴더 | `projects\02-company-profile` (Git 루트는 `final-project`). 미커밋 변경 그대로 보존, 초기화·재clone 없음 |
| 프로젝트 `.venv` | Python 3.12.10, fastapi 0.141.1 / uvicorn 0.51.0 / **openai 3.14.0** / python-dotenv 1.2.3 / jsonschema 4.26.0 / httpx 0.28.1 → 그대로 재사용 |
| 8000 포트 | PID 25244, 15:58:30 시작. 이 프로젝트 코드 실행 중(최종 코드 수정 15:56:03보다 나중에 시작, `/`가 이 폴더의 B 화면 4,187바이트를 그대로 제공) → **재사용, 중복 실행하지 않음** |
| 현재 모드 | 가짜 TXT 2개를 실제로 올려 확인: 202 → ready, `run_meta.json`의 `agent_mode=mock`, `llm_called=false`, `result_is_mock=true`, 13개 섹션 |
| `.env` | 이 PC에 **없음**(키 값은 읽지도 만들지도 않았음) |

- **openai 버전 차이(확인된 사실):** 시스템(스토어) Python의 openai는 **1.58.1**로 `client.responses`가 없고,
  프로젝트 `.venv`는 **3.14.0**으로 있다(둘 다 직접 실행해 확인). 실제 호출은 `.venv`로 서버를 띄워야 한다.
- **정정(16:25):** 이 자리에 "실행 중이던 서버가 시스템 Python이라 llm 호출이 불가능하다"고 적었으나,
  근거로 쓴 것은 `Win32_Process.CommandLine`뿐이었다. `.venv\Scripts\python.exe`로 띄운 프로세스도
  명령줄에는 스토어 Python 경로가 그대로 찍힌다(16:25에 새로 띄운 서버에서 확인). 즉 명령줄로는 구분되지 않으므로
  **이전 서버가 어느 해석기였는지는 확인되지 않은 채 종료됐다.** 실제 구분은 적재된 site-packages 경로로 해야 한다.

## 작업 6 — 문서 API를 D의 render_document 연결 지점으로 구현 (C 소유, backend/main.py)

기존에는 ready여도 무조건 409를 돌려주고 요청 본문을 읽지 않았다. 계약(4절·8절)대로 다음을 구현했다.

- 요청 본문 `{"format":"md"|"docx"}`를 실제로 읽는다. 형식이 없거나 다른 값이면 409 DOCUMENT_FAILED.
- `backend/document_generator.py`가 있으면 `render_document(job["result"], <작업폴더>/documents, format)`를 호출한다.
  없으면 지금처럼 409(미연결 안내). **C가 대신 문서 생성기를 만들지 않았다.**
- 클라이언트가 보낸 profile·경로·파일명은 받지 않고 서버가 보관한 같은 job_id의 결과만 넘긴다.
- 반환값이 (1) 실제 파일이고 (2) 그 작업 폴더 안이며 (3) 요청한 형식의 확장자일 때만 성공으로 처리한다.
  아니면 409. D가 던진 예외도 409 DOCUMENT_FAILED로 바꾸고 상세는 서버 로그에만 남긴다.
- 성공 시 실제 파일 바이트 + `Content-Disposition: attachment` + 형식별 Content-Type.
- 문서만 실패한 경우 작업의 `result`와 `ready`는 그대로 둔다.

**검증:** `scripts/check_document_api.py` **18/18 PASS**(신규, C 소유).
D 모듈 자리에 **이 스크립트 안에서만 쓰는 시험용 임시 대역**을 끼워 성공/예외/폴더 밖 경로/형식 불일치를 확인했다.
대역은 `backend/`에 저장하지 않았고 **실제 문서 생성 기능이 아니다.** 이 검사 통과는 문서 기능 완료가 아니다.

## 작업 7 — supported 사실이 없을 때의 동작을 문서와 일치시킴 (backend/main.py)

`handoff/day2_전달사항.md`에는 "supported_facts가 비어 있으면 C가 A를 호출하지 않고 안내 문구로 조립한다"고
적어 두었는데, 코드는 supported가 하나도 없어도 `draft_profile` 없음을 이유로 drafting에서 멈췄다.
`supported_facts`가 있을 때만 A 함수를 요구하도록 고쳤다(없으면 안내 문구만으로 조립 후 validating으로 진행).

## 변경분 회귀 검증 (실제 실행, 바꾼 부분만)

| 검사 | 결과 |
|---|---|
| `scripts/check_document_api.py` (신규) | 18/18 PASS |
| `scripts/check_backend.py --offline` | 9/9 PASS |
| `scripts/check_profile_builder.py` | 11/11 PASS |
| `scripts/check_llm_mode.py` | 7/7 PASS |

전체 HTTP 시험(37건)·업로드 저장 시험(16건)은 이번에 바꾼 부분과 무관해 다시 돌리지 않았다.
문서 API의 바깥 동작은 오늘도 409로 같아서, 실행 중인 서버(변경 전 코드)를 그대로 써도 화면 시험 결과는 달라지지 않는다.

## 준비만 해 둔 것 — 실제 AI 호출 (아직 미실행)

- 신규 `scripts/check_llm_job.py`: 가짜 TXT 2개로 업로드 1건 = **OpenAI 호출 1회**만 하고,
  상태 변화·`run_meta.json`·`company_info.json` 요약을 출력한다. `--variant`로 변형 자료 시험.
  키 값은 읽지도 출력하지도 않는다.
- 실행 조건: (1) `.env`에 `AGENT_MODE=llm`·`OPENAI_API_KEY`·`OPENAI_MODEL`, (2) `.venv` python으로 서버 재시작.
- **아직 `.env`가 없어 실행하지 않았다. 실제 OpenAI 호출 성공은 여전히 미확인이다.**

## 실제 완료 / 미실행 / 수령 대기 구분

**오늘 실제로 실행해 확인한 것(C)**
- 기준 폴더·`.venv`·8000 서버가 이 프로젝트 것임을 실제 요청으로 확인(모드 mock, 실제 LLM 호출 없음).
- 문서 API 연결 지점 구현과 18개 항목 검사 통과(시험용 대역 기준).
- supported 없음 경로 수정, 바꾼 부분 회귀 검사 4종 통과.

**미실행(하지 않았고 성공으로 적지 않음)**
- 실제 OpenAI 호출(`.env` 없음) → `extract_company_info` 실제 성공 미확인.
- 브라우저 클릭 흐름(가짜 TXT 2개 선택 → 생성 → ready 표시): 주소·파일 위치·기대 결과만 안내했고 **사람 클릭 시험은 미실시**.
- 실제 MD/DOCX 파일 생성과 사람이 파일을 열어 본 확인.
- llm 모드에서 느린 호출 중 상태 조회가 막히지 않는지 실측.

**다른 담당자 수령 대기**
- A: `draft_profile(supported_facts)` — `backend/agent.py`에 함수 없음(검색 확인). `prompts/draft.txt`는 있으나 함수는 미도착.
- A/사용자: `.env`의 `OPENAI_API_KEY`·`OPENAI_MODEL`.
- D: `backend/validators.py`, `backend/document_generator.py` — 두 파일 모두 없음. 서버 연결 지점은 준비됨.
- B: 사람이 하는 브라우저 클릭 시험.

수령 대기 항목을 C가 대신 만들지 않았고, 실패를 Mock으로 대체하지 않았으며, 검사 전 성공 플래그를 넣지 않았다.


---

# 서버 상태 갱신 (16:4x, C)

- 이전 기록의 "실행 중인 서버(변경 전 코드)"는 그 뒤 종료되었고, **16:25:50에 다시 시작된 서버(PID 16844)가
  마지막 코드 수정(16:23:33) 이후에 뜬 것**이라 현재 8000 포트 서버는 최신 코드(문서 API 연결 지점 포함)를 싣고 있다.
- 다만 이 서버도 여전히 **Windows 스토어 Python**으로 실행 중이다(프로젝트 `.venv` 아님).
  mock 모드·화면 클릭 시험에는 문제가 없지만, **llm 시험 전에는 반드시 `.venv` python으로 재시작**해야 한다(작업 5의 위험 그대로).
- 실측(가짜 TXT 2개 실제 업로드): `/` B 화면 200 → POST 202 → ready(13개 섹션, is_mock=true),
  `run_meta.json` agent_mode=mock·llm_called=false, 문서 API md/pdf 모두 409 DOCUMENT_FAILED(형식 검사 포함 동작 확인).
- `.venv`로 중복 실행을 시도했으나 포트 점유(10048)로 바인딩 실패 → 서버 이중 실행 없음(단일 서버 유지).

---

# 이어받은 세션 2차(16:20~) — 문서 API 보완과 서버 재시작

## 작업 8 — 문서 API의 누락 보완 (backend/main.py, C 소유)

보완 전 코드가 실제로 검사한 것은 **(1) 파일 존재 (2) 작업 폴더 내부 (3) 확장자** 세 가지뿐이었다(코드 확인).
수요일 업무서 03-②의 "파일 존재·**크기** 확인"이 빠져 있었다. 다음을 더했다.

- **0바이트 파일은 성공으로 내려보내지 않는다** → 409 DOCUMENT_FAILED. 사람이 열어 보기 전까지 실패를 모르는 상태를 막는다.
- **경로 확인·크기 조회 중의 파일 오류(OSError)도 공통 문서 오류로** 처리한다(예외를 그대로 올려 500을 내지 않는다).
- **반환값이 경로가 아닌 경우**(dict·None 등)도 409로 끝낸다.
- 위 검사는 `_check_document_file()`로 모아 두었고, 실패 사유는 **서버 로그에만** 남기고 응답 문구는 공통 메시지로 통일한다.
- 어떤 실패에서도 그 작업의 `result`와 `ready`는 그대로 둔다.
- **동기 함수인 D의 `render_document`를 `run_in_threadpool`로 실행**하도록 바꿨다. 이전에는 async 엔드포인트 안에서
  직접 호출해 문서 생성이 오래 걸리면 이벤트 루프가 막혔다. 폴더 생성(`mkdir`)도 같이 스레드풀로 옮겼다.

**검증:** `scripts/check_document_api.py` **25/25 PASS**(기존 18개 + 신규 7개).
새로 확인한 것: 빈 파일 거부, 빈 파일 거부 후 result·ready 유지, 경로가 아닌 반환값(500 아님),
느린 생성(1.5초) 중 **상태 조회가 0.00초에 응답**(0.5초 미만), 느린 생성도 결국 200.

> 이 검사는 **시험용 임시 대역**으로 한 제한적 확인이다. `backend/document_generator.py`(D 소유)는 여전히 없고,
> **실제 문서 생성 성공·실제 MD 파일 열기 확인은 하지 않았다.** 둘을 같은 것으로 기록하지 않는다.

## 작업 9 — 올바른 Python으로 최신 서버 재시작 (실제 실행)

| 단계 | 결과 |
|---|---|
| 8000 포트 재확인 | PID **25244**(이전 보고와 같음), `uvicorn backend.main:app --host 127.0.0.1 --port 8000` |
| 이 프로젝트 서버인지 확인 | 새 업로드 1건 → 이 폴더 `private_runs/<job_id>/run_meta.json`이 실제로 생성됨 |
| 종료 | `taskkill /PID 25244`(정상 종료 요청) → 응답 없어 `Stop-Process`로 종료. **그 PID만** 종료, 다른 Python은 건드리지 않음 |
| 재시작 | `.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000` (작업 폴더에서, 최소화 창) |
| 새 PID | **16844** (16:25:50 시작) |
| 실제 해석기 확인 | 적재 모듈 경로가 `...\02-company-profile\.venv\Lib\site-packages\pydantic_core\...pyd` → **`.venv` 사용 확인** |
| 프로세스 수 | 단일 프로세스(=워커 1개). 이전 실행과 같게 `--workers` 플래그 없이 띄웠다(플래그를 주면 감독 프로세스가 하나 더 생긴다) |
| 현재 모드 | `.env`가 없어 **mock**. 새 업로드로 확인: 202 → ready, `agent_mode=mock`, `llm_called=false`, 13개 섹션 |
| 화면·문서 API | `GET /` 200(4,187바이트), `/app.js` 200, 문서 API(md) **409 DOCUMENT_FAILED**(D 모듈 없음) |

- 서버를 다시 띄웠으므로 **이전 job_id는 모두 없어졌다**(메모리 보관). 확인은 모두 새 업로드로 했다.

## 변경분 회귀 검증 (실제 실행)

| 검사 | 결과 |
|---|---|
| `scripts/check_document_api.py` | 25/25 PASS |
| `scripts/check_backend.py --offline` | 9/9 PASS |
| `scripts/check_llm_mode.py` | 7/7 PASS |

`check_profile_builder.py`·전체 HTTP 시험·업로드 저장 시험은 이번에 바꾼 부분(문서 API·서버 실행)과 무관해 다시 돌리지 않았다.

## 실제 AI 검증 — 여전히 미실행

- `.env` **없음**(16:27 재확인). 키 값을 읽거나 출력하거나 대화로 받지 않았다.
- 필요한 입력: 프로젝트 루트 `.env`에 `AGENT_MODE=llm`, `OPENAI_API_KEY`, `OPENAI_MODEL` 세 줄.
- 준비되면: 서버를 `.venv`로 다시 시작(지금 방식 그대로) → `scripts\check_llm_job.py` 1회 실행(업로드 1건 = 호출 1회).
  확인할 것은 추출 결과 저장(`company_info.json`)과 처리 중 상태 조회 응답이며,
  **추출 성공 ≠ 전체 작업 완료**로 나눠 기록한다.

## A/D 수령 여부 (16:27 재확인)

| 전달물 | 소유 | 상태 |
|---|---|---|
| `draft_profile(supported_facts)` | A | **미수령** (`backend/agent.py`에 함수 없음. `prompts/draft.txt`만 있음) |
| `backend/validators.py` | D | **미수령** (파일 없음) |
| `backend/document_generator.py` | D | **미수령** (파일 없음) |

세 함수 모두 서버가 파일만 들어오면 자동으로 찾아 쓰도록 연결 지점이 준비돼 있다. C가 대신 만들지 않았다.
함수가 들어오면 실제 입출력을 대조한 뒤 최종 결과와 MD 응답을 검증할 차례다(아직 대조할 대상이 없다).

## 완료 / 미실행 / 수령 대기 (2차 기준)

**실제로 실행해 확인한 것**
- 문서 API 보완(크기·파일 오류·경로 아닌 반환값·스레드풀) 및 25개 항목 검사 통과 — **시험용 대역 기준**.
- 8000 서버를 `.venv` Python으로 재시작하고 해석기·모드·화면·문서 API를 새 업로드로 확인.
- 기준 문서 경로 정정 및 수요일 업무서 기준 폴더 보존.

**미실행(성공으로 적지 않음)**
- 실제 OpenAI 호출(`.env` 없음).
- **사람이 하는 브라우저 클릭 시험** — 주소·파일·기대 결과만 안내했다. 형님이 확인해 주기 전까지 완료로 적지 않는다.
- 실제 MD/DOCX 파일 생성과 파일 열기 확인.
- llm 모드에서 느린 실제 호출 중 상태 조회 실측(대역으로 한 문서 생성 쪽만 확인했다).

**수령 대기**
- A: `draft_profile`. D: `validators.py`, `document_generator.py`. 사용자: `.env` 3개 항목.

**전달 여부 구분**
- `handoff/day2_전달사항.md`를 **작성**했다. 이 PC에서 A/B/D에게 **실제로 보냈는지는 확인되지 않았다**(전달 기록 없음).

---

# 팀 저장소 PR #1 보완 — A 모듈 미수령 상황 처리

브랜치 `feat/company-profile-backend`(base `develop`). 원본 개인 폴더가 아니라 팀 저장소
`agent-ddalgi`에서 작업한 내용이다.

## 무엇이 문제였나

팀 저장소에는 A의 `backend/agent.py`가 없다(A가 직접 올릴 파일이라 C가 넣지 않았다).
그 상태에서 `llm` 모드로 작업을 돌리면 `_run_llm_job()`이 함수에 들어오자마자
`from backend import agent`에서 실패했는데, 그 시점의 작업 상태가 아직 `extracting`이었다. 결과적으로

- 오류 단계가 `analyzing`이 아니라 `extracting`으로 기록되고,
- `run_meta.json`이 아예 남지 않아 **실제 호출을 하지 않았다는 사실이 기록되지 않았다**.

`scripts/check_llm_mode.py`가 이 두 가지를 잡아 2건 실패했다(초기 PR 본문에 그대로 적었다).

## 고친 내용 (`backend/main.py`)

- 모듈 적재보다 **먼저 `status`를 `analyzing`으로 바꾼다.** 실제 호출을 시도하는 단계가 `analyzing`이므로
  적재 실패도 그 단계의 오류로 남는다.
- 적재를 `_load_agent_module()`로 분리해 **원인을 세 가지로 구분**한다.

| 원인 | run_meta.json의 note | 사용자에게 보이는 안내 |
|---|---|---|
| A의 `backend/agent.py` 미수령 | `A의 backend/agent.py 미수령(추출 기능 미연결)` | 추출 기능이 아직 연결되지 않았습니다… |
| 모듈은 있으나 의존 패키지 없음(openai 등) | `agent 모듈이 필요로 하는 패키지 없음: <이름>` | AI 호출에 필요한 패키지가 설치되어 있지 않습니다… |
| 모듈 로드 중 다른 오류(문법 오류 등) | `agent 모듈 로드 중 오류(상세는 서버 로그)` | 추출 기능을 불러오지 못했습니다… |

- 공통 오류 코드는 계약 범위 안의 **`INVALID_OUTPUT`**, 단계는 **`analyzing`**이다. 새 코드를 만들지 않았다.
- **실제 AI를 부르지 못했으므로 `run_meta.json`에 `llm_called=false`와 위 사유를 남긴다.**
- `result=null`, `status=error`, **Mock 대체 없음**, 잠금 해제로 다음 작업 접수 가능 — 이전 동작 그대로 유지된다.
- **가짜 `agent.py`를 만들지 않았고, 실패하던 검사를 지우거나 건너뛰지 않았다.** 코드가 실제로 상황을 처리하게 고쳤다.

## 검증 (팀 저장소 코드 기준, 가짜 자료·오프라인)

| 검사 | 결과 |
|---|---|
| `scripts/check_llm_mode.py` | 9/9 PASS + 1건 건너뜀 |
| `scripts/check_backend.py --offline` | 9/9 PASS |
| `scripts/check_upload_storage.py --offline` | 9/9 PASS |
| `scripts/check_document_api.py` | 25/25 PASS (시험용 대역 기준) |
| `validate_fixtures.py` | PASS |

`check_llm_mode.py`에 실패 원인 구분 확인 2건을 더했다(`run_meta.note`, 안내 문구). 이 검사는 저장소에
`agent.py`가 있는지에 따라 기대값을 바꿔 판정한다.

**건너뛴 1건**: "의존성 누락 분류"는 `backend/agent.py`가 없으면 자동으로 시험할 수 없어 건너뛴다.
이 분기는 **저장소 밖 임시 사본**에 시험용 파일을 두고 한 번 확인했다(분류 PASS).
그 파일은 저장소에 넣지 않았고, 커밋에도 없다.

## 단정하지 않는 것

- **"A 파일이 올라오면 통과한다"고 적지 않는다.** 이번에 확인한 것은 *A 모듈이 없을 때* 서버가
  올바른 단계·코드·기록으로 실패한다는 것뿐이다. **A 코드를 받은 뒤에는 실제 연동을 다시 검증해야 한다**
  (`extract_company_info`의 실제 입출력, `.env` 설정, 실제 호출 성공, `company_info.json` 기록).
- 실제 OpenAI 호출, 실제 MD/DOCX 파일 생성, 브라우저 클릭 시험은 여전히 하지 않았다.

## 참고: 폴더가 갈라졌다

이 수정은 팀 저장소(`Documents\Codex\agent-ddalgi`)에만 적용했다. 개인 작업 폴더
(`final-project\projects\02-company-profile`)의 `backend/main.py`는 아직 이전 코드다.
개인 폴더에서 서버를 띄워 시험할 때는 이 차이를 감안해야 한다.
