import {tasks} from './data/tasks.js';
import {experimentPage, predictionPage, escape} from './pages/workspace.js';

const app = document.querySelector('#app');
const storageKey = 'gotrain-workspace-drafts-v1';
let drafts = {};
try {
  const saved = JSON.parse(localStorage.getItem(storageKey));
  if (saved && typeof saved === 'object' && !Array.isArray(saved)) drafts = saved;
} catch { /* Draft storage is optional. */ }
let current = tasks[0];
let view = 'Task';
let sidebarOpen = false;
const modelIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/></svg>';
const menuIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/></svg>';

function taskPage() {
  return `<section class="welcome" aria-labelledby="welcome-title">
    <div class="welcome-mark">${modelIcon}</div>
    <h1 id="welcome-title">What should your model do?</h1>
    <p>Choose a dataset and describe your task.</p>
    <article class="dataset-card">
      <div class="dataset-heading"><span class="dataset-icon">${modelIcon}</span><div><h2>${escape(current.name)}</h2><p>${escape(current.description)}</p></div></div>
      <div class="detail-tags"><span>${escape(current.kind)}</span><span>${current.channels} bands</span><span>${escape(current.metric)}</span></div>
      <button class="text-button" data-action="suggest">Use suggested task <span aria-hidden="true">↗</span></button>
    </article>
  </section>`;
}

function render() {
  app.innerHTML = `<a class="skip-link" href="#main-content">Skip to workspace</a>
    <div class="app-layout ${sidebarOpen ? 'sidebar-open' : ''}">
      <button class="sidebar-backdrop" data-action="sidebar" aria-label="Close dataset navigation" ${sidebarOpen ? '' : 'hidden'}></button>
      <aside class="sidebar" aria-label="Dataset navigation">
        <div class="sidebar-top"><a href="/" class="brand">GoTrain<span>Workspace</span></a><button class="icon-button mobile-close" data-action="sidebar" aria-label="Close dataset navigation">×</button></div>
        <div class="nav-heading">Datasets</div>
        <nav aria-label="Supported datasets">${tasks.map(task => `<button class="project-link ${task.id === current.id ? 'active' : ''}" data-task="${task.id}" aria-current="${task.id === current.id ? 'true' : 'false'}">${modelIcon}<span>${escape(task.name)}</span></button>`).join('')}</nav>
        <div class="sidebar-bottom"><span class="sidebar-note">Geospatial classification<br>and segmentation</span><div class="profile"><span class="avatar">GT</span><div>GoTrain team<small>Model workspace</small></div></div></div>
      </aside>
      <div class="main-shell">
        <header class="topbar"><div><button class="icon-button" data-action="sidebar" aria-label="Toggle dataset navigation" aria-expanded="${matchMedia('(max-width: 760px)').matches ? sidebarOpen : !sidebarOpen}">${menuIcon}</button><span class="workspace-title">${escape(current.name)}</span></div><span class="preview-badge">Design preview</span></header>
        <nav class="view-nav" aria-label="Workspace views">${['Task', 'Experiments', 'Predictions'].map(name => `<button data-view="${name}" class="${view === name ? 'active' : ''}" aria-current="${view === name ? 'page' : 'false'}">${name}</button>`).join('')}</nav>
        <main id="main-content" tabindex="-1" class="${view === 'Task' ? 'task-main' : 'detail-main'}">${view === 'Task' ? taskPage() : view === 'Experiments' ? experimentPage(current) : predictionPage(current)}</main>
        ${view === 'Task' ? `<div class="composer-dock"><form id="task-form" class="composer"><label class="sr-only" for="task-input">Task description for ${escape(current.name)}</label><textarea id="task-input" name="goal" rows="2" maxlength="2000" placeholder="${escape(current.goal)}" aria-describedby="connection-note">${escape(typeof drafts[current.id] === 'string' ? drafts[current.id] : '')}</textarea><div class="composer-tools"><span class="dataset-reference">${escape(current.id)}</span><button class="build-button" type="submit" disabled>Build model <span aria-hidden="true">↑</span></button></div></form><p id="connection-note">Training, predictions and exports will be available when the workspace is connected.</p></div>` : ''}
      </div>
    </div>`;
  if (matchMedia('(max-width: 760px)').matches) {
    const sidebar = document.querySelector('.sidebar');
    sidebar.inert = !sidebarOpen;
    sidebar.setAttribute('aria-hidden', String(!sidebarOpen));
    document.querySelector('.main-shell').inert = sidebarOpen;
  }
}

document.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button) return;
  if (button.dataset.task) {
    current = tasks.find(task => task.id === button.dataset.task);
    sidebarOpen = false;
    render();
    document.querySelector(matchMedia('(max-width: 760px)').matches ? '#main-content' : `[data-task="${current.id}"]`).focus();
  } else if (button.dataset.view) {
    view = button.dataset.view;
    render();
    document.querySelector(`[data-view="${view}"]`).focus();
  } else if (button.dataset.action === 'sidebar') {
    sidebarOpen = !sidebarOpen;
    render();
    document.querySelector(sidebarOpen ? `[data-task="${current.id}"]` : '.topbar .icon-button').focus();
  } else if (button.dataset.action === 'suggest') {
    drafts[current.id] = current.goal;
    saveDraft();
    const input = document.querySelector('#task-input');
    input.value = current.goal;
    input.focus();
  }
});

function saveDraft() {
  try { localStorage.setItem(storageKey, JSON.stringify(drafts)); } catch { /* No persistence when unavailable. */ }
}
document.addEventListener('input', event => {
  if (event.target.id !== 'task-input') return;
  drafts[current.id] = event.target.value;
  saveDraft();
});
document.addEventListener('submit', event => {
  if (event.target.id === 'task-form') event.preventDefault();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && sidebarOpen) {
    sidebarOpen = false;
    render();
    document.querySelector('.topbar .icon-button').focus();
  }
});
matchMedia('(max-width: 760px)').addEventListener('change', () => { sidebarOpen = false; render(); });
render();
