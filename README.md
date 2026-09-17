agent-ddalgi

인공지능사관학교 14기 기업연계 프로젝트 — 거산케미칼 영업지원 AI 에이전트 (백엔드)

프론트엔드는 별도 저장소입니다 → agent-ddalgi-team/agent-ddalgi-frontend

저장소 구조
조직: agent-ddalgi-team (GitHub Organization)
백엔드: agent-ddalgi (이 저장소)
프론트: agent-ddalgi-frontend
프론트/백엔드는 별개 저장소입니다. 각자 폴더에서 clone해 작업합니다.
브랜치 구조
main — 검증이 끝난 코드만 올라갑니다. 직접 push하지 않습니다.
develop — 통합 기준. 작업한 내용을 먼저 여기에 모읍니다.
작업 브랜치 — 각자 작업할 때 develop에서 만듭니다.
브랜치 이름 규칙

영어 소문자 + 하이픈으로 쓰고, 접두사를 붙입니다.

접두사	용도	예시
feat/	새 기능	feat/upload-ui
fix/	버그 수정	fix/upload-error
chore/	설정·정리	chore/remove-old-frontend
docs/	문서	docs/readme-update

한글·대문자·띄어쓰기는 쓰지 않습니다.

작업 흐름

작업은 항상 아래 순서로 합니다.

bash
git switch develop
git pull                       # 최신 받기 (작업 시작 전 항상)
git switch -c feat/작업이름     # develop에서 새 브랜치

# ...작업...
git add -A                     # 변경(삭제 포함) 담기
git commit -m "feat: 작업 내용"
git push -u origin feat/작업이름

# → GitHub에서 Pull Request 생성 (base = develop)
커밋 메시지: <접두사>: <한글 설명> (예: feat: 파일 업로드 화면 추가)
PR의 base(합쳐지는 곳)는 반드시 develop입니다. main으로 잡히면 develop으로 바꿉니다.
PR은 깃마스터가 확인한 뒤 머지합니다. 머지된 작업 브랜치는 삭제합니다.
develop에서 동작을 확인한 뒤, 검증이 끝나면 main으로 머지합니다.

Pull Request 작성
base ← compare: develop ← 내브랜치 인지 확인 (base가 main이면 변경)
제목: 무슨 작업인지 한 줄
설명: 무엇을·왜 했는지 + 확인한 것. 길게 쓰지 말고, 리뷰어가 한눈에 이해하도록 짧게 요약합니다. (핵심만 3~5줄, 필요하면 불릿으로)
Files changed: 내 작업 파일 수와 맞는지 확인 (수십 개면 base가 잘못된 것)

지켜야 할 규칙
자기 담당 파일만 수정합니다. 다른 사람 작업 파일을 고쳐야 하면 먼저 알립니다.
contracts/ 안의 파일을 수정할 때는 팀에 먼저 알립니다. 프론트·백엔드·에이전트 모두에 영향이 갑니다.
requirements.txt 등 공용 파일 변경도 팀에 알립니다. (머지 후 각자 pip install -r 재실행)
기업에서 받은 자료는 저장소에 올리지 않습니다. 공유 문서함을 사용합니다.
API 키는 .env 파일에만 둡니다. 코드에 직접 쓰지 않습니다.
.venv, .env, private_runs/는 .gitignore에 등록되어 있습니다.

자주 겪는 문제
증상	해결
GitHub에 브랜치가 안 보임	push를 안 함 → git push -u origin 브랜치
PR에 파일이 수십 개 뜸	base가 main → develop으로 변경
Already up to date인데 내용이 다름	내 로컬 수정을 아직 커밋/push 안 함 (또는 다른 브랜치를 보는 중)
dubious ownership 경고	git config --global --add safe.directory <폴더경로>
CONFLICT (충돌)	임의로 저장하지 말고 멈춘 뒤 깃마스터에게 문의
파일이 수정(M) 상태인데 기억이 없음	git status 확인 후, 실수면 git checkout 파일명으로 되돌리기
