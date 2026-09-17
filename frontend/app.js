// 1단계: 파일 선택 목록 표시 + 생성 버튼 자리
// 2단계: Mock JSON을 읽어 renderProfile(profile)로 정상/오류 화면 표시
// 3단계(다음)에서 여기에 실제 생성·조회 API 호출을 연결합니다.

const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const companyHint = document.getElementById('companyHint');
const generateBtn = document.getElementById('generateBtn');
const statusArea = document.getElementById('statusArea');
const errorArea = document.getElementById('errorArea');
const mockInput = document.getElementById('mockInput');
const mockBadge = document.getElementById('mockBadge');
const companyInfoArea = document.getElementById('companyInfoArea');
const draftArea = document.getElementById('draftArea');
const confirmArea = document.getElementById('confirmArea');
const sourcesArea = document.getElementById('sourcesArea');

// 화면에 보여줄 한글 이름. contracts/contract.md 8절의 표와 동일해야 함.
const FIELD_LABELS = {
  company_name: '회사명',
  company_summary: '회사 개요',
  business_areas: '사업 분야',
  products_services: '제품·서비스',
  technology: '기술',
  strengths: '강점',
  customers_markets: '고객·시장',
  certifications: '인증·승인·특허',
  history: '연혁',
  processes: '공정 목록',
  process_count: '공정 수',
  capabilities: '대응 범위',
  lead_time: '납기',
  other_info: '기타 핵심 정보',
};

const STATUS_LABELS = {
  supported: '근거 있음',
  conflict: '상충',
  needs_confirmation: '확인 필요',
  not_found: '자료 없음',
};

fileInput.addEventListener('change', () => {
  fileList.innerHTML = '';
  Array.from(fileInput.files).forEach((file) => {
    const li = document.createElement('li');
    li.textContent = file.name;
    fileList.appendChild(li);
  });
});

let pollTimer = null;

generateBtn.addEventListener('click', async () => {
  errorArea.textContent = '';
  clearResultAreas();

  if (fileInput.files.length === 0) {
    errorArea.textContent = '파일을 먼저 선택해 주세요.';
    return;
  }

  stopPolling();
  generateBtn.disabled = true;
  statusArea.textContent = '요청을 보내는 중...';

  try {
    const created = await createProfileJob(fileInput.files, companyHint.value.trim());
    statusArea.textContent = `상태: ${created.status} (job_id: ${created.job_id})`;
    startPolling(created.job_id);
  } catch (err) {
    generateBtn.disabled = false;
    errorArea.textContent = err && err.message ? `[${err.code}] ${err.message}` : '요청 중 오류가 발생했습니다.';
  }
});

