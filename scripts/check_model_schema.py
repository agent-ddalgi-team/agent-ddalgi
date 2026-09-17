"""GPT에 넘길 모델용 출력 스키마를 OpenAI 호출 없이 검사한다.

실행(프로젝트 루트에서):
    .\\.venv\\Scripts\\python.exe scripts\\check_model_schema.py
"""
from __future__ import annotations
import copy
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.agent import COMPANY_INFO_KEYS, build_model_output_schema  # noqa: E402

STATUSES = ['supported', 'conflict', 'needs_confirmation', 'not_found']
FORBIDDEN_KEYS = ('fact_id', 'sources', 'is_mock', 'validation', 'schema_version')


def walk_objects(node, path='$'):
    """스키마 안의 모든 object 정의를 (경로, 정의)로 돌려준다."""
    if isinstance(node, dict):
        if node.get('type') == 'object':
            yield path, node
        for key, value in node.items():
            yield from walk_objects(value, f'{path}.{key}')


def main() -> int:
    failures: list[str] = []

    def check(ok: bool, rule: str) -> None:
        print(('PASS' if ok else 'FAIL') + ': ' + rule)
        if not ok:
            failures.append(rule)

    schema = build_model_output_schema()
    defs = schema['$defs']

    # 1) 스키마 자체의 구조 검사
    Draft202012Validator.check_schema(schema)
    check(True, 'JSON Schema 문법 오류 없음')
    check(list(schema['properties']) == list(COMPANY_INFO_KEYS) and schema['required'] == list(COMPANY_INFO_KEYS),
          f'company_info {len(COMPANY_INFO_KEYS)}개 키 모두 required')
    status = defs['field']['properties']['status']
    check(defs['field']['required'] == ['status', 'facts'] and status.get('type') == 'string' and status['enum'] == STATUSES,
          '각 항목 = status(string, 4개 상태만) + facts 배열')
    check(defs['fact']['required'] == ['text', 'evidence'], '각 fact = text + evidence 배열 (fact_id 없음)')
    check(defs['evidence']['required'] == ['source_id', 'locator', 'quote'], '각 evidence = source_id + locator + quote')
    schema_text = json.dumps(schema)
    check(not any(f'"{key}"' in schema_text for key in FORBIDDEN_KEYS),
          'fact_id·sources·is_mock·validation·schema_version 없음')
    objects = list(walk_objects(schema))
    check(all(obj.get('additionalProperties') is False and sorted(obj['required']) == sorted(obj['properties'])
              for _, obj in objects),
          f'Structured Outputs strict 조건: object {len(objects)}곳 모두 추가 키 금지 + 모든 속성 required')

    # 2) 예시 데이터로 통과·거부 확인. 가짜 Mock의 company_info에서 fact_id만 뺀 것을 정상 예시로 쓴다.
    validator = Draft202012Validator(schema)
    mock = json.loads((ROOT / 'fixtures/mock_profile.json').read_text(encoding='utf-8'))['company_info']
    sample = copy.deepcopy(mock)
    for field in sample.values():
        for fact in field['facts']:
            del fact['fact_id']
    check(validator.is_valid(sample), '정상 예시(가짜 Mock, fact_id 제거) 통과')

    def rejects(mutate, rule: str) -> None:
        bad = copy.deepcopy(sample)
        mutate(bad)
        check(not validator.is_valid(bad), rule)

    rejects(lambda d: d.pop('lead_time'), '항목 하나가 빠진 응답은 거부')
    rejects(lambda d: d['lead_time'].update(status='unknown'), '4개 외 상태는 거부')
    rejects(lambda d: d['company_name']['facts'][0].update(fact_id='F001'), 'GPT가 fact_id를 넣은 응답은 거부')
    rejects(lambda d: d.update(sources=[]), 'sources를 추가한 응답은 거부')
    rejects(lambda d: d['company_name']['facts'][0]['evidence'][0].pop('quote'), 'evidence에 quote가 빠진 응답은 거부')

    # 3) 형식은 맞지만 의미가 틀린 응답: 모델용 스키마로는 못 잡는다는 것을 보여준다.
    wrong_meaning = copy.deepcopy(sample)
    wrong_meaning['certifications'] = {'status': 'not_found', 'facts': sample['company_name']['facts']}
    print('NOTE: "not_found인데 facts가 있음" 응답의 모델용 스키마 통과 여부 =',
          validator.is_valid(wrong_meaning), '→ 의미 규칙은 이후 코드 검사에서 따로 확인')

    print('ALL PASS' if not failures else f'FAILED: {len(failures)}건')
    return 0 if not failures else 1


if __name__ == '__main__':
    sys.exit(main())
