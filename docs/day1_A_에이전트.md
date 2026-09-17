# 화요일 실행 기록 — 2026-09-15

> 이 파일은 새로 추가한 기록 양식입니다. 공통 규격 원본은 `contracts/contract.md`입니다.
> 2026-09-16 기준: A의 사용자 PC 실행과 가짜 자료 기준 실제 LLM 호출은 확인됨. A/B/C 팀 합의와 실제 기업 자료 검증은 아직 확인되지 않았습니다.
> 실제로 확인한 행만 갱신하세요. 비밀 키와 실제 기업 원문은 이 문서에 쓰지 않습니다.

## 1. 시작 전 확인

| 확인 항목 | 제안 또는 현재 확인 상태 | 확인자·확인 시점 |
|---|---|---|
| 운영체제 / 편집기 | Windows 11 Pro / VS Code | A, 2026-09-15 |
| Python 버전 / 실행 방법 | Python 3.13.12 / 프로젝트 `.venv`의 python.exe 직접 실행(`.\.venv\Scripts\python.exe`). 패키지: jsonschema 4.26.0, openai 3.14.0, python-dotenv 1.2.3 | A, 2026-09-15 (도구 실행으로 확인) |
| 기존 팀 폴더·저장소 | 사용자 확인 전. 기존 폴더가 있으면 덮어쓰지 않음 | 미확인 |
| 공통 기준 | 첨부 v1.0 유지 제안. A/B/C 합의는 아직 미확인 | 미확인 |
| A 오늘 목표 | 실제 LLM 호출 → company_info 추출 JSON 저장 | 합의 확인 전 |
| B/C 오늘 목표 | 가짜 TXT 업로드 → 작업 번호 → Mock 조회 → 화면 표시 | 합의 확인 전 |
| 첫 입력 | 동봉 가짜 TXT 2개. 기업 사실이 아님 | 입력 파일 준비됨 |
| LLM 제공사 / 모델 | OpenAI Responses API / gpt-5.6-terra. 연결 테스트 성공(`scripts/test_openai_connection.py` → PASS). API 키 값은 기록하지 않음 | A, 2026-09-15 |
| 기업 원문 외부 LLM 입력 허용 | 확인되지 않음. 확인 전에는 기업 원문을 입력하지 않음 | 미확인 |
| 공유할 공통 자료 | contracts/와 fixtures/ | 전달 미확인 |

## 2. 실제 실행 기록

