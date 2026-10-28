'use strict';
const $ = id => document.getElementById(id);
let file = null, objectURL = null, job = null, events = [], busy = false;
let roi = null, drawing = false, origin = null, activeEvent = null, statusInfo = null;
const ns = 'http://www.w3.org/2000/svg';
const fallbackTargets = {kitchen: ['cap_absent', 'mask_uncovered', 'uniform_absent'], front: ['table_uncleared', 'bread_shelf_underfilled', 'cashier_vacancy']};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function message(text, error = false) {
  $('message').textContent = englishText(text, 'Something went wrong. Try again or contact the server owner.');
  document.querySelector('.statusline').dataset.state = error ? 'error' : busy ? 'busy' : 'idle';
}
async function request(path, body) {
  const response = await fetch(path, body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {});
  if (response.status === 401) throw Error('Your session has expired. Reload the page and sign in again.');
  let data;
  try { data = await response.json(); } catch { throw Error('The server returned an unexpected response. Try again.'); }
  if (!response.ok) throw Error(englishText(data.error, 'The request failed. Try again.'));
  return data;
}
function updateInterface() {
  const spec = statusInfo?.engines?.yolo, ready = Boolean(spec?.available);
  const targets = statusInfo?.scene_targets?.[$('scene').value] || fallbackTargets[$('scene').value];
  $('checkList').replaceChildren(...targets.map(id => element('li', '', COPY.checks[id] || englishText(statusInfo?.target_labels?.[id]?.en, 'Scene check'))));
  $('prompt').value = targets.map(id => statusInfo?.target_labels?.[id]?.en || COPY.targets[id]).join(' · ');
  const kind = file ? (file.type.startsWith('video') ? 'video' : 'image') : null;
  const supported = !kind || Boolean(spec?.media_types?.includes(kind));
  $('apiStatus').textContent = !spec ? 'Connecting' : `YOLO + MobileNetV3 ${ready ? 'ready' : 'unavailable'}`;
  $('apiStatus').dataset.state = !spec ? 'connecting' : ready ? 'ready' : 'error';
  $('analyze').disabled = busy || !ready || !supported;
  const cashier = targets.includes('cashier_vacancy');
  $('drawRoi').disabled = busy || !cashier; $('clearRoi').disabled = busy || !cashier;
  $('cashierRoiNote').textContent = spec?.cashier_roi_required
    ? 'Select the employee work area behind the cashier counter to run this check.'
    : 'A cashier region can help focus the check. It does not measure how long the station was unattended.';
}
$('scene').onchange = () => { roi = null; updateRoi(); updateInterface(); };
function loadFile(value) {
  if (busy || !value) return;
  if (!value.size) return message('This file is empty or unavailable. Choose it again.', true);
  if (value.size > 30 * 1024 * 1024) return message('Choose a file smaller than 30 MB.', true);
  if (!['image/jpeg', 'image/png', 'video/mp4', 'video/quicktime'].includes(value.type)) return message('Use a JPG, PNG, MP4 or MOV file.', true);
  file = value; job = null; events = []; roi = null; activeEvent = null;
  drawing = false; origin = null; overlay.classList.remove('drawing'); updateRoi();
  $('results').hidden = true; $('json').disabled = $('csv').disabled = true;
  showUncertain.checked = false;
  if (objectURL) URL.revokeObjectURL(objectURL);
  objectURL = URL.createObjectURL(file);
  $('fileName').textContent = englishText(file.name, 'File selected');
  const video = file.type.startsWith('video');
  $('video').pause(); $('video').hidden = !video; $('image').hidden = video; $('empty').hidden = true;
  (video ? $('video') : $('image')).src = objectURL;
  updateInterface(); message('File ready. Check the scene, then run analysis.');
}
$('media').onchange = () => loadFile($('media').files[0]);
$('drop').ondragover = e => { e.preventDefault(); if (!busy) $('drop').classList.add('dragover'); };
$('drop').ondragleave = () => $('drop').classList.remove('dragover');
$('drop').ondrop = e => { e.preventDefault(); $('drop').classList.remove('dragover'); loadFile(e.dataTransfer.files[0]); };
$('video').onloadedmetadata = () => { if ($('video').duration > 60.5) message('Trim the video to 60 seconds or less.', true); };
$('image').onerror = () => message('The browser could not open this image. Try another JPG or PNG.', true);
$('video').onerror = () => { if (file?.type.startsWith('video')) message('The browser could not play this video. Try an H.264 MP4.', true); };
function base64File(value) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader(); reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = () => reject(Error('The file could not be read. Choose it again.')); reader.readAsDataURL(value);
  });
}
function mediaElement() { return $('video').hidden ? $('image') : $('video'); }
const stage = element('div', 'media-stage'); $('video').before(stage); stage.append($('video'), $('image'));
const overlay = document.createElementNS(ns, 'svg'); overlay.id = 'evidenceOverlay';
overlay.setAttribute('viewBox', '0 0 1000 1000'); overlay.setAttribute('preserveAspectRatio', 'none'); stage.append(overlay);
function rect(box, kind) {
  if (!Array.isArray(box) || box.length !== 4 || box.some(v => !Number.isFinite(v))) return;
  const shape = document.createElementNS(ns, 'rect');
  for (const [name, value] of Object.entries({x: box[0], y: box[1], width: box[2] - box[0], height: box[3] - box[1], class: kind})) shape.setAttribute(name, value);
  overlay.append(shape);
}
function drawOverlay() {
  overlay.replaceChildren();
  if (roi) rect(roi.map(v => v * 1000), 'roi-box');
  if (activeEvent) for (const box of activeEvent.boxes_1000 || [activeEvent.bbox_1000]) rect(box, 'issue-box');
}
function updateRoi() { $('roiValue').value = roi ? roi.map(n => n.toFixed(3)).join(', ') : ''; drawOverlay(); }
$('drawRoi').onclick = () => {
  if (!file || !mediaElement().getBoundingClientRect().width) return message('Add a file before selecting a cashier region.', true);
  if (!$('video').hidden) $('video').pause();
  drawing = true; overlay.classList.add('drawing');
  message('Drag over the area where the cashier stands.');
};
$('clearRoi').onclick = () => { roi = null; drawing = false; origin = null; overlay.classList.remove('drawing'); updateRoi(); };
function point(e) {
  const box = overlay.getBoundingClientRect();
  return [Math.max(0, Math.min(1, (e.clientX - box.left) / box.width)), Math.max(0, Math.min(1, (e.clientY - box.top) / box.height))];
}
function setRoi(end) { roi = [Math.min(origin[0], end[0]), Math.min(origin[1], end[1]), Math.max(origin[0], end[0]), Math.max(origin[1], end[1])]; drawOverlay(); }
overlay.onpointerdown = e => {
  if (!drawing || busy) return;
  origin = point(e); overlay.setPointerCapture(e.pointerId); e.preventDefault();
};
overlay.onpointermove = e => { if (origin) setRoi(point(e)); };
overlay.onpointerup = e => {
  if (!origin) return;
  setRoi(point(e)); origin = null; drawing = false; overlay.classList.remove('drawing');
  if (roi && (roi[2] - roi[0] < .01 || roi[3] - roi[1] < .01)) roi = null;
  updateRoi(); message(roi ? 'Cashier region selected.' : 'The selection was too small. Drag to select a region.');
};
overlay.onpointercancel = () => { origin = null; drawing = false; overlay.classList.remove('drawing'); };
$('video').addEventListener('play', () => { activeEvent = null; drawOverlay(); });
$('video').addEventListener('timeupdate', () => { if (activeEvent && Math.abs($('video').currentTime - activeEvent.start_s) > .3) { activeEvent = null; drawOverlay(); } });
function viewEvent(event) {
  activeEvent = event;
  if (!$('video').hidden) { $('video').pause(); $('video').currentTime = event.start_s; }
  drawOverlay(); mediaElement().scrollIntoView({block: 'center', behavior: 'smooth'});
}
const showLabel = element('label', 'filter'), showUncertain = element('input');
showUncertain.type = 'checkbox'; showUncertain.id = 'showUncertain';
showLabel.append(showUncertain, document.createTextNode('Include uncertain findings'));
$('events').before(showLabel); showUncertain.onchange = renderEvents;
const allChecks = element('details'), auditTitle = element('summary', '', 'All model checks'), auditScroll = element('div', 'audit-scroll');
allChecks.id = 'allAssessments'; allChecks.append(auditTitle, auditScroll); $('events').after(allChecks);
function renderAudit() {
  const table = element('table', 'audit-table'), head = element('thead'), hr = element('tr');
  for (const title of ['Time', 'Check', 'Result', 'Evidence']) hr.append(element('th', '', title));
  head.append(hr); table.append(head);
  const body = element('tbody');
  for (const frame of job?.frame_results || []) for (const row of frame.assessments || []) {
    const tr = element('tr');
    const execution = row.execution_status || 'completed';
    const result = execution !== 'completed' ? 'Not completed' : {present: 'Issue observed', absent: 'No issue detected', uncertain: 'Uncertain'}[row.status] || 'Not evaluated';
    for (const text of [formatTime(frame.timestamp_s), COPY.targets[row.type] || englishText(row.type, 'Check'), result, evidenceText(row.evidence)]) tr.append(element('td', '', text));
    body.append(tr);
  }
  table.append(body); auditScroll.replaceChildren(table);
}
function formatTime(value) { return `${Number(value || 0).toFixed(1)} s`; }
function renderSummary() {
  const original = job?.events || [], observed = original.filter(e => e.status === 'observed').length, uncertain = original.filter(e => e.status === 'uncertain').length;
  const notRun = (job?.frame_results || []).flatMap(f => f.assessments || []).filter(r => (r.execution_status || 'completed') !== 'completed').length;
  $('metrics').replaceChildren(...[[observed, 'Issue categories'], [uncertain, 'Uncertain categories'], [notRun, 'Checks not completed']].map(([count, title]) => {
    const metric = element('div', 'metric'); metric.append(element('strong', '', count), element('span', '', title)); return metric;
  }));
  $('summary').textContent = 'Original model results, grouped by category across sampled frames.';
}
function renderEvents() {
  const container = $('events'); container.replaceChildren();
  let count = 0;
  events.forEach((event, index) => {
    if (event.status === 'uncertain' && !showUncertain.checked) return;
    count++;
    const card = element('article', 'event'), header = element('div', 'event-header');
    header.append(element('h3', '', findingLabel(event)), element('span', event.status === 'uncertain' ? 'badge uncertain' : 'badge', event.status === 'uncertain' ? 'Uncertain' : 'Issue observed'));
    const evidence = element('p', 'event-evidence', evidenceText(event.evidence));
    card.append(header, evidence);
    const toolbar = element('div', 'evidence-toolbar');
    const observations = event.observations || [event];
    toolbar.append(element('span', 'sample-caption', file?.type.startsWith('video') ? 'Evidence at' : 'Evidence'));
    for (const observation of observations) {
      const button = element('button', 'sample-button', file?.type.startsWith('video') ? formatTime(observation.start_s) : 'View image');
      button.type = 'button';
      button.onclick = () => {
        toolbar.querySelectorAll('button').forEach(b => b.classList.remove('active')); button.classList.add('active');
        evidence.textContent = evidenceText(observation.evidence); viewEvent(observation);
      };
      toolbar.append(button);
    }
    card.append(toolbar);
    const edit = element('details', 'event-edit'), editTitle = element('summary', '', 'Edit finding'), grid = element('div', 'edit-grid');
    edit.append(editTitle, grid);
    function field(title, key, type = 'text') {
      const label = element('label', type === 'textarea' ? 'wide' : '', title);
      const input = element(type === 'textarea' ? 'textarea' : 'input');
      if (type !== 'textarea') input.type = type;
      if (type === 'number') { input.min = '0'; input.max = String(job?.duration_s || 0); input.step = '0.1'; }
      input.value = type === 'number' ? event[key] : !event[key] ? '' : key === 'behavior' ? findingLabel(event) : evidenceText(event[key]);
      input.disabled = busy;
      input.oninput = () => {
        event[key] = type === 'number' ? Number(input.value) : input.value;
        if (key === 'behavior') header.querySelector('h3').textContent = englishText(input.value, 'Finding');
        if (key === 'evidence') evidence.textContent = evidenceText(input.value);
      };
      label.append(input); grid.append(label);
    }
    field('Category', 'behavior');
    const statusLabel = element('label', '', 'Review status'), select = element('select');
    for (const [value, label] of [['observed', 'Issue observed'], ['uncertain', 'Uncertain']]) select.append(new Option(label, value));
    select.value = event.status; select.disabled = busy; select.onchange = () => { event.status = select.value; renderEvents(); };
    statusLabel.append(select); grid.append(statusLabel);
    if (file?.type.startsWith('video')) {
      field('Representative frame (seconds)', 'start_s', 'number');
      field('Frame end (not duration)', 'end_s', 'number');
    }
    field('Evidence or correction', 'evidence', 'textarea');
    const remove = element('button', 'remove', 'Remove from review'); remove.disabled = busy;
    remove.onclick = () => { events.splice(index, 1); activeEvent = null; drawOverlay(); renderEvents(); };
    grid.append(remove); card.append(edit); container.append(card);
  });
  if (!count) container.append(element('p', 'empty-results', events.some(e => e.status === 'uncertain')
    ? 'No issue findings in this draft. Include uncertain findings or open All model checks to inspect the other results.'
    : 'No findings in this draft. Open All model checks to inspect uncertain or incomplete assessments before interpreting this result.'));
}
function setBusy(value) {
  busy = value;
  for (const id of ['analyze', 'media', 'scene', 'sampleCount', 'drawRoi', 'clearRoi', 'addEvent', 'save', 'notes']) $(id).disabled = value;
  $('drop').setAttribute('aria-disabled', String(value));
  document.querySelector('.statusline').dataset.state = value ? 'busy' : 'idle';
  updateInterface();
}
$('analyze').onclick = async () => {
  if (busy) return;
  if (!file) return message('Add an image or video first.', true);
  const spec = statusInfo?.engines?.yolo;
  if (!spec?.available) return message('YOLO + MobileNetV3 is not ready on this server. Contact the site owner.', true);
  if (file.type.startsWith('video') && (!Number.isFinite($('video').duration) || $('video').duration > 60.5)) return message('Wait for the video to load. It must be 60 seconds or less.', true);
  drawing = false; origin = null; overlay.classList.remove('drawing');
  setBusy(true); job = null; events = []; activeEvent = null;
  $('results').hidden = true; $('json').disabled = $('csv').disabled = true; drawOverlay();
  let failure = null;
  try {
    message('Uploading media...');
    const response = await request('/api/analyze', {scene: $('scene').value, prompt: $('prompt').value, cashier_roi: roi, sample_count: Number($('sampleCount').value), media_base64: await base64File(file)});
    for (;;) {
      await new Promise(resolve => setTimeout(resolve, 1800));
      job = await request('/api/jobs/' + response.id);
      if (job.state === 'failed') throw Error(job.error);
      if (job.state === 'completed') break;
      message(job.progress ? `Analyzing frame ${job.progress.completed_frames} of ${job.progress.total_frames}...` : 'Waiting for the model. Video analysis may take a few minutes.');
    }
    events = structuredClone(job.events); showUncertain.checked = false;
    $('modelName').textContent = `YOLO + MobileNetV3 · ${job.scene === 'front' ? 'Front of house' : 'Kitchen'} · ${englishText(job.provider_model, 'Model result')}`;
    document.querySelector('.warning').hidden = !file.type.startsWith('video');
    $('notes').value = ''; $('results').hidden = false; $('json').disabled = $('csv').disabled = false;
    renderSummary(); renderAudit();
  } catch (error) { failure = error; }
  finally { setBusy(false); if (job?.state === 'completed') renderEvents(); }
  if (failure) message(failure.message, true);
  else { message('Analysis complete. Review the findings before exporting.'); $('results').scrollIntoView({block: 'start', behavior: 'smooth'}); }
};
$('addEvent').onclick = () => {
  if (!job || busy) return;
  events.push({start_s: 0, end_s: 0, behavior: '', status: 'observed', evidence: ''}); renderEvents();
  const last = $('events').lastElementChild; last.querySelector('details').open = true;
  last.querySelector('input').focus();
};
$('save').onclick = async () => {
  if (!job || busy) return;
  const invalid = events.some(e => !e.behavior.trim() || !e.evidence.trim() || !Number.isFinite(e.start_s) || !Number.isFinite(e.end_s) || e.start_s < 0 || e.start_s > e.end_s || e.end_s > job.duration_s);
  if (invalid) return message('Give each finding a category, evidence and valid frame time before saving.', true);
  $('save').disabled = true;
  try {
    await request('/api/review', {id: job.id, result: {summary: $('summary').textContent, events}, notes: $('notes').value});
    job = await request('/api/jobs/' + job.id);
    message('Review saved. The original predictions are unchanged.');
  } catch (error) { message(error.message, true); } finally { $('save').disabled = false; }
};
function download(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], {type})), a = element('a');
  a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$('json').onclick = () => { if (job) download('deviationlab-' + job.id + '.json', JSON.stringify({...job, unsaved_review_draft: {events, notes: $('notes').value}, exported_at: new Date().toISOString()}, null, 2), 'application/json'); };
