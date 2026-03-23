document.addEventListener('DOMContentLoaded', function() {
  const searchForm = document.getElementById('search-form');
  const filterForm = document.getElementById('filter-form');
  const searchInput = document.getElementById('search-input');
  const perPageSelect = document.getElementById('per-page');

  // Карта соответствия: Ключ для функций -> Имя куки
  const cookieNames = {
    finish: 'finish',
    status: 'status',
    category: 'category',
    sla_avr: 'sla_avr',
    sla_rvr: 'sla_rvr',
    sla_dgu: 'sla_dgu',
    pole: 'pole',
    base_station: 'base_station',
    responsible_user: 'responsible_user',
    incident_date_to: 'incident_date_to',
    incident_date_from: 'incident_date_from',
    per_page: 'per_page'
  };

  // -------------------- HELPERS --------------------
  function getQuery() {
    return searchInput ? searchInput.value.trim() : '';
  }

  function isSearchByCode(query) {
    if (!query) return false;

    // Проверяем строгое соответствие: только префикс, дефис и цифры
    // ^(NT|AVRSERVICE) — только эти варианты в начале
    // -\d+$ — дефис и цифры до самого конца строки
    return /^(NT|AVRSERVICE)-\d+$/i.test(query.trim());
  }
  function isSearchMode() {
    return isSearchByCode(getQuery());
  }

  // ---- COOKIE HELPERS ----
  function setCookie(name, value, days = 30) {
    const d = new Date();
    d.setTime(d.getTime() + days * 24 * 60 * 60 * 1000);
    document.cookie = `${name}=${value};path=/;expires=${d.toUTCString()}`;
  }

  function deleteCookie(name) {
    document.cookie = name + "=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT";
  }

  function getCookie(name) {
    const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : null;
  }

  // ---- 1. ВОССТАНОВЛЕНИЕ ЗНАЧЕНИЙ ИЗ COOKIE (НО НЕ В РЕЖИМЕ ПОИСКА ПО КОДУ) ----
  function restoreValue(input, name) {
    if (!input) return;

    if (isSearchMode()) return;
    
    // Если сервер прислал пусто (value == ""), пробуем восстановить из куки
    if (input.value === "" || input.value === null) {
      const cookieValue = getCookie(cookieNames[name]);
      if (cookieValue) {
        input.value = cookieValue;
        // Генерируем событие change, чтобы отработала синхронизация со скрытыми полями
        input.dispatchEvent(new Event('change'));
      }
    }
  }

  // ---- 2. СОХРАНЕНИЕ В COOKIE ПРИ ИЗМЕНЕНИИ (НО НЕ В РЕЖИМЕ ПОИСКА ПО КОДУ) ----
  function saveOnChange(input, name) {
    if (!input) return;
  
    input.addEventListener('change', () => {
      if (isSearchMode()) {
        deleteCookie(cookieNames[name]); // не даём сохранять
        return;
      }

      if (input.value) {
        setCookie(cookieNames[name], input.value);
      } else {
        deleteCookie(cookieNames[name]);
      }
    });
  }

  // ---- 3. СИНХРОНИЗАЦИЯ СКРЫТЫХ ПОЛЕЙ В searchForm ----
  function syncHiddenField(input, fieldName) {
    if (!input || !searchForm) return;

    const updateHidden = () => {
      let hidden = searchForm.querySelector(`input[name="${fieldName}"]`);
      if (hidden) {
        hidden.value = input.value;
      }
    };

    input.addEventListener('change', updateHidden);
    updateHidden(); // Вызываем сразу при загрузке
  }

  // Список элементов для обработки
  const elements = [
    { el: document.getElementById('finish-select'), name: 'finish' },
    { el: document.getElementById('status-select'), name: 'status' },
    { el: document.getElementById('category-select'), name: 'category' },
    { el: document.getElementById('responsible-user-select'), name: 'responsible_user' },
    { el: document.getElementById('sla-avr'), name: 'sla_avr' },
    { el: document.getElementById('sla-rvr'), name: 'sla_rvr' },
    { el: document.getElementById('sla-dgu'), name: 'sla_dgu' },
    { el: document.getElementById('pole-input'), name: 'pole' },
    { el: document.getElementById('base-station-input'), name: 'base_station' },
    { el: document.getElementById('incident-date-from'), name: 'incident_date_from' },
    { el: document.getElementById('incident-date-to'), name: 'incident_date_to' },
    { el: perPageSelect, name: 'per_page' }
  ];

  // Запуск всех функций для каждого элемента
  elements.forEach(item => {
    if (item.el) {
      restoreValue(item.el, item.name);
      saveOnChange(item.el, item.name);
      syncHiddenField(item.el, item.name);
    }
  });

  // ----- СИНХРОНИЗАЦИЯ ПОИСКОВОЙ СТРОКИ (Q) -----
  if (searchInput && filterForm) {
    searchInput.addEventListener('input', () => {
      let hiddenQ = filterForm.querySelector('input[name="q"]');
      if (!hiddenQ) {
        hiddenQ = document.createElement('input');
        hiddenQ.type = 'hidden';
        hiddenQ.name = 'q';
        filterForm.appendChild(hiddenQ);
      }
      hiddenQ.value = searchInput.value;
    });
  }
});
