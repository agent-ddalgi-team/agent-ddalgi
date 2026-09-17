"""4-5단계 확인: check_company_info 검사 규칙과 fact_id 부여를 OpenAI 호출 없이 검사한다.

정상 예시와 일부러 틀린 응답은 모두 가짜 Mock(fixtures/)에서 만든다. 파일은 저장하지 않는다.
실행(프로젝트 루트에서):
    .\\.venv\\Scripts\\python.exe scripts\\check_company_info_rules.py
"""
from __future__ import annotations
import copy
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.agent import AgentError, assign_fact_ids, check_agent_input, check_company_info  # noqa: E402

# details에 들어가도 되는 키. 원문 text·API 키 같은 값이 섞이지 않았는지 확인한다.
ALLOWED_DETAIL_KEYS = {
    'rule', 'field', 'status', 'fact_index', 'evidence_index', 'source_id', 'locator', 'quote',
    'expected', 'actual', 'missing_keys', 'unexpected_keys', 'value_name',
}


def contract_validator() -> Draft202012Validator:
    """공통 스키마(profile.schema.json)의 company_info 규칙만 떼어 검사기로 만든다. 파일은 읽기만 한다."""
    schema = json.loads((ROOT / 'contracts/profile.schema.json').read_text(encoding='utf-8'))
    return Draft202012Validator({'$defs': schema['$defs'], **schema['properties']['company_info']})


def main() -> int:
    agent_input = json.loads((ROOT / 'fixtures/agent_input_mock.json').read_text(encoding='utf-8'))
    check_agent_input(agent_input)
    expected = json.loads((ROOT / 'fixtures/mock_profile.json').read_text(encoding='utf-8'))['company_info']
    # GPT 응답 모양의 정상 예시: Mock company_info에서 fact_id만 뺀 것
    sample = copy.deepcopy(expected)
    for field in sample.values():
        for fact in field['facts']:
            del fact['fact_id']
    failures: list[str] = []

    def report(ok: bool, name: str, got: object) -> None:
        print(f"{'OK ' if ok else 'BAD'} {name}: {got}")
        if not ok:
            failures.append(name)

    print('[정상 예시]')
    before = json.dumps(sample, sort_keys=True)
    check_company_info(sample, agent_input)
    numbered = assign_fact_ids(sample)
    ids = [fact['fact_id'] for field in numbered.values() for fact in field['facts']]
    report(True, '5개 규칙 검사', 'PASS')
    report(ids == [f'F{n:03d}' for n in range(1, len(ids) + 1)], 'fact_id 부여 순서', ', '.join(ids))
    report(numbered == expected, 'Mock company_info의 fact_id·내용과 동일', numbered == expected)
    report(contract_validator().is_valid(numbered), '부여 결과가 공통 스키마 company_info 규칙 통과', 'PASS')
    report(json.dumps(sample, sort_keys=True) == before, '원래 응답 객체는 바뀌지 않음', 'PASS')

    def fact(d, key, i=0):
        return d[key]['facts'][i]

    def ev(d, key, i=0, j=0):
        return d[key]['facts'][i]['evidence'][j]

    cases = [
        ('lead_time 항목 누락', lambda d: d.pop('lead_time'), 'company_info_keys'),
        ('sources 키 추가', lambda d: d.update(sources=[]), 'company_info_keys'),
        ('GPT가 fact_id를 넣음', lambda d: fact(d, 'company_name').update(fact_id='F001'), 'field_shape'),
        ('facts가 배열이 아님', lambda d: d['history'].update(facts='없음'), 'field_shape'),
        ('4개 외 status', lambda d: d['history'].update(status='unknown'), 'status_value'),
        ('not_found인데 facts 1개',
         lambda d: d['certifications'].update(facts=copy.deepcopy(d['company_name']['facts'])), 'status_fact_count'),
        ('conflict인데 facts 1개', lambda d: d['process_count']['facts'].pop(), 'status_fact_count'),
        ('supported인데 facts 0개', lambda d: d['company_summary'].update(facts=[]), 'status_fact_count'),
        ('needs_confirmation인데 facts 0개', lambda d: d['lead_time'].update(facts=[]), 'status_fact_count'),
        ('text 공백', lambda d: fact(d, 'company_name').update(text='  '), 'empty_value'),
        ('quote 빈 문자열', lambda d: ev(d, 'business_areas').update(quote=''), 'empty_value'),
        ('evidence 빈 배열', lambda d: fact(d, 'lead_time').update(evidence=[]), 'evidence_empty'),
        ('없는 source_id S999', lambda d: ev(d, 'company_name').update(source_id='S999'), 'evidence_location_unknown'),
        ('없는 locator 9행', lambda d: ev(d, 'company_name').update(locator='9행'), 'evidence_location_unknown'),
        ('원문에 없는 quote "공정 수: 5개"',
         lambda d: ev(d, 'process_count', 1).update(quote='공정 수: 5개'), 'quote_not_in_source'),
        ('다른 행의 문장을 quote로 사용',
         lambda d: ev(d, 'company_name').update(quote='회사 개요: 테스트용 기업입니다.'), 'quote_not_in_source'),
        ('규칙 2·5 동시 위반 → 순서상 규칙 2에서 멈춤',
         lambda d: (d['technology'].update(facts=copy.deepcopy(d['company_name']['facts'])),
                    ev(d, 'lead_time').update(quote='납기 3일')), 'status_fact_count'),
    ]

    print('[일부러 틀린 응답]')
    for name, mutate, rule in cases:
        bad = copy.deepcopy(sample)
        mutate(bad)
        before = json.dumps(bad, sort_keys=True)
        try:
            check_company_info(bad, agent_input)
        except AgentError as exc:
            details = exc.details or {}
            ok = (exc.code == 'INVALID_OUTPUT' and exc.rule == rule and details.get('rule') == rule
                  and set(details) <= ALLOWED_DETAIL_KEYS and json.dumps(bad, sort_keys=True) == before)
            report(ok, name, f'{exc.code} [{exc.rule}] {json.dumps(details, ensure_ascii=False)}')
        else:
            report(False, name, '거부되지 않음')

    print('ALL OK' if not failures else f'FAILED: {len(failures)}건')
    return 0 if not failures else 1


if __name__ == '__main__':
    sys.exit(main())
