r"""LLM 연결부 회귀 검사: 가짜 추출·본문 결과와 예외만 사용하며 API를 호출하지 않는다.

실행: .\.venv\Scripts\python.exe scripts\check_llm_pipeline.py
"""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["AGENT_MODE"] = "llm"

from backend import agent, main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class PipelineChecks(unittest.TestCase):
    def setUp(self):
        stack = self.enterContext(ExitStack())
        folder = stack.enter_context(tempfile.TemporaryDirectory())
        stack.enter_context(patch.object(main, "PRIVATE_RUNS", Path(folder)))
        stack.enter_context(patch.object(main, "_jobs", {}))
        # 잘못된 대역 설정으로도 실제 SDK 호출이 일어나지 않게 막는다.
        stack.enter_context(patch.object(agent, "OpenAI", side_effect=AssertionError("실제 API 호출 금지")))
        self.profile = json.loads((ROOT / "fixtures/mock_profile.json").read_text(encoding="utf-8"))
        self.sections = json.loads((ROOT / "fixtures/day2_draft_supported_example.json").read_text(encoding="utf-8"))
        self.extract = stack.enter_context(patch.object(
            agent, "extract_company_info", return_value=copy.deepcopy(self.profile["company_info"])))
        self.draft = stack.enter_context(patch.object(
            agent, "draft_profile", return_value=copy.deepcopy(self.sections)))
        self.client = stack.enter_context(TestClient(main.app))

    def submit(self):
        files = [("files", (name, (ROOT / "fixtures" / name).read_bytes(), "text/plain"))
                 for name in ("mock_source_a.txt", "mock_source_b.txt")]
        response = self.client.post("/api/profiles", files=files)
        self.assertEqual(response.status_code, 202, response.text)
        queued = response.json()
        self.assertEqual(queued["status"], "queued")
        self.assertIsNone(queued["result"])
        self.assertIsNone(queued["error"])
        result = self.client.get(f"/api/profiles/{queued['job_id']}")
        self.assertEqual(result.status_code, 200)
        return result.json()

    def assert_failure(self, body, code, stage, retryable):
        self.assertEqual(body["status"], "error")
        self.assertIsNone(body["result"])
        self.assertEqual(body["error"]["code"], code)
        self.assertEqual(body["error"]["stage"], stage)
        self.assertEqual(body["error"]["retryable"], retryable)
        self.assertFalse((main.PRIVATE_RUNS / body["job_id"] / "result.json").exists())

    def test_ready_after_real_assembly_and_validation(self):
        body = self.submit()
        self.assertEqual(body["status"], "ready", body)
        self.assertIsNone(body["error"])
        self.assertEqual(body["result"]["draft_sections"], self.profile["draft_sections"])
        self.assertEqual(body["result"]["validation"], {
            "schema_valid": True, "evidence_links_valid": True, "human_review_required": True})
        saved = json.loads((main.PRIVATE_RUNS / body["job_id"] / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, body["result"])
        self.extract.assert_called_once()
        self.draft.assert_called_once()

    def test_extract_timeout(self):
        self.extract.side_effect = agent.AgentError("LLM_TIMEOUT", "openai_timeout", "시험 시간 초과")
        self.assert_failure(self.submit(), "LLM_TIMEOUT", "analyzing", True)
        self.draft.assert_not_called()

    def test_draft_timeout_and_next_job(self):
        self.draft.side_effect = agent.AgentError("LLM_TIMEOUT", "openai_timeout", "시험 시간 초과")
        self.assert_failure(self.submit(), "LLM_TIMEOUT", "drafting", True)
        self.draft.side_effect = None
        self.assertEqual(self.submit()["status"], "ready")

    def test_invalid_draft_output(self):
        self.draft.side_effect = agent.AgentError("INVALID_OUTPUT", "bad_fact_ids", "본문 근거 오류")
        self.assert_failure(self.submit(), "INVALID_OUTPUT", "drafting", False)

    def test_missing_supported_paragraphs(self):
        self.draft.return_value = []
        self.assert_failure(self.submit(), "INVALID_OUTPUT", "drafting", False)

    def test_invalid_evidence_fails_validation(self):
        info = self.extract.return_value
        fact = next(f for field in info.values() for f in field["facts"])
        fact["evidence"][0]["quote"] = "자료에 존재하지 않는 인용"
        self.assert_failure(self.submit(), "INVALID_OUTPUT", "validating", False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
