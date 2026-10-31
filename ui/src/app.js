const app = document.querySelector('#app');
const storageKey = 'gotrain-message-draft-v1';
const sessionKey = 'gotrain-request-session-v1';
app.innerHTML = `<header class="topbar"><a class="brand" href="./">GoTrain</a><span id="connection">Connecting…</span></header>
<main><section class="workspace" aria-labelledby="title"><div class="mark" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/></svg></div><h1 id="title">What would you like to build?</h1><p class="intro">Tell the agent your goal and constraints.</p>
<form id="message-form"><label class="sr-only" for="message">Message to the agent</label><textarea id="message" name="message" rows="5" maxlength="4000" placeholder="Explain what you want the model to do, the data you have, and any time or compute limits. You can also name a prepared dataset, such as EuroSAT." aria-describedby="preview-note"></textarea>
<div id="attachment" class="attachment" hidden><span id="filename"></span><button id="remove-file" type="button" aria-label="Remove selected dataset">×</button></div>
<div class="composer-actions"><label class="upload-button"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4m-4 4 4-4 4 4M5 15v5h14v-5"/></svg><span>Upload dataset</span><input id="dataset" type="file" accept=".zip,application/zip" aria-label="Upload dataset" aria-describedby="preview-note"></label><button class="send-button" id="send" type="submit" disabled>Send <span aria-hidden="true">↑</span></button></div></form>
<p id="preview-note" class="note">Checking workspace availability…</p><p id="status" class="status" role="status" aria-live="polite"></p><section id="request-state" class="request-state" aria-label="Agent request" hidden></section></section></main>`;
const message = document.querySelector('#message');
const dataset = document.querySelector('#dataset');
const send = document.querySelector('#send');
const status = document.querySelector('#status');
const panel = document.querySelector('#request-state');
let connected = false, busy = false, health = null;
let jobPoll = 0;
let session = {conversationId: null, datasetId: null, datasetName: null, limits: {}, pending: null};
function persist() {
  try {
    localStorage.setItem(storageKey, message.value);
    localStorage.setItem(sessionKey, JSON.stringify(session));
  } catch { /* The request still works without browser storage. */ }
}
try {
  message.value = localStorage.getItem(storageKey) || '';
  const saved = JSON.parse(localStorage.getItem(sessionKey));
  if (saved && typeof saved === 'object') session = {...session, ...saved};
} catch { /* Storage is optional. */ }
function updateSend() {
  send.disabled = busy || !message.value.trim();
  message.disabled = dataset.disabled = document.querySelector('#remove-file').disabled = busy;
  send.textContent = busy ? 'Checking…' : 'Send ↑';
}
function showAttachment() {
  const file = dataset.files[0];
  const name = file?.name || session.datasetName;
  document.querySelector('#attachment').hidden = !name;
  document.querySelector('#filename').textContent = name || '';
}
async function api(path, options = {}) {
  const response = await fetch(new URL('api/' + path, document.baseURI), {
    ...options, headers: {'X-GoTrain-Request': '1', ...options.headers},
  });
  const value = await response.json();
  if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : 'The request was invalid. Check your message, dataset and limits.');
  return value;
}
function text(tag, value, parent = panel) {
  const element = document.createElement(tag);
  element.textContent = value;
  parent.append(element);
  return element;
}
function showRecord(record) {
  panel.replaceChildren();
  panel.hidden = false;
  session.conversationId = record.id;
  session.datasetId = record.dataset_id;
  session.limits = record.limits;
  const needsInput = record.status === 'needs_input';
  text('h2', needsInput ? 'A little more information' : record.status === 'ready_for_review' ? 'Review your request' : 'Checking your request');
  if (record.questions?.length) {
    const list = document.createElement('ul');
    for (const question of record.questions) text('li', question, list);
    panel.append(list);
    message.placeholder = 'Reply here to continue the same request…';
  }
  if (record.summary) {
    const summary = record.summary;
    const list = document.createElement('dl');
    for (const [label, value] of Object.entries({Goal: summary.goal, Dataset: summary.dataset_id,
      Task: summary.task.kind, 'Maximum runtime': `${summary.limits.runtime_seconds / 60} minutes`,
      'GPU allowance': `${summary.limits.gpu_seconds / 60} minutes`})) {
      text('dt', label, list); text('dd', value, list);
    }
    panel.append(list);
    const button = text('button', 'Start training');
    button.type = 'button';
    button.disabled = !health?.training_enabled || Boolean(session.jobRequested);
    button.className = 'send-button';
    button.addEventListener('click', async () => {
      button.disabled = true;
      session.startRequest ||= `request_${crypto.randomUUID().replaceAll('-', '')}`;
      session.jobRequested = true; persist();
      try {
        await api(`conversations/${session.conversationId}/start`, {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({request_id:session.startRequest})});
      } catch (error) { status.textContent = error.message; }
      watchJob(); // Read any saved intent even if the start response disconnected.
    });
    text('p', health?.training_enabled ? 'Your request is prepared.' : 'Request prepared. Training is not enabled yet; no GPU work has started.');
  }
  text('small', `${record.model_requests} model request(s) used. Validation only; test data stays sealed.`);
  if (record.status !== 'checking') {
    const reset = text('button', 'New request');
    reset.type = 'button';
    reset.className = 'new-request';
    reset.addEventListener('click', () => {
      session = {conversationId: null, datasetId: null, datasetName: null, limits: {}, pending: null};
      dataset.value = '';
      message.value = '';
      panel.hidden = true;
      status.textContent = '';
      showAttachment(); persist(); updateSend(); message.focus();
    });
  }
  persist();
  if (session.jobRequested) watchJob();
}

