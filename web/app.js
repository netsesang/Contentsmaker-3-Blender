// Contentsmaker-3-Blender Studio Frontend Controller

const $ = (id) => document.getElementById(id);

let pollTimer = null;
let currentRenders = [];

async function api(path, method = 'GET', body = null) {
  const opts = { method, headers: {} };
  if (body) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API 요청 실패');
  }
  return res.json();
}

// 1. Status Check
async function checkStatus() {
  const badge = $('blenderStatusBadge');
  const text = $('blenderStatusText');
  try {
    const data = await api('/api/status');
    const bl = data.blender || {};
    if (bl.installed) {
      badge.className = 'status-badge badge-connected';
      text.textContent = `${bl.version || 'Blender 정상 연결'} (GPU 활성)`;
    } else {
      badge.className = 'status-badge badge-disconnected';
      text.textContent = 'Blender 미설치 / 경로 지정 필요';
    }
  } catch (e) {
    badge.className = 'status-badge badge-disconnected';
    text.textContent = '서버 연결 실패';
  }
}

// 2. Preset Selectors
function initPresets() {
  // Lighting Presets
  document.querySelectorAll('#lightingGrid .preset-card').forEach((card) => {
    card.addEventListener('click', () => {
      document.querySelectorAll('#lightingGrid .preset-card').forEach((c) => c.classList.remove('active'));
      card.classList.add('active');
      $('lightingInput').value = card.dataset.val;
    });
  });

  // Camera Presets
  document.querySelectorAll('#cameraGrid .preset-card').forEach((card) => {
    card.addEventListener('click', () => {
      document.querySelectorAll('#cameraGrid .preset-card').forEach((c) => c.classList.remove('active'));
      card.classList.add('active');
      $('cameraInput').value = card.dataset.val;
    });
  });

  // Engine Chip Selector
  document.querySelectorAll('#engineSelect .chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('#engineSelect .chip').forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');
    });
  });

  // Floor Slider
  $('floorsInput').addEventListener('input', (e) => {
    $('floorsVal').textContent = `${e.target.value}층`;
  });
}

// 3. Render Form Submission
function initRenderForm() {
  $('renderForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = $('btnRender');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> 렌더링 큐 전송 중...';

    const formData = new FormData(e.target);
    const selectedEngine = formData.get('engine') || 'CYCLES';
    const isVolumetric = $('volumetricCheck') ? $('volumetricCheck').checked : true;
    const isDof = $('dofCheck') ? $('dofCheck').checked : true;

    const payload = {
      building_style: formData.get('building_style'),
      floors: parseInt(formData.get('floors'), 10),
      lighting: $('lightingInput').value,
      camera_shot: $('cameraInput').value,
      aspect_ratio: formData.get('aspect_ratio'),
      duration: parseFloat(formData.get('duration')),
      engine: selectedEngine,
      volumetric: isVolumetric,
      fstop: isDof ? 1.8 : 8.0,
      samples: selectedEngine === 'CYCLES' ? 96 : 48,
      fps: 30
    };

    try {
      const res = await api('/api/render', 'POST', payload);
      $('renderProgressBanner').classList.remove('hidden');
      $('progressTitle').textContent = `시네마틱 3D 로컬 렌더링 시작 (${res.job_id})`;
      $('progressDetail').textContent = `Blender ${selectedEngine} (OptiX 가속) 엔진 가동 중... 잠시만 기다려주세요.`;
      startPolling();
    } catch (err) {
      alert(`렌더링 시작 오류: ${err.message}`);
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<span class="btn-icon">⚡</span><span class="btn-text">3D 장면 로컬 렌더링 시작 (0원)</span>';
    }
  });
}

// 4. Polling & Jobs
function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const jobs = await api('/api/jobs');
      const active = Object.values(jobs).filter((j) => j.status === 'rendering');
      if (active.length > 0) {
        $('renderProgressBanner').classList.remove('hidden');
        const latestLog = active[0].recent_logs?.slice(-1)[0] || '렌더링 진행 중...';
        $('progressDetail').textContent = latestLog;
      } else {
        $('renderProgressBanner').classList.add('hidden');
        clearInterval(pollTimer);
        pollTimer = null;
        loadRenders();
      }
    } catch (e) {
      console.error(e);
    }
  }, 2000);
}

