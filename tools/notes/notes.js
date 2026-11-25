const collapsed = 'collapsed';
const expanded = 'expanded';

function setNoteState(card, button, state) {
  card.dataset.state = state;
  button.hidden = !state;
  button.setAttribute('aria-expanded', String(state === expanded));
  const action = state === expanded ? '收起' : '展开';
  button.setAttribute('aria-label', `${action}小记：${card.querySelector('time').dateTime}`);
}

function initCards() {
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
    observer.observe(card.querySelector('.note-content'), { box: 'border-box' });

    button.addEventListener('click', () => {
      const isExpanded = card.dataset.state === expanded;
      setNoteState(card, button, isExpanded ? collapsed : expanded);
      if (isExpanded && card.getBoundingClientRect().top < 0) card.scrollIntoView();
    });
    card.addEventListener('click', event => {
      if (card.dataset.state !== collapsed || event.defaultPrevented) return;
      if (event.target.closest('a, button') || !getSelection().isCollapsed) return;
      setNoteState(card, button, expanded);
    });
    preview.addEventListener('focusin', event => {
      if (card.dataset.state !== collapsed || !event.target.matches(':focus-visible')) return;
      if (event.target.getBoundingClientRect().bottom <= preview.getBoundingClientRect().bottom - 24) return;
      setNoteState(card, button, expanded);
    });
  }
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
  let selectedTick;

  function showSlot(slot) {
    const selected = Math.round(slot);
    ticks.forEach((tick, index) => {
      const distance = slot < 0 ? Infinity : Math.abs(index - slot);
      tick.style.setProperty('--tick-length', `${getTickLength(distance)}px`);
      tick.toggleAttribute('data-active', index === selected);
    });
    const tick = ticks[selected];
    if (tick === selectedTick) return;
    selectedTick = tick;
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

  list.addEventListener('pointermove', event => {
    if (event.pointerType === 'touch') return;
    const { top, height } = list.getBoundingClientRect();
    const slot = (event.clientY - top) * ticks.length / height - .5;
    showSlot(Math.min(ticks.length - 1, Math.max(0, slot)));
  });
  list.addEventListener('pointerleave', showKeyboardFocus);
  list.addEventListener('focusin', showKeyboardFocus);
  list.addEventListener('focusout', () => queueMicrotask(showKeyboardFocus));
}

initCards();
initScale();
