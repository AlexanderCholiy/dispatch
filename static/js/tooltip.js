// Функция для создания и показа тултипа
function createAndShowTooltip(targetEl) {
  const title = targetEl.getAttribute('data-title');
  if (!title) return null;

  // Проверяем, не создан ли уже тултип для этого элемента (чтобы не дублировать)
  let tooltip = document.querySelector(`.tooltip-text[data-target-id="${targetEl.dataset.id || 'default'}"]`);
  
  // Если тултип еще не создан или элемент новый, создаем его
  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.className = 'tooltip-text';
    tooltip.textContent = title;
    tooltip.style.display = 'none'; // Скрыт по умолчанию
    tooltip.style.position = 'absolute';
    tooltip.style.zIndex = '1000';
    
    // Добавляем уникальный ID для отслеживания (если нужно)
    if (!targetEl.dataset.id) {
      targetEl.dataset.id = Date.now() + Math.random().toString(36).substr(2, 9);
    }
    tooltip.setAttribute('data-target-id', targetEl.dataset.id);
    
    document.body.appendChild(tooltip);
  }

  let showTimeout = null;

  function showTooltip() {
    tooltip.style.display = 'block';
    tooltip.style.opacity = '0';
    tooltip.style.pointerEvents = 'none';
    tooltip.style.transition = 'none';
    tooltip.style.transform = 'translateX(-50%) translateY(0)';

    const elRect = targetEl.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();

    const spaceBelow = window.innerHeight - elRect.bottom;
    const spaceAbove = elRect.top;

    // Позиционирование по вертикали
    if (spaceBelow >= tooltipRect.height + 6) {
      tooltip.style.top = `${elRect.bottom + 6}px`;
    } else if (spaceAbove >= tooltipRect.height + 6) {
      tooltip.style.top = `${elRect.top - tooltipRect.height - 6}px`;
    } else {
      tooltip.style.top = `${elRect.bottom + 6}px`;
    }

    // Позиционирование по горизонтали с учётом края окна
    let left = elRect.left + elRect.width / 2;
    if (left + tooltipRect.width / 2 > window.innerWidth) {
      left = window.innerWidth - tooltipRect.width / 2 - 8;
    }
    if (left - tooltipRect.width / 2 < 0) {
      left = tooltipRect.width / 2 + 8;
    }

    tooltip.style.left = `${left}px`;
    tooltip.style.transform = `translateX(-50%) translateY(0)`;

    setTimeout(() => {
      tooltip.style.transition = 'opacity 0.2s ease-in-out, transform 0.2s ease-in-out';
      tooltip.style.opacity = '1';
      tooltip.style.pointerEvents = 'auto';
    }, 10);
  }

  function hideTooltip() {
    clearTimeout(showTimeout);
    showTimeout = null;
    tooltip.style.opacity = '0';
    tooltip.style.pointerEvents = 'none';
    setTimeout(() => {
      tooltip.style.display = 'none';
    }, 300);
  }

  // Вешаем события прямо на элемент (так как мы теперь управляем созданием)
  targetEl.addEventListener('mouseenter', () => {
    showTimeout = setTimeout(showTooltip, 1000);
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