// 5. Load Renders Gallery
async function loadRenders() {
  try {
    const list = await api('/api/renders');
    currentRenders = list;
    const grid = $('clipsGrid');

    if (!list || list.length === 0) {
      grid.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🏙️</div>
          <h3>아직 렌더링된 3D 씬이 없습니다.</h3>
          <p>좌측 패널에서 스타일을 설정하고 <strong>[로컬 렌더링 시작]</strong>을 누르세요.</p>
        </div>`;
      return;
    }

    grid.innerHTML = list.map((item) => {
      const is916 = item.aspect_ratio === '9:16';
      const videoSrc = `/api/renders/${item.mp4_file}`;
      const thumbSrc = `/api/renders/${item.thumb_file}`;
      const p = item.params || {};

      return `
        <div class="clip-card" data-job="${item.job_id}">
          <div class="clip-media ${is916 ? 'ratio-9-16' : ''}">
            <video src="${videoSrc}" poster="${thumbSrc}" controls loop preload="metadata" muted playsinline></video>
            <span class="clip-duration-badge">${item.duration || 4}s · ${item.aspect_ratio || '16:9'}</span>
          </div>
          <div class="clip-body">
            <div>
              <div class="clip-meta">${item.created_at || ''} · ${item.job_id}</div>
              <div class="clip-tags">
                <span class="tag-badge">🏢 ${p.building_style || '빌딩'} (${p.floors || 12}층)</span>
                <span class="tag-badge">💡 ${p.lighting || '조명'}</span>
                <span class="tag-badge">🎥 ${p.camera_shot || '카메라'}</span>
              </div>
            </div>
            <div class="clip-actions" style="margin-top: 0.8rem;">
              <button class="btn-send-cm2" onclick="openSendModal('${item.job_id}')" title="4-2(Contentsmaker-2) 씬으로 전송">
                ⚡ 4-2로 주입
              </button>
              <button class="btn-icon-action" onclick="openFileInExplorer('${item.mp4_full_path.replace(/\\/g, '\\\\')}')" title="탐색기에서 파일 선택 (4-2로 드래그앤드롭 가능)">
                📁
              </button>
              <button class="btn-icon-action" onclick="copyPath('${item.mp4_full_path.replace(/\\/g, '\\\\')}')" title="절대 경로 복사">
                📋
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('갤러리 로드 실패', err);
  }
}

// 6. 4-2 Integration Actions
function openFileInExplorer(filePath) {
  api('/api/open-folder', 'POST', { file_path: filePath })
    .catch((err) => alert(`폴더 열기 실패: ${err.message}`));
}

function copyPath(filePath) {
  navigator.clipboard.writeText(filePath)
    .then(() => alert(`경로가 복사되었습니다:\n${filePath}`))
    .catch(() => alert('복사 실패'));
}

function openSendModal(jobId) {
  $('modalJobId').value = jobId;
  $('sendModal').classList.remove('hidden');
}

function initModal() {
  $('btnCloseModal').addEventListener('click', () => $('sendModal').classList.add('hidden'));
  $('btnCancelSend').addEventListener('click', () => $('sendModal').classList.add('hidden'));

  $('btnConfirmSend').addEventListener('click', async () => {
    const jobId = $('modalJobId').value;
    const planId = $('modalPlanId').value.trim();
    const slot = $('modalSlotSelect').value;
    const cm2Url = $('modalCm2Url').value.trim();

    if (!planId) {
      alert('Contentsmaker-2의 기획안 ID (Plan ID)를 입력해주세요.');
      return;
    }

    const btn = $('btnConfirmSend');
    btn.disabled = true;
    btn.textContent = '주입 중...';

    try {
      const res = await api('/api/send-to-contentsmaker2', 'POST', {
        job_id: jobId,
        plan_id: planId,
        slot,
        cm2_url: cm2Url
      });
      alert(res.message || '전송 완료!');
      $('sendModal').classList.add('hidden');
    } catch (err) {
      alert(`4-2 전송 실패:\n${err.message}\n\n팁: 탐색기(📁) 버튼을 눌러 해당 MP4 파일을 4-2 웹 화면 씬 카드에 직접 드래그앤드롭하셔도 바로 들어갑니다!`);
    } finally {
      btn.disabled = false;
      btn.textContent = '🚀 지금 4-2로 주입하기';
    }
  });
}

// 7. General Buttons
function initActions() {
  $('btnOpenFolder').addEventListener('click', () => {
    api('/api/open-folder', 'POST', {})
      .catch((err) => alert(err.message));
  });

  $('btnRefresh').addEventListener('click', () => {
    checkStatus();
    loadRenders();
  });
}

// Initialize on DOM load
window.addEventListener('DOMContentLoaded', () => {
  checkStatus();
  initPresets();
  initRenderForm();
  initModal();
  initActions();
  loadRenders();
});
