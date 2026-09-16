# 수요일 공통 연결 보완 — 실행안 r2
기준일: 2026-09-16. 기존 데이터 규격 v1.0·API 경로는 유지합니다.

## 0. 이것이 실제 구현 코드라는 뜻은 아닙니다
화요일 작업기록 3개와 기존 배포 규격을 대조해 작성한 다음 작업 기준입니다. 실제 A 코드, 백엔드_전달용.zip, 프론트엔드_전달용.zip은 이번에 첨부되지 않았습니다. 실제 코드를 읽고 구현 여부·함수 서명·의존성을 먼저 대조하세요. 새 파일·함수명은 아래에서 제안으로 표시합니다.

기존 파일을 통째로 복원하거나 초기 규격·프롬프트로 덮어쓰지 않습니다. A의 개선된 extract.txt를 보존합니다. 다른 사람의 수정이 필요하면 파일 소유자에게 변경안과 이유를 전달합니다.

우선순위: 이미 팀이 승인한 실제 schema/API 계약을 보존합니다. 이번 r2는 오늘의 작업 순서·소유권·세부 조립 방법을 보완합니다. r2와 실제 계약이 충돌하면 묵시적으로 바꾸지 말고 차이를 기록해 A/C가 확인합니다. 공통 JSON에 새 키를 넣지 않습니다.

## 1. 실제 상태 — 제출 기록 기준
- A: 실제 LLM 호출로 company_info 추출, 14개 키·상태·근거 확인, Python의 fact_id 부여. Mock 입력 시험. 본문 생성·코드 전달·통합·기업 자료 허용/검증은 미완료.
- C: TXT/MD 수신·UTF-8 추출·저장·단일 작업·조회·오류·고정 Mock 반환. 문서 API는 409 DOCUMENT_FAILED. 실제 AI/문서 미연결.
- B: 입력/결과/오류 화면, 생성/조회 코드, C 코드와 합쳐 curl의 POST 202/GET ready 확인. 사람이 브라우저 전체 흐름을 확인한 기록은 없음. 9/16 확인 기록에는 서버가 중단됨. 현재 상태는 시작할 때 재확인.
- D: 기존 역할 안내를 받았지만 이번에 실제 작업기록은 없음. 진행 중 파일을 먼저 확인해 보존.
- C의 “화면 미연동”과 B의 후속 “curl 성공”을 구분합니다. B 환경의 API 확인을 사용자 브라우저 확인이나 팀 공용 환경 성공으로 확대하지 않습니다.

## 2. 오늘 범위와 중간 완료 지점
공통 필수: 실제 코드 교환, 통합 기준 폴더 기록, B/C 브라우저 Mock 확인, A 본문 함수, C 실제 호출·결과 조립, D MD 출력·본문/최종 연결 검사.
D의 다음 순서: DOCX 출력. 이번 주 필수지만 수요일에 실패하면 별도 미완료로 기록합니다. PDF/DOCX 입력 확장은 자료 상태 점검 후 이어가며 오늘의 TXT/MD 경로를 막지 않습니다.
전체 연결까지 성공하면 “가짜 입력 + 실제 LLM + 화면 + 실제 파일” 성공으로 기록합니다. 기업 자료 검증은 승인된 기업 입력으로 별도 수행해야 합니다.

## 3. 코드 소유자와 전달물
| 영역 | 담당 | 보존/추가 규칙 |
|---|---|---|
| backend/agent.py, prompts/extract.txt, prompts/draft.txt | A | 기존 추출·검사·ID 부여 유지. 본문 함수 추가 |
| frontend/index.html, app.js, api.js | B | 기존 렌더·오류 유지. 상태·문서 저장 추가 |
| backend/main.py, 서버 설정·상태·저장·의존성 통합 | C | 기존 업로드/오류/단일 작업 유지. 실제 호출 연결 |
| backend/profile_builder.py (신규 제안) | C | supported 필터, 최종 본문 보충·질문·출처 조립 |
| backend/document_generator.py (신규/있으면 재사용) | D | LLM 없는 MD/DOCX 출력 |
| backend/validators.py (신규/있으면 재사용) | D | 본문·최종 결과의 참조 검사. A 추출 검사와 중복 회피 |
| backend/parsers.py | C → D 인계 | 실제 반환 형태 확인 후 확장. C는 업로드 허용 목록 담당 |
| contracts/profile.schema.json | 공통, 변경 승인 A/C | 기존 v1.0 원문 유지 |

