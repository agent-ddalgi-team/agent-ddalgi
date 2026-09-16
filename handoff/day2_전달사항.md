# 수요일(2026-09-16) C → A/B/D 전달사항

통합 기준 폴더: `Documents\Codex\final-project\projects\02-company-profile` (Git 관리).
공용 `FINAL_geosan_공용기준_0916.zip`에서 A의 `backend/agent.py`·강화된 `prompts/extract.txt`·테스트 스크립트,
B의 `frontend/` 3개 파일을 이 폴더로 합쳤다. `contracts/`·`fixtures/`·C 서버 코드는 기존 것을 보존했다.

## B에게

- 실행 주소: `http://127.0.0.1:8000/` — B의 index.html/app.js/api.js가 이 서버 "/"에서 그대로 제공된다(상대 경로 그대로 동작).
- 현재 모드: `AGENT_MODE=mock`(기본). 202 → queued → ready 흐름과 오류 응답은 화요일과 동일.
- llm 모드일 때 달라지는 점: A의 `draft_profile`·D의 검사 모듈이 연결되기 전에는 `analyzing`(성공 시 `drafting`)까지 진행 후 **status=error**로 끝난다. ready가 나오면 그때는 완성 초안이다. 오류 코드는 기존 목록 그대로(INVALID_OUTPUT, LLM_TIMEOUT 등), 화면 수정 필요 없음.
- 문서 API: 아직 모든 형식이 `409 DOCUMENT_FAILED`(MD/DOCX 모두 미준비). D의 render_document 연결 후 MD부터 열린다.
- 남은 확인: 통합 기준 PC에서 브라우저로 가짜 TXT 2개(fixtures/mock_source_a.txt, mock_source_b.txt) 업로드 → ready 표시까지 클릭 흐름을 함께 확인해야 한다(서버·화면 제공은 확인 완료, 클릭 시험은 미실시).

## A에게

- `extract_company_info()` 호출 경로를 서버에 연결했다: 업로드 → 파서 `source_units` → `agent_input`(schema_version 1.0, company_name_hint, source_units) → `analyzing`에서 호출. 입력 예시는 `handoff/agent_input_example.json`, 실제 업로드 기준 재생성은 `scripts/make_agent_input.py`.
- 오류 매핑: `AgentError.code`(NEEDS_TEXT_SOURCE/INPUT_TOO_LARGE/LLM_TIMEOUT/INVALID_OUTPUT)는 그대로 작업 오류로 쓴다. `.env` 미설정(RuntimeError)과 그 밖의 OpenAI 예외는 INVALID_OUTPUT으로 변환하고 상세는 서버 로그에만 남긴다.
- 이 PC에는 아직 `.env`(OPENAI_API_KEY/OPENAI_MODEL)가 없어 **실제 호출 성공은 미확인**이다. 키 설정 방법 또는 A PC에서의 통합 시험 협의 필요.
- **요청: `draft_profile(supported_facts) -> supported 본문 배열`.** 입력 모양은 `fixtures/day2_supported_facts.json`([{"field","fact_id","text"}]), 출력 모양은 `fixtures/day2_draft_supported_example.json`([{"key","title","paragraphs":[{"text","fact_ids"}]}]). supported 섹션만 반환, 새 fact_id 생성 금지. C 서버는 `backend.agent.draft_profile`이 생기면 자동으로 호출한다(현재는 없어서 drafting에서 error로 종료).
- supported_facts가 비어 있으면 C가 호출하지 않고 안내 문구로 조립한다(억지 호출 없음).

## D에게

- 현재 파서: `backend/parsers.py` — `extract_sources(stored_files) -> (source_units, source_manifest, warnings)`. source_id `S001…`(서버 부여), locator `N행`(원본 행 번호), UTF-8 strict, 빈 파일은 예외. 이 반환 모양을 보존해 주세요.
- 추출 기록 구조: `private_runs/<job_id>/extraction.json`(stored_files·source_manifest·source_units·경고), `agent_input.json`, llm 모드에선 `company_info.json`(중간 추출)·`run_meta.json`(모드·실제 호출 여부). 예시: `handoff/extraction_example.json`.
- **요청 함수(서버가 기다리는 연결 지점):**
  - `validate_draft(draft_sections, company_info) -> 오류 목록` / `validate_profile_result(profile, source_units) -> 오류 목록` — `backend/validators.py`로 두면 서버가 `validating` 단계에서 자동 사용. 모듈이 없으면 지금은 validating에서 error로 끝낸다(검사 없이 ready 금지).
  - `render_document(profile, output_dir, format) -> 실제 파일 Path` — `POST /api/profiles/{job_id}/document`에서 서버 보관 결과를 넘겨 호출 예정. MD부터. 실패는 예외로 던져 주면 C가 `DOCUMENT_FAILED`로 변환한다(성공 시에만 파일 응답). 출력은 서버가 지정한 작업 폴더 안, 기본 파일명 `회사소개서_초안.md`.
- 스키마 검사는 C가 `profile_builder.schema_errors()`(jsonschema)로 수행 중이니 중복 구현하지 않아도 된다. fact 참조 규칙 검사(fact_ids가 supported만 참조, 안내 문구 fact_ids=[])의 1차 버전은 조립 시 C가 확인하지만, 최종 판정은 D 검사 기준.

---

## 추가 전달 (16:30 기준, C 단독 진행분)

### D에게 — 문서 API 연결 지점이 준비됐습니다 (파일만 넣으면 됨)

`backend/document_generator.py`에 아래 함수를 두면 C 코드 수정 없이 바로 연결됩니다.

```python
def render_document(profile: dict, output_dir: Path, format: str) -> Path:
    ...  # 실제 파일을 만들고 그 경로를 돌려준다
```

