// 3단계: C(백엔드)의 생성·조회 API 호출 코드.
// 계약(contracts/contract.md) 기준: 백엔드(backend/main.py)가 http://127.0.0.1:8000 에서
// 화면(frontend/)과 API를 같은 origin으로 함께 제공한다. 그래서 상대 경로를 쓴다.
// 반드시 http://127.0.0.1:8000/ 주소로 화면을 열어야 한다 (Live Server 5500 아님).
// API 필드 이름(files, company_name_hint, job_id)은 바꾸지 않는다.
const BASE_URL = '';

// 응답 본문이 JSON이 아니면(정적 서버의 404 페이지 등) 원인을 알아볼 수 있는 오류로 바꾼다.
async function parseJsonResponse(res) {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch (e) {
    throw {
      code: 'NOT_JSON_RESPONSE',
      message: `이 주소(${res.url})는 JSON API 응답을 주지 않습니다 (HTTP ${res.status}). 실제 백엔드 서버 주소가 맞는지 확인하세요.`,
    };
  }
}

// POST /api/profiles
// 성공(202): {"job_id":"...","status":"queued","result":null,"error":null}
// 실패: 오류 상태코드 + {"error": ErrorObject}
async function createProfileJob(files, companyNameHint) {
  const formData = new FormData();
  Array.from(files).forEach((file) => {
    formData.append('files', file); // 같은 필드 이름으로 반복 전송
  });
  if (companyNameHint) {
    formData.append('company_name_hint', companyNameHint);
  }
  // Content-Type(및 boundary)은 브라우저가 FormData로부터 자동 설정하도록 둔다.

  const res = await fetch(`${BASE_URL}/api/profiles`, {
    method: 'POST',
    body: formData,
  });

  const body = await parseJsonResponse(res);
  if (!res.ok) {
    const err = body && body.error ? body.error : { code: 'UNKNOWN', message: '요청이 실패했습니다.' };
    throw err;
  }
  return body; // {job_id, status, result, error}
}

// GET /api/profiles/{job_id}
async function getProfileJob(jobId) {
  const res = await fetch(`${BASE_URL}/api/profiles/${encodeURIComponent(jobId)}`);
  const body = await parseJsonResponse(res);
  if (!res.ok) {
    const err = body && body.error ? body.error : { code: 'UNKNOWN', message: '조회가 실패했습니다.' };
    throw err;
  }
  return body; // {job_id, status, result, error}
}