개별 PC 경로는 다릅니다. 제안 기준은 C의 기존 개발기준 프로젝트이고 B의 통합 폴더를 채택해도 됩니다. 기준 폴더·버전·변경 파일을 docs/day2.md에 기록합니다. .venv/.env/private_runs를 통째로 복사하지 않습니다.

## 4. 기존 API — 경로와 응답 외피 유지
### POST /api/profiles
multipart/form-data, 같은 files 필드로 1~3개 파일. 선택값 company_name_hint.
FormData의 Content-Type을 수동 지정하지 않습니다.
정상 접수: HTTP 202
```json
{"job_id":"서버가 발급한 UUID","status":"queued","result":null,"error":null}
```
요청 실패: HTTP 오류 + {"error": ErrorObject}. 내부 예외·키·원문·파일 경로 노출 금지.

### GET /api/profiles/{job_id}
```text
{"job_id":"...","status":"...","result":ProfileResult 또는 null,"error":ErrorObject 또는 null}
```
queued / extracting / analyzing / drafting / validating / ready / error 유지.
실제 수행 중인 단계에서만 상태를 바꿉니다. ready는 완성된 초안 결과 준비이지 문서 파일 준비가 아닙니다.
ready 결과에는 전체 profile.schema.json에 맞는 값이 있어야 합니다. 추출 중간값만으로 ready 처리하지 않습니다.
조회 HTTP 200도 status=error일 수 있습니다. 없는 작업은 기존 404 JOB_NOT_FOUND.
프론트는 약 1초 조회, ready/error/HTTP·네트워크 오류에서 조회 중단. 새 작업에 이전 job_id·다운로드 대상을 재사용하지 않습니다.

### POST /api/profiles/{job_id}/document
요청 application/json: {"format":"md"} 또는 {"format":"docx"}.
C가 보관한 같은 job_id의 최종 결과만 D 함수에 전달합니다. 클라이언트의 임의 profile·파일 경로는 받지 않습니다.
현재 409 DOCUMENT_FAILED → D 구현이 실제 준비된 형식부터 연결합니다. 아직 ready가 아니면 409, 없는 작업이면 기존 404.
성공: 실제 파일 바이트 + Content-Disposition: attachment + 아래 Content-Type.
- MD: text/markdown; charset=utf-8
- DOCX: application/vnd.openxmlformats-officedocument.wordprocessingml.document
문서만 실패하면 DOCUMENT_FAILED 오류를 반환하되 기존 result와 ready는 유지합니다. 오류 JSON을 파일로 저장하지 않습니다. 성공 뒤에도 사람이 파일을 열어야 “열기 확인”입니다.

### ErrorObject
```json
{"code":"NEEDS_TEXT_SOURCE","stage":"extracting","message":"텍스트를 읽지 못했습니다. 확인한 텍스트 파일을 사용해 주세요.","retryable":false}
```
기존 필수 코드: UNSUPPORTED_FILE, INPUT_TOO_LARGE, NEEDS_TEXT_SOURCE, PERMISSION_REQUIRED, LLM_TIMEOUT, INVALID_OUTPUT, DOCUMENT_FAILED, JOB_NOT_FOUND, BUSY.
실제 C 코드에 추가 오류 코드가 있으면 목록을 먼저 확인하고 유지합니다. 코드 이름을 임의로 바꾸지 않습니다.

