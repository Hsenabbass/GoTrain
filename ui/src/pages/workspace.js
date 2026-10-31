export const escape = value => String(value).replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));

export function experimentPage(task) {
  return `<section aria-labelledby="experiments-title"><div class="section-title"><h1 id="experiments-title">Experiments</h1><p>Training attempts and model selection for ${escape(task.name)}.</p></div>
    <div class="empty-state"><span class="empty-icon" aria-hidden="true">≋</span><h2>Your experiment history will appear here</h2><p>Compare validation results and see why a candidate was kept or rejected.</p><span class="pill">Awaiting connection</span></div></section>`;
}

export function predictionPage(task) {
  return `<section aria-labelledby="predictions-title"><div class="section-title"><h1 id="predictions-title">Predictions</h1><p>Use the selected ${escape(task.name)} model on compatible imagery.</p></div>
    <div class="prediction-layout"><div class="empty-state"><span class="empty-icon" aria-hidden="true">▧</span><h2>${task.kind === 'Segmentation' ? 'Inspect a predicted mask' : 'Classify an image'}</h2><p>${task.kind === 'Segmentation' ? 'Compare an image with its predicted mask and overlay.' : 'See the predicted class and model probabilities for an image.'}</p><button class="button" disabled aria-describedby="prediction-note">Choose image</button><p id="prediction-note" class="connection-note">Prediction will be available when connected.</p></div>
    <aside class="input-requirements"><span class="eyebrow">INPUT REQUIREMENTS</span><h2>${escape(task.inputName)}</h2><p>${escape(task.inputDescription)}</p><dl><div><dt>Channels</dt><dd>${task.channels}</dd></div><div><dt>Image size</dt><dd>${task.size}</dd></div><div><dt>Task</dt><dd>${escape(task.kind)}</dd></div></dl></aside></div></section>`;
}
