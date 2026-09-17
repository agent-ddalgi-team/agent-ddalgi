"""A 담당 Agent 실행 테스트: 가짜 입력으로 extract_company_info를 1회 호출하고,
Mock 기대 상태 자동 검사를 모두 통과한 경우에만 결과를 저장한다.

실행(프로젝트 루트에서):
    .\\.venv\\Scripts\\python.exe scripts\\test_agent.py
기존 결과 파일을 일부러 새 결과로 바꿀 때만:
    .\\.venv\\Scripts\\python.exe scripts\\test_agent.py --overwrite

입력은 fixtures/agent_input_mock.json(가짜 자료)으로 고정한다. 실제 기업 자료는 이 스크립트로 넣지 않는다.
검사하는 것: 14개 키, Mock 기대 상태, fact_id 순서, 근거 위치, quote 원문 포함, 공통 스키마 company_info 규칙.
검사하지 않는 것: 문장 표현이 mock_profile.json과 같은지, 동일 사실의 evidence 개수, 사람의 의미 검토.
"""
from __future__ import annotations
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import openai
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.agent import COMPANY_INFO_KEYS, AgentError, AgentInputError, extract_company_info  # noqa: E402

INPUT_PATH = ROOT / 'fixtures' / 'agent_input_mock.json'
OUTPUT_PATH = ROOT / 'private_runs' / 'day1' / 'agent_extract_01.json'

# 가짜 자료(mock_source_a/b.txt)의 기대 상태: (status, 최소 facts 수). 여기에 없는 항목은 not_found + facts=[].
EXPECTED = {
    'company_name': ('supported', 1),
    'company_summary': ('supported', 1),
    'business_areas': ('supported', 1),
    'process_count': ('conflict', 2),
    'lead_time': ('needs_confirmation', 1),
}


def contract_validator() -> Draft202012Validator:
    """공통 스키마(profile.schema.json)의 company_info 규칙만 떼어 검사기로 만든다. 파일은 읽기만 한다."""
    schema = json.loads((ROOT / 'contracts/profile.schema.json').read_text(encoding='utf-8'))
    return Draft202012Validator({'$defs': schema['$defs'], **schema['properties']['company_info']})