function cell(value) { let text = String(value ?? ''); if (/^[=+@\-\t\r]/.test(text)) text = "'" + text; return '"' + text.replaceAll('"', '""') + '"'; }
$('csv').onclick = () => {
  if (!job) return;
  const rows = [['job_id', 'source_sha256', 'engine', 'model', 'adapter', 'engine_protocol', 'scene', 'engine_input_mode', 'external_processing', 'row_type', 'time_s', 'deviation', 'finding', 'execution_status', 'evidence', 'bbox_1000', 'review_notes', 'sample_times_s', 'sample_observations']];
  const prefix = [job.id, job.source_sha256, job.engine, job.provider_model, job.protocol_version, job.engine_protocol, job.scene, job.engine_capabilities?.input_mode || 'image', job.engine_capabilities?.external ?? ''];
  for (const frame of job.frame_results) for (const row of frame.assessments) rows.push([...prefix, 'model_check', frame.timestamp_s, row.type, row.status, row.execution_status || 'completed', row.evidence, JSON.stringify(row.bbox_1000), '', '', '']);
  for (const [type, items, notes] of [['saved_human_review', job.review_history.at(-1)?.result.events || [], job.review_history.at(-1)?.notes || ''], ['unsaved_review_draft', events, $('notes').value]]) for (const row of items) rows.push([...prefix, type, row.start_s, row.deviation_type || row.behavior, row.status, 'human_review', row.evidence, JSON.stringify(row.bbox_1000), notes, JSON.stringify(row.sample_times_s || []), JSON.stringify(row.observations || [])]);
  download('deviationlab-' + job.id + '.csv', '\ufeff' + rows.map(row => row.map(cell).join(',')).join('\r\n'), 'text/csv;charset=utf-8');
};
updateInterface();
request('/api/status').then(value => { statusInfo = value; updateInterface(); message('Add an image or short video to begin.'); }).catch(error => { $('apiStatus').textContent = 'Connection unavailable'; $('apiStatus').dataset.state = 'error'; message(error.message, true); });
