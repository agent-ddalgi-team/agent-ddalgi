"""4-4단계 확인: 가짜 입력으로 OpenAI를 한 번 호출해 JSON 객체를 받는지만 본다. 파일은 저장하지 않는다.

실행(프로젝트 루트에서):
    .\\.venv\\Scripts\\python.exe scripts\\check_openai_extract.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import openai
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.agent import (  # noqa: E402
    AgentError, assign_fact_ids, build_model_output_schema, call_openai, check_agent_input, check_company_info,
    load_extract_prompt,
)

# 가짜 자료만 사용한다. 실제 기업 자료로 바꾸지 않는다.
INPUT_PATH = ROOT / 'fixtures' / 'agent_input_mock.json'


def main() -> int:
    agent_input = json.loads(INPUT_PATH.read_text(encoding='utf-8'))
    check_agent_input(agent_input)
    try:
        parsed, meta = call_openai(load_extract_prompt(), agent_input)
    except AgentError as exc:
        print(f'FAIL: {exc.code} [{exc.rule}] {exc.message}')
        if exc.details:
            print('call:', exc.details)
        return 1
    except openai.APIError as exc:
        print(f'FAIL: OpenAI {type(exc).__name__}: {exc.message}')
        return 1

    print('PASS: OpenAI 응답을 JSON 객체(Python dict)로 받음')
    print('call:', meta)
    # 참고용 형식 확인. 내용·근거가 맞는지는 검사하지 않는다.
    errors = list(Draft202012Validator(build_model_output_schema()).iter_errors(parsed))
    print('모델용 스키마 형식(참고):', 'OK' if not errors else f'{len(errors)}건 불일치')
    for key, field in parsed.items():
        facts = field.get('facts', []) if isinstance(field, dict) else []
        print(f'- {key}: {field.get("status") if isinstance(field, dict) else field} / facts {len(facts)}')
        for fact in facts:
            refs = ', '.join(f'{e.get("source_id")} {e.get("locator")} "{e.get("quote")}"' for e in fact.get('evidence', []))
            print(f'    text="{fact.get("text")}" <- {refs}')
    # 4-5단계: 받은 응답을 규칙 검사하고, 통과한 경우에만 fact_id를 붙인다.
    try:
        check_company_info(parsed, agent_input)
    except AgentError as exc:
        print(f'FAIL: {exc.code} [{exc.rule}] {exc.message}')
        print('details:', json.dumps(exc.details, ensure_ascii=False))
        return 1
    numbered = assign_fact_ids(parsed)
    print('PASS: check_company_info 5개 규칙 통과 → fact_id 부여')
    for key, field in numbered.items():
        for fact in field['facts']:
            print(f'    {fact["fact_id"]} {key} ({field["status"]}): "{fact["text"]}"')
    print('NOT CHECKED: 문장 의미의 사람 검토, extract_company_info 완성, 파일 저장')
    return 0


if __name__ == '__main__':
    sys.exit(main())