function startPolling(jobId) {
  pollTimer = setInterval(async () => {
    try {
      const response = await getProfileJob(jobId);
      statusArea.textContent = `상태: ${response.status} (job_id: ${jobId})`;

      if (response.status === 'ready' || response.status === 'error') {
        stopPolling();
        generateBtn.disabled = false;
        handleJobResponse(response);
      }
    } catch (err) {
      stopPolling();
      generateBtn.disabled = false;
      errorArea.textContent = err && err.message ? `[${err.code}] ${err.message}` : '조회 중 오류가 발생했습니다.';
    }
  }, 1000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

mockInput.addEventListener('change', () => {
  const file = mockInput.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = () => {
    let response;
    try {
      response = JSON.parse(reader.result);
    } catch (e) {
      errorArea.textContent = 'JSON 형식을 읽지 못했습니다: ' + e.message;
      return;
    }
    handleJobResponse(response);
  };
  reader.onerror = () => {
    errorArea.textContent = '파일을 읽는 중 오류가 발생했습니다.';
  };
  reader.readAsText(file, 'utf-8');
});

// GET /api/profiles/{job_id} 응답 형태: {job_id, status, result, error}
function handleJobResponse(response) {
  errorArea.textContent = '';
  clearResultAreas();

  if (response.status === 'error') {
    statusArea.textContent = '상태: error';
    const err = response.error;
    errorArea.textContent = err ? `[${err.code}] ${err.message}` : '알 수 없는 오류입니다.';
    return; // 오류는 결과로 처리하지 않음
  }

  if (response.status === 'ready' && response.result) {
    statusArea.textContent = '상태: ready';
    renderProfile(response.result);
    return;
  }

  // queued / extracting / analyzing / drafting / validating
  statusArea.textContent = `상태: ${response.status} (아직 준비되지 않았습니다.)`;
}

function clearResultAreas() {
  mockBadge.hidden = true;
  companyInfoArea.innerHTML = '';
  draftArea.innerHTML = '';
  confirmArea.innerHTML = '';
  sourcesArea.innerHTML = '';
}

function renderProfile(profile) {
  clearResultAreas();
  mockBadge.hidden = !profile.is_mock;

  renderCompanyInfo(profile.company_info);
  renderDraftSections(profile.draft_sections);
  renderNeedsConfirmation(profile.needs_confirmation);
  renderSources(profile.sources, profile.company_info);
}

function renderCompanyInfo(companyInfo) {
  Object.keys(FIELD_LABELS).forEach((key) => {
    const field = companyInfo[key];
    if (!field) return;

    const wrap = document.createElement('div');

    const title = document.createElement('span');
    title.className = 'field-title';
    title.textContent = FIELD_LABELS[key];
    wrap.appendChild(title);

    const badge = document.createElement('span');
    badge.className = `field-status status-${field.status}`;
    badge.textContent = STATUS_LABELS[field.status] || field.status;
    wrap.appendChild(badge);

    if (field.facts.length === 0) {
      const p = document.createElement('div');
      p.textContent = '자료 없음';
      wrap.appendChild(p);
    } else {
      const ul = document.createElement('ul');
      field.facts.forEach((fact) => {
        const li = document.createElement('li');
        li.textContent = fact.text;
        ul.appendChild(li);
      });
      wrap.appendChild(ul);
    }

    companyInfoArea.appendChild(wrap);
  });
}

function renderDraftSections(draftSections) {
  draftSections.forEach((section) => {
    const wrap = document.createElement('div');

    const title = document.createElement('div');
    title.className = 'field-title';
    title.textContent = section.title;
    wrap.appendChild(title);

    // paragraphs 배열의 text를 순서대로 그대로 표시한다. 다시 작성하지 않는다.
    section.paragraphs.forEach((paragraph) => {
      const p = document.createElement('p');
      p.textContent = paragraph.text;
      wrap.appendChild(p);
    });

    draftArea.appendChild(wrap);
  });
}

function renderNeedsConfirmation(needsConfirmation) {
  if (!needsConfirmation || needsConfirmation.length === 0) {
    confirmArea.textContent = '확인이 필요한 항목이 없습니다.';
    return;
  }
  const ul = document.createElement('ul');
  needsConfirmation.forEach((item) => {
    const li = document.createElement('li');
    li.textContent = `[${FIELD_LABELS[item.field] || item.field}] ${item.question}`;
    ul.appendChild(li);
  });
  confirmArea.appendChild(ul);
}

function renderSources(sources, companyInfo) {
  const sourceNameById = {};
  (sources || []).forEach((s) => {
    sourceNameById[s.source_id] = s.file_name;
  });

  const sourceList = document.createElement('ul');
  (sources || []).forEach((s) => {
    const li = document.createElement('li');
    li.textContent = `${s.file_name} (${s.source_id})`;
    sourceList.appendChild(li);
  });
  sourcesArea.appendChild(sourceList);

  const evidenceList = document.createElement('ul');
  Object.values(companyInfo).forEach((field) => {
    field.facts.forEach((fact) => {
      fact.evidence.forEach((ev) => {
        const li = document.createElement('li');
        const fileName = sourceNameById[ev.source_id] || ev.source_id;
        li.textContent = `${fileName} · ${ev.locator}: "${ev.quote}"`;
        evidenceList.appendChild(li);
      });
    });
  });
  sourcesArea.appendChild(evidenceList);
}
