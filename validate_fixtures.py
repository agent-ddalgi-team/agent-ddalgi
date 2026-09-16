"""Validate the bundled synthetic fixtures, not real company truth.

Run: python -m pip install jsonschema
     python validate_fixtures.py
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any


def validate() -> None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise SystemExit('Install jsonschema first: python -m pip install jsonschema') from exc
    root = Path(__file__).resolve().parent
    schema = json.loads((root / 'contracts/profile.schema.json').read_text(encoding='utf-8'))
    profile = json.loads((root / 'fixtures/mock_profile.json').read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(profile)
    if not profile['is_mock']:
        raise ValueError('Bundled fixtures must be clearly marked as mock.')

    sources: dict[str, list[str]] = {}
    for source in profile['sources']:
        filename = source['file_name']
        if Path(filename).name != filename:
            raise ValueError('Fixture source must be a plain filename.')
        sources[source['source_id']] = (root / 'fixtures' / filename).read_text(encoding='utf-8').splitlines()

    facts: dict[str, dict[str, Any]] = {}
    for field in profile['company_info'].values():
        for fact in field['facts']:
            fid = fact['fact_id']
            if fid in facts:
                raise ValueError(f'Duplicate fact_id: {fid}')
            facts[fid] = {'status': field['status'], 'fact': fact}
            for e in fact['evidence']:
                if e['source_id'] not in sources:
                    raise ValueError(f'Unknown source: {e["source_id"]}')
                if not e['locator'].endswith('행'):
                    raise ValueError('This fixture validator supports numbered TXT lines only.')
                line = int(e['locator'][:-1])
                lines = sources[e['source_id']]
                if line < 1 or line > len(lines) or e['quote'] not in lines[line - 1]:
                    raise ValueError(f'Quote not found at its specified location: {fid}')

    placeholders = {'자료에서 확인되지 않음', '추가 확인 필요'}
    for section in profile['draft_sections']:
        for paragraph in section['paragraphs']:
            if not paragraph['fact_ids']:
                if paragraph['text'] not in placeholders:
                    raise ValueError('Uncited paragraph is not an approved placeholder.')
            for fid in paragraph['fact_ids']:
                if fid not in facts or facts[fid]['status'] != 'supported':
                    raise ValueError(f'Draft refers to a missing or unsupported fact: {fid}')

    ready = json.loads((root / 'fixtures/mock_job_ready.json').read_text(encoding='utf-8'))
    if ready['status'] != 'ready' or ready['result'] != profile:
        raise ValueError('Ready API fixture differs from the common profile.')
    print('PASS: JSON Schema, source locations, unique fact IDs, draft links, API fixture consistency.')
    print('Not checked: semantic truth, current company facts, LLM/API execution, DOCX rendering.')


if __name__ == '__main__':
    validate()