def run_checks(info: Any, agent_input: dict[str, Any]) -> list[str]:
    """모든 검사를 실행하고 실패한 검사 이름 목록을 돌려준다. 빈 목록이면 모두 통과."""
    failures: list[str] = []

    def check(ok: bool, name: str, detail: str = '') -> None:
        print(f"{'PASS' if ok else 'FAIL'}: {name}" + (f' ({detail})' if detail else ''))
        if not ok:
            failures.append(name)

    # 1) 반환 키 14개
    keys_ok = isinstance(info, dict) and len(info) == len(COMPANY_INFO_KEYS) and set(info) == set(COMPANY_INFO_KEYS)
    check(keys_ok, f'반환 키 {len(COMPANY_INFO_KEYS)}개', f'실제 {len(info) if isinstance(info, dict) else type(info).__name__}')
    if not keys_ok:
        return failures

    # 2) Mock 기대 상태
    for key in COMPANY_INFO_KEYS:
        status, min_facts = EXPECTED.get(key, ('not_found', 0))
        actual_status, count = info[key]['status'], len(info[key]['facts'])
        if status == 'not_found':
            ok, want = actual_status == status and count == 0, 'facts=[]'
        else:
            ok, want = actual_status == status and count >= min_facts, f'facts {min_facts}개 이상'
        check(ok, f'기대 상태 {key} = {status}, {want}', f'실제 {actual_status} / facts {count}')

    # 3) fact_id가 F001부터 중복 없이 순서대로
    ids = [fact.get('fact_id') for key in COMPANY_INFO_KEYS for fact in info[key]['facts']]
    expected_ids = [f'F{n:03d}' for n in range(1, len(ids) + 1)]
    check(ids == expected_ids and len(set(ids)) == len(ids), 'fact_id F001부터 중복 없이 순서대로', ', '.join(map(str, ids)))

    # 4) evidence의 source_id + locator가 입력에 존재, 5) quote가 그 source_unit text 안에 존재
    source_texts = {(unit['source_id'], unit['locator']): unit['text'] for unit in agent_input['source_units']}
    evidences = [(fact['fact_id'], ev) for key in COMPANY_INFO_KEYS for fact in info[key]['facts'] for ev in fact['evidence']]
    unknown = [f'{fid} {ev["source_id"]} {ev["locator"]}' for fid, ev in evidences
               if (ev['source_id'], ev['locator']) not in source_texts]
    check(not unknown, f'evidence {len(evidences)}개의 source_id+locator가 입력 source_units에 존재', ', '.join(unknown))
    not_in_text = [f'{fid} {ev["source_id"]} {ev["locator"]}' for fid, ev in evidences
                   if (ev['source_id'], ev['locator']) in source_texts
                   and ev['quote'] not in source_texts[(ev['source_id'], ev['locator'])]]
    check(not not_in_text, f'quote {len(evidences)}개가 해당 source_unit text 안에 존재', ', '.join(not_in_text))

    # 6) 공통 스키마 company_info 규칙(상태별 facts 개수·필수 키·빈 문자열 금지 포함)
    errors = list(contract_validator().iter_errors(info))
    check(not errors, '공통 스키마(profile.schema.json) company_info 규칙', '; '.join(e.message[:100] for e in errors[:3]))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description='가짜 입력으로 extract_company_info를 실행하고 검사 통과 시 결과를 저장한다.')
    parser.add_argument('--overwrite', action='store_true', help='기존 agent_extract_01.json을 새 결과로 바꾼다')
    args = parser.parse_args()
    output_name = OUTPUT_PATH.relative_to(ROOT).as_posix()

    # 기존 결과가 있으면 API를 부르기 전에 알리고 멈춘다.
    if OUTPUT_PATH.exists() and not args.overwrite:
        print(f'STOP: 기존 결과 파일이 있습니다: {output_name}')
        print('내용을 확인한 뒤 새 결과로 바꾸려면 --overwrite를 붙여 다시 실행하세요. API는 호출하지 않았습니다.')
        return 2

    # 호출 정보(모델·상태·토큰 수)만 화면에 보인다. 키·원문은 기록하지 않는다.
    logging.basicConfig(format='%(message)s')
    logging.getLogger('backend.agent').setLevel(logging.INFO)

    agent_input = json.loads(INPUT_PATH.read_text(encoding='utf-8'))
    print(f'입력: {INPUT_PATH.relative_to(ROOT).as_posix()} (가짜 자료, source_units {len(agent_input["source_units"])}개)')
    try:
        info = extract_company_info(agent_input)
    except (AgentError, AgentInputError) as exc:
        print(f'FAIL: extract_company_info - {exc}')
        if getattr(exc, 'details', None):
            print('details:', json.dumps(exc.details, ensure_ascii=False))
        print('결과 파일을 저장하지 않았습니다.')
        return 1
    except openai.APIError as exc:
        print(f'FAIL: OpenAI {type(exc).__name__}: {exc.message}')
        print('결과 파일을 저장하지 않았습니다.')
        return 1
    print('PASS: extract_company_info 실행 성공')

    failures = run_checks(info, agent_input)
    if failures:
        print(f'FAILED: {len(failures)}건 - 결과 파일을 저장하지 않았습니다.')
        return 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        # --overwrite가 없으면 'x' 모드: 검사 도중 파일이 생겼더라도 덮어쓰지 않는다.
        with OUTPUT_PATH.open('w' if args.overwrite else 'x', encoding='utf-8', newline='\n') as file:
            file.write(json.dumps(info, ensure_ascii=False, indent=2) + '\n')
    except FileExistsError:
        print(f'STOP: 실행 중에 결과 파일이 생겼습니다. 덮어쓰지 않았습니다: {output_name}')
        return 2
    saved_ok = json.loads(OUTPUT_PATH.read_text(encoding='utf-8')) == info
    print(f"{'PASS' if saved_ok else 'FAIL'}: 저장한 파일을 다시 읽어 반환값과 일치 확인")
    if not saved_ok:
        return 1
    print(f'ALL PASS: {output_name} 저장 완료 (company_info만 저장, 중간 결과이며 최종 ProfileResult 아님)')
    print('NOT CHECKED: 사람의 원문 의미 검토, 실제 기업 자료 검증')
    return 0


if __name__ == '__main__':
    sys.exit(main())
