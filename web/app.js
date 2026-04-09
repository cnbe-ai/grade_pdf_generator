// ═══════════════════════════════════════════════════
// 수준별 개별화 학습 자료 자동 생성 시스템 - Web App
// ═══════════════════════════════════════════════════

const GEMINI_MODEL = 'gemini-2.5-flash';

// ── State ──
const state = {
    rawData: null,        // parsed spreadsheet rows
    columns: [],          // column headers
    classified: [],       // classified student data
    levelStats: {},       // per-level statistics
    generated: {},        // generated problems per level
    cancelled: false,
};

const LEVEL_KR = { advanced: '심화', standard: '표준', remedial: '보충' };
const LEVEL_COLORS = { advanced: '#1565C0', standard: '#F57F17', remedial: '#2E7D32' };

const SYSTEM_PROMPT = `당신은 한국 고등학교/대학교 물리 전문 출제 교수입니다.
학생 수준에 맞는 물리 문제를 JSON 형식으로만 반환합니다.

반환 JSON 형식:
{
  "problems": [
    {
      "number": 1,
      "type": "객관식|단답형|서술형|계산",
      "question": "문제 내용 (수식은 LaTeX 형식)",
      "options": ["①...", "②...", "③...", "④...", "⑤..."],
      "answer": "정답",
      "explanation": "풀이 및 해설",
      "difficulty": "상|중|하",
      "estimated_time": "분 단위"
    }
  ],
  "level_summary": "이 수준 학생들을 위한 학습 안내"
}

중요 규칙:
- options 필드는 객관식 문제에만 포함합니다. 다른 유형에서는 이 필드를 생략하세요.
- 수식은 반드시 LaTeX 형식으로 작성합니다 (예: $v = v_0 + at$).
- 문제는 한국어로 작성합니다.
- JSON만 반환하고, 다른 텍스트는 포함하지 마세요.`;

const LEVEL_PROMPTS = {
    advanced: "수능 1등급 수준의 심화 문제를 출제하세요.\n- 복합 개념 적용이 필요한 문제\n- 그래프 분석, 실험 설계 해석 포함\n- 고난도 계산 및 추론 능력 요구\n- 실생활 응용 및 융합 문제 포함",
    standard: "수능 3-4등급 수준의 표준 문제를 출제하세요.\n- 개념 확인 및 기본 응용 문제\n- 공식 적용 및 간단한 계산 문제\n- 핵심 개념의 이해도를 확인하는 문제\n- 적절한 난이도 배분",
    remedial: "기초 수준의 보충 문제를 출제하세요.\n- 기초 개념 반복 확인 문제\n- 단계별 풀이가 유도되는 문제\n- 핵심 공식과 개념을 직접 적용하는 문제\n- 힌트를 포함한 문제 (풀이 방향 제시)\n- 자신감을 줄 수 있는 난이도",
};

// ── Tab Navigation ──
function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.getElementById('tab-' + tabId).classList.add('active');
    const btns = document.querySelectorAll('.tab-btn');
    const idx = { api: 0, data: 1, generate: 2, pdf: 3 }[tabId];
    if (btns[idx]) btns[idx].classList.add('active');
}

// ── Tab 1: API Settings ──
function toggleKeyVisibility() {
    const inp = document.getElementById('apiKey');
    const btn = document.getElementById('toggleKeyBtn');
    if (inp.type === 'password') { inp.type = 'text'; btn.textContent = '숨김'; }
    else { inp.type = 'password'; btn.textContent = '표시'; }
}

async function testConnection() {
    const apiKey = document.getElementById('apiKey').value.trim();
    if (!apiKey) { alert('API 키를 입력하세요.'); return; }
    const status = document.getElementById('connStatus');
    status.textContent = '연결 테스트 중...';
    status.className = 'text-sm text-blue-600';
    try {
        await callGeminiAPI("테스트입니다. '연결 성공'이라고만 답하세요.", null, apiKey, GEMINI_MODEL, 50);
        status.textContent = '✓ 연결 성공!';
        status.className = 'text-sm text-green-600 font-bold';
        setStatus('API 연결 성공');
    } catch (e) {
        status.textContent = '✗ 연결 실패';
        status.className = 'text-sm text-red-600 font-bold';
        alert('연결 실패:\n\n' + e.message);
    }
}

function saveSettings() {
    const settings = {
        schoolName: document.getElementById('schoolName').value,
        teacherName: document.getElementById('teacherName').value,
    };
    localStorage.setItem('physics_gen_settings', JSON.stringify(settings));
    alert('설정이 저장되었습니다.');
}