| 담당 | 오늘 작업 | 파일 | 완료 조건 | 상태 | 실행 근거 | 막힘·다음 행동 |
|---|---|---|---|---|---|---|
| A/B/C | 공통 기준 확인 | contracts/contract.md, contracts/profile.schema.json | 동일 규격·Mock 사용 확인 | 미확인 | 아직 없음 | 세 명의 확인을 기록 |
| A | 내 PC 개발환경 확인 | validate_fixtures.py | 내 PC에서 검사 통과 | 완료 | `.\.venv\Scripts\python.exe validate_fixtures.py` → PASS 출력 | LLM 제공사/API 키 확인 |
| A | 가짜 입력 확인 | private_runs/day1/ag
ent_input.json | 가짜 TXT의 위치·텍스트와 일치 | 파일 준비됨, 사용자 대조 미확인 | 동봉 가짜 입력 7개 단위 | 내용 확인 후 사용 |
| A | 추출 프롬프트 확인 | prompts/extract.txt | 14개 키·상태·근거 규칙 확인 | 프롬프트 보강 2건 반영 / 의미 상태 재검증 성공(가짜 자료) / 대표 함수·결과 저장은 30·31행에서 가짜 자료 기준 완료 / 반복 호출 안정성·실제 기업 자료 검증 미완료. 보강(2026-09-16): ① 정성적 납기 표현만 있고 기간·기준·적용 조건이 없으면 needs_confirmation ② fact text에는 자료의 사실·표현만 담고 자료 부재·분류 이유는 넣지 않으며 불명확성은 status로 표현 | [의미 분류 문제] 4-5 재호출(2회차)에서 lead_time "빠른 납기"가 supported로 분류됨(1회차는 needs_confirmation). 형식·근거 검사는 통과했으나 작업기준 5절 기대(needs_confirmation)와 불일치 → 규칙 ① 보강. [재검증 — day1 작업의 연장, 실제 확인 날짜 2026-09-16] 규칙 ① 프롬프트 보강 후 Mock 재호출 성공(`.\.venv\Scripts\python.exe scripts\check_openai_extract.py`, 가짜 입력 fixtures/agent_input_mock.json, gpt-5.6-terra, completed, 5개 규칙 통과). lead_time = needs_confirmation / facts 1, process_count = conflict / facts 2, company_name·company_summary·business_areas = supported, 나머지 9개 = not_found / facts 0으로 나머지 기대 상태도 일치. 토큰 합계 1,614. 실제 기업 자료 미사용 | 1회 결과라 반복 안정성은 미확인. 재검증 응답의 lead_time fact text에 분류 이유가 섞여 규칙 ② 추가(규칙 ② 반영 후 결과는 30행 4-6·31행 기록). Python에 특정 문구 판정은 넣지 않음 |
| A | 실제 LLM 호출 함수 | backend/agent.py | 실제 호출 후 company_info만 반환 | extract_company_info 대표 함수 실행 성공 / Mock 기대 상태 자동 검사 PASS / agent_extract_01.json 저장 완료 / 실제 기업 자료 검증 미완료 (가짜 자료 기준 확인이며 실제 기업 자료 기준 Agent 검증은 아님) | 2026-09-16 4-4: `.\.venv\Scripts\python.exe scripts\check_openai_extract.py` → 가짜 입력으로 gpt-5.6-terra 호출, completed, JSON 객체 수신, 토큰 1,611. 4-5: `.\.venv\Scripts\python.exe scripts\check_company_info_rules.py` → ALL OK(정상 예시 통과·F001~F006 부여·공통 스키마 company_info 통과, 일부러 틀린 응답 17건 모두 INVALID_OUTPUT 거부). 실제 재호출 → 5개 규칙 통과·F001~F006 부여, 토큰 1,592. 단 이 재호출에서 lead_time 의미 분류 불일치(29행, 프롬프트 보강으로 대응). 4-6: 규칙 ② 반영 후 대표 함수 extract_company_info 1회 실행 → 기대 상태 일치(수동 대조), 토큰 1,643. 4-4~4-6 시점에는 결과 파일 미저장이었고, 저장은 31행 test_agent.py 실행에서 완료 | [C 협의] agent_input 형식 오류(AgentInputError)는 새 공통 API code를 만들지 않고 내부 계약 오류로 유지. C는 extract_company_info 호출 전에 agent_input을 검증. 남은 일: 사람의 원문 의미 검토, 실제 기업 자료 검증(외부 LLM 입력 허용 확인 후), 반복 호출 안정성 확인, C 전달(5절) |
| A | 실행·결과 저장 | scripts/test_agent.py, private_runs/day1/agent_extract_01.json | 재실행 가능한 명령과 결과 저장 | 완료(가짜 자료 기준) / 실제 기업 자료 검증 미완료 | 2026-09-16(day1 작업의 연장) `.\.venv\Scripts\python.exe scripts\test_agent.py` → ALL PASS: extract_company_info 대표 함수 실행 성공(gpt-5.6-terra, completed, 토큰 입력 1,158 / 출력 476 / 합계 1,634), 반환 키 14개, Mock 기대 상태 자동 검사 PASS(supported 3·conflict 1·needs_confirmation 1·not_found 9), fact_id F001~F006 순서·중복 없음, evidence 7개 위치 존재·quote 원문 포함, 공통 스키마 company_info 규칙 통과. agent_extract_01.json 저장 완료(기존 파일 없음 확인 후 새로 저장, 저장 후 재읽기 일치). 문장 표현·동일 사실 evidence 개수 차이는 검사 대상 아님. 실제 기업 자료 미사용 | 실제 기업 자료 검증 미완료. 재실행 시 기존 결과 파일이 있으면 API 호출 전에 STOP, 의도적으로 바꿀 때만 `--overwrite` |
| B | Mock 화면 | frontend/ | 정상·빈 값·상충·질문·오류 표시 | 상태 미확인 | 아직 없음 | B가 실행 근거 작성 |
| C | 업로드·조회 API | backend/main.py | 파일 수신·job_id·Mock 조회 | 상태 미확인 | 아직 없음 | C가 실행 근거 작성 |
| B/C | 첫 연결 | frontend/, backend/ | 화면 → 서버 → Mock → 화면 시연 | 미확인 | 아직 없음 | 각 코드 준비 후 연결 |

