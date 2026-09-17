"""OpenAI Responses API 연결만 확인하는 최소 테스트. 회사 자료는 보내지 않는다.

실행(프로젝트 루트에서):
    .\\.venv\\Scripts\\python.exe scripts\\test_openai_connection.py
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

import openai
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    # 1) 프로젝트 루트의 .env에서 키와 모델 이름을 읽는다. 키 값은 화면에 출력하지 않는다.
    load_dotenv(ROOT / '.env')
    api_key = os.getenv('OPENAI_API_KEY', '').strip()
    model = os.getenv('OPENAI_MODEL', '').strip()
    if not api_key:
        print('FAIL: .env의 OPENAI_API_KEY가 비어 있습니다.')
        return 1
    if not model:
        print('FAIL: .env의 OPENAI_MODEL이 비어 있습니다.')
        return 1

    # 2) OpenAI 연결 도구를 만든다. 60초 안에 응답이 없으면 멈추고, 자동 재시도는 1번까지만 한다.
    client = OpenAI(api_key=api_key, timeout=60, max_retries=1)

    # 3) 아주 짧은 질문 하나만 보낸다. store=False: 이 테스트 대화를 OpenAI 쪽에 저장하지 않도록 요청한다.
    try:
        response = client.responses.create(
            model=model,
            input="연결 테스트입니다. '연결 성공'이라고만 답하세요.",
            max_output_tokens=200,
            store=False,
        )
    except openai.AuthenticationError:
        print('FAIL: API 키가 거부되었습니다. .env의 키 값과 계정 상태를 확인하세요.')
        return 1
    except openai.PermissionDeniedError:
        print(f'FAIL: 이 계정/프로젝트에 모델 사용 권한이 없습니다: {model}')
        return 1
    except openai.NotFoundError:
        print(f'FAIL: 모델을 찾을 수 없습니다. OPENAI_MODEL 이름을 확인하세요: {model}')
        return 1
    except openai.RateLimitError:
        print('FAIL: 사용 한도 초과 또는 결제/크레딧 문제입니다. OpenAI 대시보드의 Billing/Limits를 확인하세요.')
        return 1
    except (openai.APIConnectionError, openai.APITimeoutError):
        print('FAIL: OpenAI 서버에 연결하지 못했습니다. 인터넷·회사 방화벽·프록시를 확인하세요.')
        return 1
    except openai.APIStatusError as exc:
        print(f'FAIL: API 오류 HTTP {exc.status_code}: {exc.message}')
        return 1

    # 4) 결과를 확인한다. 응답 문장, 실제 응답한 모델, 사용한 토큰 수만 출력한다.
    print('PASS: Responses API 호출 성공')
    print('status:', response.status)
    print('model:', response.model)
    print('answer:', response.output_text.strip() or '(빈 응답)')
    if response.usage:
        print('tokens: input', response.usage.input_tokens, '/ output', response.usage.output_tokens)
    return 0


if __name__ == '__main__':
    sys.exit(main())
