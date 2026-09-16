"""TXT/MD 파서 — D 인수인계 대상.

경계(contracts/contract.md 3. 모듈 경계):
    extract_sources(stored_files) -> (source_units, source_manifest, warnings)

입력
- stored_files: [{"source_id": "S001", "stored_path": str 또는 Path, "display_name": "원본이름.txt"}, ...]
  source_id는 서버(main.py)가 업로드 순서대로 S001, S002, S003을 붙인다.
  저장 경로도 서버가 정한다(private_runs/<job_id>/S001.txt). 클라이언트 입력으로 경로를 만들지 않는다.

출력
- source_units: [{"source_id", "locator", "text"}]
  - locator: "N행". N은 원본 파일의 1부터 시작하는 행 번호.
  - 행 구분은 \\r\\n, \\r, \\n 세 가지만 인정한다(split_lines). 편집기에서 보는 행 번호와 같다.
  - 빈 행·공백만 있는 행은 unit을 만들지 않지만 번호는 그대로 센다(원문 행 번호 유지).
  - text: 그 행의 앞뒤 공백만 제거한 값. 행 내부는 바꾸거나 자르지 않는다.
  - 파일 맨 앞 UTF-8 BOM은 인코딩 표식이므로 제거한다(1행 text에 섞이지 않게).
- source_manifest: [{"source_id", "file_name", "document_date": None}] — 업로드한 자료 목록.
  TXT/MD에서는 문서 작성일을 알 수 없으므로 None. 파일 시간으로 대신하지 않는다.
- warnings: 사람이 읽을 비치명 경고 문자열 목록. 현재 TXT/MD 규칙은 문제를 모두 예외로 처리하므로 빈 목록이다.

예외(작업 전체를 error로 끝낸다. 문제 파일만 건너뛰고 성공 처리하지 않는다)
- UnsupportedEncoding: UTF-8(strict)로 디코딩할 수 없는 파일이 하나라도 있음 → UNSUPPORTED_FILE
- NeedsTextSource: 비어 있거나 공백만 있는 파일이 하나라도 있음 → NEEDS_TEXT_SOURCE

PDF/DOCX는 첫날 미구현이다. 지원 확장자는 .txt/.md뿐이며 검사는 서버(main.py)가 먼저 한다.
source_units 안의 내용은 자료 데이터일 뿐이며 지시·링크·스크립트로 실행하지 않는다.
근거 인용(evidence) 검사도 split_lines로 행을 나눠야 locator와 같은 행을 가리킨다.
"""
from __future__ import annotations

import re
from pathlib import Path

_LINE_BREAK = re.compile(r"\r\n|\r|\n")


class NeedsTextSource(Exception):
    """읽을 수 있는 텍스트가 없는 파일이 있을 때(NEEDS_TEXT_SOURCE)."""


class UnsupportedEncoding(Exception):
    """UTF-8로 디코딩할 수 없는 파일이 있을 때(UNSUPPORTED_FILE)."""


def split_lines(text: str) -> list[str]:
    """행 번호 규칙의 기준. \\r\\n, \\r, \\n만 행 구분으로 본다."""
    return _LINE_BREAK.split(text)


def extract_sources(stored_files: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    source_units: list[dict] = []
    source_manifest: list[dict] = []
    warnings: list[str] = []

    for item in stored_files:
        source_id = item["source_id"]
        display_name = item["display_name"]
        raw = Path(item["stored_path"]).read_bytes()

        try:
            # strict 디코딩: 잘못된 바이트를 무시하거나 대체 문자로 바꾸지 않는다.
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise UnsupportedEncoding(
                f"{display_name}: UTF-8로 읽을 수 없는 파일입니다. UTF-8로 저장한 TXT/MD를 사용해 주세요."
            ) from exc

        units = [
            {"source_id": source_id, "locator": f"{line_no}행", "text": line.strip()}
            for line_no, line in enumerate(split_lines(text), start=1)
            if line.strip()
        ]
        if not units:
            raise NeedsTextSource(
                f"{display_name}: 내용이 비어 있어 텍스트를 추출하지 못했습니다. 확인한 텍스트본을 사용해 주세요."
            )

        source_units.extend(units)
        source_manifest.append(
            {"source_id": source_id, "file_name": display_name, "document_date": None}
        )

    if not source_units:
        raise NeedsTextSource("텍스트를 추출하지 못했습니다. 확인한 텍스트본을 사용해 주세요.")

    return source_units, source_manifest, warnings
