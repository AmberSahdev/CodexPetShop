(() => {
  const form = document.getElementById('upload-form');
  const nameInput = document.getElementById('name');
  const nameStatus = document.getElementById('name-status');

  const folderDrop = document.getElementById('folder-drop');
  const folderInput = document.getElementById('folder-input');
  const folderSummary = document.getElementById('folder-summary');
  const folderSummaryText = document.getElementById('folder-summary-text');
  const folderError = document.getElementById('folder-error');

  const submitBtn = document.getElementById('submit-btn');
  const submitError = document.getElementById('submit-error');
  const steps = [...document.querySelectorAll('.step')];

  const ID_RE = /^[a-z0-9-]{2,24}$/;
  const MAX_SPRITE = 2 * 1024 * 1024;

  let petJsonFile = null;
  let spritesheetFile = null;

  const state = { nameOk: false, folderOk: false };

  function setStepActive(i, active) {
    const el = steps[i]; if (!el) return;
    el.classList.toggle('opacity-40', !active);
    el.classList.toggle('pointer-events-none', !active);
  }
  function refresh() {
    setStepActive(1, state.nameOk);
    setStepActive(2, state.nameOk && state.folderOk);
    submitBtn.disabled = !(state.nameOk && state.folderOk);
  }

  // ---------- Step 1: name availability ----------
  let checkSeq = 0, checkTimer = null;
  function setNameStatus(text, color, icon) {
    const iconHtml = icon ? `<span class="material-symbols-outlined text-[16px]">${icon}</span>` : '';
    nameStatus.innerHTML = iconHtml + (text ? `<span>${text}</span>` : '');
    nameStatus.className = 'text-sm min-w-[6rem] flex items-center gap-1 ' + (color || 'text-base1');
  }
  async function checkName() {
    const v = nameInput.value.trim().toLowerCase();
    nameInput.value = v;
    state.nameOk = false; refresh();
    if (!v) { setNameStatus(''); return; }
    if (!ID_RE.test(v)) { setNameStatus('invalid', 'text-sol-red', 'error'); return; }
    setNameStatus('checking…', 'text-base1', 'progress_activity');
    const seq = ++checkSeq;
    try {
      const res = await fetch(`/api/check/${encodeURIComponent(v)}`);
      const data = await res.json();
      if (seq !== checkSeq) return;
      if (data.available) { setNameStatus('available', 'text-sol-green', 'check_circle'); state.nameOk = true; }
      else { setNameStatus('taken', 'text-sol-red', 'block'); }
    } catch (e) { setNameStatus('error', 'text-sol-red', 'error'); }
    refresh();
  }
  nameInput.addEventListener('input', () => {
    clearTimeout(checkTimer);
    checkTimer = setTimeout(checkName, 300);
  });

  // ---------- Step 2: folder drop / pick ----------
  function readEntries(dirReader) {
    return new Promise((resolve, reject) => {
      const all = [];
      const next = () => dirReader.readEntries(batch => {
        if (!batch.length) return resolve(all);
        all.push(...batch); next();
      }, reject);
      next();
    });
  }
  async function walkEntry(entry, files) {
    if (entry.isFile) {
      await new Promise((res, rej) => entry.file(f => { files.push(f); res(); }, rej));
    } else if (entry.isDirectory) {
      const reader = entry.createReader();
      const children = await readEntries(reader);
      for (const c of children) await walkEntry(c, files);
    }
  }
  function nameOf(f) { return (f.webkitRelativePath || f.name).split('/').pop().toLowerCase(); }
  function setFolderError(msg) { folderError.textContent = msg; folderSummary.classList.add('hidden'); state.folderOk = false; refresh(); }
  function processFiles(files) {
    folderError.textContent = '';
    petJsonFile = null; spritesheetFile = null;
    for (const f of files) {
      const n = nameOf(f);
      if (n === 'pet.json') petJsonFile = f;
      else if (n === 'spritesheet.webp') spritesheetFile = f;
    }
    if (!petJsonFile) return setFolderError("Folder is missing pet.json.");
    if (!spritesheetFile) return setFolderError("Folder is missing spritesheet.webp.");
    if (spritesheetFile.size > MAX_SPRITE)
      return setFolderError(`spritesheet.webp is too large (${(spritesheetFile.size/1024/1024).toFixed(2)} MB; limit 2 MB).`);
    folderSummaryText.textContent = `Found pet.json + spritesheet.webp (${(spritesheetFile.size/1024).toFixed(0)} KB)`;
    folderSummary.classList.remove('hidden');
    state.folderOk = true; refresh();
  }
  folderInput.addEventListener('change', () => processFiles([...folderInput.files]));
  ['dragenter','dragover'].forEach(ev => folderDrop.addEventListener(ev, e => {
    e.preventDefault(); e.stopPropagation(); folderDrop.classList.add('drop-active');
  }));
  ['dragleave','drop'].forEach(ev => folderDrop.addEventListener(ev, e => {
    e.preventDefault(); e.stopPropagation(); folderDrop.classList.remove('drop-active');
  }));
  folderDrop.addEventListener('drop', async e => {
    const items = e.dataTransfer.items ? [...e.dataTransfer.items] : [];
    const files = [];
    if (items.length && items[0].webkitGetAsEntry) {
      for (const it of items) {
        const entry = it.webkitGetAsEntry && it.webkitGetAsEntry();
        if (entry) await walkEntry(entry, files);
      }
    } else if (e.dataTransfer.files) {
      files.push(...e.dataTransfer.files);
    }
    if (!files.length) return setFolderError("Couldn't read that drop. Try dragging the folder again, or click to pick.");
    processFiles(files);
  });

  // ---------- Submit ----------
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (submitBtn.disabled) return;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="material-symbols-outlined">progress_activity</span> Posting…';
    submitError.textContent = '';
    const fd = new FormData();
    fd.append('name', nameInput.value);
    fd.append('pet_json', petJsonFile, 'pet.json');
    fd.append('spritesheet', spritesheetFile, 'spritesheet.webp');
    try {
      const res = await fetch('/upload', { method: 'POST', body: fd });
      const data = await res.json();
      if (res.ok && data.ok) { window.location = data.redirect; return; }
      submitError.textContent = data.error || `Upload failed (${res.status}).`;
    } catch (err) {
      submitError.textContent = `Network error: ${err.message}`;
    }
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<span class="material-symbols-outlined">check</span> Post pet';
  });
})();
