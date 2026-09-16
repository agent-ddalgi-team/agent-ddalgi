# 수요일 가짜 자료의 용도

모두 실제 기업 자료가 아닙니다. day2_supported_facts.json과 day2_draft_supported_example.json은 기존 최종 Mock에서 분리한 형태 예시이며 이번에 LLM이 생성한 결과가 아닙니다.

1. mock_source_a.txt와 mock_source_b.txt: 고정 Mock 화면/서버 확인 또는 실제 LLM 호출 시험.
2. day2_supported_facts.json: A의 새 본문 함수 입력 예시. field는 내부 전달용으로만 사용.
3. day2_draft_supported_example.json: 기존 Mock의 supported 섹션을 분리한 출력 모양 예시. 전체 최종 결과가 아님.
4. day2_variant_source_a.txt와 day2_variant_source_b.txt: 실제 LLM 경로에서 두 파일을 함께 넣어 회사명과 사업이 달라지는지 시험. 회사명 힌트도 바꾸거나 비움. 두 파일 모두 회사명을 바꾸었으므로 이름 상충을 만들지 않음.

기대 확인: 새로운 결과에 '두번째 테스트 회사'와 '테스트 사업 B'가 반영되어야 합니다. 공정 수의 상충과 납기 확인 필요는 남습니다. 문구 전체가 정확히 같아야 하는 시험은 아니며, 근거·상태·입력 변경 반영을 확인합니다. 기존 mock_job_ready.json은 고정 Mock의 응답이며 변형 입력의 실제 LLM 결과로 재사용하지 않습니다.