## 2-1. A/B/C 공통 기준 확인 체크리스트

세 명이 각각 확인한 뒤 체크하고 26행에 확인자·시점을 기록합니다. 2026-09-16 현재 아무도 체크하지 않았습니다.

- [ ] `schema_version` "1.0"과 `contracts/profile.schema.json`을 수정 없이 사용한다.
- [ ] `company_info` 14개 키를 모두 유지하고, 자료가 없는 항목도 `{"status":"not_found","facts":[]}`로 둔다.
- [ ] status는 supported / conflict / needs_confirmation / not_found 4개만 쓰고, 화면에 항목별 상태를 함께 표시한다.
- [ ] API는 `POST /api/profiles`, `GET /api/profiles/{job_id}`이며 결과는 `result` 안, 오류는 ErrorObject로 반환한다.
- [ ] A의 반환값은 company_info뿐이며 `sources`·`is_mock`·`validation`·`schema_version`은 C가 채운다.
- [ ] Mock·가짜 TXT 결과는 화면·보고에 "테스트 데이터"로 표시하고 실제 기업 분석 완료로 보고하지 않는다.
- [ ] 실제 기업 자료는 4절에 외부 LLM 입력 허용을 기록한 뒤에만 사용하고, `.env`·`private_runs/`·원문을 Git에 올리지 않는다.

## 3. 패키지 준비 시 확인한 범위

이 절은 **파일을 준비한 보조 실행환경의 검사 기록**입니다. 사용자 PC의 완료 기록이 아닙니다.

- 첨부 `02_A_팀장_Agent_AI작업기준(1).md`의 기계용 부록 11개 파일을 원문 그대로 복원했습니다.
- 공통 필드 14개, 가짜 입력 7개 단위, 가짜 원문의 행 위치 일치를 확인했습니다.
- 실행환경: Python 3.13.5, jsonschema 4.26.0.
- 실행 명령: `python validate_fixtures.py`.

```text
PASS: JSON Schema, source locations, unique fact IDs, draft links, API fixture consistency.
Not checked: semantic truth, current company facts, LLM/API execution, DOCX rendering.
```

사용자 PC 실행, 화면·서버 연동, 실제 LLM 호출, 실제 기업 자료 시험, 문서 출력은 검증하지 않았습니다.
JSON 구조와 인용 위치가 맞는 것만으로 문장 의미 또는 기업 사실이 검증된 것은 아닙니다.

## 4. 자료 사용 허용 기록

| 자료 | 열람 | 로컬 저장 | 외부 LLM 입력 | 대외 공개 | 확인자·시점 |
|---|---|---|---|---|---|
| 동봉 가짜 TXT | 테스트용 | 테스트용 | 가짜 자료로 호출 시험 가능 | 기업 사실로 사용 금지 | 첨부 안내 기준 |
| 실제 기업 자료 | 미확인 | 미확인 | 미확인: 확인 전 입력 금지 | 미확인 | 담당자 확인 필요 |

## 5. C에게 전달할 Agent 실행 정보

- 전달 상태: 미전달 (내용 정리 2026-09-16). 가짜 자료로만 실행 확인, 실제 기업 자료 미검증
- 함수: `extract_company_info(agent_input) -> company_info` (`backend/agent.py`). 파일을 저장하지 않음
- 입력: `fixtures/agent_input_mock.json` 형식(`schema_version` "1.0", `company_name_hint` 선택·근거 아님, `source_units`[{source_id, locator, text}]). C가 호출 전 형식 검증
- 출력: 14개 항목 company_info(fact_id 포함), 최종 ProfileResult 아님. `sources`·`is_mock`·`validation`·`schema_version`은 C가 설정
- 출력 예시: `private_runs/day1/agent_extract_01.json` (Git 제외 위치, 허용된 저장 위치로 따로 전달)
- 실행: `.\.venv\Scripts\python.exe scripts\test_agent.py` (기존 결과가 있으면 API 호출 전 STOP, 의도적 교체만 `--overwrite`)
- 환경: `.venv`에 openai·python-dotenv·jsonschema, 루트 `.env`에 `OPENAI_API_KEY`·`OPENAI_MODEL` (키 값은 공유하지 않음)
- 오류: `AgentInputError`(입력 형식, 내부 계약 오류·새 API code 없음) / `AgentError` `NEEDS_TEXT_SOURCE`·`INPUT_TOO_LARGE`·`LLM_TIMEOUT`·`INVALID_OUTPUT`(rule·details 포함)
- 협의 필요: 그 밖의 OpenAI API 오류(키·권한·모델·한도·연결)는 맞는 공통 code가 없음 → ErrorObject 매핑 결정
- 호출 방식: 동기 함수, OpenAI 1회·timeout 60초·재시도 1회 → 상태 조회를 막지 않게 별도 실행(스레드 등)으로 호출

