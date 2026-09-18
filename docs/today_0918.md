# 2026-09-18(금) 실행 기록 — A (팀장 + Agent)

담당 요구: R03(14개 정보·근거) / R04(소개서 본문) / R07(최종 결과 검사) / R10(자료 허용·검토)

> 이 문서에는 **실제로 실행해 확인한 것만** 적는다. 입력은 전부 가짜 테스트 자료이며,
> 실제 기업 자료는 사용하지 않았다. 원문·생성 결과·`.env`는 Git에 올리지 않는다.

## 1. 오늘 작업한 코드

| 커밋 | 내용 | PR | 상태 |
|---|---|---|---|
| `a911b88` | fix: 추출 프롬프트의 상태별 facts 규칙 보강 | #7 | develop 병합 |
| `342c2a8` | feat: 회사소개서 본문 생성 및 검증 기능 추가 | #8 | develop 병합 |

변경 파일: `prompts/extract.txt`, `backend/agent.py`, `scripts/check_draft_rules.py`.
`backend/main.py`·`backend/profile_builder.py`·`backend/validators.py`·`contracts/`는 수정하지 않았다.

### 추출 프롬프트 보강 (R03)

`needs_confirmation`인데 `facts`가 빈 배열로 돌아와 `INVALID_OUTPUT[status_fact_count]`가
간헐적으로 발생했다. 원인은 개수 규칙이 모델에 전달되지 않는 것이었다.

- `contracts/profile.schema.json`의 `allOf`/`if`/`then`·`minItems`는 Structured Outputs strict에서
  제외되므로(`build_model_output_schema`), 모델이 보는 스키마에는 개수 하한이 없다.
- `prompts/extract.txt`에도 개수를 명시한 줄은 `not_found` 하나뿐이었다.

프롬프트에만 두 가지를 보강했다(코드 변경 없음).

1. `supported`/`needs_confirmation`은 1개 이상, `conflict`는 2개 이상을 명시
2. "불명확성은 status로 표현한다"가 "fact를 만들지 말라"로 과잉 적용되지 않도록 단서 추가

### 본문 생성 (R04)

`backend/agent.py`에 `draft_profile(supported_facts) -> draft_sections`를 추가했다.

- 입력: `profile_builder.collect_supported_facts()`의 `[{field, fact_id, text}]`
- 출력: `[{key, title, paragraphs: [{text, fact_ids}]}]` — supported 섹션만
- `company_name`은 단독 본문 섹션이 없어 대상에서 제외한다(13개 섹션 기준).
  단 다른 섹션이 그 `fact_id`를 근거로 참조하는 것은 허용된다.
- 누락·상충 항목의 고정 안내 문구는 C(`profile_builder`)가 붙이므로,
  본문이 같은 문구를 만들면 `INVALID_OUTPUT[placeholder_text]`로 거부한다.
- 기존 `call_openai`는 `_call_openai_json`으로 분리해 추출/본문이 공유한다.
  공개 함수명·시그니처·동작은 그대로 유지했다.

### 검증 (R07)

D의 `backend/validators.py`(`validate_draft`, `validate_profile_result`)가 이미 있어
**새로 만들지 않고 재사용**했다. A 쪽에는 모델 응답 검사(`check_draft_sections`)만 추가했다.

## 2. 실제 실행 기록

`AGENT_MODE=llm`, 프로젝트 `.venv`, `backend.main:app`, `127.0.0.1:8000`, `--reload` 없음.

| job_id | 입력 | 모드 | 호출 | 토큰 | 결과 |
|---|---|---|---|---|---|
| `1009d15b-d00d-448c-9398-f8b1b39c6c07` | `mock_source_a/b.txt` | llm | 2회 | 2,525 | ready → MD·DOCX 생성 |
| `0d40cd02-dbaa-4913-ae92-be3759539f5f` | `day2_variant_source_a/b.txt` | llm | 2회 | 2,516 | ready → MD 생성 |

두 작업 모두 `run_meta.json`에 `agent_mode=llm`, `llm_called=true`,
`input_kind=fake_test_data`가 기록됐다. 고정 Mock 결과로 대체되지 않았다.

