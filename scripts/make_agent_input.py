"""A에게 넘길 agent_input 예시(가짜 자료)를 만든다.

두 방법 모두 서버와 같은 backend/parsers.py 규칙으로 만든 source_units를 쓴다.

1) 실제 업로드 결과 복사 — 서버에 가짜 TXT 2개를 업로드한 작업의 기록을 그대로 복사
       python scripts/make_agent_input.py --job <job_id>
   원본: private_runs/<job_id>/agent_input.json (서버가 추출 직후 저장)

2) 서버 없이 재생성 — fixtures/mock_source_a.txt(S001), mock_source_b.txt(S002)를 파서로 직접 추출
       python scripts/make_agent_input.py [--hint 테스트 회사]

출력: handoff/agent_input_example.json (키: schema_version, company_name_hint, source_units만)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import parsers  # noqa: E402

AGENT_INPUT_KEYS = {"schema_version", "company_name_hint", "source_units"}


def from_job(job_id: str) -> dict:
    path = ROOT / "private_runs" / job_id / "agent_input.json"
    if not path.is_file():
        raise SystemExit(f"작업 기록이 없습니다: private_runs/{job_id}/agent_input.json")
    return json.loads(path.read_text(encoding="utf-8"))


def from_fixtures(hint: str | None) -> dict:
    stored_files = [
        {"source_id": "S001", "stored_path": ROOT / "fixtures" / "mock_source_a.txt",
         "display_name": "mock_source_a.txt"},
        {"source_id": "S002", "stored_path": ROOT / "fixtures" / "mock_source_b.txt",
         "display_name": "mock_source_b.txt"},
    ]
    source_units, _manifest, _warnings = parsers.extract_sources(stored_files)
    return {"schema_version": "1.0", "company_name_hint": hint, "source_units": source_units}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--job", help="업로드 작업 번호. 주면 private_runs/<job_id>/agent_input.json을 복사")
    ap.add_argument("--hint", default="테스트 회사", help="--job 없이 만들 때 company_name_hint")
    ap.add_argument("--out", default=str(ROOT / "handoff" / "agent_input_example.json"))
    args = ap.parse_args()

    agent_input = from_job(args.job) if args.job else from_fixtures(args.hint)
    if set(agent_input) != AGENT_INPUT_KEYS or agent_input["schema_version"] != "1.0":
        raise SystemExit(f"agent_input 모양이 규격과 다릅니다: keys={sorted(agent_input)}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(agent_input, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    appendix = json.loads((ROOT / "fixtures" / "agent_input_mock.json").read_text(encoding="utf-8"))
    print(f"저장: {out}")
    print(f"출처: {'private_runs/' + args.job + '/agent_input.json' if args.job else 'fixtures 가짜 TXT 직접 추출'}")
    print(f"source_units {len(agent_input['source_units'])}개, company_name_hint={agent_input['company_name_hint']!r}")
    print(f"fixtures/agent_input_mock.json(부록 원문)과 동일: {agent_input == appendix}")


if __name__ == "__main__":
    main()