function loadSettings() {
    const saved = localStorage.getItem('physics_gen_settings');
    if (saved) {
        const s = JSON.parse(saved);
        if (s.schoolName) document.getElementById('schoolName').value = s.schoolName;
        if (s.teacherName) document.getElementById('teacherName').value = s.teacherName;
    }
}

// ── Tab 2: Data & Settings ──
function setupDropZone() {
    const dz = document.getElementById('dropZone');
    dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('dragover'); });
    dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
    dz.addEventListener('drop', e => {
        e.preventDefault();
        dz.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) processFile(file);
    });
}

function handleFileUpload(event) {
    const file = event.target.files[0];
    if (file) processFile(file);
}

function processFile(file) {
    const reader = new FileReader();
    reader.onload = function (e) {
        try {
            const data = new Uint8Array(e.target.result);
            const workbook = XLSX.read(data, { type: 'array' });
            const sheet = workbook.Sheets[workbook.SheetNames[0]];
            const json = XLSX.utils.sheet_to_json(sheet);
            if (json.length === 0) { alert('데이터가 비어있습니다.'); return; }
            state.rawData = json;
            state.columns = Object.keys(json[0]);
            showFileInfo(file.name, json.length);
            populateColumnSelectors();
        } catch (err) {
            alert('파일 읽기 오류: ' + err.message);
        }
    };
    reader.readAsArrayBuffer(file);
}

function loadSampleData() {
    const names = ["김민준","이서연","박지호","최수아","정예준","강하은","조민서","윤지우","장서준","임하린",
                   "한도윤","오시은","신지안","권하준","송지유","류현우","문서영","배준서","홍다은","황지훈",
                   "전소율","나윤아","구민재","유서현","양태현","백지민","서연우","노하영","곽승현","진예은"];
    // seeded normal distribution approximation
    const scores = [82,91,55,43,76,68,88,37,72,60,95,48,63,79,52,70,84,45,66,57,90,39,74,61,50,86,42,78,67,53];
    state.rawData = names.map((n, i) => ({ '학생이름': n, '점수': scores[i] }));
    state.columns = ['학생이름', '점수'];
    showFileInfo('샘플 데이터', 30);
    populateColumnSelectors();
    document.getElementById('nameCol').value = '학생이름';
    document.getElementById('scoreCol').value = '점수';
    setStatus('샘플 데이터 로드 완료 (30명)');
}

function showFileInfo(name, count) {
    const info = document.getElementById('fileInfo');
    info.textContent = `✓ ${name} (${count}명)`;
    info.classList.remove('hidden');
    document.getElementById('columnMapping').classList.remove('hidden');
}

function populateColumnSelectors() {
    ['nameCol', 'scoreCol'].forEach(id => {
        const sel = document.getElementById(id);
        sel.innerHTML = '<option value="">-- 선택 --</option>';
        state.columns.forEach(col => {
            const opt = document.createElement('option');
            opt.value = col; opt.textContent = col;
            sel.appendChild(opt);
        });
    });
    // auto-map
    state.columns.forEach(col => {
        if (col.includes('이름') || col.toLowerCase().includes('name'))
            document.getElementById('nameCol').value = col;
        if (col.includes('점수') || col.toLowerCase().includes('score') || col.includes('성적'))
            document.getElementById('scoreCol').value = col;
    });
}

function classifyStudents() {
    const nameCol = document.getElementById('nameCol').value;
    const scoreCol = document.getElementById('scoreCol').value;
    if (!nameCol || !scoreCol) { alert('학생이름 컬럼과 점수 컬럼을 선택하세요.'); return; }

    const advPct = parseInt(document.getElementById('advPct').value);
    const remPct = parseInt(document.getElementById('remPct').value);

    // Parse scores
    let students = state.rawData.map(row => ({
        name: String(row[nameCol] || ''),
        score: parseFloat(row[scoreCol]),
    })).filter(s => !isNaN(s.score));

    if (students.length === 0) { alert('유효한 점수 데이터가 없습니다.'); return; }

    // Sort scores for percentile calculation
    const scores = students.map(s => s.score).sort((a, b) => a - b);
    const advThreshold = percentile(scores, 100 - advPct);
    const remThreshold = percentile(scores, remPct);

    students.forEach(s => {
        if (s.score >= advThreshold) { s.level = 'advanced'; s.levelKr = '심화'; }
        else if (s.score <= remThreshold) { s.level = 'remedial'; s.levelKr = '보충'; }
        else { s.level = 'standard'; s.levelKr = '표준'; }
    });

    students.sort((a, b) => b.score - a.score);
    state.classified = students;

    // Stats
    state.levelStats = {};
    ['advanced', 'standard', 'remedial'].forEach(level => {
        const group = students.filter(s => s.level === level);
        state.levelStats[level] = {
            count: group.length,
            avg: group.length > 0 ? Math.round(group.reduce((a, b) => a + b.score, 0) / group.length * 10) / 10 : 0,
        };
    });

    renderStudentTable();
    setStatus(`분류 완료 - 심화: ${state.levelStats.advanced.count}명 | 표준: ${state.levelStats.standard.count}명 | 보충: ${state.levelStats.remedial.count}명`);
}

