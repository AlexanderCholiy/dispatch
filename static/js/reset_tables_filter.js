// reset_tables_filter.js

document.addEventListener('DOMContentLoaded', () => {
  const resetButton = document.getElementById('reset-filters');
  const filterForm = document.getElementById('filter-form');
  const searchInput = document.getElementById('search-input');
  const perPageSelect = document.getElementById('per-page');
  const searchForm = document.getElementById('search-form'); // Для очистки скрытых полей в поиске

  if (!resetButton || !filterForm) return;

  resetButton.addEventListener('click', () => {
    // 1. Сохраняем per_page, чтобы не сбросить его при перезагрузке страницы (если нужно)
    const perPageValue = perPageSelect ? perPageSelect.value : null;

    // 2. Очистка стандартных инпутов внутри формы
    const inputs = filterForm.querySelectorAll('input:not([type="hidden"])');
    inputs.forEach(input => {
      if (['text', 'email', 'number', 'search', 'datetime-local'].includes(input.type)) {
        input.value = '';
      }
    });

    // 3. Функция удаления куки
    const deleteCookie = (name) => {
      document.cookie = name + "=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT";
    };

    // 4. Карта соответствия: ID элемента -> Имя куки
    // ВАЖНО: Убедитесь, что у ваших div.multiple-select-wrapper есть id, совпадающий с ключами здесь
    const elementToCookieMap = {
      // Инциденты
      'finish-select': 'finish',
      'was-read': 'was_read',
      'status-select': 'status',
      'category-select': 'category',
      'responsible-user-select': 'responsible_user',
      'sla-avr': 'sla_avr',
      'sla-rvr': 'sla_rvr',
      'sla-dgu': 'sla_dgu',
      'avr-contractor-select': 'avr_contractor',
      'region-responsible-manager-select': 'region_responsible_manager',
      'macroregion-select': 'macroregion',
      'operator-group-select': 'operator_group',
      'incident-type-select': 'incident_type',
      'pole-input': 'pole',
      'base-station-input': 'base_station',
      'incident-date-from': 'incident_date_from',
      'incident-date-to': 'incident_date_to',
      
      // Почта
      'folder-select': 'folder',
      'email-from-input': 'email_from',
      'email-date-from': 'email_date_from',
      'email-date-to': 'email_date_to',
      
      // Пользователи (Здесь должен быть ID вашего кастомного селекта)
      'role-select': 'role', 
      
      // Энергетика
      'type-select': 'type',
      'company-select': 'company',
      'declarant-select': 'declarant',
      
      // Уведомления
      'read-select': 'read',
      'level-select': 'level'
    };

    // Проходим по карте и сбрасываем элементы
    Object.keys(elementToCookieMap).forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        const cookieName = elementToCookieMap[id];

        // --- ЛОГИКА ДЛЯ КАСТОМНЫХ МНОГОКРАТНЫХ ВЫБОРОВ ---
        if (el.classList.contains('multiple-select-wrapper')) {
          const trigger = el.querySelector('.dropdown-trigger');
          const options = el.querySelectorAll('.option-item');
          const hiddenSelect = el.querySelector('select[multiple]');
          const menu = el.querySelector('.dropdown-menu');

          if (trigger && options.length > 0 && hiddenSelect) {
            // 1. Снимаем класс выбранности со всех опций
            options.forEach(opt => opt.classList.remove('is-selected'));
            
            // 2. Сбрасываем скрытый select
            Array.from(hiddenSelect.options).forEach(opt => opt.selected = false);
            
            // 3. Обновляем текст в кнопке
            const filterName = trigger.getAttribute('data-filter-name') || 'Фильтр';
            trigger.querySelector('.selected-label').textContent = `${filterName}: Все`;
            
            // 4. Закрываем меню, если открыто
            if (menu) {
              menu.classList.remove('open');
              trigger.classList.remove('active');
            }

            // 5. Очищаем соответствующее скрытое поле в search-form (если оно есть)
            if (searchForm) {
              const hiddenSearchField = searchForm.querySelector(`input[name="${cookieName}"]`);
              if (hiddenSearchField) hiddenSearchField.value = '';
            }
          }
        } 
        // --- ЛОГИКА ДЛЯ СТАНДАРТНЫХ SELECT ---
        else if (el.tagName === 'SELECT') {
          el.selectedIndex = 0;
        } 
        // --- ЛОГИКА ДЛЯ INPUT ---
        else {
          el.value = '';
        }

        // Удаляем куку
        deleteCookie(cookieName);
      }
    });

    // 5. Очистка остальных скрытых полей поиска (если они не попали в карту выше)
    const hiddenIds = [
      'search-hidden-role', 
      'search-hidden-per-page', 
      'filter-hidden-q',
      // Добавьте сюда остальные IDs скрытых полей, которые нужно сбрасывать
      'search-hidden-finish', 'search-hidden-status', 'search-hidden-category'
    ];
    
    hiddenIds.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });

    // 6. Восстановление служебных полей
    if (perPageSelect && perPageValue) perPageSelect.value = perPageValue;
    if (searchInput) searchInput.value = '';
    
    // Опционально: Отправка формы после сброса
    // filterForm.submit();
  });
});