const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const uiUtils = fs.readFileSync(path.join(__dirname, 'ui-utils.js'), 'utf8');
const cacheStamp = now => Math.floor(now / 1e8);

class Element {
  constructor(tagName, document) {
    this.tagName = tagName.toUpperCase();
    this.document = document;
    this.attributes = {};
    this.dataset = {};
    this.style = {};
    this.children = [];
    this.listeners = {};
    this.classList = {
      add: (...names) => this.updateClasses(names, true),
      remove: (...names) => this.updateClasses(names, false),
      contains: name => this.className.split(/\s+/).includes(name),
      toggle: (name, force) => {
        const enabled = force === undefined ? !this.classList.contains(name) : force;
        this.updateClasses([name], enabled);
        return enabled;
      },
    };
  }

  updateClasses(names, enabled) {
    const classes = new Set(this.className.split(/\s+/).filter(Boolean));
    names.forEach(name => enabled ? classes.add(name) : classes.delete(name));
    this.className = [...classes].join(' ');
  }

  get className() { return this.attributes.class || ''; }
  set className(value) { this.attributes.class = value; }
  get id() { return this.attributes.id || ''; }
  set id(value) { this.attributes.id = value; }
  get src() { return this.attributes.src || ''; }
  set src(value) { this.attributes.src = value; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) {
    if (name.startsWith('data-')) return this.dataset[name.slice(5)] ?? null;
    return this.attributes[name] ?? null;
  }
  hasAttribute(name) { return this.getAttribute(name) !== null; }
  removeAttribute(name) {
    if (name.startsWith('data-')) delete this.dataset[name.slice(5)];
    else delete this.attributes[name];
  }
  set innerHTML(value) {
    this.children = [];
    const iframe = value.match(/<iframe\b([^>]*)>/i);
    if (iframe) {
      const element = new Element('iframe', this.document);
      for (const match of iframe[1].matchAll(/\b(data-[\w-]+)(?:=["']([^"']*)["'])?/g)) {
        element.dataset[match[1].slice(5)] = match[2] ?? '';
      }
      this.appendChild(element);
    }
  }
  appendChild(child) { this.children.push(child); child.parentElement = this; return child; }
  addEventListener(type, listener) { (this.listeners[type] ||= []).push(listener); }
  removeEventListener() {}
  click() { (this.listeners.click || []).forEach(listener => listener.call(this, { preventDefault() {} })); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) {
    return this.children.flatMap(child => [child, ...child.querySelectorAll('*')])
      .filter(element => matches(element, selector));
  }
}

