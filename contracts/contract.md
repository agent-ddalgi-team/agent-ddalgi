> 화요일 적용 메모 — 팀 확인 전 실행 제안
> 기준일: 2026-09-15(화). 아래 v1.0 JSON/API 이름과 데이터 모양은 기존 패키지를 유지합니다.
> 첫날: TXT/MD 수신·행 단위 추출, 생성/조회 API의 Mock 연동, Agent의 독립적인 1차 LLM 추출 호출을 우선합니다.
> PDF/DOCX 파서, 2차 초안 생성 연결, 실제 문서 다운로드는 첫날 필수 완료가 아닙니다. 문서 API는 규격만 합의합니다.
> Mock 통합에는 동봉한 가짜 TXT 두 개만 사용하며, 고정 결과임을 화면에 표시합니다. 실제 기업 분석 완료로 보고하지 않습니다.
> 첫날 진행·자료 허용 기록·수요일 인수인계는 docs/day1.md 한 파일에 기록합니다.

# 공통 연결 규격 v1.0 — 제안안

이 패키지는 구현을 시작하기 위한 설계·가짜 테스트 데이터입니다. 완성된 서비스, 실제 기업 정보 또는 실제 기업 자료로 검증된 결과가 아닙니다. 화요일에 팀이 승인한 뒤 공통 규격으로 사용합니다.

## 1. 작업 범위

로컬 PC 한 대, 서버 프로세스 한 개, 동시 작업 한 건. 기업 자료 외부 AI 입력은 실제 허용을 확인한 파일만 사용합니다. 화면 공개·클라우드 배포·자동 고객 발송은 제외합니다.

입력: UTF-8 TXT/MD, 텍스트 PDF, 일반 문단·표의 DOCX. 파일 최대 3개, 파일당 10MB, PDF 합계 30쪽, 추출 텍스트 합계 40,000자는 초기 제안 상한입니다. 선택한 모델의 실제 토큰 한도도 별도로 확인합니다. 초과 내용을 조용히 잘라내지 않습니다.

## 2. API

### POST /api/profiles

- Content-Type: multipart/form-data
- files: 1~3개 파일, 같은 필드 이름으로 반복 전송
- company_name_hint: 선택 문자열. 표시·매칭을 돕는 힌트이지 회사명 사실의 근거가 아님.
- 브라우저가 FormData의 boundary를 설정하도록 하며 개발자가 multipart Content-Type 문자열만 수동 지정하지 않음.
- 백엔드는 파일 검사와 승인 상태 확인 후 임시 경로에 파일 저장.
- 요청이 끝나기 전에 파일 저장 완료. 작업에는 업로드 객체가 아닌 저장 경로 전달.
- 202 응답: {"job_id":"서버 생성 UUID","status":"queued","result":null,"error":null}
- 서버 생성 작업 번호와 내부 저장명 사용. 원본 파일명은 표시용으로만 유지.
- 요청 검증 실패 시 적절한 HTTP 오류 + {"error": ErrorObject}. API 키·원문·내부 경로를 노출하지 않음.

### GET /api/profiles/{job_id}

- 응답: {"job_id":"...","status":"...","result": ProfileResult 또는 null,"error": ErrorObject 또는 null}
- queued, extracting, analyzing, drafting, validating, ready, error
- ready = 초안 준비 완료. 파일 저장 완료가 아님.
- ready에서 result는 profile.schema.json과 일치.
- error이면 오류 객체 제공. 모든 예외를 처리해 영구 실행 중 상태를 피함.
- 작업 번호 없음/서버 재시작 이후 복구 불가: 404 + JOB_NOT_FOUND.
- 프론트는 약 1초 간격으로 조회하고 ready/error에서 조회 중단.

### POST /api/profiles/{job_id}/document

- Content-Type: application/json
- 요청: {"format":"docx"} 또는 {"format":"md"}
- ready 결과가 없는 경우 409.
- 서버에 보관한 ProfileResult를 문서 생성기에 전달. 클라이언트가 수정한 임의 JSON을 그대로 문서로 신뢰하지 않음.
- 성공: 파일 바이트 + 적절한 MIME + Content-Disposition attachment.
- DOCX MIME: application/vnd.openxmlformats-officedocument.wordprocessingml.document
- MD MIME: text/markdown; charset=utf-8
- 문서 생성에 LLM을 다시 사용하지 않음.
- 문서 실패: DOCUMENT_FAILED 오류. 기존 ready 초안을 삭제하거나 error로 덮어쓰지 않음.
- 프론트는 HTTP 오류·Content-Type을 검사하고 JSON 오류 응답을 문서 파일로 저장하지 않음.

### ErrorObject