function percentile(sortedArr, pct) {
    const idx = (pct / 100) * (sortedArr.length - 1);
    const lower = Math.floor(idx);
    const upper = Math.ceil(idx);
    if (lower === upper) return sortedArr[lower];
    return sortedArr[lower] + (sortedArr[upper] - sortedArr[lower]) * (idx - lower);
}

function renderStudentTable() {
    const tbody = document.getElementById('studentTable');
    tbody.innerHTML = '';
    state.classified.forEach(s => {
        const tr = document.createElement('tr');
        tr.className = 'border-t';
        tr.innerHTML = `<td class="px-4 py-2">${esc(s.name)}</td>
                        <td class="px-4 py-2 text-center">${s.score}</td>
                        <td class="px-4 py-2 text-center level-${s.level} font-bold">${s.levelKr}</td>`;
        tbody.appendChild(tr);
    });
    const bar = document.getElementById('statsBar');
    bar.classList.remove('hidden');
    document.getElementById('statAdv').textContent = `심화: ${state.levelStats.advanced.count}명 (평균 ${state.levelStats.advanced.avg}점)`;
    document.getElementById('statStd').textContent = `표준: ${state.levelStats.standard.count}명 (평균 ${state.levelStats.standard.avg}점)`;
    document.getElementById('statRem').textContent = `보충: ${state.levelStats.remedial.count}명 (평균 ${state.levelStats.remedial.avg}점)`;
}

// ── Tab 3: Problem Generation ──
async function callGeminiAPI(prompt, systemPrompt, apiKey, model, maxTokens = 8000) {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
    const body = {
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: { maxOutputTokens: maxTokens, temperature: 0.7 },
    };
    if (systemPrompt) {
        body.system_instruction = { parts: [{ text: systemPrompt }] };
    }
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const errMsg = err.error?.message || `HTTP ${res.status}`;
        // 사용자 친화적 에러 메시지
        if (errMsg.includes('quota') || errMsg.includes('Quota') || errMsg.includes('rate') || errMsg.includes('429')) {
            throw new Error(
                'API 요청 제한 오류입니다.\n\n' +
                '해결 방법:\n' +
                '1. 잠시 후 다시 시도하세요 (무료 요금제는 분당 15회 제한).\n' +
                '2. Google Cloud Console(console.cloud.google.com)에서 "Generative Language API"를 활성화하세요.\n' +
                '3. API 키를 aistudio.google.com/apikey 에서 새로 발급해 보세요.'
            );
        }
        if (errMsg.includes('API_KEY_INVALID') || errMsg.includes('invalid')) {
            throw new Error('API 키가 올바르지 않습니다. Google AI Studio에서 키를 다시 확인해주세요.');
        }
        if (errMsg.includes('permission') || errMsg.includes('Permission')) {
            throw new Error('API 권한이 없습니다. Google Cloud Console에서 "Generative Language API"를 활성화해주세요.');
        }
        throw new Error(errMsg);
    }
    const data = await res.json();
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!text) throw new Error('AI 응답이 비어있습니다.');
    return text;
}

function appendLog(msg) {
    const area = document.getElementById('log-area');
    const ts = new Date().toLocaleTimeString('ko-KR', { hour12: false });
    area.innerHTML += `<div>[${ts}] ${esc(msg)}</div>`;
    area.scrollTop = area.scrollHeight;
}