호출 수와 토큰은 서버 로그(`backend.agent`의 `openai call`, httpx의 `api.openai.com` 요청)로
확인했다. 두 실행 모두 **SDK 내부 재시도 0회**, 전부 `200 OK`.
`OPENAI_MAX_RETRIES = 1`이라 논리 호출 1건당 최대 2번 요청이 가능하지만 실제로는 발생하지 않았다.
문서(MD/DOCX) 생성 중 추가 LLM 호출은 **0회**였다.

### 입력을 바꾸면 결과가 바뀌는가 (R08 / 최소테스트 2번)

| | 기준 (`1009d15b`) | variant (`0d40cd02`) |
|---|---|---|
| 회사명 사실 | 테스트 회사 | 두번째 테스트 회사 |
| 사업 분야 사실 | 테스트 사업 A | 테스트 사업 B |
| 개요 본문 | 테스트 회사는 테스트용 기업입니다. | 두번째 테스트 회사는 테스트용 기업입니다. |
| 사업 분야 본문 | 테스트 회사의 사업 분야로 테스트 사업 A가 제공되었습니다. | 테스트 사업 B |
| MD 근거 자료 | mock_source_a/b.txt | day2_variant_source_a/b.txt |

두 실행 모두 상태 분포는 supported 3 / conflict 1 / needs_confirmation 1 / not_found 9,
`process_count`는 2개와 3개의 상충을 `conflict`로 유지했다.
`fact_id`는 F001~F006으로 중복·재부여 없이 유지됐다.

variant의 사업 분야 본문은 서술문 없이 값만 나왔다. 근거·`fact_ids` 규칙 위반은 아니지만
기준 실행과 문장 형태가 달라진 점을 기록해 둔다. 이 때문에 코드·프롬프트를 고치지는 않았다.

### 오프라인 검사 (유료 호출 없음)

`check_model_schema` / `check_company_info_rules` / `check_draft_rules` /
`check_profile_builder` / `test_validators` / `check_llm_mode` — 모두 통과.

`scripts/check_draft_rules.py`는 이번에 추가한 A 테스트다. 일부러 틀린 응답 17건
(섹션 누락·중복, `company_name` 단독 섹션, 제목 불일치, 서버 안내 문구 중복 생성,
`fact_ids` 빈 배열·중복·없는 ID, supported 아닌 사실 참조)을 모두 거부하는지 확인한다.

`scripts/check_llm_job.py`는 `company_info.json`만 있으면 통과로 판정하므로
`ready` 판정에는 쓰지 않았다. C의 파일은 수정하지 않고 별도 임시 검사로 확인했다.

## 3. 산출물 위치 (Git 제외)

```
private_runs/1009d15b-.../result.json, documents/회사소개서_초안.md, .docx
private_runs/0d40cd02-.../result.json, documents/회사소개서_초안.md
```

`private_runs/`는 `.gitignore`로 제외된다. `.env`·API 키는 어디에도 기록하지 않았다.

## 4. 자료 사용 허용 (R10)

기업 원문의 외부 LLM 입력 허용은 **여전히 미확인**이다. 새 허용 근거를 받지 못했다.
확인 전까지 가짜 테스트 자료만 사용하며, 실제 기업 자료 검증은 진행하지 않는다.

## 5. 다음 담당자에게

- **B**: variant job `0d40cd02-dbaa-4913-ae92-be3759539f5f`를 React 화면에서 조회해
  회사명 "두번째 테스트 회사", 사업 분야 "테스트 사업 B"가 표시되는지 확인해 주세요.
  R08의 화면 대조 증거가 아직 없습니다.
- **C**: 같은 job_id로 DOCX 생성을 확인해 주세요. 이번 범위에서는 MD만 확인했습니다.
- **A(본인)**: 생성 문장의 의미를 원문과 직접 대조해야 합니다. 자동 검사는 `fact_ids`가
  supported 사실을 가리키는지와 인용문이 원문에 있는지만 봅니다.