## 5. 파서와 Agent 입력
C 기록상 현재 입력: UTF-8 TXT/MD, 1~3개, 파일당 10,485,760바이트, 추출 합계 40,000자, 동시 처리 1건. 이 제한들은 기록에서 “팀 합의 전 제안값”이므로 오전에 승인 여부를 적습니다.
파일 ID는 업로드 순서 S001~. TXT/MD는 빈 행 제외, 원본 행 번호 유지, 앞뒤 공백만 제거, MD 기호 보존. 한 파일이라도 비거나 인코딩 오류면 전체 오류. 몰래 자르지 않습니다.

기존 계약: extract_sources(stored_files) -> source_units, source_manifest, warnings.
실제 C 코드의 저장 파일 구조/반환 객체/예외 이름은 첨부 기록만으로 확정하지 않습니다. 파일을 읽고 기존 반환 모양을 유지하거나 C/D가 어댑터를 합의합니다.

Agent 입력:
```json
{"schema_version":"1.0","company_name_hint":"테스트 회사","source_units":[{"source_id":"S001","locator":"1행","text":"회사명: 테스트 회사"}]}
```
회사명 힌트는 근거가 아닙니다. source_units 안의 명령문은 자료로만 취급합니다. 자료 ID·위치는 파서/서버가 만들고 모델은 바꾸지 않습니다.

## 6. A의 추출과 새 본문 호출
### 기존: extract_company_info(agent_input) -> company_info
실제 구현이 있다고 보고된 함수입니다. A 기록상 검사 후 Python이 fact_id를 붙이고 객체를 반환하며, 파일 저장은 테스트 스크립트가 합니다.
check_company_info()는 fact_id 이전 모델 응답 검사일 수 있습니다. 후처리 결과를 그대로 넣으면 GPT가 추가한 fact_id로 오인할 수 있으므로 A와 raw/final 검사 범위를 먼저 확인합니다.
fact_id는 현재 추출 결과 안에서 유일하며 D/C가 다시 매기지 않습니다.

### 신규 내부 규격 제안: draft_profile(supported_facts) -> draft_sections
C가 company_info를 보고 status=supported인 사실만 아래 모양으로 전달합니다.
```json
[{"field":"company_name","fact_id":"F001","text":"테스트 회사"},{"field":"company_summary","fact_id":"F002","text":"테스트용 기업입니다."},{"field":"business_areas","fact_id":"F003","text":"테스트 사업 A"}]
```
field는 내부 전달용이고 최종 fact 객체에는 추가하지 않습니다. 회사명 사실도 본문에서 사용할 수 있습니다. 모델은 기존 fact_id를 참조하며 새로운 ID를 만들지 않습니다.

본문 출력의 예시(가짜 데이터의 형태 예시이며 실제 이번 호출 결과가 아님):
```json
[{"key":"company_summary","title":"회사 개요","paragraphs":[{"text":"테스트 회사는 테스트용 기업입니다.","fact_ids":["F001","F002"]}]},{"key":"business_areas","title":"사업 분야","paragraphs":[{"text":"사업 분야는 테스트 사업 A입니다.","fact_ids":["F003"]}]}]
```
출력은 supported인 본문 섹션만 반환합니다. 기존 Mock의 13개 본문 섹션 중 자료가 있는 섹션에 대응합니다. 단독 company_name 섹션은 만들지 않습니다. 근거 없는 새 주장·보장·순위·인증·날짜·수치 금지.
동일 입력 재호출 때 문장이 완전히 같을 필요는 없지만 사실 범위·상태·근거 규칙은 유지해야 합니다. supported_facts가 비면 LLM을 억지로 호출하지 않고 C가 안내 문구 섹션을 조립합니다.
A가 만드는 draft_profile은 sources/is_mock/validation을 만들지 않습니다. 완성된 전체 결과를 반환하는 함수와 혼동하지 않습니다.