## 6. 수요일 D 인수인계 — 종료 전에 실제 상태로 갱신

작성 기준: 2026-09-16, docs/day1.md에 실행 근거가 있는 것만 완료로 적음.

목표·범위:
- 화요일 목표: A는 실제 LLM으로 company_info 1차 추출·저장, B/C는 Mock 결과로 화면·서버 연결.
- 첫날 필수 아님: PDF/DOCX 파서, 초안 생성(draft.txt) 연결, 실제 문서 다운로드.

A/B/C별 완료와 실행 근거:
- A: 가짜 자료 기준 완료. `scripts/test_agent.py` ALL PASS(gpt-5.6-terra, 토큰 1,634) → `private_runs/day1/agent_extract_01.json` 저장(2절 31행).
- A: 규칙 검사 `scripts/check_company_info_rules.py` ALL OK(일부러 틀린 응답 17건 거부), 스키마 검사 `scripts/check_model_schema.py` ALL PASS(2절 30행).
- B: 상태 미확인. 실행 근거 없음(2절 32행).
- C: 상태 미확인. 실행 근거 없음(2절 33행).
- B/C 첫 연결: 미확인(2절 34행).

미완료·막힌 이유·확인할 사람:
- 실제 기업 자료 검증: 미완료. 외부 LLM 입력 허용이 미확인(4절) → A가 자료 담당자에게 확인.
- A/B/C 공통 기준 합의: 미확인(2-1 체크리스트 미체크) → A·B·C.
- C 전달: 미전달(5절) → A.
- OpenAI API 오류(키·권한·한도·연결)의 ErrorObject 매핑: 미정 → A·C.
- 반복 호출 안정성: 미확인. lead_time이 한 번 supported로 분류된 이력 있음(2절 29행) → A.
- 사람의 원문 의미 검토: 미실시(agent_extract_01.json 문장·상태) → A 또는 D.
- 원문 비교 정규화 규칙: 미정. 현재 quote는 글자 그대로 비교 → D·A.
- API 키 재발급: 작업 중 `.env` 내용이 AI 대화에 표시된 이력이 있어 재발급을 권장했으나 실시 여부 미확인 → A.

서버/화면 실행 명령·주소:
- A Agent 테스트: `.\.venv\Scripts\python.exe scripts\test_agent.py` (프로젝트 루트, `.env` 필요, 기존 결과가 있으면 STOP)
- 가짜 데이터 검사: `.\.venv\Scripts\python.exe validate_fixtures.py`
- B 화면 / C 서버 실행 명령·주소: 기록 없음(B/C 작성 필요).

공통 JSON/API 기준: `contracts/contract.md`, `contracts/profile.schema.json`

D 첫 작업: 인수인계 확인 → Mock 실행 → 기존 TXT/MD 파서 확인 → 허용된 원본 1개 추출.
그 뒤 Mock의 draft_sections로 실제 MD 파일 저장·열기, 같은 결과의 DOCX 출력 순서로 진행.
- 참고: 추출·인용 검사를 보강할 때 `backend/agent.py`의 check_company_info 규칙(14개 키·상태별 facts 수·빈 값·근거 위치·quote 원문 포함)을 기준으로 삼을 수 있음. 허용된 원본이 없으면 실제 기업 자료 추출은 진행하지 않음.

자료 보관 위치·사용 허용·정리 상태:
- 가짜 자료: `fixtures/`, 가짜 입력 복사본 `private_runs/day1/agent_input.json`, 가짜 자료 추출 결과 `private_runs/day1/agent_extract_01.json`(Git 제외).
- 실제 기업 자료: 사용·저장하지 않음. 사용 허용 미확인.
- `.env`(API 키)와 `private_runs/`는 Git 제외 규칙 확인됨. 키 값은 이 문서에 기록하지 않음.
- 임시 저장 정리: 미실시(현재 private_runs에는 가짜 자료만 있음).
