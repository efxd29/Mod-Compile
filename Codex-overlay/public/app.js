const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const state = {
  token: '', socket: null, connected: false, codexReady: false, host: null,
  workspace: '', currentThread: null, threads: [], models: [], model: '',
  pending: new Map(), rpcId: 100, currentView: 'chat', currentDir: '.', currentFile: null,
  attachments: [], activeTurn: null, activeTurnId: null, messageNodes: new Map(),
  approvalRequest: null, terminalSessions: new Set(), submitting: false
};

function getToken() {
  const params = new URLSearchParams(location.search);
  const incoming = params.get('token');
  if (incoming) {
    localStorage.setItem('codexToken', incoming);
    params.delete('token');
    const suffix = params.toString();
    history.replaceState({}, '', location.pathname + (suffix ? `?${suffix}` : '') + location.hash);
  }
  return localStorage.getItem('codexToken') || '';
}
state.token = getToken();

function applyTheme(theme) {
  const selected = theme === 'light' ? 'light' : 'dark';
  document.documentElement.dataset.theme = selected;
  document.documentElement.style.colorScheme = selected;
  const meta = $('meta[name="theme-color"]');
  if (meta) meta.content = selected === 'light' ? '#f5f6f8' : '#111111';
  const button = $('#themeToggle');
  const label = $('#themeLabel');
  const description = $('#themeDescription');
  if (button) button.textContent = selected === 'light' ? 'Use dark mode' : 'Use light mode';
  if (label) label.textContent = selected === 'light' ? 'Light mode' : 'Dark mode';
  if (description) description.textContent = selected === 'light' ? 'Bright surfaces and dark text.' : 'Dark surfaces and light text.';
}
function toggleTheme() {
  const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
  localStorage.setItem('codexTheme', next);
  applyTheme(next);
}

applyTheme(localStorage.getItem('codexTheme') || 'dark');

