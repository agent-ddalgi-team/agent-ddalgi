r"""llm 모드 실제 호출 확인 — 가짜 TXT 2개로 업로드 1건, OpenAI 호출 1회만 한다.

미리 준비할 것:
  1) 프로젝트 루트의 .env에 AGENT_MODE=llm, OPENAI_API_KEY, OPENAI_MODEL을 채운다.
  2) 서버를 .venv의 python으로 다시 시작한다(.env는 시작할 때만 읽는다).
     .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

실행(프로젝트 루트에서):
  .\.venv\Scripts\python.exe scripts\check_llm_job.py            # 기본 가짜 자료(mock_source_a/b)
  .\.venv\Scripts\python.exe scripts\check_llm_job.py --variant  # 변형 가짜 자료(day2_variant_source_a/b)

이 스크립트는 키 값을 읽거나 출력하지 않는다. 결과 판정은 run_meta.json의 llm_called과
작업 상태로만 한다. A의 draft_profile이 오기 전에는 drafting 단계 error가 정상이다.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"
PAIRS = {
    False: ("mock_source_a.txt", "mock_source_b.txt", "테스트 회사"),
    True: ("day2_variant_source_a.txt", "day2_variant_source_b.txt", None),
}


def main() -> int:
    variant = "--variant" in sys.argv
    name_a, name_b, hint = PAIRS[variant]
    files = [
        ("files", (name, (ROOT / "fixtures" / name).read_bytes(), "text/plain"))
        for name in (name_a, name_b)
    ]
    data = {"company_name_hint": hint} if hint else {}
    print(f"입력(가짜 테스트 자료): {name_a}, {name_b} / company_name_hint={hint!r}")

    with httpx.Client(base_url=BASE, timeout=30) as client:
        res = client.post("/api/profiles", files=files, data=data)
        print(f"POST /api/profiles → {res.status_code}")
        if res.status_code != 202:
            print("접수 실패:", res.text[:300])
            return 1
        job_id = res.json()["job_id"]
        print("job_id:", job_id)

        seen: list[str] = []
        body = None
        # LLM 호출은 최대 60초(agent.OPENAI_TIMEOUT_SECONDS) + 재시도 1회까지 걸릴 수 있다.
        for _ in range(300):
            body = client.get(f"/api/profiles/{job_id}").json()
            if not seen or seen[-1] != body["status"]:
                seen.append(body["status"])
            if body["status"] in ("ready", "error"):
                break
            time.sleep(0.5)

    print("상태 변화:", " → ".join(seen))
    print("최종 status:", body["status"])
    if body["error"]:
        print("error:", json.dumps(body["error"], ensure_ascii=False))

    job_dir = ROOT / "private_runs" / job_id
    meta_path = job_dir / "run_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    print("run_meta:", json.dumps(meta, ensure_ascii=False, indent=2))

    info_path = job_dir / "company_info.json"
    if info_path.is_file():
        company_info = json.loads(info_path.read_text(encoding="utf-8"))
        print("\ncompany_info.json (실제 추출 결과 요약):")
        for key, field in company_info.items():
            print(f"- {key}: {field['status']} / facts {len(field['facts'])}")
            for fact in field["facts"]:
                ev = ", ".join(f'{e["source_id"]} {e["locator"]}' for e in fact["evidence"])
                print(f'    {fact["fact_id"]} "{fact["text"]}" <- {ev}')
    else:
        print("\ncompany_info.json 없음 → 추출 결과가 만들어지지 않았다.")

    print(f"\n작업 폴더: {job_dir}")
    print("파일:", sorted(p.name for p in job_dir.iterdir()) if job_dir.is_dir() else "없음")

    if meta.get("agent_mode") != "llm":
        print("\n판정: 서버가 llm 모드가 아니다(.env 확인 후 서버 재시작 필요). 실제 호출 없음.")
        return 1
    if not meta.get("llm_called"):
        print("\n판정: 실제 호출에 도달하지 못했다(설정·입력 문제). 위 error를 확인한다.")
        return 1
    if info_path.is_file():
        print("\n판정: extract_company_info 실제 호출 성공(중간 결과 기록됨).")
        print("      A의 draft_profile·D의 검사 모듈이 없으면 그 다음 단계에서 error로 끝나는 것이 정상이다.")
        print("NOT CHECKED: 본문 생성, 검사, 최종 ready, 문서 파일, 추출 내용의 사람 검토")
        return 0
    print("\n판정: 호출은 했으나 추출 결과가 검사를 통과하지 못했다. 위 error를 확인한다.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
