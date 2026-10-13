/* Bearbeitungsmodus. Wird nur vom lokalen Server (admin/server.py) eingehängt, nie in die gebaute Seite. */
(function () {
  'use strict';

  var A = window.ADMIN;
  var el = function (tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };

  function api(path, body, headers) {
    var opt = { method: body === undefined ? 'GET' : 'POST', headers: Object.assign({ 'X-Admin-Token': A.token }, headers || {}) };
    if (body !== undefined) opt.body = (body instanceof Blob || typeof body === 'string') ? body : JSON.stringify(body);
    return fetch(path, opt).then(function (r) {
      return r.json().then(function (j) { if (!r.ok || j.error) throw new Error(j.error || 'Fehler ' + r.status); return j; });
    });
  }

  /* ---------- Leiste ---------- */

  var bar = el('div', 'ad-bar');
  var info = el('span', 'ad-info');
  var note = el('span', 'ad-note');
  var discard = el('button', 'ad-btn ad-quiet', 'Verwerfen');
  var publish = el('button', 'ad-btn ad-main', 'Veröffentlichen');
  bar.appendChild(el('span', 'ad-mark', 'Bearbeiten'));
  bar.appendChild(info); bar.appendChild(note); bar.appendChild(discard); bar.appendChild(publish);
  document.body.appendChild(bar);
  document.documentElement.classList.add('ad-on');

  function say(text, bad) { note.textContent = text || ''; note.classList.toggle('ad-bad', !!bad); }

  function refresh() {
    return api('/_admin/status').then(function (s) {
      var open = s.count > 0 || s.dirty;
      info.textContent = s.count ? s.count + (s.count === 1 ? ' Änderung' : ' Änderungen') + ' (' + s.text + ')'
        : s.dirty ? 'Änderungen offen' : s.pending_upload ? 'Gespeichert, noch nicht hochgeladen' : 'Alles veröffentlicht';
      discard.hidden = !open;
      publish.disabled = !open && !s.pending_upload;
      if (s.no_push) bar.classList.add('ad-test');
    }).catch(function (e) { say(e.message, true); });
  }

  // Zwei Klicks statt Rückfrage-Fenster: erster Klick fragt nach, zweiter führt aus.
  function twoStep(btn, askText, run) {
    var label = btn.textContent, timer = null;
    btn.addEventListener('click', function () {
      if (btn.classList.contains('ad-ask')) { clearTimeout(timer); btn.classList.remove('ad-ask'); btn.textContent = label; run(); return; }
      btn.classList.add('ad-ask'); btn.textContent = askText;
      timer = setTimeout(function () { btn.classList.remove('ad-ask'); btn.textContent = label; }, 4000);
    });
  }

  twoStep(discard, 'Wirklich alles verwerfen?', function () {
    say('Verwerfe …');
    api('/_admin/discard', {}).then(function () { location.reload(); }).catch(function (e) { say(e.message, true); });
  });

  publish.addEventListener('click', function () {
    publish.disabled = true; say('Veröffentliche …');
    api('/_admin/publish', {}).then(function (r) { say(r.message); return refresh(); })
      .catch(function (e) { say(e.message, true); publish.disabled = false; });
  });

  refresh();
  if (!A.editable) { info.textContent = ''; say('Auf dieser Seite gibt es nichts zu bearbeiten. Bilder pflegst du in den Galerien unter ART.'); return; }

  /* ---------- Galerie ---------- */

  var gallery = document.querySelector('.gallery');
  var relayout = function () { if (window.NSGallery) window.NSGallery.relayout(); };
  var byFile = {}, techniques = [];
  var fileOf = function (a) { return a.getAttribute('data-id') + '.jpg'; };
  var links = function () { return [].slice.call(gallery.querySelectorAll('.g-item')); };

  api('/_admin/items?page=' + A.page).then(function (r) {
    r.items.forEach(function (it) { byFile[it.file] = it; });
    techniques = r.techniques;
    // Großansicht war schon offen (Direktlink), bevor die Daten da waren: Felder jetzt nachreichen
    if (current && !form) document.dispatchEvent(new CustomEvent('lb:show', { detail: { link: current } }));
  });

  /* ---------- Hochladen ---------- */

  var drop = el('button', 'ad-drop', '+  Bilder hinzufügen');
  drop.appendChild(el('small', null, 'hierher ziehen oder klicken'));
  var picker = el('input'); picker.type = 'file'; picker.multiple = true; picker.accept = 'image/*'; picker.hidden = true;
  document.querySelector('.site-header').appendChild(drop);
  document.body.appendChild(picker);
  drop.addEventListener('click', function () { picker.click(); });
  picker.addEventListener('change', function () { upload([].slice.call(picker.files)); });

  var hasFiles = function (e) { return e.dataTransfer && [].indexOf.call(e.dataTransfer.types || [], 'Files') >= 0; };
  document.addEventListener('dragover', function (e) { if (hasFiles(e)) { e.preventDefault(); drop.classList.add('ad-over'); } });
  document.addEventListener('dragleave', function (e) { if (!e.relatedTarget) drop.classList.remove('ad-over'); });
  document.addEventListener('drop', function (e) {
    if (!hasFiles(e)) return;
    e.preventDefault(); drop.classList.remove('ad-over');
    upload([].slice.call(e.dataTransfer.files));
  });

  function upload(files) {
    files = files.filter(function (f) { return /^image\//.test(f.type) || /\.(jpe?g|png|heic|tiff?)$/i.test(f.name); });
    if (!files.length) return;
    var done = 0, failed = [];
    var next = function () {
      if (done + failed.length === files.length) {
        if (failed.length) { say(failed.length + ' Datei(en) nicht übernommen: ' + failed.join(', '), true); if (done) setTimeout(function () { location.reload(); }, 2500); } else location.reload();
        return;
      }
      var f = files[done + failed.length];
      say('Lade hoch ' + (done + failed.length + 1) + ' von ' + files.length + ' …');
      // Neue Bilder landen vorn; damit die Auswahl ihre Reihenfolge behält, von hinten nach vorn hochladen.
      api('/_admin/upload?page=' + A.page, f, { 'X-Filename': encodeURIComponent(f.name), 'Content-Type': 'application/octet-stream' })
        .then(function () { done++; next(); }).catch(function () { failed.push(f.name); next(); });
    };
    files.reverse();
    next();
  }

  /* ---------- Sortieren durch Ziehen ---------- */

  var dragging = null, orderBefore = '';
  links().forEach(function (a) {
    a.draggable = true;
    a.addEventListener('dragstart', function (e) {
      dragging = a; orderBefore = links().map(fileOf).join('|');
      e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', fileOf(a));
      setTimeout(function () { a.classList.add('ad-dragging'); }, 0);
    });
    a.addEventListener('dragover', function (e) {
      if (!dragging || dragging === a) return;
      e.preventDefault();
      var box = a.getBoundingClientRect(), after = e.clientX > box.left + box.width / 2;
      var ref = after ? a.nextSibling : a;
      if (ref !== dragging && dragging.nextSibling !== ref) { gallery.insertBefore(dragging, ref); relayout(); }
    });
    a.addEventListener('dragend', function () {
      a.classList.remove('ad-dragging'); dragging = null;
      var files = links().map(fileOf);
      if (files.join('|') === orderBefore) return;
      api('/_admin/order', { page: A.page, files: files }).then(refresh).catch(function (e) { say(e.message, true); });
    });
  });

  /* ---------- Felder in der Großansicht ---------- */

  var form = null, current = null;

  function field(label, name, value, wide) {
    var wrap = el('label', 'ad-field' + (wide ? ' ad-wide' : ''));
    wrap.appendChild(el('span', null, label));
    var input = el(wide === 'area' ? 'textarea' : 'input');
    input.name = name; input.value = value || '';
    if (wide === 'area') input.rows = 4; else input.type = 'text';
    wrap.appendChild(input);
    return wrap;
  }

  function buildForm(link) {
    var file = fileOf(link), it = byFile[file];
    var f = el('form', 'ad-form');
    f.appendChild(field('Titel', 'title', it.title, true));
    if (it.fields) {
      f.appendChild(field('Maße', 'size', it.fields.size));
      f.appendChild(field('Jahr', 'year', it.fields.year));
      var tech = field('Technik', 'technique', it.fields.technique, true);
      tech.querySelector('input').setAttribute('list', 'ad-tech');
      f.appendChild(tech);
      var list = el('datalist'); list.id = 'ad-tech';
      techniques.forEach(function (t) { var o = el('option'); o.value = t; list.appendChild(o); });
      f.appendChild(list);
      var priv = el('label', 'ad-check');
      var box = el('input'); box.type = 'checkbox'; box.name = 'private'; box.checked = it.fields.private;
      priv.appendChild(box); priv.appendChild(el('span', null, 'private collection'));
      f.appendChild(priv);
    } else {
      f.appendChild(field('Angaben (eine Zeile pro Angabe)', 'description', it.description, 'area'));
    }
    var state = el('span', 'ad-saved');
    var del = el('button', 'ad-btn ad-del', 'Bild löschen'); del.type = 'button';
    f.appendChild(state); f.appendChild(del);

    var saveTimer = null;
    var save = function () {
      var val = function (n) { return f.elements[n] ? f.elements[n].value : ''; };
      var body = { page: A.page, file: file, title: val('title') };
      if (it.fields) body.fields = { size: val('size'), technique: val('technique'), year: val('year'), private: f.elements['private'].checked };
      else body.description = val('description');
      state.textContent = 'Speichere …';
      api('/_admin/item', body).then(function (r) {
        Object.assign(it, r.item); if (!r.item.fields) it.fields = null;
        link.setAttribute('data-title', it.title); link.setAttribute('data-desc', it.description);
        var img = link.querySelector('img'); if (img) img.alt = it.title.replace(/\n/g, ' ');
        state.textContent = 'Gespeichert'; refresh();
      }).catch(function (e) { state.textContent = e.message; });
    };
    f.addEventListener('input', function () { clearTimeout(saveTimer); state.textContent = ''; saveTimer = setTimeout(save, 700); });
    f.addEventListener('submit', function (e) { e.preventDefault(); });
    twoStep(del, 'Wirklich löschen?', function () {
      clearTimeout(saveTimer);
      api('/_admin/delete', { page: A.page, file: file }).then(function () { location.hash = ''; location.reload(); })
        .catch(function (e) { state.textContent = e.message; });
    });
    return f;
  }

  document.addEventListener('lb:show', function (e) {
    var infoBox = document.querySelector('.lb-info'), link = e.detail.link;
    if (form) form.remove();
    current = link;
    if (!byFile[fileOf(link)]) return;
    form = buildForm(link);
    infoBox.appendChild(form);
    infoBox.classList.add('ad-editing');
  });
  document.addEventListener('lb:hide', function () { if (form) { form.remove(); form = null; } current = null; });
})();