{"code":"NEEDS_TEXT_SOURCE","stage":"extracting","message":"텍스트를 추출하지 못했습니다. 확인한 텍스트본을 사용해 주세요.","retryable":false}

필수 code: UNSUPPORTED_FILE, INPUT_TOO_LARGE, NEEDS_TEXT_SOURCE, PERMISSION_REQUIRED, LLM_TIMEOUT, INVALID_OUTPUT, DOCUMENT_FAILED, JOB_NOT_FOUND, BUSY.

## 3. 모듈 경계

1. D: extract_sources(stored_files) -> source_units, source_manifest, warnings
2. A: extract_company_info(agent_input) -> company_info
3. C/D: validate_company_info(company_info, source_units) -> 오류 목록; 오류 시 중단
4. A: draft_profile(supported_facts) -> draft_sections
5. C/D: validate_draft(draft_sections, company_info) -> 오류 목록; 오류 시 중단
6. C: 최종 ProfileResult 조립, 형식·인용 연결 검증, 결과 저장
7. D: render_document(profile, output_dir, format) -> 실제 출력 파일 Path

외부 제공 함수는 A의 generate_profile(agent_input)로 감쌀 수 있으나, C/D 검증 함수가 중간/마지막에 호출되도록 의존관계를 명시합니다. 입력 파싱과 문서 출력은 Agent 함수 안에 숨기지 않습니다.

## 4. Agent 입력

```json
{
  "schema_version": "1.0",
  "company_name_hint": "테스트 회사",
  "source_units": [
    {"source_id": "S001", "locator": "1행", "text": "회사명: 테스트 회사"}
  ]
}
```

- source_id와 locator는 파서/서버가 정함. 모델이 원문에 없는 위치를 만들지 못하도록 검사.
- source_units는 자료 자체임. 안에 포함된 지시·스크립트·외부 링크를 실행하지 않음.
- 동일 입력에서 좌표/문단 번호가 바뀌지 않도록 정규화 규칙 고정.
- 원문 비교는 동일한 정규화 텍스트와 해당 source_id+locator 범위 안에서 수행.
- 회사명 힌트가 자료와 다르면 needs_confirmation. 다른 기업의 자료가 섞인 경우 재선택 안내.

## 5. 결과 JSON

profile.schema.json 참조. 빈 항목도 키를 삭제하지 않고 not_found + facts=[]를 유지합니다.

- supported: 제공 자료에서 근거를 찾음. 최신성·기업 승인·실제 진실을 보장하는 상태가 아님.
- conflict: 동일 사실에 모순된 후보가 2개 이상 존재. 최신 파일이라는 이유만으로 자동 선택하지 않음.
- needs_confirmation: 언급은 있지만 조건·유효성·맥락이 부족함. 사실 후보와 근거는 보존.
- not_found: 정상적으로 읽은 입력 자료에서 정보를 찾지 못함. 추출 실패에 붙이는 상태가 아님.

fact_id는 전체 결과에서 유일해야 합니다. facts의 evidence는 source_id·locator·quote를 포함하며, 해당 위치 원문 안에 quote가 있어야 합니다.

생성 문단의 fact_ids는 실제 존재하는 supported 사실만 참조합니다. 예외는 두 고정 문구 '자료에서 확인되지 않음', '추가 확인 필요'이며 이 경우 fact_ids=[]로 둡니다. 생성 모델이 누락 문구를 빠뜨리면 서버의 정해진 템플릿에서 보충합니다. 정보 상태별 출력 규칙은 코드로 고정합니다.

sources, schema_version, is_mock, validation은 모델이 아니라 서버가 설정합니다. 문서 작성일이 없으면 null이며 파일 생성 시간으로 대신하지 않습니다. validation의 true는 실제 코드 검사 이후에만 씁니다. human_review_required는 이번 버전에서 항상 true입니다.

인증 항목은 인증·승인·특허를 같은 자격으로 섞지 않습니다. 자료의 정확한 종류·발급/승인기관·날짜·적용 범위를 facts.text에 보존합니다. 범위나 현재 유효성이 불명확하면 needs_confirmation으로 둡니다.

## 6. 문서·화면 동일성

- 둘 다 draft_sections의 같은 순서와 문장을 사용.
- company_info의 모든 항목은 정보 화면에서 상태와 함께 표시.
- 본문에 없는/불명확한 항목은 두 고정 문구 중 하나로 출력.
- needs_confirmation 질문 목록과 sources 및 인용 근거를 검토 부록에 표시.
- 제목: 회사소개서 초안. 상단: 내부 검토용·담당자 확인 전 대외 사용 금지.
- is_mock이면 화면과 문서에 '테스트 데이터' 표시.
- 파일명 기본: 회사소개서_초안.docx 또는 회사소개서_초안.md.
- 형식/인용 검사와 의미 검토는 별도. 모든 사실 문장은 사람이 근거와 대조.