function setProgress(level, value) {
    const ids = { advanced: 'Adv', standard: 'Std', remedial: 'Rem' };
    const bar = document.getElementById('prog' + ids[level]);
    const label = document.getElementById('prog' + ids[level] + 'Label');
    if (value < 0) {
        bar.style.width = '0%'; label.textContent = '오류'; label.className = 'w-16 text-sm text-right text-red-600 font-bold';
    } else if (value >= 1) {
        bar.style.width = '100%'; label.textContent = '완료!'; label.className = 'w-16 text-sm text-right text-green-600 font-bold';
    } else {
        bar.style.width = (value * 100) + '%'; label.textContent = Math.round(value * 100) + '%'; label.className = 'w-16 text-sm text-right text-blue-600';
    }
}

async function generateForLevel(level, count, avgScore, types, subject, unit, showHints, apiKey, model) {
    const kr = LEVEL_KR[level];
    const levelPrompt = LEVEL_PROMPTS[level];
    let hintInst = (showHints || level === 'remedial') ? '\n- 각 문제에 풀이 힌트를 포함하세요.' : '';
    const prompt = `과목: ${subject}\n단원: ${unit}\n학생 수준: ${level} (평균 점수: ${avgScore}점)\n문제 유형: ${types.join(', ')}\n문제 수: ${count}문항\n\n${levelPrompt}\n${hintInst}\n\n위 조건에 맞는 ${count}개의 물리 문제를 JSON 형식으로 생성하세요.`;

    const maxRetries = 3;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
        if (state.cancelled) return { problems: [], level_summary: '생성 취소됨' };
        try {
            appendLog(`[${kr}] 문제 생성 시도 ${attempt + 1}/${maxRetries}...`);
            setProgress(level, 0.1 + attempt * 0.1);
            let text = await callGeminiAPI(prompt, SYSTEM_PROMPT, apiKey, model);
            text = text.trim();
            // Remove code blocks
            if (text.startsWith('```')) {
                const lines = text.split('\n');
                text = lines.slice(1).join('\n');
                if (text.endsWith('```')) text = text.slice(0, -3);
                text = text.trim();
            }
            const result = JSON.parse(text);
            appendLog(`[${kr}] 완료! ${result.problems?.length || 0}문항 생성됨`);
            setProgress(level, 1.0);
            return result;
        } catch (e) {
            appendLog(`[${kr}] 오류 (시도 ${attempt + 1}): ${e.message}`);
            if (attempt === maxRetries - 1) {
                setProgress(level, -1);
                throw e;
            }
            await sleep(2 ** attempt * 1000);
        }
    }
}

async function startGeneration() {
    const apiKey = document.getElementById('apiKey').value.trim();
    if (!apiKey) { alert('탭 ①에서 API 키를 입력하세요.'); switchTab('api'); return; }
    const subject = document.getElementById('subject').value;
    const unit = document.getElementById('unit').value.trim();
    if (!unit) { alert('탭 ②에서 단원을 입력하세요.'); switchTab('data'); return; }
    const types = [...document.querySelectorAll('.problem-type:checked')].map(el => el.value);
    if (types.length === 0) { alert('최소 한 개 이상의 문제 유형을 선택하세요.'); return; }
    const model = GEMINI_MODEL;
    const showHints = document.getElementById('showHints').checked;

    const counts = {
        advanced: parseInt(document.getElementById('advCount').value) || 10,
        standard: parseInt(document.getElementById('stdCount').value) || 10,
        remedial: parseInt(document.getElementById('remCount').value) || 10,
    };
    const avgScores = {
        advanced: state.levelStats.advanced?.avg || 85,
        standard: state.levelStats.standard?.avg || 60,
        remedial: state.levelStats.remedial?.avg || 35,
    };

    // UI state
    state.cancelled = false;
    document.getElementById('generateBtn').disabled = true;
    document.getElementById('cancelBtn').disabled = false;
    document.getElementById('log-area').innerHTML = '';
    ['advanced', 'standard', 'remedial'].forEach(l => setProgress(l, 0));

    appendLog('문제 생성을 시작합니다...');
    appendLog(`과목: ${subject} / 단원: ${unit}`);
    appendLog(`문제 유형: ${types.join(', ')}`);

    // 무료 요금제 분당 요청 제한 방지를 위해 순차 실행 (사이에 2초 대기)
    for (const level of ['advanced', 'standard', 'remedial']) {
        if (state.cancelled) break;
        try {
            const result = await generateForLevel(level, counts[level], avgScores[level], types, subject, unit, showHints, apiKey, GEMINI_MODEL);
            state.generated[level] = result;
        } catch (e) {
            appendLog(`[${LEVEL_KR[level]}] 최종 실패: ${e.message}`);
        }
        // 다음 수준 호출 전 2초 대기 (rate limit 방지)
        if (level !== 'remedial' && !state.cancelled) {
            appendLog('요청 제한 방지를 위해 잠시 대기 중...');
            await sleep(2000);
        }
    }

    const total = Object.values(state.generated).reduce((s, r) => s + (r?.problems?.length || 0), 0);
    appendLog(`전체 완료! 총 ${total}문항 생성됨`);
    setStatus(`문제 생성 완료: 총 ${total}문항`);

    document.getElementById('generateBtn').disabled = false;
    document.getElementById('cancelBtn').disabled = true;

    if (total > 0) {
        alert(`총 ${total}문항이 생성되었습니다.\n탭 ④에서 PDF를 저장하세요.`);
    }
}