function matches(element, selector) {
  if (selector === '*') return true;
  const attribute = selector.match(/\[data-tab=["']([^"']+)["']\]/);
  if (attribute && element.dataset.tab !== attribute[1]) return false;
  const id = selector.match(/#([\w-]+)/);
  if (id && element.id !== id[1]) return false;
  const classes = [...selector.matchAll(/\.([\w-]+)/g)].map(match => match[1]);
  if (!classes.every(name => element.classList.contains(name))) return false;
  const tag = selector.match(/^[a-z][\w-]*/i);
  return !tag || element.tagName === tag[0].toUpperCase();
}

function createPage(hash) {
  const document = {};
  const root = document.documentElement = new Element('html', document);
  const body = document.body = root.appendChild(new Element('body', document));
  const add = (parent, tag, id, classes = '') => {
    const element = parent.appendChild(new Element(tag, document));
    element.id = id;
    element.className = classes;
    return element;
  };
  const navTag = html.match(/<a\b[^>]*data-tab=["']overview["'][^>]*>/i)?.[0];
  const panelTag = html.match(/<section\b[^>]*id=["']overview["'][^>]*>/i)?.[0];
  assert.ok(navTag && panelTag, '页面必须包含总览导航和面板');
  const classes = tag => tag.match(/\bclass=["']([^"']*)["']/i)?.[1] || '';
  const nav = add(body, 'nav', 'tool-nav');
  const overviewNav = add(nav, 'a', '', classes(navTag));
  overviewNav.dataset.tab = 'overview';
  const panels = add(body, 'main', 'panels');
  add(panels, 'section', 'overview', classes(panelTag));
  add(body, 'div', 'mechanism-list');
  add(body, 'span', 'tool-count');
  document.createElement = tag => new Element(tag, document);
  document.getElementById = id => root.querySelectorAll('*').find(element => element.id === id) || null;
  document.querySelectorAll = selector => root.querySelectorAll(selector);
  document.querySelector = selector => root.querySelector(selector);
  document.addEventListener = () => {};
  const timers = [];
  const clock = { now: 1700000000000 };
  class FrozenDate extends Date {
    static now() { return clock.now; }
  }
  const location = { hash, pathname: '/tools/index.html', origin: 'https://example.com' };
  const context = vm.createContext({
    document, location, URL,
    Date: FrozenDate,
    history: { replaceState() {} },
    setTimeout: callback => timers.push(callback),
    requestAnimationFrame: callback => callback(),
  });
  context.window = context;
  return { context, document, timers, clock };
}

const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)];
const headEnd = html.indexOf('</head>');
const externalIndex = scripts.findIndex(script => /\bsrc\s*=/.test(script[1]));

function runBeforeExternal(hash) {
  const page = createPage(hash);
  assert.ok(externalIndex >= 0, '页面必须包含外链脚本');
  const earlyScripts = scripts.slice(0, externalIndex);
  const headScripts = earlyScripts.filter(script => script.index < headEnd);
  assert.ok(headScripts.length, '必须在 head 执行首屏遮挡脚本');
  headScripts.forEach(script => vm.runInContext(script[2], page.context));
  page.initiallyBlocked = page.document.documentElement.classList.contains('initial-tab');
  const classList = page.document.documentElement.classList;
  const remove = classList.remove;
  classList.remove = (...names) => {
    if (names.includes('initial-tab') && classList.contains('initial-tab')) {
      const nav = page.document.querySelectorAll('.nav-link.active');
      const panels = page.document.querySelectorAll('.tab-content.active');
      page.beforeReveal = {
        nav: nav.map(element => element.dataset.tab),
        panels: panels.map(element => element.id),
        src: panels[0]?.querySelector('iframe')?.src || '',
      };
    }
    remove(...names);
  };
  earlyScripts.filter(script => script.index > headEnd)
    .forEach(script => vm.runInContext(script[2], page.context));
  return page;
}

for (const [hash, expected, blocked] of [
  ['#notes', 'notes', true],
  ['', 'overview', false],
  ['#overview', 'overview', false],
  ['#not-a-tool', 'overview', true],
  ['#pngya', 'pngya', true],
  ['#tool-count', 'overview', true],
]) {
  test(`首屏初始化 ${hash || '空 hash'}`, () => {
    const { context, document, timers, initiallyBlocked, beforeReveal, clock } = runBeforeExternal(hash);
    assert.equal(initiallyBlocked, blocked, 'head 阶段遮挡状态错误');
    if (blocked) {
      assert.deepEqual(beforeReveal?.nav, [expected], '解除遮挡前必须激活正确导航');
      assert.deepEqual(beforeReveal?.panels, [expected], '解除遮挡前必须激活正确面板');
      if (expected !== 'overview') assert.ok(beforeReveal.src, '解除遮挡前必须设置 iframe 地址');
    }
    assert.equal(document.documentElement.classList.contains('initial-tab'), false, '初始化后必须解除遮挡');
    const activeNav = document.querySelectorAll('.nav-link.active');
    const activePanels = document.querySelectorAll('.tab-content.active');
    assert.equal(activeNav.length, 1, '只能有一个激活导航');
    assert.equal(activeNav[0].dataset.tab, expected);
    assert.equal(activePanels.length, 1, '只能有一个激活面板');
    assert.equal(activePanels[0].id, expected);
    const frames = document.querySelectorAll('iframe');
    const loaded = frames.filter(frame => frame.hasAttribute('src'));
    if (expected === 'overview') {
      assert.equal(loaded.length, 0, '总览不应加载工具');
    } else {
      assert.equal(loaded.length, 1, '仅加载目标工具');
      assert.equal(loaded[0], activePanels[0].querySelector('iframe'));
      if (expected === 'notes') {
        assert.equal(loaded[0].src, `notes/dist/index.html?t=${cacheStamp(clock.now)}`);
        assert.equal(loaded[0].getAttribute('data-src'), 'notes/dist/index.html');
      } else {
        assert.equal(new URL(loaded[0].src, 'https://example.com/tools/index.html').href,
          new URL('pngya/index.html', 'https://example.com/tools/index.html').href);
        assert.equal(loaded[0].hasAttribute('data-src'), false);
      }
    }
    vm.runInContext(`${uiUtils}\nUIUtils.initTabs();`, context);
    assert.equal(timers.length, 0, '外链脚本不应安排延迟初始切换');
    assert.equal(document.querySelector('.tab-content.active').id, expected);
  });
}

test('笔记缓存戳按 1e8 毫秒分桶，其它工具只加载一次', () => {
  const page = runBeforeExternal('#notes');
  const { context, document, timers, clock } = page;
  const iframe = document.getElementById('notes').querySelector('iframe');
  const notesUrl = now => `https://example.com/tools/notes/dist/index.html?t=${cacheStamp(now)}`;
  assert.equal(iframe.src, `notes/dist/index.html?t=${cacheStamp(clock.now)}`);
  vm.runInContext(`${uiUtils}\nUIUtils.initTabs();`, context);

  document.querySelector('.nav-link[data-tab="notes"]').click();
  assert.equal(iframe.src, notesUrl(clock.now));
  assert.equal(iframe.getAttribute('data-src'), 'notes/dist/index.html');

  clock.now += 1;
  document.querySelector('.nav-link[data-tab="notes"]').click();
  assert.equal(iframe.src, notesUrl(clock.now));

  document.querySelector('.nav-link[data-tab="pngya"]').click();
  timers.splice(0).forEach(callback => callback());
  const pngya = document.getElementById('pngya').querySelector('iframe');
  const pngyaSrc = pngya.src;
  assert.ok(pngyaSrc);
  assert.equal(pngya.hasAttribute('data-src'), false);

  clock.now += 1e8;
  document.querySelector('.nav-link[data-tab="notes"]').click();
  timers.splice(0).forEach(callback => callback());
  assert.equal(iframe.src, notesUrl(clock.now));

  document.querySelector('.nav-link[data-tab="pngya"]').click();
  timers.splice(0).forEach(callback => callback());
  assert.equal(pngya.src, pngyaSrc);
});

test('首屏遮挡样式覆盖总览导航和面板', () => {
  const styles = [...html.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)].map(match => match[1]).join('\n');
  const rules = [...styles.matchAll(/([^{}]+)\{([^{}]+)\}/g)]
    .filter(match => match[1].includes('initial-tab') && /(?:display\s*:\s*none|visibility\s*:\s*hidden)/i.test(match[2]));
  assert.ok(rules.some(rule => /data-tab\s*=\s*["']?overview/.test(rule[1])), '遮挡规则必须隐藏总览导航');
  assert.ok(rules.some(rule => /(?:#overview|\.overview)/.test(rule[1])), '遮挡规则必须隐藏总览面板');
});
