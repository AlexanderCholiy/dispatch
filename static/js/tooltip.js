// Функция для создания и показа тултипа
function createAndShowTooltip(targetEl) {
  const title = targetEl.getAttribute('data-title');
  if (!title) return null;

  if (!targetEl.dataset.id) {
    targetEl.dataset.id = Date.now() + Math.random().toString(36).substr(2, 9);
  }

  let tooltip = document.querySelector(`.tooltip-text[data-target-id="${targetEl.dataset.id}"]`);

  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.className = 'tooltip-text';
    tooltip.style.position = 'fixed';
    tooltip.style.zIndex = '1000';
    tooltip.style.display = 'none';
    tooltip.style.opacity = '0';
    tooltip.style.pointerEvents = 'none';
    tooltip.style.transition = 'opacity 0.2s ease-in-out';
    tooltip.setAttribute('data-target-id', targetEl.dataset.id);
    document.body.appendChild(tooltip);
  }

  let showTimeout = null;

  function showTooltip() {
    const currentTitle = targetEl.getAttribute('data-title');
    if (!currentTitle) return;

    tooltip.textContent = currentTitle;

    // Сначала показываем невидимо, чтобы браузер отрисовал и мы могли измерить
    tooltip.style.display = 'block';
    tooltip.style.opacity = '0';
    tooltip.style.visibility = 'hidden';

    // Ждём следующий кадр, чтобы браузер гарантированно отрисовал
    requestAnimationFrame(() => {
      const elRect = targetEl.getBoundingClientRect();
      const tooltipRect = tooltip.getBoundingClientRect();

      const spaceBelow = window.innerHeight - elRect.bottom;
      const spaceAbove = elRect.top;

      // Позиционирование по вертикали
      if (spaceBelow >= tooltipRect.height + 8) {
        tooltip.style.top = `${elRect.bottom + 8}px`;
      } else if (spaceAbove >= tooltipRect.height + 8) {
        tooltip.style.top = `${elRect.top - tooltipRect.height - 8}px`;
      } else {
        // Не хватает места ни сверху, ни снизу — показываем ближе к краю
        tooltip.style.top = spaceBelow > spaceAbove
          ? `${elRect.bottom + 4}px`
          : `${Math.max(4, elRect.top - tooltipRect.height - 4)}px`;
      }

      // Позиционирование по горизонтали
      let left = elRect.left + elRect.width / 2;
      const halfWidth = tooltipRect.width / 2;

      if (left + halfWidth > window.innerWidth - 8) {
        left = window.innerWidth - halfWidth - 8;
      }
      if (left - halfWidth < 8) {
        left = halfWidth + 8;
      }

      tooltip.style.left = `${left}px`;
      tooltip.style.transform = 'translateX(-50%)';

      // Показываем
      tooltip.style.visibility = 'visible';
      tooltip.style.opacity = '1';
      tooltip.style.pointerEvents = 'auto';
    });
  }

  function hideTooltip() {
    clearTimeout(showTimeout);
    showTimeout = null;
    tooltip.style.opacity = '0';
    tooltip.style.pointerEvents = 'none';
    setTimeout(() => {
      if (tooltip.style.opacity === '0') {
        tooltip.style.display = 'none';
        tooltip.style.visibility = 'hidden';
      }
    }, 200);
  }

  targetEl.addEventListener('mouseenter', () => {
    showTimeout = setTimeout(showTooltip, 800);
  });

  targetEl.addEventListener('mouseleave', hideTooltip);

  return tooltip;
}

// Глобальный слушатель делегирования событий
document.addEventListener('DOMContentLoaded', () => {
  // Инициализируем существующие элементы
  document.querySelectorAll('.tooltip').forEach(el => {
    if (!el.hasAttribute('data-tooltip-initialized')) {
      createAndShowTooltip(el);
      el.setAttribute('data-tooltip-initialized', 'true');
    }
  });
});

// Делегирование для динамических элементов
document.addEventListener('mouseover', (e) => {
  const targetEl = e.target.closest('.tooltip');
  if (targetEl && !targetEl.hasAttribute('data-tooltip-initialized')) {
    createAndShowTooltip(targetEl);
    targetEl.setAttribute('data-tooltip-initialized', 'true');
  }
});

document.addEventListener('mouseout', (e) => {
  const targetEl = e.target.closest('.tooltip');
  if (targetEl && targetEl.hasAttribute('data-tooltip-initialized')) {
    // Находим тултип, связанный с этим элементом
    const tooltipId = targetEl.dataset.id;
    if (tooltipId) {
      const tooltip = document.querySelector(`.tooltip-text[data-target-id="${tooltipId}"]`);
      if (tooltip) {
        // Очищаем таймеры, если они есть (через замыкание сложно, поэтому просто скрываем)
        // Для полной чистоты лучше хранить ссылку на таймер, но здесь упростим:
        tooltip.style.opacity = '0';
        tooltip.style.pointerEvents = 'none';
        setTimeout(() => {
          tooltip.style.display = 'none';
        }, 300);
      }
    }
  }
});