- `profile`: 서버가 보관한 그 job_id의 최종 결과(공통 JSON v1.0). 클라이언트가 보낸 값이 아닙니다.
- `output_dir`: 서버가 만들어 넘기는 `private_runs/<job_id>/documents`. **이 폴더 안에만 저장**해 주세요.
- `format`: `"md"` 또는 `"docx"` (소문자). MD부터면 됩니다. docx는 아직 없어도 409로 나갑니다.
- 반환: 실제로 만든 파일의 `Path`. 기본 파일명 `회사소개서_초안.md` / `.docx`.
- C가 성공으로 인정하는 조건 3가지 — (1) 실제 존재하는 파일, (2) `output_dir` 안, (3) 요청한 format과 같은 확장자.
  하나라도 어긋나면 409 `DOCUMENT_FAILED`로 나갑니다(파일을 억지로 내보내지 않습니다).
- 실패는 그냥 예외로 던져 주세요. C가 `DOCUMENT_FAILED`로 바꾸고 상세는 서버 로그에만 남깁니다.
  예외 종류는 가리지 않습니다(따로 예외 클래스를 맞추지 않아도 됩니다).
- 문서만 실패해도 그 작업의 `result`와 `ready`는 그대로 둡니다.

`backend/validators.py`(validate_draft / validate_profile_result)도 같은 방식으로 자동 연결됩니다.
지금은 두 파일 모두 없어서 각각 `validating` 단계 error, 문서 API 409로 끝납니다.

참고: C는 `scripts/check_document_api.py`에서 **시험용 임시 대역**으로 API 쪽 처리만 확인했습니다(18/18).
실제 문서 생성 기능은 만들지 않았고, 그 검사는 D 구현을 대신하지 않습니다.

### A에게 — 실제 호출 환경 조건

- `backend/agent.py`는 Responses API(`client.responses.create`, `text.format=json_schema`)를 씁니다.
  이 PC의 시스템(스토어) Python에 깔린 openai는 **1.58.1**이라 `client.responses`가 없고, 프로젝트 `.venv`는 **3.14.0**입니다.
  **반드시 프로젝트 `.venv`로 서버를 실행해야** 실제 호출이 됩니다.
  (정정: 앞서 "실행 중이던 서버가 시스템 Python"이라고 적었으나, 명령줄만으로는 둘을 구분할 수 없습니다.
  `.venv`로 띄운 프로세스도 명령줄에는 스토어 Python 경로가 찍힙니다. 구분은 적재된 site-packages 경로로 해야 합니다.
  현재 서버는 `.venv` 사용이 확인된 상태입니다.)
- `.env`(AGENT_MODE=llm, OPENAI_API_KEY, OPENAI_MODEL)는 아직 이 PC에 없습니다. 실제 호출 성공은 여전히 미확인입니다.
- 호출 1회로 확인할 스크립트는 준비해 뒀습니다: `scripts/check_llm_job.py` (가짜 TXT 2개, 업로드 1건 = 호출 1회).
- `draft_profile(supported_facts)`는 아직 `backend/agent.py`에 없습니다(`prompts/draft.txt`는 받았습니다).
  supported 사실이 하나도 없는 경우에는 C가 A를 호출하지 않고 안내 문구로만 조립하도록 고쳤습니다.

### B에게 — 지금 클릭 시험을 하면 됩니다

- 서버는 `http://127.0.0.1:8000/`에서 mock 모드로 실행 중입니다(그대로 두고 쓰면 됩니다).
- 올릴 파일: `fixtures\mock_source_a.txt`, `fixtures\mock_source_b.txt` (가짜 테스트 자료).
- 기대: 202 접수 → 상태 표시 → `ready`, "테스트 데이터" 표시, 본문 13개 섹션.
- 문서 다운로드는 아직 모든 형식이 409 `DOCUMENT_FAILED`입니다(화면 수정 필요 없음).

---

## 추가 전달 (16:40 기준) — 문서 API 보완

### D에게 — C가 성공으로 인정하는 조건이 4가지로 늘었습니다

`render_document`가 돌려준 결과를 C가 이렇게 확인합니다. 하나라도 어긋나면 409 `DOCUMENT_FAILED`입니다.

1. 실제로 존재하는 **파일**일 것
2. C가 넘긴 `output_dir`(`private_runs/<job_id>/documents`) **안**일 것
3. 요청한 format과 **같은 확장자**일 것
4. **0바이트가 아닐 것** ← 새로 추가 (수요일 업무서 03-②의 "파일 존재·크기 확인")

- 반환값이 경로가 아니면(예: dict·None) 그것도 409입니다. 500을 내지 않습니다.
- 경로 확인·크기 조회 중 생긴 파일 오류(OSError)도 409로 바꿉니다.
- 실패 사유는 서버 로그에만 남고, 응답 문구는 공통 메시지입니다.
- **C는 `render_document`를 스레드풀에서 실행합니다.** 동기 함수 그대로 만들어 주시면 됩니다.
  문서 생성이 오래 걸려도 다른 요청(상태 조회 등)은 막히지 않습니다. 시험용 대역 1.5초 기준으로 확인했습니다.
- 문서 생성이 실패해도 그 작업의 `result`와 `ready`는 그대로 둡니다.

### 아직 그대로인 것

- `backend/validators.py`, `backend/document_generator.py`, A의 `draft_profile`은 **여전히 미수령**입니다(16:27 확인).
- 문서 API는 모든 형식이 409입니다. C가 문서 생성기를 대신 만들지 않았습니다.
- 서버는 16:25에 프로젝트 `.venv`로 다시 띄웠습니다(mock 모드). **이전 job_id는 모두 사라졌으니 새로 업로드해 주세요.**