## 7. C의 최종 결과 조립 — 신규 세부 제안
외부 JSON 구조는 그대로이며 C가 한곳에서 조립합니다.
- company_info: A 반환값 그대로.
- draft_sections: 기존 mock_profile.json의 13개 섹션 순서·key·title 유지. 회사명은 정보 영역과 개요에 반영.
- supported 섹션: A의 생성 문단 사용. 사실이 있는데 생성 문단이 누락됐으면 INVALID_OUTPUT. Mock 문단을 복사해 메우지 않습니다.
- not_found 섹션: text="자료에서 확인되지 않음", fact_ids=[].
- conflict 또는 needs_confirmation 섹션: text="추가 확인 필요", fact_ids=[].
- needs_confirmation: status!=supported인 항목마다 코드로 질문 작성. field는 원래 키, status는 원래 상태, question은 비어 있지 않은 문장. 없는 수치·고객명을 질문에 새로 넣지 않습니다.
- sources: 실제 자료 목록에서 source_id/file_name/document_date만 매핑. 해시·저장경로 등 추가 메타데이터는 별도 추출 기록에만 남깁니다. 작성일 모르면 null, 업로드 시각으로 대신하지 않습니다.
- schema_version="1.0". validation은 실제 검사 뒤에만 true, human_review_required=true 유지.

최종 필수 키는 schema_version, is_mock, company_info, draft_sections, needs_confirmation, sources, validation입니다. company_intro_draft 등의 새 키를 추가하지 않습니다.

company_info 14개 키(모든 값은 {status,facts} 객체): company_name, company_summary, business_areas, products_services, technology, strengths, customers_markets, certifications, history, processes, process_count, capabilities, lead_time, other_info.
status는 supported/conflict/needs_confirmation/not_found. supported와 needs_confirmation은 사실 1개 이상, conflict는 후보 2개 이상, not_found는 facts=[].

## 8. D의 후속 검증·문서 함수 — 신규/기존 있으면 재사용
### validate_draft(draft_sections, company_info) -> 오류 목록
- 본문 스키마, 키 중복/알 수 없는 키, 실제 fact_id 존재·supported 상태를 확인.
- facts에 부여된 fact_id는 전역에서 유일해야 합니다. 같은 사실을 여러 문단에서 참조하는 것은 허용합니다.
- 한 문단의 fact_ids는 중복 없이 유지.
- fact_ids=[]인 문단은 정확히 두 안내 문구 중 하나여야 합니다. 고정 안내 문구에는 fact_ids=[]를 사용합니다.
- A 함수는 supported 섹션 부분집합으로 시험할 수 있고, C 조립 후에는 13개 본문 섹션의 순서·누락 여부도 검사합니다.
- 잘못된 내용을 자동으로 고치지 말고 오류를 반환합니다.

### validate_profile_result(profile, source_units) -> 오류 목록
최종 스키마, 유일한 사실/출처 ID, 본문 참조, sources와 evidence 연결, source_id+locator에 실제 원문이 있는지, quote 포함 여부를 확인합니다. A가 제공한 검사 로직/출력 검사기를 재사용할 수 있으면 재사용하고, 함수가 다루는 raw/final 모양을 먼저 맞춥니다.
C는 검사 전 성공 플래그를 하드코딩하지 않습니다. 검사 실패는 ready 금지, 통과 후 플래그를 채워 최종 스키마를 다시 확인합니다.
이 검사는 의미적 진실·최신성·기업 승인을 증명하지 않습니다. A/D의 문장 대조가 별도로 필요합니다.