function cancelGeneration() {
    state.cancelled = true;
    appendLog('생성 취소 요청됨...');
    document.getElementById('cancelBtn').disabled = true;
}

// ── Tab 4: PDF Output ──
function previewLevel(level) {
    const data = state.generated[level];
    const area = document.getElementById('previewArea');
    if (!data || !data.problems || data.problems.length === 0) {
        area.innerHTML = '<p class="text-gray-400">해당 수준의 생성된 문제가 없습니다.</p>';
        return;
    }
    let html = `<div class="space-y-4">`;
    if (data.level_summary) {
        html += `<div class="bg-gray-50 p-3 rounded text-sm text-gray-600 italic">${esc(data.level_summary)}</div>`;
    }
    data.problems.forEach(p => {
        html += `<div class="border-l-4 pl-4 py-2" style="border-color:${LEVEL_COLORS[level]}">
            <div class="font-bold text-sm">${p.number}. [${esc(p.type)}] ${p.difficulty ? '(난이도: ' + esc(p.difficulty) + ')' : ''} ${p.estimated_time ? '[' + esc(p.estimated_time) + ']' : ''}</div>
            <div class="mt-1">${esc(p.question)}</div>`;
        if (p.options && p.options.length > 0) {
            html += `<div class="mt-1 ml-4 text-gray-700">${p.options.map(o => `<div>${esc(o)}</div>`).join('')}</div>`;
        }
        html += `<details class="mt-2"><summary class="text-xs text-blue-500 cursor-pointer">정답 및 해설 보기</summary>
            <div class="mt-1 text-xs bg-blue-50 p-2 rounded"><b>정답:</b> ${esc(p.answer)}<br><b>해설:</b> ${esc(p.explanation || '')}</div></details>`;
        html += `</div>`;
    });
    html += `</div>`;
    area.innerHTML = html;
}