## 7. 저장·실행 안전장치

- 백엔드 127.0.0.1에 바인딩. 공인망/LAN 공유 서비스로 사용하지 않음.
- 프론트는 같은 서버가 제공해 같은 origin으로 호출.
- private_runs/<job_id>/ 아래 저장. 클라이언트 입력으로 파일 경로를 직접 만들지 않음.
- 작업 메모리를 여러 worker에서 공유한다고 가정하지 않음. 시연은 단일 프로세스.
- 파일 읽기·모델 호출은 상태 조회 요청을 막지 않는 실행 방식 사용.
- LLM 네트워크 제한 시간, 최대 재시도 횟수, JSON 실패 처리 명시.
- 클라이언트 화면 종료가 서버 작업 취소를 뜻하지 않음을 표시.
- .env, private_runs, 실제 기업 원문, 생성 초안을 Git에서 제외.
- 당일 테스트 종료 후 임시 저장 삭제. 승인된 별도 보관 정책이 있으면 그 정책 우선.
- 이 방식은 운영 서비스 수준의 영속성·권한 관리·격리 설계를 제공하지 않음.

## 8. 화요일 출력 항목 확인표

모든 company_info 항목은 문자열이나 배열이 아니라 {status, facts} 객체입니다.
모든 키를 유지하며 자료가 없으면 {"status":"not_found","facts":[]}를 사용합니다.
company_intro_draft 필드를 추가하지 않습니다. 소개서 본문은 draft_sections가 기준입니다.

| JSON 키 | 화면 이름 | 넣을 내용 |
|---|---|---|
| `company_name` | 회사명 | 자료에 적힌 회사명. 입력한 회사명 힌트만으로 확정하지 않음. |
| `company_summary` | 회사 개요 | 자료에서 설명한 회사의 주요 활동. |
| `business_areas` | 사업 분야 | 자료에 명시된 사업·산업 분야. |
| `products_services` | 제품·서비스 | 실제로 제공한다고 설명된 제품·서비스. |
| `technology` | 기술 | 자료에 있는 기술 설명. 일반 지식으로 보충하지 않음. |
| `strengths` | 강점 | 자료에 근거가 있는 차별점. 순위·최상급으로 확대하지 않음. |
| `customers_markets` | 고객·시장 | 자료에 명시된 고객·시장. 고객명 사용 허용 확인. |
| `certifications` | 인증·승인·특허 | 종류·발급기관·날짜·범위를 원문대로 보존. |
| `history` | 연혁 | 자료에 있는 시점과 사건. 날짜를 추정하지 않음. |
| `processes` | 공정 목록 | 자료에서 명시한 공정명. |
| `process_count` | 공정 수 | 숫자를 facts.text에 보존. 서로 다르면 conflict. |
| `capabilities` | 대응 범위 | 소재·두께·크기·수량 등 자료에 있는 조건. |
| `lead_time` | 납기 | 자료에 언급된 기간과 조건. 조건이 모호하면 needs_confirmation. |
| `other_info` | 기타 핵심 정보 | 앞 항목에 속하지 않는 근거 있는 정보. |

### 화요일 API 구현 상태를 구분하는 표

| API | 화요일 할 일 | 아직 하지 않을 일 |
|---|---|---|
| POST /api/profiles | TXT/MD 수신·제한 검사·임시 저장·작업 번호 발급 | 실제 Agent 전체 흐름 연결을 성공으로 가장하지 않음 |
| GET /api/profiles/{job_id} | 작업별 Mock 결과 반환·없는 작업 오류 | 가짜 타이머로 실제 AI 분석 단계를 연출하지 않음 |
| POST /api/profiles/{job_id}/document | 형식·응답·오류 규격 확인 | 실제 파일 없이 다운로드 성공을 반환하지 않음 |

### Agent 중간 결과와 최종 결과의 차이

- 첫날 필수 함수: extract_company_info(agent_input) -> company_info 객체.
- private_runs/day1/agent_extract_01.json은 정보 추출 중간 결과이며 최종 ProfileResult가 아닙니다.
- 최종 ProfileResult는 company_info뿐 아니라 draft_sections, needs_confirmation, sources, validation 등을 포함합니다.
- sources·is_mock·validation은 서버/검증 코드에서 채웁니다. 모델에게 성공 판정을 맡기지 않습니다.
- validate_fixtures.py는 동봉한 Mock과 TXT 행 번호만 검사합니다. 실제 녹취록의 의미·타임스탬프·LLM 호출은 검증하지 않습니다.