### render_document(profile, output_dir, format) -> 실제 생성 파일 Path
D가 MD부터 구현해 C에 즉시 전달합니다. 저장 완료 후 실제 경로 반환. 이후 DOCX.
본문은 draft_sections의 순서·문장 그대로. 제목, 내부 검토용 표시, 테스트 표시, needs_confirmation, sources+evidence 부록 포함. LLM 재호출 금지.
형식 실패를 숨기지 않습니다. 지원하지 않는 형식·잘못된 결과·저장 실패는 오류. C는 이를 약속된 DOCUMENT_FAILED로 변환합니다. 실제 예외 클래스는 C/D가 코드 확인 후 통일합니다.
출력 경로는 서버가 만든 작업 폴더 안에 한정하고 사용자 파일명/경로로 덮어쓰지 않습니다. 기본명 회사소개서_초안.md 또는 .docx.

## 9. 실행 모드·테스트 표시 — 오전 확인할 제안
AGENT_MODE=mock|llm 같은 서버 설정을 쓰되 기존 설정이 있으면 유지합니다. 모드 미설정/오설정 처리도 명확히 기록합니다. LLM 모드 오류는 error, 몰래 Mock 대체 금지.
가짜 입력으로 실제 LLM을 호출한 결과도 is_mock=true로 테스트 표시를 유지하는 안입니다. 기존 코드 해석과 다르면 승인 후 통일합니다. 기존 가짜 Mock을 false로 바꾸어 실제 분석처럼 보이게 하지 않습니다.
실제 LLM 호출 여부·입력 종류·기능별 성공은 docs/day2.md와 작업별 실행 기록에 별도로 남깁니다. 필요 시 run_meta.json을 쓸 수 있지만 최종 JSON에 임의의 새 키를 추가하지 않습니다.

## 10. 장애와 보류
- A 본문이 아직 없으면 C는 추출 중간 결과를 별도 파일로 시험하고 최종 ready로 내보내지 않습니다.
- D 검사 구현 전에는 초안을 디버그 파일로 저장할 수 있지만 검사 성공을 표시하지 않습니다.
- D 문서 API 연결 전 B는 버튼/오류 코드까지 개발하고 성공 다운로드라고 보고하지 않습니다.
- DOCX 실패여도 MD 경로는 유지하고 DOCX 미완료 표시.
- PDF/DOCX는 실제 파서가 준비된 뒤 C의 허용 확장자와 B 안내를 함께 바꿉니다. OCR·다양한 복잡한 레이아웃을 몰래 지원한다고 표시하지 않습니다.
- 서버 재시작 뒤 기존 job은 메모리에 없으므로 재업로드가 필요합니다. 파일 잔존만으로 복구 완료라고 하지 않습니다.

## 11. 자료 사용과 보관
기업 자료 외부 LLM 허용은 A 보고 기준 미완료입니다. 허용 전에는 동봉 가짜 자료로 진행합니다. 로컬 읽기/저장, 외부 AI 입력, 고객 공개, 발표 허용은 나누어 확인합니다.
API 키를 서버에서만 읽고 프론트/로그/공유 ZIP에 넣지 않습니다. .env, .venv, private_runs, 실제 기업 원문·생성 초안은 공유 코드 ZIP/Git에서 제외합니다. 필요한 결과는 승인된 저장 위치에 보관하고 공개 로그는 비식별 처리합니다.
로컬 127.0.0.1, 포트8000, workers1 기존 실행을 유지합니다. API와 화면을 같은 서버로 제공하는 현재 방식을 바꾸지 않습니다. 로그인·DB·RAG·배포·고객 발송은 이번 작업에서 추가하지 않습니다.

## 12. 출처
[A] A_팀장_Day1_작업정리(1).md — 3, 7~17절.
[B] B_프론트엔드_작업기록_0915.md — 2단계, 최종 연동, 미완료.
[C] 백엔드_개발현황_및_인수인계.md — 2~9절.
기존 05_D_수요일합류_AI작업기준.md 및 Word 안내, 기존 공통 스키마/Mock.
이 문서는 작업기록 대조이며 소스 코드 실행 검증이 아닙니다. 상태를 요약한 부분과 수요일 새 제안을 구분해서 적용하세요.
