function updateScrollPadding(selector) {
  const el = document.querySelector(selector);
  if (!el) return;

  const hasScroll = el.scrollHeight > el.clientHeight;

  if (hasScroll) {
    el.classList.add('has-scroll');
  } else {
    el.classList.remove('has-scroll');
  }
}

function initScrollPadding(selector, toggleSelector = null) {
  // запуск сразу
  document.addEventListener('DOMContentLoaded', () => updateScrollPadding(selector));

  // запуск при клике на кнопку раскрытия
  if (toggleSelector) {
    document.querySelector(toggleSelector)
      ?.addEventListener('click', () => {
        setTimeout(() => updateScrollPadding(selector), 0);
      });
  }

  // запуск при ресайзе окна (частично ловит zoom)
  window.addEventListener('resize', () => updateScrollPadding(selector));

  // отслеживаем изменения размеров элемента (ловит zoom идеально)
  const el = document.querySelector(selector);
  if (el) {
    new ResizeObserver(() => updateScrollPadding(selector)).observe(el);
  }
}

/* ИНИЦИАЛИЗАЦИЯ ДЛЯ ДВУХ БЛОКОВ */

// История статусов
initScrollPadding('.status-history', '.toggle-status-history');

// История инцидентов
initScrollPadding('.incident-history', '.toggle-incident-history');