function watchJob() {
  const poll = ++jobPoll, conversation = session.conversationId;
  async function tick() {
    if (poll !== jobPoll || session.conversationId !== conversation || !session.jobRequested) return;
    try {
      const state = await api(`conversations/${conversation}/job`);
      if (poll !== jobPoll || session.conversationId !== conversation) return;
      let view = document.querySelector('#job-state');
      if (!view) { view = document.createElement('div'); view.id = 'job-state'; panel.append(view); }
      view.replaceChildren();
      text('h2', state.status === 'selected' ? 'Model selected' : state.stage || state.status, view);
      if (state.elapsed_seconds !== undefined) text('p', `${Math.floor(state.elapsed_seconds)} seconds elapsed · ${state.attempts || 0} attempts · ${state.model_requests || 0} model requests`, view);
      if (state.gpu_seconds !== undefined) text('small', `${Math.ceil(state.gpu_seconds)} GPU-job seconds charged or reserved.`, view);
      if (state.best) text('p', `Selected model: ${state.best}`, view);
      if (state.error) text('p', state.error, view);
      if (state.audit_required) text('p', 'This run needs operator review. It will not restart automatically.', view);
      const active = !['selected', 'stopped', 'failed', 'interrupted'].includes(state.status);
      const reset = panel.querySelector('.new-request');
      if (reset) reset.disabled = active;
      if (active && state.status !== 'stopping') {
        const stop = text('button', 'Stop after current experiment', view);
        stop.type = 'button'; stop.className = 'new-request';
        stop.addEventListener('click', async () => {
          stop.disabled = true;
          try { await api(`conversations/${conversation}/stop`, {method:'POST'}); watchJob(); }
          catch (error) { status.textContent = error.message; stop.disabled = false; }
        });
      }
      if (active) setTimeout(tick, 2000);
    } catch (error) { status.textContent = error.message; }
  }
  tick();
}

message.addEventListener('input', () => { updateSend(); status.textContent = ''; persist(); });
dataset.addEventListener('change', () => {
  if (session.conversationId) {
    status.textContent = 'This attachment belongs to an existing request. Finish that request before changing its dataset.';
    dataset.value = '';
    return;
  }
  session.datasetId = session.datasetName = null;
  showAttachment();
  persist();
});
document.querySelector('#remove-file').addEventListener('click', () => {
  if (session.conversationId) {
    status.textContent = 'The dataset is preserved for replies to this request.';
    return;
  }
  dataset.value = '';
  session.datasetId = session.datasetName = null;
  showAttachment(); persist();
});
document.querySelector('#message-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!message.value.trim() || busy) return;
  if (!connected) {
    status.textContent = 'The service is not connected. Your message and dataset have not been sent.';
    return;
  }
  busy = true; updateSend();
  try {
    const file = dataset.files[0];
    if (file && !session.datasetId) {
      if (!file.name.toLowerCase().endsWith('.zip')) throw new Error('Choose a ZIP containing manifest.json and its labeled images or masks.');
      if (file.size > health.upload_bytes) throw new Error('The ZIP exceeds this workspace’s upload limit.');
      status.textContent = 'Uploading and validating the dataset…';
      const imported = await api('datasets', {method: 'POST', body: file, headers: {'Content-Type': 'application/zip'}});
      session.datasetId = imported.id;
      session.datasetName = file.name;
      persist();
    }
    const content = {message: message.value.trim(), dataset_id: session.datasetId,
      conversation_id: session.conversationId, limits: session.limits};
    const serialized = JSON.stringify(content);
    if (!session.pending || session.pending.content !== serialized) {
      session.pending = {content: serialized, requestId: 'request_' + crypto.randomUUID().replaceAll('-', '')};
    }
    persist();
    status.textContent = 'Checking your task and constraints. Training has not started.';
    const record = await api('conversations', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({...content, request_id: session.pending.requestId})});
    session.pending = null;
    message.value = '';
    status.textContent = '';
    showRecord(record);
    showAttachment();
  } catch (error) {
    status.textContent = error.message || 'Connection interrupted. Your request is saved; retry safely.';
  } finally {
    busy = false; updateSend();
  }
});

async function connect() {
  try {
    health = await api('health');
    connected = health.service === 'gotrain';
    document.querySelector('#connection').textContent = health.preflight_enabled ? 'Request validation' : 'Service preview';
    document.querySelector('#preview-note').textContent = 'Attach a labeled manifest ZIP, or name a prepared dataset. Sending checks the request before any training.';
    if (session.conversationId) showRecord(await api('conversations/' + encodeURIComponent(session.conversationId)));
  } catch {
    document.querySelector('#connection').textContent = 'Design preview';
    document.querySelector('#preview-note').textContent = 'Preview only. Messages and selected files stay on this device until the service is connected.';
  }
  showAttachment(); updateSend();
}
connect();