function toast(message, duration = 3000) {
  const node = $('#toast'); node.textContent = message; node.classList.remove('hidden');
  clearTimeout(toast.timer); toast.timer = setTimeout(() => node.classList.add('hidden'), duration);
}
function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[c]);
}
function renderMarkdown(text = '') {
  let safe = escapeHtml(text);
  const blocks = [];
  safe = safe.replace(/```([\w-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const marker = `@@CODE${blocks.length}@@`; blocks.push(`<pre><code>${code.replace(/\n$/, '')}</code></pre>`); return marker;
  });
  safe = safe.replace(/`([^`]+)`/g, '<code>$1</code>');
  safe = safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  safe = safe.replace(/(^|\n)### (.+)/g, '$1<strong>$2</strong>');
  safe = safe.replace(/\n/g, '<br>');
  safe = safe.replace(/@@CODE(\d+)@@/g, (_, index) => blocks[Number(index)] || '');
  return safe;
}
async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set('Authorization', `Bearer ${state.token}`);
  if (options.body && !(options.body instanceof Blob) && typeof options.body === 'string') headers.set('content-type', 'application/json');
  const response = await fetch(path, { ...options, headers });
  const type = response.headers.get('content-type') || '';
  if (!response.ok) {
    const error = type.includes('application/json') ? (await response.json()).error : await response.text();
    throw new Error(error || `HTTP ${response.status}`);
  }
  if (type.includes('application/json')) return response.json();
  return response;
}

function connectSocket() {
  if (!state.token) { toast('Token pairing tidak ditemukan. Buka link yang ditampilkan di Termux.'); return; }
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${location.host}/ws?token=${encodeURIComponent(state.token)}`;
  const ws = new WebSocket(wsUrl); state.socket = ws;
  ws.addEventListener('open', () => {
    state.connected = true; updateConnection();
    toast('Terhubung ke host. Menyalakan Codex App Server…', 2500);
  });
  ws.addEventListener('message', event => {
    let packet; try { packet = JSON.parse(event.data); } catch { return; }
    handlePacket(packet);
  });
  ws.addEventListener('close', () => {
    state.connected = false; state.codexReady = false; updateConnection();
    setTimeout(() => { if (state.socket === ws) connectSocket(); }, 3500);
  });
  ws.addEventListener('error', () => updateConnection());
}
function updateConnection() {
  const pill = $('#connectionPill');
  const dot = pill.querySelector('.status-dot');
  const label = pill.querySelector('span:last-child');
  pill.classList.toggle('connected', state.connected && state.codexReady);
  dot.classList.toggle('online', state.connected && state.codexReady);
  dot.classList.toggle('offline', !state.connected);
  label.textContent = !state.connected ? 'Disconnected' : state.codexReady ? 'Connected' : 'Starting Codex';
  $('#hostDot').classList.toggle('online', state.connected);
  $('#hostDot').classList.toggle('offline', !state.connected);
  $('#hostName').textContent = state.host?.host || (state.connected ? 'Termux host' : 'Host disconnected');
  $('#hostPath').textContent = state.workspace || 'waiting for workspace';
}
function rpc(method, params = {}, timeout = 45000) {
  if (!state.socket || state.socket.readyState !== WebSocket.OPEN) return Promise.reject(new Error('Belum tersambung ke host.'));
  const id = ++state.rpcId;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { state.pending.delete(id); reject(new Error(`Codex timeout: ${method}`)); }, timeout);
    state.pending.set(id, { resolve, reject, timer, method });
    state.socket.send(JSON.stringify({ method, id, params }));
  });
}
function handlePacket(packet) {
  if (packet.type === 'host_status') {
    state.host = packet.status; state.workspace = packet.status.workspace || state.workspace;
    updateConnection(); setWorkspaceLabel(); refreshSettings(); return;
  }
  if (packet.type === 'codex_ready') {
    state.codexReady = true; state.host = packet.status || state.host; state.workspace = packet.status?.workspace || state.workspace;
    updateConnection(); setWorkspaceLabel(); refreshSettings(); loadModels(); loadThreads(); return;
  }
  if (packet.type === 'codex_state') {
    state.codexReady = packet.status?.codex === 'ready'; updateConnection(); refreshSettings();
    if (packet.error) toast(`Codex: ${packet.error}`, 5000); return;
  }
  if (packet.type === 'host_log') return;
  if (packet.type === 'terminal_output') { appendTerminal(packet); return; }
  if (packet.type === 'terminal_exit') { appendTerminalExit(packet); return; }
  if (packet.type === 'client_error') { toast(packet.error || 'Bridge error'); return; }
  if (packet.type === 'codex_message') handleCodexMessage(packet.message);
}
function handleCodexMessage(msg) {
  if (!msg) return;
  if (msg.id !== undefined && msg.method) {
    showApproval(msg); return;
  }
  if (msg.id !== undefined && !msg.method && state.pending.has(msg.id)) {
    const pending = state.pending.get(msg.id); state.pending.delete(msg.id); clearTimeout(pending.timer);
    if (msg.error) pending.reject(new Error(msg.error.message || JSON.stringify(msg.error)));
    else pending.resolve(msg.result);
    return;
  }
  const p = msg.params || {};
  switch (msg.method) {
    case 'item/started':
      if (p.item) addItem(p.item, 'started');
      break;
    case 'item/completed':
      if (p.item) addItem(p.item, 'completed');
      break;
    case 'item/agentMessage/delta': {
      const id = p.itemId || p.item?.id || `agent-${p.turnId || 'active'}`;
      let record = state.messageNodes.get(id);
      if (!record) record = createAssistantMessage(id);
      const delta = p.delta || p.text || '';
      record.text += delta; record.textNode.innerHTML = renderMarkdown(record.text); scrollChat();
      break;
    }
    case 'turn/started':
      state.activeTurnId = p.turn?.id || state.activeTurnId;
      state.activeTurn = true; showActivity('Codex is working…'); break;
    case 'turn/completed':
      state.activeTurn = false; state.activeTurnId = null; hideActivity();
      if (p.turn?.status === 'failed') toast(p.turn.error?.message || 'Turn failed', 5000);
      break;
    case 'turn/plan/updated':
      addActivity((p.plan || []).map(step => `${step.status === 'completed' ? '✓' : step.status === 'inProgress' ? '◉' : '○'} ${step.step}`).join('\n') || p.explanation || 'Plan updated', 'plan'); break;
    case 'turn/diff/updated':
      if (p.diff) addActivity(`File changes updated\n${p.diff}`, 'diff');
      break;
    case 'warning': case 'configWarning': case 'error': {
      const message = p.message || p.summary || JSON.stringify(p);
      if (/could not find bubblewrap on PATH/i.test(message)) break;
      addActivity(message, 'warning'); break;
    }
    case 'serverRequest/resolved':
      if (state.approvalRequest && state.approvalRequest.id === p.requestId) closeApproval();
      break;
    default:
      if (msg.method?.startsWith('item/') && msg.method.includes('requestApproval')) showApproval(msg);
  }
}
function createAssistantMessage(id) {
  $('#welcome').classList.add('hidden');
  const row = document.createElement('div'); row.className = 'message assistant';
  row.innerHTML = `<div class="message-avatar"><img src="/icon-192.png" alt="Codex" /></div><div class="message-content"><div class="message-text"></div></div>`;
  $('#messages').append(row);
  const record = { row, textNode: row.querySelector('.message-text'), text: '' };
  state.messageNodes.set(id, record); return record;
}
function addUserMessage(text, id) {
  if (id && state.messageNodes.has(id)) return;
  $('#welcome').classList.add('hidden');
  const row = document.createElement('div'); row.className = 'message user';
  row.innerHTML = `<div class="message-content"><div class="message-text"></div></div>`;
  const textNode = row.querySelector('.message-text');
  textNode.textContent = text;
  $('#messages').append(row);
  if (id) state.messageNodes.set(id, { row, textNode, text });
  scrollChat();
}
function addItem(item, status) {
  if (item.type === 'agentMessage') {
    let record = state.messageNodes.get(item.id);
    if (!record) record = createAssistantMessage(item.id);
    if (item.text && item.text.length >= record.text.length) record.text = item.text;
    record.textNode.innerHTML = renderMarkdown(record.text); scrollChat();
  } else if (item.type === 'userMessage' && (status === 'started' || status === 'completed')) {
    const text = (item.content || []).filter(x => x.type === 'text').map(x => x.text).join('\n');
    if (text) addUserMessage(text, item.id);
  } else if (item.type === 'commandExecution') {
    const details = [item.command?.join?.(' ') || item.command || '', item.cwd || '', item.aggregatedOutput || ''].filter(Boolean).join('\n');
    addActivity(details || `Command ${status}: ${item.status || ''}`, 'command');
  } else if (item.type === 'fileChange') {
    const paths = (item.changes || []).map(change => `${change.kind || 'change'} · ${change.path}`).join('\n');
    addActivity(paths || `File changes ${status}`, 'file');
  } else if (item.type === 'plan') addActivity(item.text || 'Implementation plan', 'plan');
  else if (item.type === 'webSearch') addActivity(`Web search: ${item.query || ''}`, 'search');
}
function addActivity(text, kind = 'info') {
  if (!text) return;
  const icons = { log:'·', plan:'☷', command:'›_', file:'▤', diff:'⌁', warning:'!', search:'⌕', info:'•' };
  const row = document.createElement('div'); row.className = 'activity-card';
  row.innerHTML = `<div class="activity-card-head"><span class="activity-symbol">${icons[kind] || '•'}</span><span>${escapeHtml(kind === 'command' ? 'Command' : kind === 'file' ? 'File update' : kind === 'plan' ? 'Plan' : kind === 'warning' ? 'Notice' : kind === 'search' ? 'Search' : kind === 'diff' ? 'Diff' : 'Host log')}</span></div><pre></pre>`;
  row.querySelector('pre').textContent = String(text).slice(0, 6000);
  $('#messages').append(row); scrollChat();
}
function showActivity(text) { $('#activityText').textContent = text; $('#activityLine').classList.remove('hidden'); scrollChat(); }
function hideActivity() { $('#activityLine').classList.add('hidden'); }
function scrollChat() { const pane = $('#chatScroll'); requestAnimationFrame(() => { pane.scrollTop = pane.scrollHeight; }); }
function showApproval(msg) {
  const p = msg.params || {};
  state.approvalRequest = { id: msg.id, method: msg.method, params: p };
  const command = p.command ? (Array.isArray(p.command) ? p.command.join(' ') : p.command) : p.reason || 'Codex meminta izin untuk melanjutkan.';
  $('#approvalTitle').textContent = msg.method.includes('fileChange') ? 'Allow file changes?' : 'Allow command execution?';
  $('#approvalReason').textContent = p.reason || (msg.method.includes('fileChange') ? 'Codex ingin mengubah file di workspace.' : 'Codex ingin menjalankan command pada host.');
  $('#approvalCommand').textContent = command;
  $('#approvalOverlay').classList.remove('hidden');
}
function closeApproval() { state.approvalRequest = null; $('#approvalOverlay').classList.add('hidden'); }
function answerApproval(decision) {
  if (!state.approvalRequest) return;
  const id = state.approvalRequest.id;
  if (state.socket?.readyState === WebSocket.OPEN) state.socket.send(JSON.stringify({ id, result: { decision } }));
  closeApproval();
}

async function loadModels() {
  try {
    const result = await rpc('model/list', { limit: 80, includeHidden: false });
    state.models = result.data || [];
    const select = $('#modelSelect'); select.innerHTML = '';
    state.models.forEach(model => {
      const option = document.createElement('option'); option.value = model.model || model.id; option.textContent = model.displayName || model.model || model.id; select.append(option);
    });
    const selected = state.models.find(m => m.isDefault) || state.models[0];
    if (selected) { state.model = selected.model || selected.id; select.value = state.model; }
  } catch (error) { $('#modelSelect').innerHTML = '<option value="">Default model</option>'; console.warn(error); }
}
async function loadThreads() {
  try {
    const result = await rpc('thread/list', { limit: 50, sortKey: 'updated_at', sortDirection: 'desc' });
    state.threads = result.data || []; renderThreads();
  } catch (error) { console.warn('thread/list:', error); }
}
function renderThreads() {
  const nodes = state.threads.map(thread => {
    const title = thread.name || thread.preview || 'New conversation';
    const button = document.createElement('button'); button.className = `thread-entry${state.currentThread?.id === thread.id ? ' selected' : ''}`;
    button.innerHTML = `${escapeHtml(title)}<small>${new Date((thread.updatedAt || thread.createdAt || Date.now()/1000) * 1000).toLocaleDateString()}</small>`;
    button.addEventListener('click', () => openThread(thread)); return button;
  });
  const list = $('#threadList'); list.replaceChildren(...(nodes.length ? nodes : [Object.assign(document.createElement('div'), { className:'side-empty', textContent:'No conversations yet.' })]));
  const history = $('#historyList'); history.replaceChildren();
  if (!state.threads.length) { history.innerHTML = '<div class="empty-panel">No conversations yet. Start a new chat.</div>'; return; }
  state.threads.forEach(thread => {
    const row = document.createElement('button'); row.className = 'history-row';
    row.innerHTML = `<span class="history-symbol">◫</span><span class="history-text"><strong>${escapeHtml(thread.name || thread.preview || 'New conversation')}</strong><small>${escapeHtml(thread.preview || 'Codex conversation')} · ${new Date((thread.updatedAt || thread.createdAt || 0) * 1000).toLocaleString()}</small></span><span class="history-arrow">›</span>`;
    row.addEventListener('click', () => openThread(thread)); history.append(row);
  });
}
async function openThread(thread) {
  try {
    await rpc('thread/resume', { threadId: thread.id, excludeTurns: true });
    state.currentThread = thread; $('#chatTitle').textContent = thread.name || thread.preview || 'Conversation';
    $('#messages').replaceChildren(); state.messageNodes.clear(); $('#welcome').classList.add('hidden');
    const history = await rpc('thread/items/list', { threadId: thread.id, limit: 100, sortDirection: 'asc' });
    for (const entry of (history.data || [])) if (entry.item) addItem(entry.item, 'completed');
    if (!history.data?.length) $('#welcome').classList.remove('hidden');
    setView('chat'); renderThreads(); closeSidebar();
  } catch (error) { toast(`Tidak bisa membuka thread: ${error.message}`, 5000); }
}
function newChat() {
  state.currentThread = null; state.activeTurn = false; state.activeTurnId = null;
  $('#chatTitle').textContent = 'New task'; $('#messages').replaceChildren(); state.messageNodes.clear();
  $('#welcome').classList.remove('hidden'); hideActivity(); setView('chat'); closeSidebar(); $('#promptInput').focus(); renderThreads();
}
async function sendPrompt() {
  const input = $('#promptInput'); const text = input.value.trim();
  if (!text && !state.attachments.length) return;
  if (!state.codexReady) return toast('Codex App Server belum siap.');
  if (state.submitting) return;
  state.submitting = true;
  $('#sendButton').disabled = true;
  try {
    const uploaded = [];
    for (const file of state.attachments) {
      try {
        const result = await api(`/api/fs/upload?path=${encodeURIComponent('.')}`, { method: 'POST', headers: { 'x-file-name': encodeURIComponent(file.name) }, body: file });
        uploaded.push({ file, path: result.path });
      } catch (error) {
        toast(`Upload ${file.name} gagal: ${error.message}`, 5000);
        return;
      }
    }
    const inputItems = [];
    let combinedText = text;
    if (uploaded.length) {
      const names = uploaded.map(item => item.path);
      combinedText += `${combinedText ? '\n\n' : ''}Attached files uploaded to the workspace:\n${names.map(name => `- ${name}`).join('\n')}`;
      for (const item of uploaded) {
        if (/\.(png|jpe?g|webp|gif)$/i.test(item.path)) inputItems.push({ type: 'localImage', path: `${state.workspace}/${item.path}` });
      }
    }
    inputItems.unshift({ type: 'text', text: combinedText });
    input.value = ''; input.style.height = 'auto'; state.attachments = []; renderAttachments();
    if (!state.currentThread) {
      const params = { cwd: state.workspace };
      if (state.model) params.model = state.model;
      const start = await rpc('thread/start', params, 60000);
      state.currentThread = start.thread;
      $('#chatTitle').textContent = start.thread?.name || 'New task';
    }
    const params = { threadId: state.currentThread.id, input: inputItems, cwd: state.workspace };
    if (state.model) params.model = state.model;
    await rpc('turn/start', params, 60000);
    state.activeTurn = true; showActivity('Codex is working…');
    loadThreads();
  } catch (error) {
    addActivity(error.message, 'warning'); toast(`Codex request gagal: ${error.message}`, 5000);
  } finally {
    state.submitting = false;
    $('#sendButton').disabled = false;
  }
}
async function stopTurn() {
  if (!state.currentThread || !state.activeTurnId) { toast('Tidak ada turn aktif.'); return; }
  try { await rpc('turn/interrupt', { threadId: state.currentThread.id, turnId: state.activeTurnId }); } catch (error) { toast(error.message); }
}

function setView(name) {
  state.currentView = name;
  $$('.view').forEach(view => view.classList.toggle('active-view', view.id === `view-${name}`));
  $$('.side-nav[data-view], .bottom-nav-item[data-view]').forEach(node => node.classList.toggle('active', node.dataset.view === name));
  if (name === 'files') loadFiles(state.currentDir);
  if (name === 'settings') refreshSettings();
  if (name === 'history') loadThreads();
  closePopover();
}
function openSidebar() { $('#sidebar').classList.add('open'); $('#scrim').classList.add('show'); }
function closeSidebar() { $('#sidebar').classList.remove('open'); $('#scrim').classList.remove('show'); }
function setWorkspaceLabel() {
  const path = state.workspace || 'Workspace';
  $('#workspaceLabel').textContent = path.split('/').filter(Boolean).slice(-2).join('/') || path;
  $('#popoverWorkspace').textContent = path;
  $('#contextLabel').textContent = path.split('/').slice(-2).join('/') || 'Termux host';
  $('#terminalCwd').textContent = path;
}
function closePopover() { $('#workspacePopover').classList.add('hidden'); }
async function refreshSettings() {
  try {
    const [host, workspace] = await Promise.all([api('/api/status'), api('/api/workspace')]);
    state.host = host; state.workspace = workspace.path; updateConnection(); setWorkspaceLabel();
    $('#settingsHost').textContent = host.host;
    $('#settingsPlatform').textContent = host.platform;
    $('#settingsCodex').textContent = host.codex;
    $('#settingsPort').textContent = host.port;
    $('#settingsStatus').textContent = host.codex === 'ready' ? 'Connected' : host.codex;
    $('#workspacePath').value = workspace.path;
  } catch (error) { toast(error.message); }
}

function renderAttachments() {
  const tray = $('#attachmentTray'); tray.replaceChildren();
  state.attachments.forEach((file, index) => {
    const chip = document.createElement('span'); chip.className = 'attachment-chip'; chip.textContent = `${file.name} ×`;
    chip.title = 'Tap to remove'; chip.addEventListener('click', () => { state.attachments.splice(index, 1); renderAttachments(); }); tray.append(chip);
  });
}
function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`; if (bytes < 1024*1024) return `${(bytes/1024).toFixed(1)} KB`; return `${(bytes/1024/1024).toFixed(1)} MB`;
}
async function loadFiles(dir = '.') {
  try {
    state.currentDir = dir;
    const result = await api(`/api/fs/list?path=${encodeURIComponent(dir)}`);
    renderBreadcrumbs(result.path); const list = $('#fileList'); list.replaceChildren();
    if (dir !== '.') {
      const up = document.createElement('button'); up.className = 'file-row'; up.innerHTML = '<span class="file-icon folder">↰</span><span class="file-name">..</span><span class="file-meta">Parent directory</span>';
      up.addEventListener('click', () => loadFiles(pathParent(dir))); list.append(up);
    }
    if (!result.entries.length) list.innerHTML = '<div class="empty-panel">This folder is empty.</div>';
    for (const entry of result.entries) {
      const row = document.createElement('button'); row.className = 'file-row';
      const directory = entry.type === 'directory';
      const icon = directory ? '▰' : entry.type === 'symlink' ? '↗' : fileIcon(entry.name);
      row.innerHTML = `<span class="file-icon ${directory ? 'folder' : ''}">${icon}</span><span class="file-name">${escapeHtml(entry.name)}</span><span class="file-meta">${directory ? 'Folder' : formatSize(entry.size)}</span>`;
      row.addEventListener('click', () => directory ? loadFiles(entry.path) : openFile(entry)); list.append(row);
    }
  } catch (error) { $('#fileList').innerHTML = `<div class="empty-panel">${escapeHtml(error.message)}</div>`; }
}
function pathParent(p) { const pieces = p.split('/').filter(Boolean); pieces.pop(); return pieces.join('/') || '.'; }
function fileIcon(name) { const ext = name.split('.').pop().toLowerCase(); return ({js:'JS',ts:'TS',tsx:'TS',jsx:'JS',json:'{}',md:'M',yml:'Y',yaml:'Y',html:'H',css:'#',sh:'$_',py:'Py',rs:'Rs',toml:'T',java:'J',kt:'K',png:'▧',jpg:'▧',zip:'▣'})[ext] || '·'; }
function renderBreadcrumbs(dir) {
  const node = $('#breadcrumbs'); node.replaceChildren();
  const home = document.createElement('button'); home.textContent = 'workspace'; home.addEventListener('click', () => loadFiles('.')); node.append(home);
  let current = '';
  if (dir && dir !== '.') for (const piece of dir.split('/')) {
    current = current ? `${current}/${piece}` : piece;
    const value = current; const sep = document.createElement('span'); sep.textContent = '›'; sep.style.color = '#555'; node.append(sep);
    const button = document.createElement('button'); button.textContent = piece; button.addEventListener('click', () => loadFiles(value)); node.append(button);
  }
}
async function openFile(entry) {
  if (entry.type === 'symlink' || entry.type !== 'file') return toast('File type ini tidak bisa dibuka.');
  try {
    const result = await api(`/api/fs/read?path=${encodeURIComponent(entry.path)}`);
    state.currentFile = entry.path; $('#editorName').textContent = entry.name; $('#editorPath').textContent = result.path;
    $('#fileEditor').value = result.content; $('#editorPanel').classList.remove('hidden');
  } catch (error) {
    if (confirm(`${error.message}\n\nUnduh file ini?`)) downloadFile(entry.path);
  }
}
async function saveFile() {
  if (!state.currentFile) return;
  try { await api('/api/fs/write', { method:'POST', body: JSON.stringify({ path:state.currentFile, content:$('#fileEditor').value }) }); toast('File tersimpan.'); loadFiles(state.currentDir); }
  catch (error) { toast(`Save gagal: ${error.message}`, 5000); }
}
async function downloadFile(filePath) {
  try {
    if (navigator.userAgent.includes('CodexAndroid')) {
      // The native wrapper intercepts this private scheme and downloads with an Authorization header.
      location.href = `codex-download://file?path=${encodeURIComponent(filePath)}`;
      return;
    }
    const response = await api(`/api/fs/download?path=${encodeURIComponent(filePath)}`);
    const blob = await response.blob(); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = filePath.split('/').pop(); a.click(); setTimeout(() => URL.revokeObjectURL(url), 1500);
  } catch (error) { toast(error.message); }
}
async function uploadProjectFiles(files) {
  for (const file of files) {
    try { await api(`/api/fs/upload?path=${encodeURIComponent(state.currentDir || '.')}`, { method:'POST', headers:{ 'x-file-name': encodeURIComponent(file.name) }, body:file }); }
    catch (error) { toast(`Upload gagal: ${error.message}`, 5000); }
  }
  await loadFiles(state.currentDir); toast('Upload selesai.');
}

async function runTerminal(command) {
  if (!command.trim()) return;
  if (!confirm(`Jalankan perintah ini di HP host?\n\n${command}\n\nCommand akan berjalan sebagai user Termux.`)) return;
  const output = $('#terminalOutput');
  const line = document.createElement('div'); line.className = 'terminal-command'; line.textContent = `$ ${command}`; output.append(line); output.scrollTop = output.scrollHeight;
  try {
    const result = await api('/api/terminal', { method:'POST', body:JSON.stringify({ command, cwd:state.currentDir === '.' ? '.' : state.currentDir }) });
    state.terminalSessions.add(result.id);
  } catch (error) { const e = document.createElement('div'); e.className='terminal-error'; e.textContent = error.message; output.append(e); }
}
function appendTerminal(packet) {
  const node = document.createElement('span'); node.textContent = packet.data;
  if (packet.stream === 'stderr') node.className = 'terminal-error';
  $('#terminalOutput').append(node); $('#terminalOutput').scrollTop = $('#terminalOutput').scrollHeight;
}
function appendTerminalExit(packet) {
  const node = document.createElement('div'); node.className = packet.code === 0 ? 'terminal-success' : 'terminal-error'; node.textContent = packet.error ? `Process error: ${packet.error}` : `Process exited with code ${packet.code}`;
  $('#terminalOutput').append(node); $('#terminalOutput').scrollTop = $('#terminalOutput').scrollHeight;
}

// Navigation and controls
$('#menuButton').addEventListener('click', openSidebar);
$('#sidebarClose').addEventListener('click', closeSidebar);
$('#scrim').addEventListener('click', closeSidebar);
$$('[data-view]').forEach(node => node.addEventListener('click', () => setView(node.dataset.view)));
$('#newChat').addEventListener('click', newChat); $('#historyNewChat').addEventListener('click', newChat);
$('#themeToggle').addEventListener('click', toggleTheme);
$('#refreshThreads').addEventListener('click', loadThreads);
$('#sendButton').addEventListener('click', sendPrompt);
$('#promptInput').addEventListener('input', event => { event.target.style.height = 'auto'; event.target.style.height = `${Math.min(event.target.scrollHeight,160)}px`; });
$('#promptInput').addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendPrompt(); } });
$('#stopTurn').addEventListener('click', stopTurn);
$('#modelSelect').addEventListener('change', event => { state.model = event.target.value; });
$('#attachButton').addEventListener('click', () => $('#fileInput').click());
$('#fileInput').addEventListener('change', event => { state.attachments.push(...event.target.files); renderAttachments(); event.target.value=''; });
$('#projectFilesButton').addEventListener('click', () => setView('files'));
$('#uploadFiles').addEventListener('click', () => $('#fileUploadInput').click());
$('#fileUploadInput').addEventListener('change', event => { uploadProjectFiles([...event.target.files]); event.target.value=''; });
$('#refreshFiles').addEventListener('click', () => loadFiles(state.currentDir));
$('#closeEditor').addEventListener('click', () => $('#editorPanel').classList.add('hidden'));
$('#saveFile').addEventListener('click', saveFile);
$('#terminalForm').addEventListener('submit', event => { event.preventDefault(); const input=$('#terminalInput'); runTerminal(input.value); input.value=''; });
$('#clearTerminal').addEventListener('click', () => $('#terminalOutput').replaceChildren());
$('#declineApproval').addEventListener('click', () => answerApproval('decline'));
$('#acceptApproval').addEventListener('click', () => answerApproval('accept'));
$('#acceptSession').addEventListener('click', () => answerApproval('acceptForSession'));
$('#workspaceButton').addEventListener('click', () => $('#workspacePopover').classList.toggle('hidden'));
$('#popoverSettings').addEventListener('click', () => { closePopover(); setView('settings'); });
$('#topSettings').addEventListener('click', () => setView('settings'));
$('#saveWorkspace').addEventListener('click', async () => {
  try { const result=await api('/api/workspace',{method:'POST',body:JSON.stringify({path:$('#workspacePath').value.trim()})}); state.workspace=result.path; setWorkspaceLabel(); toast('Workspace updated.'); loadFiles('.'); }
  catch(error){ toast(error.message,5000); }
});
$('#restartCodex').addEventListener('click', async () => { if(!confirm('Restart Codex App Server? Active turns may be interrupted.')) return; try{await api('/api/codex/restart',{method:'POST',body:'{}'});toast('Restart requested.');}catch(error){toast(error.message);} });
$$('.suggestion').forEach(button => button.addEventListener('click', () => { $('#promptInput').value=button.dataset.prompt; $('#promptInput').focus(); sendPrompt(); }));
$('#threadMenuButton').addEventListener('click', () => {
  if (!state.currentThread) return toast('Belum ada thread aktif.');
  const action = prompt('Ketik: reload untuk memuat ulang, archive untuk arsipkan thread.');
  if (action === 'reload') openThread(state.currentThread);
  if (action === 'archive') rpc('thread/archive',{threadId:state.currentThread.id}).then(()=>{toast('Thread diarsipkan.');newChat();loadThreads();}).catch(e=>toast(e.message));
});

async function initialize() {
  if (!state.token) {
    document.body.innerHTML = '<div style="padding:30px;color:#eee;background:#111;min-height:100%;font:14px system-ui"><h2>Pairing token tidak ditemukan</h2><p>Buka alamat pairing lengkap yang dicetak Termux host, atau masukkan URL yang memiliki parameter <code>?token=…</code>.</p></div>';
    return;
  }
  try { const host = await api('/api/status'); state.host=host; state.workspace=host.workspace; updateConnection(); setWorkspaceLabel(); refreshSettings(); }
  catch (error) { toast(`Host belum bisa diakses: ${error.message}`, 6000); }
  connectSocket();
}
initialize();