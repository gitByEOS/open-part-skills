/* mindmap 视图交互：渲染树、搜索、层级展开、板块导航、明暗切换 */
(function () {
  'use strict';

  // 板块配色：暗色底上保证对比度
  var PALETTE = ['#5b9dff', '#ff7a45', '#2fbf8f', '#f5b83d', '#f2637e', '#7c6ff0',
    '#38bdf8', '#a3e635', '#f472b6', '#fb923c', '#34d399', '#e879f9'];
  var INITIAL_EXPAND = 99; // 默认全部展开

  var data = JSON.parse(document.getElementById('doc-data').textContent);
  var root = data.root;

  // HTML 转义 + 行内 code 渲染
  function inline(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/`([^`]+)`/g, '<code>$1</code>');
  }

  function build(node) {
    var el = document.createElement('div');
    el.className = 'node';
    // 圆点逐级缩小 2%
    el.style.setProperty('--dot', (6 * Math.pow(0.98, Math.max(node.depth - 1, 0))).toFixed(2) + 'px');
    var hasKids = node.children.length > 0;
    el.classList.toggle('has', hasKids);

    var row = document.createElement('div');
    row.className = 'row';
    var tw = document.createElement('span');
    tw.className = 'tw';
    tw.textContent = hasKids ? '▸' : '';
    row.appendChild(tw);
    var label = document.createElement('span');
    label.className = 'label';
    node.labelHTML = inline(node.text);
    label.innerHTML = node.labelHTML;
    row.appendChild(label);
    node.labelEl = label;
    if (hasKids) {
      var badge = document.createElement('span');
      badge.className = 'badge';
      badge.textContent = node.children.length;
      row.appendChild(badge);
    }
    el.appendChild(row);
    node.el = el;
    node.rowEl = row;

    if (hasKids) {
      var kids = document.createElement('div');
      kids.className = 'children';
      var inner = document.createElement('div');
      inner.className = 'children-inner';
      node.children.forEach(function (c) { inner.appendChild(build(c)); });
      kids.appendChild(inner);
      el.appendChild(kids);
      row.addEventListener('click', function () { el.classList.toggle('collapsed'); });
    }
    return el;
  }

  // 深度 < limit 的节点展开，其余收起
  function expandTo(node, limit) {
    if (node.el.classList.contains('has'))
      node.el.classList.toggle('collapsed', node.depth >= limit);
    node.children.forEach(function (c) { expandTo(c, limit); });
  }

  // 把 label 内命中子串包裹为 .mark，返回命中次数
  function wrapHits(labelEl, labelHTML, q) {
    labelEl.innerHTML = labelHTML; // 先恢复原始渲染
    if (!q) return 0;
    var walker = document.createTreeWalker(labelEl, NodeFilter.SHOW_TEXT);
    var texts = [];
    while (walker.nextNode()) texts.push(walker.currentNode);
    var hits = 0;
    texts.forEach(function (t) {
      var val = t.nodeValue, lower = val.toLowerCase();
      if (lower.indexOf(q) === -1) return;
      var frag = document.createDocumentFragment(), pos = 0, i;
      while ((i = lower.indexOf(q, pos)) !== -1) {
        frag.appendChild(document.createTextNode(val.slice(pos, i)));
        var span = document.createElement('span');
        span.className = 'mark';
        span.textContent = val.slice(i, i + q.length);
        frag.appendChild(span);
        hits++;
        pos = i + q.length;
      }
      frag.appendChild(document.createTextNode(val.slice(pos)));
      t.parentNode.replaceChild(frag, t);
    });
    return hits;
  }

  // 搜索：命中链保留可见并展开，只高亮命中子串
  var hitTotal = 0;
  function mark(node, q) {
    var hits = wrapHits(node.labelEl, node.labelHTML, q);
    hitTotal += hits;
    var childHit = node.children.map(function (c) { return mark(c, q); })
      .some(Boolean);
    var keep = !q || hits > 0 || childHit;
    node.el.hidden = !keep;
    if (q && childHit) node.el.classList.remove('collapsed');
    return keep;
  }

  function count(node) {
    return 1 + node.children.reduce(function (s, c) { return s + count(c); }, 0);
  }
  function maxDepth(node) {
    return node.children.length
      ? Math.max.apply(null, node.children.map(maxDepth)) : node.depth;
  }

  // ===== 渲染 =====
  document.title = data.title;
  // 标题入场：先逐字删除，再逐字打出，光标随动画结束隐藏
  (function typewriter() {
    var titleEl = document.getElementById('doc-title');
    titleEl.innerHTML = '<span id="title-text"></span><span class="caret"></span>';
    var textEl = document.getElementById('title-text');
    var chars = Array.from(data.title);
    var i = chars.length;
    textEl.textContent = data.title;
    function erase() {
      if (i > 0) {
        textEl.textContent = chars.slice(0, --i).join('');
        setTimeout(erase, 28);
      } else {
        setTimeout(type, 260);
      }
    }
    function type() {
      if (i < chars.length) {
        textEl.textContent = chars.slice(0, ++i).join('');
        setTimeout(type, 55);
      } else {
        titleEl.classList.add('done');
      }
    }
    setTimeout(erase, 350);
  })();
  document.getElementById('doc-intro').innerHTML =
    data.intro.map(inline).join('<br>');

  var treeRootEl = build(root);
  treeRootEl.classList.add('root');
  document.getElementById('tree').appendChild(treeRootEl);

  // 一级板块分配主题色 + 生成导航 chips
  var nav = document.getElementById('nav-chips');
  root.children.forEach(function (sec, i) {
    var color = PALETTE[i % PALETTE.length];
    sec.el.style.setProperty('--c', color);
    sec.el.classList.add('sec');
    var chip = document.createElement('button');
    chip.className = 'chip';
    chip.style.setProperty('--c', color);
    chip.textContent = sec.text.replace(/`([^`]+)`/g, '$1').slice(0, 24);
    chip.title = sec.text;
    chip.addEventListener('click', function () {
      sec.el.classList.remove('collapsed');
      sec.rowEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    nav.appendChild(chip);
  });

  expandTo(root, INITIAL_EXPAND);
  document.getElementById('stats').textContent =
    '节点 ' + count(root) + ' · 深度 ' + (maxDepth(root) + 1) + ' · 板块 ' + root.children.length;

  // ===== 工具栏 =====
  var seg = document.getElementById('level-seg');
  function syncSeg(limit) {
    Array.prototype.forEach.call(seg.querySelectorAll('button'), function (b) {
      b.classList.toggle('active', +b.dataset.limit === limit);
    });
  }
  syncSeg(INITIAL_EXPAND);
  seg.addEventListener('click', function (e) {
    var b = e.target.closest('button');
    if (!b) return;
    expandTo(root, +b.dataset.limit);
    syncSeg(+b.dataset.limit);
  });

  var searchEl = document.getElementById('search');
  var hitEl = document.getElementById('hit-count');
  searchEl.addEventListener('input', function (e) {
    var q = e.target.value.trim().toLowerCase();
    hitTotal = 0;
    mark(root, q);
    hitEl.textContent = q ? hitTotal + ' 处命中' : '';
    if (!q) { expandTo(root, INITIAL_EXPAND); syncSeg(INITIAL_EXPAND); }
  });

  // 明暗切换，记忆选择
  var htmlEl = document.documentElement;
  var saved = null;
  try { saved = localStorage.getItem('mindmap-theme'); } catch (e) {}
  if (saved) htmlEl.dataset.theme = saved;
  document.getElementById('theme-toggle').addEventListener('click', function () {
    htmlEl.dataset.theme = htmlEl.dataset.theme === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('mindmap-theme', htmlEl.dataset.theme); } catch (e) {}
  });

  // 快捷键：/ 聚焦搜索，Esc 清空
  document.addEventListener('keydown', function (e) {
    if (e.key === '/' && document.activeElement !== searchEl) {
      e.preventDefault();
      searchEl.focus();
    } else if (e.key === 'Escape' && document.activeElement === searchEl) {
      searchEl.value = '';
      searchEl.dispatchEvent(new Event('input'));
      searchEl.blur();
    }
  });
})();