function buildPDFHtml(level) {
    const data = state.generated[level];
    if (!data || !data.problems || data.problems.length === 0) return null;

    const kr = LEVEL_KR[level];
    const color = LEVEL_COLORS[level];
    const subject = document.getElementById('subject').value;
    const unit = document.getElementById('unit').value;
    const school = document.getElementById('schoolName').value;
    const teacher = document.getElementById('teacherName').value;
    const today = new Date().toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' });

    let html = `<div style="font-family:'Nanum Gothic',sans-serif; color:#222; width:170mm;">`;

    // ── Cover Page ──
    html += `<div style="text-align:center; padding:60px 0 40px;">
        <div style="background:${color}; color:white; padding:30px 20px; border-radius:8px; margin-bottom:30px;">
            <h1 style="font-size:26px; font-weight:800; margin:0;">${kr} 학습 자료</h1>
            <p style="font-size:16px; margin-top:10px; opacity:0.9;">${esc(subject)} - ${esc(unit)}</p>
        </div>
        <table style="margin:0 auto; border-collapse:collapse; text-align:left; font-size:13px;">
            ${school ? `<tr><td style="padding:8px 16px; background:#f5f5f5; border:1px solid #ddd; font-weight:bold;">학교</td><td style="padding:8px 16px; border:1px solid #ddd;">${esc(school)}</td></tr>` : ''}
            ${teacher ? `<tr><td style="padding:8px 16px; background:#f5f5f5; border:1px solid #ddd; font-weight:bold;">출제자</td><td style="padding:8px 16px; border:1px solid #ddd;">${esc(teacher)}</td></tr>` : ''}
            <tr><td style="padding:8px 16px; background:#f5f5f5; border:1px solid #ddd; font-weight:bold;">날짜</td><td style="padding:8px 16px; border:1px solid #ddd;">${today}</td></tr>
            <tr><td style="padding:8px 16px; background:#f5f5f5; border:1px solid #ddd; font-weight:bold;">과목</td><td style="padding:8px 16px; border:1px solid #ddd;">${esc(subject)} / ${esc(unit)}</td></tr>
        </table>
    </div>
    <div style="page-break-after:always;"></div>`;

    // ── Problems ──
    html += `<h2 style="font-size:18px; font-weight:bold; color:${color}; border-bottom:2px solid ${color}; padding-bottom:6px; margin-bottom:16px;">${kr} 학습 자료 - 문제지</h2>`;
    if (data.level_summary) {
        html += `<p style="font-size:12px; color:#555; margin-bottom:16px; font-style:italic;">${esc(data.level_summary)}</p>`;
    }

    data.problems.forEach(p => {
        html += `<div style="margin-bottom:20px;">
            <p style="font-size:13px; font-weight:bold; color:#333;">${p.number}. [${esc(p.type)}] ${p.difficulty ? '(난이도: ' + esc(p.difficulty) + ')' : ''} ${p.estimated_time ? '[예상: ' + esc(p.estimated_time) + ']' : ''}</p>
            <p style="font-size:12px; line-height:1.8; margin:6px 0 6px 16px;">${esc(p.question)}</p>`;
        if (p.options && p.options.length > 0) {
            p.options.forEach(o => {
                html += `<p style="font-size:12px; margin:2px 0 2px 28px;">${esc(o)}</p>`;
            });
        }
        if (level === 'remedial' && p.explanation) {
            const hint = p.explanation.length > 80 ? p.explanation.substring(0, 80) + '...' : p.explanation;
            html += `<div style="background:#E8F5E9; padding:8px 12px; margin:8px 0 0 16px; border-radius:4px; font-size:11px; color:#1B5E20;">💡 <b>힌트:</b> ${esc(hint)}</div>`;
        }
        if (p.type === '서술형' || p.type === '계산') {
            html += `<div style="border:1px dashed #ccc; height:60px; margin:10px 0 0 16px; border-radius:4px;"></div>`;
        }
        html += `</div>`;
    });

    // ── Answer Sheet ──
    html += `<div style="page-break-before:always;"></div>`;
    html += `<h2 style="font-size:18px; font-weight:bold; color:#B71C1C; border-bottom:2px solid #B71C1C; padding-bottom:6px; margin-bottom:16px;">${kr} 학습 자료 - 정답 및 해설</h2>`;

    data.problems.forEach(p => {
        html += `<div style="margin-bottom:14px;">
            <p style="font-size:13px; font-weight:bold; color:#B71C1C;">${p.number}번 정답: ${esc(p.answer)}</p>
            <p style="font-size:11px; line-height:1.7; margin:4px 0 0 16px; color:#333;"><b>해설:</b> ${esc(p.explanation || '')}</p>
        </div>`;
    });

    html += `</div>`;
    return html;
}

async function downloadPDF(level) {
    const htmlContent = buildPDFHtml(level);
    if (!htmlContent) { alert('먼저 탭 ③에서 문제를 생성하세요.'); return; }

    setStatus(`${LEVEL_KR[level]} PDF 생성 중...`);

    const container = document.getElementById('pdfRender');
    container.innerHTML = htmlContent;

    const filename = `${LEVEL_KR[level]}_문제지.pdf`;
    try {
        await html2pdf().set({
            margin: [15, 15, 15, 15],
            filename: filename,
            image: { type: 'jpeg', quality: 0.95 },
            html2canvas: { scale: 2, useCORS: true, letterRendering: true },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
            pagebreak: { mode: ['css', 'legacy'] },
        }).from(container).save();

        setStatus(`${filename} 저장 완료`);
    } catch (e) {
        alert('PDF 생성 오류: ' + e.message);
    }
    container.innerHTML = '';
}

async function downloadAllPDFs() {
    const levels = ['advanced', 'standard', 'remedial'];
    const available = levels.filter(l => state.generated[l]?.problems?.length > 0);
    if (available.length === 0) { alert('먼저 탭 ③에서 문제를 생성하세요.'); return; }
    for (const level of available) {
        await downloadPDF(level);
        await sleep(500);
    }
    setStatus('전체 PDF 저장 완료');
}

// ── Utility ──
function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function setStatus(msg) {
    document.getElementById('statusBar').textContent = msg;
}

// ── Init ──
document.addEventListener('DOMContentLoaded', () => {
    setupDropZone();
    loadSettings();
});
