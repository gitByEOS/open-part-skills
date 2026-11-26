const collapsed = 'collapsed';
const expanded = 'expanded';

function setNoteState(card, button, state) {
  card.dataset.state = state;
  button.hidden = !state;
  button.setAttribute('aria-expanded', String(state === expanded));
  const action = state === expanded ? '收起' : '展开';
  button.setAttribute('aria-label', `${action}小记：${card.querySelector('time').dateTime}`);
}

function expandCard(card) {
  const button = card.querySelector('.note-toggle');
  if (card.dataset.state !== collapsed) return;
  setNoteState(card, button, expanded);
}

function focusOnly(card) {
  document.querySelectorAll('main > article').forEach(other => other.toggleAttribute('data-focused', other === card));
}

function initCards(focusCard) {
  const styles = getComputedStyle(document.documentElement);
  const heightLimit = parseFloat(styles.getPropertyValue('--note-height-limit'));
  const borders = 2 * parseFloat(styles.getPropertyValue('--note-border-width'));
  const observer = new ResizeObserver(entries => {
    for (const { target, borderBoxSize } of entries) {
      const card = target.closest('article');
      const button = card.querySelector('.note-toggle');
      const isOverflowing = borderBoxSize[0].blockSize + borders > heightLimit;
      setNoteState(card, button, isOverflowing ? card.dataset.state || collapsed : '');
    }
  });

  for (const card of document.querySelectorAll('article')) {
    const preview = card.querySelector('.note-preview');
    const button = card.querySelector('.note-toggle');
    card.tabIndex = -1;
    observer.observe(card.querySelector('.note-content'), { box: 'border-box' });

    button.addEventListener('click', () => {
      const isExpanded = card.dataset.state === expanded;
      setNoteState(card, button, isExpanded ? collapsed : expanded);
      if (!isExpanded) return;
      focusOnly(null);
      if (document.activeElement?.closest('article') === card) document.activeElement.blur();
      if (card.getBoundingClientRect().top < 0) card.scrollIntoView();
    });
    card.addEventListener('click', event => {
      if (event.defaultPrevented || event.target.closest('button') || !getSelection().isCollapsed) return;
      focusCard(card);
    });
    card.addEventListener('focusin', event => {
      if (event.target.closest('.note-toggle')) return;
      focusOnly(card);
      expandCard(card);
    });
    preview.addEventListener('focusin', event => {
      if (card.dataset.state !== collapsed || !event.target.matches(':focus-visible')) return;
      if (event.target.getBoundingClientRect().bottom <= preview.getBoundingClientRect().bottom - 24) return;
      setNoteState(card, button, expanded);
    });
  }

  document.addEventListener('click', event => {
    if (event.target.closest('article, .note-scale a')) return;
    focusOnly(null);
    if (document.activeElement?.closest('article')) document.activeElement.blur();
  });
  focusOnly(document.querySelector('main > article:target'));
  window.addEventListener('hashchange', () => {
    const target = document.querySelector('main > article:target');
    focusOnly(target);
    if (target) expandCard(target);
  });
}

const idleTickLength = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--tick-idle-length'));
const tickLengths = [36, 18, 13, idleTickLength];

function getTickLength(distance) {
  const offset = Math.min(distance, tickLengths.length - 1);
  const index = Math.floor(offset);
  const start = tickLengths[index];
  const end = tickLengths[Math.ceil(offset)];
  return start + (end - start) * (offset - index);
}

function initScale() {
  const scale = document.querySelector('.note-scale');
  const list = scale.querySelector('ol');
  const ticks = [...list.querySelectorAll('a')];
  const tooltip = scale.querySelector('.scale-tooltip');
  const date = tooltip.querySelector('.scale-date');
  const summary = tooltip.querySelector('.scale-summary');
  const visibilityObserver = new IntersectionObserver(entries => {
    for (const { target, isIntersecting } of entries) {
      target.toggleAttribute('data-in-view', isIntersecting);
    }
  });
  document.querySelectorAll('main > article').forEach(card => visibilityObserver.observe(card));
  let scaleIdle = false;

  function showSlot(slot) {
    const selected = Math.round(slot);
    ticks.forEach((tick, index) => {
      const distance = slot < 0 ? Infinity : Math.abs(index - slot);
      tick.style.setProperty('--tick-length', `${getTickLength(distance)}px`);
      tick.toggleAttribute('data-active', index === selected);
    });
    const tick = ticks[selected];
    tooltip.hidden = !tick;
    if (!tick) return;
    date.textContent = tick.getAttribute('aria-label');
    summary.textContent = tick.getAttribute('aria-description') ?? '';
    summary.hidden = !summary.textContent;
    tooltip.style.setProperty('--date-position', `${100 * (selected + .5) / ticks.length}%`);
  }

  function showKeyboardFocus() {
    showSlot(ticks.indexOf(list.querySelector('a:focus-visible')));
  }

  function focusCard(card) {
    if (scale.matches(':hover')) scaleIdle = true;
    showSlot(-1);
    if (document.activeElement !== card) {
      if (scale.contains(document.activeElement)) document.activeElement.blur();
      card.focus({ preventScroll: true });
    }
  }

  ticks.forEach(tick => tick.addEventListener('click', event => {
    event.preventDefault();
    const card = document.getElementById(tick.hash.slice(1));
    if (location.hash !== tick.hash) {
      history.pushState(null, '', tick.hash);
      focusOnly(card);
      expandCard(card);
      card.scrollIntoView();
    }
    focusCard(card);
  }));

  list.addEventListener('pointermove', event => {
    if (scaleIdle || event.pointerType === 'touch') return;
    const { top, height } = list.getBoundingClientRect();
    const slot = (event.clientY - top) * ticks.length / height - .5;
    showSlot(Math.min(ticks.length - 1, Math.max(0, slot)));
  });
  list.addEventListener('pointerleave', () => {
    scaleIdle = false;
    showKeyboardFocus();
  });
  list.addEventListener('focusin', showKeyboardFocus);
  list.addEventListener('focusout', () => queueMicrotask(showKeyboardFocus));
  return focusCard;
}

initCards(initScale());
