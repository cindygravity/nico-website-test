/* Nicolas Schützinger — Galerie-Raster, Großansicht, Bilderreihe, Handy-Menü.
   Kein Framework. Die Rasterregeln sind am Wix-Original ausgemessen. */
(function () {
  'use strict';

  var MOBILE = 750;
  var isMobile = function () { return window.innerWidth <= MOBILE; };
  var unit = function () { return isMobile() ? window.innerWidth / 320 : 1; };

  function setUnit() {
    document.documentElement.style.setProperty('--uu', (Math.min(window.innerWidth, MOBILE) / 320).toFixed(4));
  }

  /* ---------- Raster ---------- */

  // Zeilen wie bei Wix: Bilder füllen eine Zeile, bis deren Höhe näher an `target` liegt als mit einem Bild weniger.
  // Gerechnet wird mit Bild + Abstand als Einheit, sonst stimmen die Umbrüche nicht mit dem Original überein.
  function layoutRows(ratios, W, gap, target) {
    var full = W + gap, rows = [], cur = [], sum = 0;
    var unitRatio = function (r) { return ((target - gap) * r + gap) / target; };
    var close = function (closed) { rows.push({ idx: cur, closed: closed }); cur = []; sum = 0; };
    ratios.forEach(function (r, i) {
      var g = unitRatio(r);
      if (cur.length) {
        var withNew = full / (sum + g) - target, without = full / sum - target;
        if (withNew < 0) {
          if (Math.abs(without) < Math.abs(withNew)) { close(true); cur.push(i); sum = g; return; }
          cur.push(i); close(true); return;
        }
      }
      cur.push(i); sum += g;
    });
    if (cur.length) close(false);

    var boxes = [], y = 0;
    rows.forEach(function (row) {
      var rsum = row.idx.reduce(function (a, i) { return a + ratios[i]; }, 0);
      var h = (full - row.idx.length * gap) / rsum;
      if (!row.closed && h > target) h = target - gap;  // unvollständige letzte Zeile wird nicht aufgeblasen
      var x = 0;
      row.idx.forEach(function (i) { var w = h * ratios[i]; boxes[i] = [x, y, w, h]; x += w + gap; });
      y += h + gap;
    });
    return { boxes: boxes, height: y - gap };
  }

  // Spalten: gleiche Breite, jedes Bild in die gerade kürzeste Spalte.
  function layoutColumns(ratios, W, gap, target) {
    var n = Math.max(1, Math.round((W + gap) / target));
    var cw = (W + gap) / n - gap, tops = [], boxes = [];
    for (var c = 0; c < n; c++) tops.push(0);
    ratios.forEach(function (r, i) {
      var col = 0;
      for (var k = 1; k < n; k++) if (tops[k] < tops[col] - 0.5) col = k;
      var h = cw / r;
      boxes[i] = [col * (cw + gap), tops[col], cw, h];
      tops[col] += h + gap;
    });
    return { boxes: boxes, height: Math.max.apply(null, tops) - gap };
  }

  function layoutGrid(count, W, gap, cols) {
    var cell = (W - gap * (cols - 1)) / cols, boxes = [];
    for (var i = 0; i < count; i++) boxes.push([(i % cols) * (cell + gap), Math.floor(i / cols) * (cell + gap), cell, cell]);
    return { boxes: boxes, height: Math.ceil(count / cols) * (cell + gap) - gap };
  }

  // Feste Collage (COMERCIAL): gemessene Kästen, mit der Breite skaliert. Zusätzliche Bilder hängen als Zeilen darunter.
  function layoutFixed(ratios, W, gap, conf) {
    var s = W / conf.base_width, boxes = [], bottom = 0;
    conf.boxes.forEach(function (b, i) {
      if (i >= ratios.length) return;
      boxes[i] = [b[0] * s, b[1] * s, b[2] * s, b[3] * s];
      bottom = Math.max(bottom, (b[1] + b[3]) * s);
    });
    if (ratios.length > conf.boxes.length) {
      var rest = layoutRows(ratios.slice(conf.boxes.length), W, gap, 360);
      rest.boxes.forEach(function (b, i) { boxes[conf.boxes.length + i] = [b[0], b[1] + bottom + gap, b[2], b[3]]; });
      bottom += gap + rest.height;
    }
    return { boxes: boxes, height: bottom };
  }

  function layoutGallery(el) {
    var mobile = isMobile(), u = unit();
    var conf = JSON.parse(el.getAttribute(mobile ? 'data-mobile' : 'data-desktop'));
    var type = el.getAttribute('data-type');
    var items = [].slice.call(el.querySelectorAll('.g-item'));
    var ratios = items.map(function (a) { return a.getAttribute('data-w') / a.getAttribute('data-h'); });
    var gap = conf.gap * u, side = conf.side * u;

    el.style.margin = (conf.top * u) + 'px ' + side + 'px ' + (conf.bottom * u) + 'px';
    var W = el.clientWidth, res;

    if (mobile) {
      var y = 0, boxes = [];
      ratios.forEach(function (r, i) { var h = type === 'grid' ? W : W / r; boxes[i] = [0, y, W, h]; y += h + gap; });
      res = { boxes: boxes, height: y - gap };
    } else if (type === 'rows') res = layoutRows(ratios, W, gap, conf.target);
    else if (type === 'columns') res = layoutColumns(ratios, W, gap, conf.target);
    else if (type === 'grid') res = layoutGrid(items.length, W, gap, conf.cols);
    else res = layoutFixed(ratios, W, gap, conf);

    items.forEach(function (a, i) {
      var b = res.boxes[i];
      a.style.left = b[0] + 'px'; a.style.top = b[1] + 'px'; a.style.width = b[2] + 'px'; a.style.height = b[3] + 'px';
      var img = a.querySelector('img');
      if (img) img.sizes = Math.ceil(b[2]) + 'px';
    });
    el.style.height = res.height + 'px';
  }

  /* ---------- Einblenden ---------- */

  function reveal(nodes) {
    if (!('IntersectionObserver' in window)) { nodes.forEach(function (n) { n.classList.add('in'); }); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        var n = e.target, img = n.querySelector('img');
        var show = function () { n.classList.add('in'); };
        if (img && !img.complete) { img.addEventListener('load', show); img.addEventListener('error', show); } else show();
        io.unobserve(n);
      });
    }, { rootMargin: '200px' });
    nodes.forEach(function (n) { io.observe(n); });
  }

  /* ---------- Großansicht ---------- */

  function Lightbox(getLinks) {
    var links = getLinks();
    var box = document.createElement('div');
    box.className = 'lb';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.innerHTML = '<div class="lb-stage"><img alt=""></div>' +
      '<div class="lb-info"><h1 class="lb-title"></h1><p class="lb-desc"></p></div>' +
      '<button class="lb-prev" aria-label="Vorheriges Bild"></button>' +
      '<button class="lb-next" aria-label="Nächstes Bild"></button>' +
      '<button class="lb-close" aria-label="Schließen"></button>';
    document.body.appendChild(box);
    var img = box.querySelector('img'), title = box.querySelector('.lb-title'), desc = box.querySelector('.lb-desc');
    var prev = box.querySelector('.lb-prev'), next = box.querySelector('.lb-next');
    var index = -1, lastFocus = null;

    function show(i, push) {
      links = getLinks();
      index = i;
      var a = links[i];
      img.removeAttribute('src');
      img.src = a.getAttribute('href');
      img.alt = a.getAttribute('data-title') || '';
      title.textContent = a.getAttribute('data-title') || '';
      desc.textContent = a.getAttribute('data-desc') || '';
      prev.hidden = i === 0;
      next.hidden = i === links.length - 1;
      var hash = '#' + a.getAttribute('data-id');
      if (push) history.pushState({ lb: true }, '', hash); else history.replaceState({ lb: true }, '', hash);
      if (links[i + 1]) new Image().src = links[i + 1].getAttribute('href');
      document.dispatchEvent(new CustomEvent('lb:show', { detail: { index: i, link: a } }));
    }
    function open(i, push) {
      lastFocus = document.activeElement;
      box.classList.add('open');
      document.body.classList.add('lb-on');
      show(i, push);
      box.querySelector('.lb-close').focus();
    }
    function hide() {
      box.classList.remove('open');
      document.body.classList.remove('lb-on');
      index = -1;
      document.dispatchEvent(new CustomEvent('lb:hide'));
      if (lastFocus && lastFocus.focus) lastFocus.focus();
    }
    function close() {
      if (index < 0) return;
      if (history.state && history.state.lb) history.back(); else { hide(); history.replaceState(null, '', location.pathname); }
    }
    function step(d) { var i = index + d; if (index >= 0 && i >= 0 && i < links.length) show(i, false); }

    links.forEach(function (a) {
      a.addEventListener('click', function (e) {
        if (e.metaKey || e.ctrlKey || e.shiftKey) return;
        e.preventDefault(); open(getLinks().indexOf(a), true);
      });
    });
    prev.addEventListener('click', function () { step(-1); });
    next.addEventListener('click', function () { step(1); });
    box.querySelector('.lb-close').addEventListener('click', close);
    document.addEventListener('keydown', function (e) {
      if (index < 0) return;
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) && e.key !== 'Escape') return;
      if (e.key === 'Escape') close();
      else if (e.key === 'ArrowRight') step(1);
      else if (e.key === 'ArrowLeft') step(-1);
    });
    window.addEventListener('popstate', function () {
      var i = fromHash();
      if (i >= 0) { if (index < 0) open(i, false); else show(i, false); } else if (index >= 0) hide();
    });
    var touchX = null;
    box.addEventListener('touchstart', function (e) { touchX = e.touches[0].clientX; }, { passive: true });
    box.addEventListener('touchend', function (e) {
      if (touchX === null) return;
      var dx = e.changedTouches[0].clientX - touchX; touchX = null;
      if (Math.abs(dx) > 50) step(dx < 0 ? 1 : -1);
    });

    function fromHash() {
      var id = decodeURIComponent(location.hash.slice(1));
      if (!id) return -1;
      links = getLinks();
      for (var i = 0; i < links.length; i++) if (links[i].getAttribute('data-id') === id) return i;
      return -1;
    }
    var start = fromHash();
    if (start >= 0) open(start, false);
  }

  /* ---------- Bilderreihe ---------- */

  function Slider(el) {
    var track = el.querySelector('.s-track'), items = [].slice.call(el.querySelectorAll('.s-item'));
    var prev = el.querySelector('.s-prev'), next = el.querySelector('.s-next'), pos = 0;
    function maxShift() { return Math.max(0, track.scrollWidth - el.clientWidth); }
    function go(i) {
      pos = Math.max(0, Math.min(items.length - 1, i));
      var shift = Math.min(items[pos].offsetLeft, maxShift());
      track.style.transform = 'translateX(' + (-shift) + 'px)';
      prev.hidden = shift <= 0;
      next.hidden = shift >= maxShift() - 1;
    }
    prev.addEventListener('click', function () { go(pos - 1); });
    next.addEventListener('click', function () { go(pos + 1); });
    window.addEventListener('resize', function () { go(pos); });
    window.addEventListener('load', function () { go(pos); });
    go(0);
  }

  /* ---------- Menü ---------- */

  function menu() {
    var toggle = document.querySelector('.menu-toggle'), root = document.documentElement;
    if (toggle) toggle.addEventListener('click', function () {
      var open = root.classList.toggle('menu-open');
      toggle.setAttribute('aria-expanded', open);
      toggle.setAttribute('aria-label', open ? 'Menü schließen' : 'Menü öffnen');
    });
    [].forEach.call(document.querySelectorAll('.sub-toggle'), function (b) {
      var li = b.parentNode;
      li.classList.add('expanded');
      b.setAttribute('aria-expanded', 'true');
      b.addEventListener('click', function () { b.setAttribute('aria-expanded', li.classList.toggle('expanded')); });
    });
  }

  /* ---------- Start ---------- */

  setUnit();
  var galleries = [].slice.call(document.querySelectorAll('.gallery'));
  var relayout = function () { setUnit(); galleries.forEach(layoutGallery); };
  relayout();
  window.addEventListener('resize', relayout);
  window.addEventListener('load', relayout);

  reveal([].slice.call(document.querySelectorAll('.g-item, .s-item')));
  [].forEach.call(document.querySelectorAll('.slider'), Slider);
  var zoomable = function () { return [].slice.call(document.querySelectorAll('.g-item[data-id], .s-item[data-id]')); };
  if (zoomable().length) Lightbox(zoomable);
  menu();
  window.NSGallery = { relayout: relayout };
})();
