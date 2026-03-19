document.addEventListener('DOMContentLoaded', () => {
  const resetButton = document.getElementById('reset-filters');
  const filterForm = document.getElementById('filter-form');
  const searchInput = document.getElementById('search-input');
  const perPageSelect = document.getElementById('per-page');

  if (resetButton && filterForm) {
    resetButton.addEventListener('click', () => {
      // 1. Сохраняем per_page
      const perPageValue = perPageSelect ? perPageSelect.value : null;

      // 2. Очищаем только видимые инпуты внутри формы (текст, даты и т.д.)
      const inputs = filterForm.querySelectorAll('input:not([type="hidden"])');
      inputs.forEach(input => {
        if (['text', 'email', 'number', 'search', 'datetime-local'].includes(input.type)) {
          input.value = '';
        }
      });

      // 3. Функция для удаления куки
      const deleteCookie = (name) => {
        document.cookie = name + "=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT";
      };

      // 4. Карта соответствия: ID элемента на странице -> Имя куки
      // Если элемент с таким ID есть на странице, то и его кука будет удалена
      const elementToCookieMap = {
        // Инциденты
        'finish-select': 'finish',
        'status-select': 'status',
        'category-select': 'category',
        'responsible-user-select': 'responsible_user',
        'sla-avr': 'sla_avr',
        'sla-rvr': 'sla_rvr',
        'sla-dgu': 'sla_dgu',
        'pole-input': 'pole',
        'base-station-input': 'base_station',
        'incident-date-from': 'incident_date_from',
        'incident-date-to': 'incident_date_to',
        
        // Почта (Emails)
        'folder-select': 'folder',
        'email-from-input': 'email_from',
        'email-date-from': 'email_date_from',
        'email-date-to': 'email_date_to',
        
        // Пользователи
        'role-select': 'role',
        
        // Энергетика
        'type-select': 'type',
        'company-select': 'company',
        'declarant-select': 'declarant',
        
        // Уведомления
        'read-select': 'read',
        'level-select': 'level'
      };

      // Проходим по карте: сбрасываем элемент и удаляем куку ТОЛЬКО если элемент существует
      Object.keys(elementToCookieMap).forEach(id => {
        const el = document.getElementById(id);
        if (el) {
          // Сбрасываем значение в интерфейсе
          if (el.tagName === 'SELECT') {
            el.selectedIndex = 0;
          } else {
            el.value = '';
          }
          // Удаляем связанную куку
          deleteCookie(elementToCookieMap[id]);
        }
      });

      // 5. Очищаем скрытые поля поиска (только если они есть)
      const hiddenIds = [
        // Инциденты
        'search-hidden-finish',
        'search-hidden-type',
        'search-hidden-status',
        'search-hidden-category',
        'search-hidden-responsible-user',
        'search-hidden-sla-avr',
        'search-hidden-sla-rvr',
        'search-hidden-sla-dgu',
        'search-hidden-pole',
        'search-hidden-base-station',
        'search-hidden-incident-date-from',
        'search-hidden-incident-date-to',
        // Почта (Emails)
        'search-hidden-folder',
        'search-hidden-email-from', 
        'search-hidden-email-date-from',
        'search-hidden-email-date-to',
        // Пользователи
        'search-hidden-role',
        // Энергетика
        'search-hidden-company',
        'search-hidden-declarant',
        // Уведомления
        'search-hidden-read',
        'search-hidden-level',
        // Общее
        'search-hidden-per-page',
        'filter-hidden-q'
      ];
      hiddenIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
      });

      // 6. Восстанавливаем служебные поля
      if (perPageSelect && perPageValue) perPageSelect.value = perPageValue;
      if (searchInput) searchInput.value = '';
      
      // Можно раскомментировать для авто-отправки формы после сброса:
      // filterForm.submit();
    });
  }
});
