const app = document.querySelector('#app');
const storageKey = 'gotrain-message-draft-v1';
app.innerHTML = `<header class="topbar"><a class="brand" href="/">GoTrain</a><span>Design preview</span></header>
<main><section class="workspace" aria-labelledby="title"><div class="mark" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/></svg></div><h1 id="title">What would you like to build?</h1><p class="intro">Tell the agent your goal and constraints.</p>
<form id="message-form"><label class="sr-only" for="message">Message to the agent</label><textarea id="message" name="message" rows="5" maxlength="4000" placeholder="Explain what you want the model to do, the data you have, and any time or compute limits." aria-describedby="preview-note"></textarea>
<div id="attachment" class="attachment" hidden><span id="filename"></span><button id="remove-file" type="button" aria-label="Remove selected dataset">×</button></div>
<div class="composer-actions"><label class="upload-button"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4m-4 4 4-4 4 4M5 15v5h14v-5"/></svg><span>Upload dataset</span><input id="dataset" type="file" aria-label="Upload dataset" aria-describedby="preview-note"></label><button class="send-button" id="send" type="submit" disabled>Send <span aria-hidden="true">↑</span></button></div></form>
<p id="preview-note" class="note">Preview only. Messages and selected files stay on this device until the agent is connected.</p><p id="status" class="status" role="status"></p></section></main>`;
const message = document.querySelector('#message');
const dataset = document.querySelector('#dataset');
const send = document.querySelector('#send');
try { message.value = localStorage.getItem(storageKey) || ''; } catch { /* Storage is optional. */ }
function updateSend() { send.disabled = !message.value.trim(); }
updateSend();
message.addEventListener('input', () => { updateSend(); document.querySelector('#status').textContent = ''; try { localStorage.setItem(storageKey, message.value); } catch {} });
dataset.addEventListener('change', () => {
 const file = dataset.files[0];
 document.querySelector('#attachment').hidden = !file;
 document.querySelector('#filename').textContent = file ? file.name : '';
 document.querySelector('#status').textContent = '';
});
document.querySelector('#remove-file').addEventListener('click', () => { dataset.value = ''; document.querySelector('#attachment').hidden = true; document.querySelector('#filename').textContent = ''; dataset.focus(); });
document.querySelector('#message-form').addEventListener('submit', event => { event.preventDefault(); if (!message.value.trim()) return; document.querySelector('#status').textContent = 'The agent is not connected yet. Your message and dataset have not been sent.'; });
