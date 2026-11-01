const app = document.querySelector('#app');
const storageKey = 'gotrain-message-draft-v1';
const sessionKey = 'gotrain-request-session-v1';
const startsKey = 'gotrain-start-requests-v1';
app.innerHTML = `<div class="shell"><aside id="sidebar" class="sidebar"><div class="sidebar-head"><a class="brand" href="./">GoTrain</a><button id="close-history" class="icon-button" type="button" aria-label="Close history">×</button></div><button id="new-chat" class="new-chat" type="button"><span>＋</span> New chat</button><section class="workflow"><p class="history-label">Current workflow</p><ol id="workflow-steps"></ol></section><p class="history-label">Conversations</p><nav id="chat-history" aria-label="Chat history"><p class="history-empty">No chats yet</p></nav><div id="connection" class="connection">Connecting…</div></aside><div id="sidebar-shade" class="sidebar-shade"></div>
<section class="chat"><header class="topbar"><button id="open-history" class="icon-button" type="button" aria-label="Open history">☰</button><span>GoTrain</span><span id="mobile-connection">Connecting…</span></header>
<main><section class="workspace" aria-labelledby="title"><div class="workspace-heading"><span>Conversation</span><span class="workspace-subtitle">Task context & clarification</span></div><div id="welcome" class="welcome"><div class="mark" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/></svg></div><h1 id="title">What do you want to train?</h1><p class="intro">Describe the outcome, dataset, and constraints. GoTrain will clarify the request before any training starts.</p></div>
<section id="request-state" class="conversation" aria-label="Conversation" aria-live="polite" hidden></section>
<p id="status" class="status" role="status" aria-live="polite"></p>
<div class="composer-wrap"><form id="message-form"><label class="sr-only" for="message">Message to the agent</label><textarea id="message" name="message" rows="2" maxlength="4000" placeholder="Message GoTrain…" aria-describedby="preview-note"></textarea>
<div id="attachment" class="attachment" hidden><span id="filename"></span><button id="remove-file" type="button" aria-label="Remove selected dataset">×</button></div>
<div class="composer-actions"><label class="upload-button"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4m-4 4 4-4 4 4M5 15v5h14v-5"/></svg><span>Upload dataset</span><input id="dataset" type="file" accept=".zip,application/zip" aria-label="Upload dataset" aria-describedby="preview-note"></label><button class="send-button" id="send" type="submit" disabled>Send <span aria-hidden="true">↑</span></button></div></form>
<p id="preview-note" class="note">Checking workspace availability…</p><section id="extras" class="tools" aria-label="Dataset and model options"></section></div></section><aside id="workbench" class="workbench" aria-label="Run and model workspace"><header class="bench-header"><div><span class="eyebrow">TASK WORKSPACE</span><h2 id="bench-title">Task overview</h2></div><span id="bench-state" class="state-badge">Ready to begin</span></header><div class="bench-tabs" role="tablist" aria-label="Task workspace views"><button id="tab-overview" role="tab" aria-selected="true" aria-controls="bench-content" type="button">Overview</button><button id="tab-experiments" role="tab" aria-selected="false" aria-controls="experiments-content" tabindex="-1" type="button">Experiments</button><button id="tab-model" role="tab" aria-selected="false" aria-controls="model-content" tabindex="-1" type="button">Use model</button></div><div id="bench-content" class="bench-panel" role="tabpanel" aria-labelledby="tab-overview"><div class="bench-empty"><div class="empty-symbol">↗</div><h3>No task selected</h3><p>Your task, resource usage and selected model will appear here. Start a conversation or reopen a saved task.</p><div class="empty-path"><span>01 &nbsp; Define your task</span><span>02 &nbsp; Follow the experiments</span><span>03 &nbsp; Use your model</span></div></div></div><div id="experiments-content" class="bench-panel" role="tabpanel" aria-labelledby="tab-experiments" hidden></div><div id="model-content" class="bench-panel" role="tabpanel" aria-labelledby="tab-model" hidden></div></aside></main></section></div>`;
const message = document.querySelector('#message');
const dataset = document.querySelector('#dataset');
const send = document.querySelector('#send');
const status = document.querySelector('#status');
const panel = document.querySelector('#request-state');
let connected = false, busy = false, health = null;
let jobPoll = 0;
let chatNavigation = 0;
let startRequests = {};
const extras = document.querySelector('#extras');
let modelList = [];
let activeTab = 'overview', historyRequest = 0, modelRequest = 0;
let currentModelVersion = null, loadedModelVersion = null;
const tabPanels = {overview: '#bench-content', experiments: '#experiments-content', model: '#model-content'};
let session = {conversationId: null, datasetId: null, datasetName: null, limits: {}, pending: null};
const sidebar = document.querySelector('#sidebar');
const historyNav = document.querySelector('#chat-history');
function persist() {
  try {
    localStorage.setItem(storageKey, message.value);
    const {runView, actionsView, latestJob, loadedPackage, modelOpen, demo, ...savedSession} = session;
    if (!demo) localStorage.setItem(sessionKey, JSON.stringify(savedSession));
    localStorage.setItem(startsKey, JSON.stringify(startRequests));
  } catch { /* The request still works without browser storage. */ }
}
try {
  message.value = localStorage.getItem(storageKey) || '';
  const saved = JSON.parse(localStorage.getItem(sessionKey));
  if (saved && typeof saved === 'object') session = {...session, ...saved};
  const starts = JSON.parse(localStorage.getItem(startsKey));
  if (starts && typeof starts === 'object' && !Array.isArray(starts)) startRequests = starts;
  if (session.conversationId && session.startRequest) startRequests[session.conversationId] ||= session.startRequest;
} catch { /* Storage is optional. */ }
function updateSend() {
  send.disabled = busy || !connected || !message.value.trim();
  message.disabled = dataset.disabled = document.querySelector('#remove-file').disabled = busy;
  document.querySelector('#new-chat').disabled = busy;
  if (session.jobRequested) { message.disabled = true; send.disabled = true; dataset.disabled = true; document.querySelector('#remove-file').disabled = true; message.placeholder = 'This request is frozen. Start a new chat for another task.'; }
  send.textContent = busy ? 'Checking…' : session.recordStatus === 'needs_input' ? 'Send reply ↑' : 'Send request ↑';
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
  if (!response.ok) {
    const error = new Error(typeof value.detail === 'string' ? value.detail : 'The request was invalid. Check your message, dataset and limits.');
    error.status = response.status;
    throw error;
  }
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
function resetRequest() {
  if (busy) return;
  chatNavigation += 1;
  jobPoll += 1;
  session = {conversationId: null, datasetId: null, datasetName: null, limits: {}, pending: null};
  resetBench();
  dataset.value = ''; message.value = '';
  message.placeholder = 'Message GoTrain…';
  panel.hidden = true; panel.replaceChildren();
  document.querySelector('#welcome').hidden = false;
  status.textContent = ''; showAttachment(); persist(); updateSend(); message.focus();
  historyNav.querySelectorAll('[aria-current]').forEach(item => item.removeAttribute('aria-current'));
  sidebar.classList.remove('open');
}
async function loadHistory() {
  if (!connected) return;
  const rows = await api('conversations');
  historyNav.replaceChildren();
  if (!rows.length) { const empty = text('p', 'No chats yet', historyNav); empty.className = 'history-empty'; return; }
  for (const row of rows) {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'history-item';
    if (row.id === session.conversationId) button.setAttribute('aria-current', 'page');
    const title = text('span', row.title, button); title.className = 'history-title';
    const meta = text('small', `${displayTime(row.updated_at)} · ${row.status.replaceAll('_', ' ')}`, button); meta.className = 'history-meta';
    button.addEventListener('click', async () => {
      if (busy) return;
      const navigation = ++chatNavigation;
      jobPoll += 1;
      busy = true; updateSend();
      status.textContent = '';
      try {
        const record = await api('conversations/' + encodeURIComponent(row.id));
        let jobRequested = false;
        try { const state = await api(`conversations/${row.id}/job`); jobRequested = Boolean(state?.status); }
        catch (error) { if (error.status !== 404) throw error; }
        if (navigation !== chatNavigation) return;
        session = {conversationId: record.id, datasetId: record.dataset_id,
          datasetName: record.dataset_id, limits: record.limits, pending: null, jobRequested};
        dataset.value = ''; message.value = '';
        showRecord(record); showAttachment(); updateSend(); sidebar.classList.remove('open');
      } catch (error) {
        if (navigation !== chatNavigation) return;
        status.textContent = error.message;
        if (session.jobRequested) watchJob();
      } finally {
        busy = false; updateSend();
      }
    });
    historyNav.append(button);
  }
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
  resetBench();
  panel.replaceChildren();
  panel.hidden = false;
  document.querySelector('#welcome').hidden = true;
  session.conversationId = record.id;
  session.datasetId = record.dataset_id;
  session.boundDatasetId = record.dataset_id;
  session.recordStatus = record.status;
  session.limits = record.limits;
  const needsInput = record.status === 'needs_input';
  for (const entry of record.messages || []) chatMessage(entry.role === 'user' ? 'user' : 'assistant', entry.content, entry.created_at);
  message.placeholder = needsInput ? 'Reply to GoTrain…' : 'Message GoTrain…';
  if (record.summary) {
    const body = chatMessage('assistant', 'I understand the request. Review it below, then start training when you are ready.', record.reviewed_at, 'summary-message');
    const summary = record.summary;
    const list = document.createElement('dl');
    for (const [label, value] of Object.entries({Goal: summary.goal, Dataset: session.datasetName || summary.dataset_id,
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
      const conversation = record.id;
      startRequests[conversation] ||= `request_${crypto.randomUUID().replaceAll('-', '')}`;
      session.jobRequested = true; persist();
      try {
        await api(`conversations/${conversation}/start`, {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({request_id:startRequests[conversation]})});
      } catch (error) { if (session.conversationId === conversation) status.textContent = error.message; }
      if (session.conversationId === conversation) watchJob(); // Reconnect; never replay Start while polling.
    });
    button.id = 'start-training';
    text('small', health?.training_enabled ? 'No training starts until you press the button.' : 'Training is not enabled; no GPU work has started.', body);
  }
  const footer = text('small', `${record.model_requests} model request(s) used · validation only · test data stays sealed.`);
  footer.className = 'conversation-note';
  document.querySelector('.shell')?.setAttribute('data-phase', session.jobRequested ? 'run' : 'compose');
  document.querySelector('#bench-state').textContent = needsInput ? 'Needs your input' : 'Review proposal';
  document.querySelector('#bench-title').textContent = needsInput ? 'Let’s clarify your task' : 'Your training proposal';
  if (record.summary) {
    const content = document.querySelector('#bench-content'); content.replaceChildren();
    const summaryBody = panel.querySelector?.('.summary-message');
    if (summaryBody) content.append(summaryBody);
  }
  renderSteps(null);
  persist();
  loadHistory().catch(() => {});
  if (session.jobRequested) watchJob();
}

function watchJob() {
  const poll = ++jobPoll, conversation = session.conversationId;
  let failures = 0;
  async function tick() {
    if (poll !== jobPoll || session.conversationId !== conversation || !session.jobRequested) return;
    try {
      const state = await api(`conversations/${conversation}/job`);
      if (poll !== jobPoll || session.conversationId !== conversation) return;
      if (failures) status.textContent = '';
      failures = 0;
      const signature = `${state.status}|${state.stage || ''}|${state.attempts || 0}|${state.model_requests || 0}`;
      if (session.jobSignature !== signature) {
        session.jobSignature = signature;
        session.jobUpdatedAt = new Date().toISOString();
        persist();
      }
      session.latestJob = state;
      document.querySelector('#start-training')?.setAttribute('disabled', '');
      updateSend();
      const active = !['ready', 'selected', 'stopped', 'failed', 'interrupted'].includes(state.status);
      const view = renderRun(state, conversation, active);
      if (state.package && !session.loadedPackage) {
        session.loadedPackage = state.package.version;
        const models = await api('models');
        if (poll !== jobPoll || session.conversationId !== conversation) return;
        const selected = models.find(row => row.version === state.package.version);
        if (selected?.validation) document.querySelector('#run-metric').textContent = `${formatMetric(selected.validation)} · validation`;
      }
      if (active) setTimeout(tick, 2000);
    } catch (error) {
      if (poll !== jobPoll || session.conversationId !== conversation) return;
      if (error.status === 400 || error.status === 403) { status.textContent = error.message; return; }
      failures += 1;
      status.textContent = 'Progress connection interrupted. Reconnecting without restarting training…';
      setTimeout(tick, Math.min(30000, 2000 * 2 ** Math.min(failures - 1, 4)));
    }
  }
  tick();
}

function action(label, callback, parent) {
  const button = text('button', label, parent);
  button.type = 'button'; button.className = 'new-request'; button.addEventListener('click', callback);
  return button;
}

function showHistory(history, parent) {
  parent.replaceChildren();
  const head = document.createElement('div'); head.className = 'section-heading'; parent.append(head);
  text('h3', 'Candidates & experiments', head);
  action('Refresh', () => loadExperiments(), head);
  text('p', session.demo ? 'Illustrative workflow records · no models trained or scores measured.' : 'Compare measured validation results below. Open a trial for training settings and the agent’s reasoning. Full-split and subset scores have different evaluation coverage.', parent).className = 'section-description';
  const rows = history.experiments || [];
  if (!rows.length) text('p', 'No experiment records yet. They appear once a trial is recorded.', parent).className = 'empty-note';
  if (rows.length) {
    const wrap = document.createElement('div'); wrap.className = 'comparison-wrap'; parent.append(wrap);
    const table = document.createElement('table'); table.className = 'comparison-table'; wrap.append(table);
    text('caption', 'Validation comparison · higher scores are better', table);
    const header = document.createElement('tr'); table.append(header);
    for (const label of ['Trial', 'Primary score', 'Macro F1', 'Images']) { const th = text('th', label, header); th.setAttribute('scope', 'col'); }
    for (const [index, row] of rows.entries()) {
      const metric = row.best_validation || row.last_validation;
      const tr = document.createElement('tr'); table.append(tr);
      text('td', `${String(index + 1).padStart(2,'0')}${row.run_id === history.selected_run ? ' · Selected' : ''}`, tr);
      text('td', metric ? formatMetric(metric) : 'Not measured', tr);
      text('td', percent(metric?.macro_f1), tr);
      text('td', metric?.images == null ? '—' : `${metric.images} · ${metric.full_split === true ? 'full' : metric.full_split === false ? 'subset' : 'scope unrecorded'}`, tr);
    }
  }
  for (const [index, row] of rows.entries()) {
    const selected = row.run_id === history.selected_run;
    const detail = document.createElement('details'); detail.className = 'experiment'; parent.append(detail);
    const summary = document.createElement('summary'); detail.append(summary);
    const title = document.createElement('span'); title.className = 'experiment-title'; summary.append(title);
    text('strong', row.recipe?.candidate || row.recipe?.model || row.recipe?.architecture || `Candidate ${index + 1}`, title);
    text('small', `Trial ${String(index + 1).padStart(2,'0')} · ${row.status || 'Recorded'}`, title);
    const metric = row.best_validation || row.last_validation;
    text('span', metric ? formatMetric(metric) : 'No score', summary).className = 'experiment-score';
    if (selected) text('span', 'Selected', summary).className = 'selection-label';
    const body = document.createElement('div'); body.className = 'experiment-body'; detail.append(body);
    if (row.hypothesis) text('p', row.hypothesis, body);
    if (row.error_type) text('p', `Failure: ${row.error_type}`, body).className = 'error-text';
    const linked = (history.decisions || []).filter(d => d.candidate === row.run_id);
    for (const decision of linked) text('p', `${decision.kept === true ? 'Kept' : decision.kept === false ? 'Not selected' : 'Decision'}: ${decision.reason || 'No reason recorded'}`, body).className = 'decision-reason';
    const facts = document.createElement('dl'); body.append(facts);
    const recipe = row.recipe || {};
    const measures = metric ? [['Validation score', formatMetric(metric)], ['Accuracy', percent(metric.accuracy)], ['Macro F1', percent(metric.macro_f1)], ['Macro IoU', percent(metric.macro_iou)], ['Validation images', metric.images], ['Evaluation coverage', metric.full_split === true ? 'Entire validation split' : metric.full_split === false ? 'Validation subset' : 'Not recorded']] : [['Validation', 'No measured score recorded']];
    for (const [name, value] of [...measures, ['Phase', recipe.phase], ['Optimizer', recipe.optimizer], ['Learning rate', recipe.lr], ['Batch size', recipe.batch_size], ['Epoch limit', recipe.epochs], ['Augmentation', typeof recipe.augment === 'boolean' ? (recipe.augment ? 'Enabled' : 'Disabled') : undefined]]) {
      if (value !== undefined && value !== null && value !== '—') { text('dt', name, facts); text('dd', String(value), facts); }
    }
    for (const [name, value] of [['Run ID', row.run_id], ['Parent', row.parent_run], ['GPU seconds', row.gpu_job_seconds], ['Completed epochs', row.epochs_completed], ['Steps', row.steps]]) {
      if (value !== undefined && value !== null) { text('dt', name, facts); text('dd', String(value), facts); }
    }
    const config = document.createElement('details'); config.className = 'config-details'; body.append(config);
    text('summary', 'Recipe configuration', config); text('pre', JSON.stringify(row.recipe || {}, null, 2), config);
  }
  text('h3', 'Decision log', parent).className = 'decision-heading';
  const decisions = history.decisions || [];
  if (!decisions.length) text('p', 'No selection decisions recorded yet.', parent).className = 'empty-note';
  const log = document.createElement('ol'); log.className = 'decision-log'; parent.append(log);
  for (const decision of decisions) {
    const item = document.createElement('li'); log.append(item);
    text('strong', decision.kept === true ? 'Candidate retained' : decision.kept === false ? 'Selection unchanged' : 'Agent decision', item);
    text('p', decision.reason || decision.hypothesis || 'No explanation recorded.', item);
  }
}
function percent(value) { return typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : '—'; }
function formatMetric(metric) {
  return `${metricLabel(metric.primary_name) || 'Score'} ${percent(metric.primary)}`;
}
function setWorkspaceTab(name) {
  activeTab = name;
  for (const [key, selector] of Object.entries(tabPanels)) {
    document.querySelector(selector).hidden = key !== name;
    const tab = document.querySelector(`#tab-${key}`);
    tab.setAttribute('aria-selected', String(key === name)); tab.tabIndex = key === name ? 0 : -1;
  }
}
async function selectWorkspaceTab(name) {
  setWorkspaceTab(name);
  if (name === 'experiments') await loadExperiments();
  if (name === 'model') {
    const version = currentModelVersion || session.latestJob?.package?.version;
    if (version && loadedModelVersion !== version) await openModel(version);
    else if (!version) showPanelEmpty('model', 'No model available yet', session.demo ? 'The preview does not produce a model. Connect to SageMaker to use a verified model package.' : 'A verified model will appear here when your run finishes. You can also open a saved model from the conversation tools.');
  }
}
function showPanelEmpty(name, title, description) {
  const target = document.querySelector(tabPanels[name]); target.replaceChildren();
  const box = document.createElement('div'); box.className = 'panel-empty'; target.append(box);
  text('h3', title, box); text('p', description, box);
}
async function loadExperiments() {
  const request = ++historyRequest, navigation = chatNavigation;
  const target = document.querySelector('#experiments-content');
  if (session.demo) { showHistory(previewHistory(), target); return; }
  const ownTask = session.conversationId && session.jobRequested && (!currentModelVersion || currentModelVersion === session.latestJob?.package?.version);
  const endpoint = ownTask ? `conversations/${session.conversationId}/history` : currentModelVersion ? `models/${currentModelVersion}/history` : null;
  if (!endpoint) { showPanelEmpty('experiments', 'No experiments yet', 'Candidates, trial results and selection decisions will be recorded here once this task runs.'); return; }
  target.setAttribute('aria-busy', 'true');
  try {
    const data = await api(endpoint);
    if (request !== historyRequest || navigation !== chatNavigation) return;
    showHistory(data, target);
  } catch (error) {
    if (request !== historyRequest || navigation !== chatNavigation) return;
    showPanelEmpty('experiments', 'Could not load experiments', error.message);
    action('Retry', loadExperiments, target);
  } finally { if (request === historyRequest) target.removeAttribute('aria-busy'); }
}

async function openModel(version, parent) {
  const navigation = chatNavigation, request = ++modelRequest;
  setWorkspaceTab('model');
  showPanelEmpty('model', 'Loading model', 'Retrieving the model’s input contract and verified package.');
  try {
    modelList = await api('models');
    if (navigation !== chatNavigation || request !== modelRequest) return;
    const model = modelList.find(row => row.version === version);
    if (!model) throw new Error('This model version is unavailable.');
    currentModelVersion = version; loadedModelVersion = version;
    parent = document.querySelector('#model-content'); parent.replaceChildren();
    const box = document.createElement('section'); box.className = 'prediction-view'; parent.append(box);
    const spec = model.task_spec;
    const toolbar = document.createElement('div'); toolbar.className = 'model-toolbar'; box.append(toolbar);
    text('h3', spec.kind === 'segmentation' ? 'Map the classes in an image' : 'Classify an image', toolbar);
    const intro = text('p', 'Try the trained model on a matching image, or load a saved validation example. Prediction uses the selected model without retraining.', box); intro.className = 'model-intro';
    const scorecard = document.createElement('div'); scorecard.className = 'model-scorecard'; box.append(scorecard);
    text('small', 'SELECTED MODEL · VALIDATION', scorecard);
    text('strong', formatMetric(model.validation), scorecard);
    text('p', `${model.validation.images == null ? 'Recorded validation result' : `${model.validation.images} validation images`} · ${model.validation.full_split === true ? 'full split' : model.validation.full_split === false ? 'subset' : 'coverage not recorded'}. This measures performance across labeled examples, not certainty for your next image.`, scorecard);
    const modelDetails = document.createElement('details'); modelDetails.className = 'model-details'; box.append(modelDetails);
    text('summary', 'Task, model version & usage terms', modelDetails);
    text('p', model.label || model.task || 'Selected model', modelDetails);
    text('small', `Version ${version}. Private research package; see TERMS.md for redistribution restrictions.`, modelDetails);
    text('p', `Input: ${spec.width} × ${spec.height} pixels, ${spec.channels} bands in this order: ${spec.band_names.join(', ')}.`, box);
    text('small', `Input scaling divisors: ${spec.input_divisors.join(', ')}. No resizing or band conversion.`, modelDetails);
    text('p', `${metricLabel(model.validation.primary_name)}: ${(Number(model.validation.primary) * 100).toFixed(2)}% on validation · not final test evaluated.`, modelDetails);
    const inputZone = document.createElement('div'); inputZone.className = 'image-input'; box.append(inputZone);
    text('strong', '1. Choose your input', inputZone);
    text('p', 'PNG, JPEG or GeoTIFF · up to 32 MiB · original dimensions required', inputZone);
    const file = document.createElement('input'); file.type = 'file'; file.accept = '.png,.jpg,.jpeg,.tif,.tiff'; file.setAttribute('aria-label', 'Image for prediction'); inputZone.append(file);
    const label = document.createElement('label'); label.className = 'compatibility';
    const check = document.createElement('input'); check.type = 'checkbox'; label.append(check, document.createTextNode(' My image matches the listed band order and units.')); box.append(label);
    file.addEventListener('change', () => {
      check.checked = false;
      resultBox.replaceChildren(); text('p', 'Run prediction to evaluate the selected image.', resultBox);
      inputZone.querySelector('.input-image-preview')?.remove();
      const selected = file.files[0];
      if (selected && /\.(png|jpe?g)$/i.test(selected.name) && selected.size <= 32 * 2 ** 20) {
        const img = document.createElement('img'); img.className = 'input-image-preview'; img.alt = 'Selected input image';
        const url = URL.createObjectURL(selected); img.onload = img.onerror = () => URL.revokeObjectURL(url); img.src = url; inputZone.append(img);
      }
    });
    const resultBox = document.createElement('div'); resultBox.setAttribute('role', 'status'); resultBox.className = 'prediction-result'; box.append(resultBox);
    text('p', 'Your result will appear here: ranked class probabilities for classification, or a class overlay and downloadable mask for segmentation.', resultBox);
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
          text('small', 'PREDICTED CLASS', resultBox);
          text('h2', prediction.result.class_name ?? `Class ${prediction.result.class_id}`, resultBox);
          text('small', 'Scores for this image · uncalibrated probabilities', resultBox);
          for (const [i, p] of [...prediction.result.probabilities.entries()].sort((a,b) => b[1]-a[1])) {
            const row = document.createElement('div'); row.className = 'probability'; resultBox.append(row);
            text('span', model.class_names[i] ?? `Class ${i}`, row); text('strong', `${(p * 100).toFixed(1)}%`, row);
            const bar = document.createElement('meter'); bar.min = 0; bar.max = 1; bar.value = p; bar.setAttribute('aria-label', model.class_names[i] ?? `Class ${i}`); row.append(bar);
          }
          text('p', 'The highest score determines the predicted class. These probabilities are not validation accuracy or a guarantee of correctness.', resultBox);
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
    const actions = document.createElement('div'); actions.className = 'model-actions'; box.insertBefore(actions, resultBox);
    const upload = action('Run prediction', () => run(false), actions);
    upload.className = 'primary-action';
    const exampleButton = action('Try a validation example', () => run(true), actions);
    text('p', 'The example uses a saved validation image with a known input format. To evaluate accuracy on your own data, predictions also need ground-truth labels.', box).className = 'section-description';
    const download = text('a', 'Download package', toolbar); download.href = `api/models/${version}/download`; download.download = '';
    action('View experiments', () => selectWorkspaceTab('experiments'), actions);
  } catch (error) {
    if (navigation !== chatNavigation || request !== modelRequest) return;
    loadedModelVersion = null;
    showPanelEmpty('model', 'Model unavailable', error.message);
    action('Retry', () => openModel(version), document.querySelector('#model-content'));
  }
}

async function loadSavedOptions() {
  extras.replaceChildren();
  const datasets = await api('datasets');
  const saved = document.createElement('details'); extras.append(saved); text('summary', 'Choose saved dataset', saved);
  const select = document.createElement('select'); select.setAttribute('aria-label', 'Saved dataset'); saved.append(select);
  for (const row of datasets) {
    const option = document.createElement('option'); option.value = row.id;
    option.textContent = `${row.task.description || row.id} · ${row.task.kind} · ${row.counts.train} train / ${row.counts.valid} validation`; select.append(option);
  }
  action('Attach saved data', () => {
    if (busy || !canAttachDataset()) { status.textContent = 'Start a new chat to replace an attached or frozen dataset.'; return; }
    session.datasetId = select.value; session.datasetName = select.options[select.selectedIndex].textContent;
    dataset.value = ''; showAttachment(); persist();
  }, saved);
  modelList = await api('models');
  if (modelList.length) {
    const use = document.createElement('details'); extras.append(use); text('summary', 'Open a saved model', use);
    const models = document.createElement('select'); models.setAttribute('aria-label', 'Existing model'); use.append(models);
    for (const row of modelList) {
      const option = document.createElement('option'); option.value = row.version; option.textContent = `${row.label || row.task} · ${row.version}`; models.append(option);
    }
    action('Try model', () => openModel(models.value, use), use);
  }
}

message.addEventListener('input', () => { updateSend(); status.textContent = ''; persist(); });
function canAttachDataset() {
  return !session.conversationId || (!session.boundDatasetId && !session.jobRequested && ['draft', 'needs_input'].includes(session.recordStatus));
}
dataset.addEventListener('change', () => {
  if (!canAttachDataset()) {
    status.textContent = 'This attachment belongs to an existing request. Finish that request before changing its dataset.';
    dataset.value = '';
    return;
  }
  session.datasetId = session.datasetName = null;
  showAttachment();
  persist();
});
document.querySelector('#remove-file').addEventListener('click', () => {
  if (!canAttachDataset()) {
    status.textContent = 'The dataset is preserved for replies to this request.';
    return;
  }
  dataset.value = '';
  session.datasetId = session.datasetName = null;
  showAttachment(); persist();
});
document.querySelector('#new-chat').addEventListener('click', resetRequest);
document.querySelector('#open-history').addEventListener('click', () => sidebar.classList.add('open'));
document.querySelector('#close-history').addEventListener('click', () => sidebar.classList.remove('open'));
document.querySelector('#sidebar-shade').addEventListener('click', () => sidebar.classList.remove('open'));
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
    document.querySelector('#mobile-connection').textContent = health.preflight_enabled ? 'Connected' : 'Preview';
    document.querySelector('#preview-note').textContent = 'Attach a labeled manifest ZIP, or name a prepared dataset. Sending checks the request before any training.';
    if (session.conversationId) showRecord(await api('conversations/' + encodeURIComponent(session.conversationId)));
    await loadHistory();
    await loadSavedOptions();
  } catch {
    document.querySelector('#connection').textContent = 'Design preview';
    document.querySelector('#mobile-connection').textContent = 'Offline';
    document.querySelector('#preview-note').textContent = 'Preview only. Messages and selected files stay on this device until the service is connected.';
    action('Play 30-second UI demo', playPreview, extras).className = 'primary-action';
  }
  showAttachment(); updateSend();
}

