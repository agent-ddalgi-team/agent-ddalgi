"""llm 모드 오류 경로 검사 — 실제 OpenAI 호출 없이 확인한다(가짜 데이터만 사용).

실행(프로젝트 루트에서):
    .\\.venv\\Scripts\\python.exe scripts\\check_llm_mode.py

확인하는 것:
- AGENT_MODE 오설정이면 서버 모듈이 시작을 거부한다(조용히 mock으로 대체하지 않음).
- llm 모드에서 LLM 설정(.env 키)이 없으면 작업이 error(INVALID_OUTPUT/analyzing)로 끝나고,
  result는 null(Mock 대체 없음), run_meta.json에 모드·호출 여부가 남고, 잠금이 풀려 다음 작업을 받는다.
확인하지 않는 것: 실제 LLM 호출 성공(.env에 키를 넣은 뒤 별도로 확인해야 한다).
주의: OPENAI_API_KEY가 이미 설정된 환경에서는 실수로 실제 호출을 하지 않도록 건너뛴다.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def fresh_main(mode: str):
    os.environ["AGENT_MODE"] = mode
    import backend.main as main_module
    return importlib.reload(main_module)


# 1) AGENT_MODE 오설정 → 서버 모듈 시작 거부
try:
    fresh_main("banana")
    check("AGENT_MODE 오설정 시 시작 거부", False, "RuntimeError가 나지 않음")
except RuntimeError:
    check("AGENT_MODE 오설정 시 시작 거부", True)

if (os.environ.get("OPENAI_API_KEY") or "").strip() or (ROOT / ".env").is_file():
    print("건너뜀: OPENAI 설정이 감지되어 '설정 누락' 오류 경로 시험을 하지 않습니다(실제 호출 방지).")
    print("실제 llm 호출 확인은 서버를 AGENT_MODE=llm으로 띄우고 가짜 TXT로 별도 진행하세요.")
    sys.exit(1 if failures else 0)

main = fresh_main("llm")
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(main.app)
FAKE = ("fake_a.txt", "회사명: 테스트 회사\n회사 개요: 테스트용 기업입니다.\n".encode("utf-8"), "text/plain")

# 2) llm 모드 + 설정 누락 → error로 종료, Mock 대체 없음
res = client.post("/api/profiles", files=[("files", FAKE)])
check("업로드 접수 202", res.status_code == 202, f"HTTP {res.status_code}")
job_id = res.json()["job_id"]
# TestClient는 응답 후 백그라운드 작업까지 실행하고 돌아오므로 바로 조회한다.
job = client.get(f"/api/profiles/{job_id}").json()
check("작업 상태 error(진행 중 멈춤 없음)", job["status"] == "error", f"status={job['status']}")
check("오류 code=INVALID_OUTPUT, stage=analyzing",
      job["error"] and job["error"]["code"] == "INVALID_OUTPUT" and job["error"]["stage"] == "analyzing",
      json.dumps(job["error"], ensure_ascii=False))
check("result는 null(Mock으로 대체하지 않음)", job["result"] is None)

meta_path = ROOT / "private_runs" / job_id / "run_meta.json"
meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else None
check("run_meta.json 기록(agent_mode=llm, llm_called=false)",
      meta is not None and meta["agent_mode"] == "llm" and meta["llm_called"] is False,
      json.dumps(meta, ensure_ascii=False) if meta else "파일 없음")

# 3) 실패 후 잠금이 풀려 다음 작업을 받는다
res2 = client.post("/api/profiles", files=[("files", FAKE)])
check("실패 후 다음 작업 접수 202(BUSY 아님)", res2.status_code == 202, f"HTTP {res2.status_code}")

# 원상 복구: 이후 다른 스크립트가 mock 기본값으로 돌도록 되돌린다.
os.environ["AGENT_MODE"] = "mock"

print()
if failures:
    print(f"FAIL {len(failures)}건: {', '.join(failures)}")
    sys.exit(1)
print("llm 모드 오류 경로 검사 모두 PASS (실제 LLM 호출 성공 여부와는 무관)")
