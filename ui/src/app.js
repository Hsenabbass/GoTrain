const app = document.querySelector('#app');
const storageKey = 'gotrain-message-draft-v1';
const sessionKey = 'gotrain-request-session-v1';
app.innerHTML = `<header class="topbar"><a class="brand" href="./">GoTrain</a><span id="connection">Connecting…</span></header>
<main><section class="workspace" aria-labelledby="title"><div id="welcome" class="welcome"><div class="mark" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/></svg></div><h1 id="title">What would you like to build?</h1><p class="intro">Tell the agent your goal and constraints.</p></div>
<section id="request-state" class="conversation" aria-label="Conversation" aria-live="polite" hidden></section>
<p id="status" class="status" role="status" aria-live="polite"></p>
<form id="message-form"><label class="sr-only" for="message">Message to the agent</label><textarea id="message" name="message" rows="3" maxlength="4000" placeholder="Message GoTrain about your model, data, and constraints…" aria-describedby="preview-note"></textarea>
<div id="attachment" class="attachment" hidden><span id="filename"></span><button id="remove-file" type="button" aria-label="Remove selected dataset">×</button></div>
<div class="composer-actions"><label class="upload-button"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4m-4 4 4-4 4 4M5 15v5h14v-5"/></svg><span>Upload dataset</span><input id="dataset" type="file" accept=".zip,application/zip" aria-label="Upload dataset" aria-describedby="preview-note"></label><button class="send-button" id="send" type="submit" disabled>Send <span aria-hidden="true">↑</span></button></div></form>
<p id="preview-note" class="note">Checking workspace availability…</p><section id="extras" class="tools" aria-label="Other options"></section></section></main>`;
const message = document.querySelector('#message');
const dataset = document.querySelector('#dataset');
const send = document.querySelector('#send');
const status = document.querySelector('#status');
const panel = document.querySelector('#request-state');
let connected = false, busy = false, health = null;
let jobPoll = 0;
const extras = document.querySelector('#extras');
let modelList = [];
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
function displayTime(value) {
  if (!value) return 'Earlier';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? 'Earlier' : date.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'});
}
function chatMessage(role, content, createdAt, className = '') {
  const row = document.createElement('article');
  row.className = `message-row ${role} ${className}`.trim();
  const avatar = text('span', role === 'user' ? 'You' : 'G', row);
  avatar.className = 'avatar';
  const body = document.createElement('div'); body.className = 'message-body'; row.append(body);
  const meta = document.createElement('div'); meta.className = 'message-meta'; body.append(meta);
  text('strong', role === 'user' ? 'You' : 'GoTrain', meta);
  text('time', displayTime(createdAt), meta).dateTime = createdAt || '';
  if (content) text('p', content, body);
  panel.append(row);
  return body;
}
function showRecord(record) {
  panel.replaceChildren();
  panel.hidden = false;
  document.querySelector('#welcome').hidden = true;
  session.conversationId = record.id;
  session.datasetId = record.dataset_id;
  session.limits = record.limits;
  const needsInput = record.status === 'needs_input';
  for (const entry of record.messages || []) chatMessage(entry.role === 'user' ? 'user' : 'assistant', entry.content, entry.created_at);
  if (needsInput) message.placeholder = 'Reply to GoTrain…';
  if (record.summary) {
    const body = chatMessage('assistant', 'I understand the request. Review it below, then start training when you are ready.', record.reviewed_at, 'summary-message');
    const summary = record.summary;
    const list = document.createElement('dl');
    for (const [label, value] of Object.entries({Goal: summary.goal, Dataset: summary.dataset_id,
      Task: summary.task.kind, 'Maximum runtime': `${summary.limits.runtime_seconds / 60} minutes`,
      'GPU allowance': `${summary.limits.gpu_seconds / 60} minutes`})) {
      text('dt', label, list); text('dd', value, list);
    }
    body.append(list);
    const button = text('button', 'Start training');
    button.type = 'button';
    button.disabled = !health?.training_enabled || Boolean(session.jobRequested);
    button.className = 'primary-action'; body.append(button);
    button.addEventListener('click', async () => {
      button.disabled = true;
      session.startRequest ||= `request_${crypto.randomUUID().replaceAll('-', '')}`;
      session.jobRequested = true; persist();
      try {
        await api(`conversations/${session.conversationId}/start`, {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({request_id:session.startRequest})});
      } catch (error) { status.textContent = error.message; }
      watchJob(); // Read any saved intent even if the start response disconnected.
    });
    text('small', health?.training_enabled ? 'No training starts until you press the button.' : 'Training is not enabled; no GPU work has started.', body);
  }
  const footer = text('small', `${record.model_requests} model request(s) used · validation only · test data stays sealed.`);
  footer.className = 'conversation-note';
  if (record.status !== 'checking') {
    const reset = text('button', 'New request');
    reset.type = 'button';
    reset.className = 'new-request';
    reset.addEventListener('click', () => {
      session = {conversationId: null, datasetId: null, datasetName: null, limits: {}, pending: null};
      dataset.value = '';
      message.value = '';
      message.placeholder = 'Explain what you want the model to do, the data you have, and any time or compute limits.';
      panel.hidden = true;
      document.querySelector('#welcome').hidden = false;
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
      const signature = `${state.status}|${state.stage || ''}|${state.attempts || 0}|${state.model_requests || 0}`;
      if (session.jobSignature !== signature) {
        session.jobSignature = signature;
        session.jobUpdatedAt = new Date().toISOString();
        persist();
      }
      let view = document.querySelector('#job-state');
      if (!view) { view = chatMessage('assistant', '', session.jobUpdatedAt, 'job-message'); view.id = 'job-state'; }
      view.replaceChildren();
      const heading = document.createElement('div'); heading.className = 'job-heading'; view.append(heading);
      text('strong', state.status === 'ready' ? 'Model ready' : state.status === 'selected' ? 'Model selected' : state.stage || state.status, heading);
      text('time', `Updated ${displayTime(session.jobUpdatedAt)}`, heading);
      if (state.elapsed_seconds !== undefined) text('p', `${Math.floor(state.elapsed_seconds)} seconds elapsed · ${state.attempts || 0} attempts · ${state.model_requests || 0} model requests`, view);
      if (state.gpu_seconds !== undefined) text('small', `${Math.ceil(state.gpu_seconds)} GPU-job seconds charged or reserved.`, view);
      if (state.best) text('p', `Selected model: ${state.best}`, view);
      if (state.error) text('p', state.error, view);
      if (state.audit_required) text('p', 'This run needs operator review. It will not restart automatically.', view);
      const active = !['ready', 'selected', 'stopped', 'failed', 'interrupted'].includes(state.status);
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
      if (state.package) {
        text('p', `Version ${state.package.version}. Validation selected; not final test evaluated.`, view);
        const selected = (await api('models')).find(row => row.version === state.package.version);
        if (selected?.validation) text('p', `${selected.validation.primary_name}: ${Number(selected.validation.primary).toFixed(4)} on validation.`, view);
        const actions = document.createElement('div'); actions.className = 'model-actions'; view.append(actions);
        action('Try model', () => openModel(state.package.version, view), actions);
        const link = text('a', 'Download model', actions); link.href = `api/models/${state.package.version}/download`; link.download = '';
      }
      if (!active) action('History', async () => {
        try { showHistory(await api(`conversations/${conversation}/history`), view); }
        catch (error) { status.textContent = error.message; }
      }, view);
      if (active) setTimeout(tick, 2000);
    } catch (error) { status.textContent = error.message; }
  }
  tick();
}

function action(label, callback, parent) {
  const button = text('button', label, parent);
  button.type = 'button'; button.className = 'new-request'; button.addEventListener('click', callback);
  return button;
}

function showHistory(history, parent) {
  parent.querySelector('.history-view')?.remove();
  const box = document.createElement('div'); box.className = 'history-view'; parent.append(box);
  text('h3', 'History', box);
  text('p', `Selected run: ${history.selected_run || 'None yet'}. Validation only.`, box);
  for (const row of history.experiments || []) {
    const detail = document.createElement('details'); box.append(detail);
    const metric = row.best_validation || row.last_validation;
    text('summary', `${row.run_id} · ${row.status}${metric ? ` · ${metric.primary_name}: ${Number(metric.primary).toFixed(4)}` : ''}`, detail);
    if (row.parent_run) text('p', `Parent: ${row.parent_run}`, detail);
    if (row.hypothesis) text('p', row.hypothesis, detail);
    if (row.gpu_job_seconds !== undefined && row.gpu_job_seconds !== null) text('p', `${Number(row.gpu_job_seconds).toFixed(2)} GPU-job seconds`, detail);
    text('p', `Recipe: ${JSON.stringify(row.recipe || {})}`, detail);
    if (row.error_type) text('p', `Failure: ${row.error_type}`, detail);
  }
  for (const decision of history.decisions || []) text('p', decision.reason || decision.hypothesis || JSON.stringify(decision), box);
}

async function openModel(version, parent) {
  try {
    modelList = await api('models');
    const model = modelList.find(row => row.version === version);
    if (!model) throw new Error('This model version is unavailable.');
    parent.querySelector('.prediction-view')?.remove();
    const box = document.createElement('section'); box.className = 'prediction-view'; parent.append(box);
    const spec = model.task_spec;
    text('h3', 'Try model', box);
    text('small', 'Redistribution terms remain unresolved; see TERMS.md in the package.', box);
    text('p', `Requires ${spec.width} × ${spec.height} pixels, ${spec.channels} bands in this order: ${spec.band_names.join(', ')}.`, box);
    text('small', `Input scaling divisors: ${spec.input_divisors.join(', ')}. No resizing or band conversion.`, box);
    text('p', `${model.validation.primary_name}: ${Number(model.validation.primary).toFixed(4)} on validation. Not final test evaluated.`, box);
    const file = document.createElement('input'); file.type = 'file'; file.accept = '.png,.jpg,.jpeg,.tif,.tiff'; file.setAttribute('aria-label', 'Image for prediction'); box.append(file);
    const label = document.createElement('label'); label.className = 'compatibility';
    const check = document.createElement('input'); check.type = 'checkbox'; label.append(check, document.createTextNode(' My image matches the listed band order and units.')); box.append(label);
    const resultBox = document.createElement('div'); box.append(resultBox);
    async function run(example) {
      resultBox.replaceChildren(); text('p', 'Predicting…', resultBox);
      upload.disabled = exampleButton.disabled = true;
      try {
        const options = {method:'POST'};
        if (!example) {
          if (!file.files[0] || !check.checked) throw new Error('Choose an image and confirm its band order and units.');
          if (file.files[0].size > 32 * 2 ** 20) throw new Error('Single images must be at most 32 MiB.');
          const ext = file.files[0].name.split('.').pop().toLowerCase();
          const media = {png:'image/png',jpg:'image/jpeg',jpeg:'image/jpeg',tif:'image/tiff',tiff:'image/tiff'}[ext];
          if (!media) throw new Error('Use PNG, JPEG or GeoTIFF.');
          options.headers = {'Content-Type':media,'X-GoTrain-Input-Contract':JSON.stringify({band_names:spec.band_names,input_divisors:spec.input_divisors})};
          options.body = file.files[0];
        }
        const prediction = await api(`models/${version}/${example ? 'example' : 'predict'}`, options);
        resultBox.replaceChildren();
        if (prediction.result.probabilities) {
          text('p', `Prediction: ${prediction.result.class_name ?? `Class ${prediction.result.class_id}`}`, resultBox);
          text('small', 'Class probabilities (not calibrated):', resultBox);
          for (const [i, p] of prediction.result.probabilities.entries()) text('p', `${model.class_names[i] ?? `Class ${i}`}: ${(p * 100).toFixed(1)}%`, resultBox);
        } else {
          const imageUrl = name => `api/predictions/${prediction.id}/${name}`;
          if (prediction.artifacts.includes('input-preview.png')) {
            const layers = document.createElement('div'); layers.className = 'mask-layers'; resultBox.append(layers);
            const base = text('img', '', layers); base.src = imageUrl('input-preview.png'); base.alt = 'Input display preview';
            const overlay = text('img', '', layers); overlay.src = imageUrl('preview.png'); overlay.alt = 'Predicted class regions'; overlay.className = 'mask-overlay'; overlay.style.opacity = '.45';
            const sliderLabel = document.createElement('label'); sliderLabel.textContent = 'Overlay opacity';
            const slider = document.createElement('input'); slider.type = 'range'; slider.min = 0; slider.max = 100; slider.value = 45;
            slider.addEventListener('input', () => { overlay.style.opacity = slider.value / 100; }); sliderLabel.append(slider); resultBox.append(sliderLabel);
          } else { const preview = text('img', '', resultBox); preview.src = imageUrl('preview.png'); preview.alt = 'Predicted class regions'; }
          const mask = text('a', 'Download class-ID mask', resultBox); mask.href = imageUrl(prediction.artifacts.includes('mask.tif') ? 'mask.tif' : 'mask.png'); mask.download = '';
          for (const [i, color] of prediction.result.colors.entries()) {
            const item = text('p', '', resultBox); const swatch = text('span', '■ ', item); swatch.style.color = `rgb(${color.join(',')})`;
            item.append(document.createTextNode(`${i}: ${prediction.result.class_names[i] ?? `Class ${i}`}`));
          }
        }
      } catch (error) { resultBox.replaceChildren(); text('p', error.message, resultBox); }
      finally { upload.disabled = exampleButton.disabled = false; }
    }
    const actions = document.createElement('div'); actions.className = 'model-actions'; box.append(actions);
    const upload = action('Predict image', () => run(false), actions);
    const exampleButton = action('Try validation example', () => run(true), actions);
    const download = text('a', 'Download model', actions); download.href = `api/models/${version}/download`; download.download = '';
    action('Model history', async () => { try { showHistory(await api(`models/${version}/history`), box); } catch (error) { status.textContent = error.message; } }, actions);
  } catch (error) { status.textContent = error.message; }
}

async function loadSavedOptions() {
  extras.replaceChildren();
  const datasets = await api('datasets');
  const saved = document.createElement('details'); extras.append(saved); text('summary', 'Use saved or prepared data', saved);
  const select = document.createElement('select'); select.setAttribute('aria-label', 'Saved dataset'); saved.append(select);
  for (const row of datasets) {
    const option = document.createElement('option'); option.value = row.id;
    option.textContent = `${row.task.description || row.id} · ${row.task.kind} · ${row.counts.train} train / ${row.counts.valid} validation`; select.append(option);
  }
  action('Attach saved data', () => {
    if (session.conversationId) { status.textContent = 'Start a new request to change the dataset.'; return; }
    session.datasetId = select.value; session.datasetName = select.options[select.selectedIndex].textContent;
    dataset.value = ''; showAttachment(); persist();
  }, saved);
  modelList = await api('models');
  if (modelList.length) {
    const use = document.createElement('details'); extras.append(use); text('summary', 'Use an existing model', use);
    const models = document.createElement('select'); models.setAttribute('aria-label', 'Existing model'); use.append(models);
    for (const row of modelList) {
      const option = document.createElement('option'); option.value = row.version; option.textContent = `${row.label || row.task} · ${row.version}`; models.append(option);
    }
    action('Try model', () => openModel(models.value, use), use);
  }
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
    document.querySelector('#connection').textContent = health.preflight_enabled ? 'SageMaker connected' : 'Service preview';
    document.querySelector('#preview-note').textContent = 'Attach a labeled manifest ZIP, or name a prepared dataset. Sending checks the request before any training.';
    if (session.conversationId) showRecord(await api('conversations/' + encodeURIComponent(session.conversationId)));
    await loadSavedOptions();
  } catch {
    document.querySelector('#connection').textContent = 'Design preview';
    document.querySelector('#preview-note').textContent = 'Preview only. Messages and selected files stay on this device until the service is connected.';
  }
  showAttachment(); updateSend();
}
connect();