function metricLabel(name) { return name === 'accuracy' ? 'Accuracy' : name === 'macro_iou' ? 'Macro IoU' : name; }
function resetBench() {
  historyRequest++; modelRequest++; currentModelVersion = loadedModelVersion = null;
  setWorkspaceTab('overview');
  document.querySelector('#experiments-content').replaceChildren();
  document.querySelector('#experiments-content').removeAttribute('aria-busy');
  document.querySelector('#model-content').replaceChildren();
  session.runView = null; session.loadedPackage = null; session.modelOpen = false; session.stepSignature = null;
  document.querySelector('.shell')?.setAttribute('data-phase', 'compose');
  document.querySelector('#bench-title').textContent = 'Task overview';
  document.querySelector('#bench-state').textContent = 'Ready to begin';
  const content = document.querySelector('#bench-content'); content.replaceChildren();
  const empty = document.createElement('div'); empty.className = 'bench-empty'; content.append(empty);
  text('span', '01 / TASK', empty).className = 'eyebrow';
  text('h3', 'No task selected', empty);
  text('p', 'Your task, resource usage and selected model will appear here. Start a conversation or reopen a saved task.', empty);
  const path = document.createElement('div'); path.className = 'empty-path'; empty.append(path);
  for (const label of ['01   Define your task', '02   Follow the experiments', '03   Use your model']) text('span', label, path);
  renderSteps(null);
}
function renderSteps(state) {
  const signature = `${state?.stage || ''}|${state?.status || ''}`;
  if (session.stepSignature === signature) return;
  session.stepSignature = signature;
  const steps = ['Inspect', 'Prepare', 'Compare', 'Refine', 'Verify & package', 'Ready'];
  const stages = ['Inspecting', 'Preparing', 'Comparing', 'Refining', 'Verifying and packaging', 'Ready'];
  const current = stages.indexOf(state?.stage);
  const list = document.querySelector('#workflow-steps'); list.replaceChildren();
  const terminal = state && ['ready','selected','stopped','failed','interrupted'].includes(state.status);
  // Only observed stages get completion marks; optional/unobserved steps are not inferred.
  session.observedStages ||= [];
  if (current >= 0 && !session.observedStages.includes(current)) session.observedStages.push(current);
  steps.forEach((label, i) => {
    const observed = session.observedStages.includes(i);
    const active = current === i && !terminal;
    const complete = observed && !active && (i !== current || state?.status === 'ready');
    const row = document.createElement('li'); row.className = active ? 'step active' : complete ? 'step complete' : 'step';
    const description = active ? 'In progress' : complete ? 'Completed' : terminal ? 'Not recorded' : 'Not started';
    text('span', active ? '◉' : complete ? '✓' : String(i+1).padStart(2,'0'), row).className = 'step-icon';
    const body = document.createElement('div'); row.append(body); text('strong', label, body); text('small', description, body);
    if (active) row.setAttribute('aria-current', 'step'); list.append(row);
  });
}
function renderRun(state, conversation, active) {
  document.querySelector('.shell')?.setAttribute('data-phase', active ? 'run' : 'result');
  renderSteps(state);
  const badge = document.querySelector('#bench-state'); badge.textContent = state.status === 'ready' ? 'Model ready' : state.status.replaceAll('_',' ');
  badge.className = active ? 'state-badge running' : 'state-badge';
  document.querySelector('#bench-title').textContent = state.package ? 'Your model is ready to use' : active ? 'Training workspace' : 'Run summary';
  const selectedChat = historyNav.querySelector?.('[aria-current="page"] .history-meta');
  if (selectedChat) selectedChat.textContent = state.package ? 'Model ready' : state.status.replaceAll('_',' ');
  let view = session.runView;
  if (!view) {
    const content = document.querySelector('#bench-content'); content.replaceChildren();
    view = document.createElement('section'); view.className = 'run-view'; content.append(view); session.runView = view;
    text('span', session.demo ? 'SIMULATED WORKFLOW' : active ? 'CURRENT ACTIVITY' : 'RUN OUTCOME', view).className = 'eyebrow';
    text('h3', '', view).id = 'run-stage';
    text('p', '', view).id = 'run-metric';
    const stats = document.createElement('div'); stats.className = 'run-stats'; view.append(stats);
    for (const [id,label] of [['elapsed','Elapsed'],['attempts','Experiments'],['calls','Agent requests'],['gpu','GPU seconds used / reserved']]) {
      const item = document.createElement('div'); stats.append(item); text('strong','—',item).id = `run-${id}`; text('span',label,item);
    }
    text('p','',view).id = 'run-decision';
    text('p','',view).id = 'run-error';
    const actions = document.createElement('div'); actions.id = 'run-actions'; actions.className = 'model-actions'; view.append(actions);
    text('small',session.demo ? 'Preview only. No compute used; all counters are illustrative.' : 'Validation results · official test evaluation pending.',view).className = 'result-note';
  }
  document.querySelector('#run-stage').textContent = state.stage || state.status;
  document.querySelector('#run-elapsed').textContent = `${Math.floor((state.elapsed_seconds || 0)/60)}m ${Math.floor((state.elapsed_seconds || 0)%60)}s`;
  document.querySelector('#run-attempts').textContent = `${state.attempts || 0}${session.limits?.attempts ? ` / ${session.limits.attempts}` : ''}`;
  document.querySelector('#run-calls').textContent = `${state.model_requests || 0}${session.limits?.model_requests ? ` / ${session.limits.model_requests}` : ''}`;
  document.querySelector('#run-gpu').textContent = `${Math.ceil(state.gpu_seconds || 0)}${session.limits?.gpu_seconds ? ` / ${session.limits.gpu_seconds}` : ''}`;
  document.querySelector('#run-decision').textContent = state.decisions?.at(-1)?.reason || (active ? 'GoTrain is working within your reviewed task and limits. Updates appear here as work progresses.' : 'Explore the selected model or review the recorded experiments.');
  document.querySelector('#run-error').textContent = state.error || (state.audit_required ? 'Operator review required. This run will not restart automatically.' : '');
  const signature = `${state.status}|${state.package?.version || ''}`;
  if (session.actionSignature !== signature || !session.actionsView || session.actionsView !== view) {
    session.actionSignature = signature; session.actionsView = view;
    const actions = document.querySelector('#run-actions'); actions.replaceChildren();
    if (!session.demo && active && state.status !== 'stopping') {
      const stop = action('Stop after current experiment', async () => {
        stop.disabled = true;
        try { await api(`conversations/${conversation}/stop`, {method:'POST'}); if (session.conversationId === conversation) watchJob(); }
        catch(error) { if (session.conversationId === conversation) { status.textContent = error.message; stop.disabled = false; } }
      },actions);
    }
    if (state.package) {
      action('Use model', () => openModel(state.package.version,view),actions).className = 'primary-action';
      const download = text('a','Download package',actions); download.href = `api/models/${state.package.version}/download`; download.download = '';
    }
    action('View experiments', () => selectWorkspaceTab('experiments'), actions);
  }
  return view;
}
function playPreview() {
  if (connected) return;
  resetRequest();
  const navigation = chatNavigation;
  session.demo = true;
  session.limits = {attempts: 3, model_requests: 12, gpu_seconds: 90};
  panel.hidden = false;
  document.querySelector('#welcome').hidden = true;
  chatMessage('user', 'Preview: build an image classifier from a labelled dataset.');
  chatMessage('assistant', 'This is a UI simulation. Stages, counters and decisions below are illustrative; no data is uploaded and no model is trained.');
  const stages = ['Inspecting', 'Preparing', 'Comparing', 'Refining', 'Verifying and packaging'];
  const notes = ['Checking the sample task and dataset structure.', 'Preparing compatible inputs for the example workflow.', 'Comparing example training approaches.', 'Illustrating a refinement of the selected approach.', 'Showing the final verification and packaging stage.'];
  let elapsed = 0;
  function tick() {
    if (connected || navigation !== chatNavigation || !session.demo) return;
    const done = elapsed >= 30, i = Math.min(4, Math.floor(elapsed / 6));
    session.previewElapsed = elapsed;
    renderRun({status: done ? 'stopped' : 'running', stage: done ? 'Preview complete' : stages[i], elapsed_seconds: elapsed, attempts: Math.min(3, Math.floor(elapsed / 9)), model_requests: Math.floor(elapsed / 3), gpu_seconds: Math.floor(elapsed * 1.4), decisions: [{reason: done ? 'The visual walkthrough is finished. No training, inference, model or score was produced.' : `Simulated activity: ${notes[i]}`}]}, null, !done);
    document.querySelector('#bench-title').textContent = 'Workflow preview';
    document.querySelector('#bench-state').textContent = 'SIMULATED · no training';
    document.querySelector('#run-metric').textContent = 'Illustrative counters only';

    if (done) action('Replay preview', playPreview, document.querySelector('#run-actions')).className = 'primary-action';
    else { elapsed++; setTimeout(tick, 1000); }
  }
  tick();
}
function previewHistory() {
  const elapsed = session.previewElapsed || 0;
  const experiments = [];
  if (elapsed >= 12) experiments.push({run_id:'preview-candidate-a', status: elapsed >= 18 ? 'simulated complete' : 'simulated running', recipe:{candidate:'Baseline recipe', phase:'compare'}, hypothesis:'Illustration: establish a reference candidate for the task.'});
  if (elapsed >= 18) experiments.push({run_id:'preview-candidate-b', status: elapsed >= 24 ? 'simulated complete' : 'simulated running', recipe:{candidate:'Refined recipe', phase:'tune'}, hypothesis:'Illustration: compare a bounded adjustment to the first candidate.'});
  return {experiments, decisions: elapsed >= 24 ? [{reason:'Illustration only: in a real run, the agent records why a candidate was retained or rejected, using its validation evidence.'}] : []};
}
for (const name of Object.keys(tabPanels)) {
  const tab = document.querySelector(`#tab-${name}`);
  tab.addEventListener('click', () => selectWorkspaceTab(name));
  tab.addEventListener('keydown', event => {
    const names = Object.keys(tabPanels), index = names.indexOf(name);
    const next = event.key === 'ArrowRight' ? names[(index + 1) % 3] : event.key === 'ArrowLeft' ? names[(index + 2) % 3] : event.key === 'Home' ? names[0] : event.key === 'End' ? names[2] : null;
    if (next) { event.preventDefault(); document.querySelector(`#tab-${next}`).focus(); selectWorkspaceTab(next); }
  });
}
session.stepSignature = null;
renderSteps(null);
connect();
