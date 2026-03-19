document.addEventListener('DOMContentLoaded', function() {
  const searchForm = document.getElementById('search-form');
  const filterForm = document.getElementById('filter-form');
  const searchInput = document.getElementById('search-input');
  const perPageSelect = document.getElementById('per-page');

  const cookieNames = {
    folder: 'folder',
    email_from: 'email_from',
    email_date_to: 'email_date_to',
    email_date_from: 'email_date_from',
    per_page: 'per_page'
  };

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

  // ---- 1. ВОССТАНОВЛЕНИЕ ЗНАЧЕНИЙ (Приоритет сервера) ----
  function restoreValue(input, name) {
    if (!input) return;
    
    // Восстанавливаем только если сервер прислал пустое поле
    if (input.value === "" || input.value === null) {
      const value = getCookie(cookieNames[name]);
      if (value !== null) {
        input.value = value;
        // Уведомляем систему о том, что значение появилось
        input.dispatchEvent(new Event('change'));
      }
    }
  }

  // ---- 2. СОХРАНЕНИЕ В COOKIE (С очисткой пустых) ----
  function saveOnChange(input, name) {
    if (!input) return;
    input.addEventListener('change', () => {
      if (input.value) {
        setCookie(cookieNames[name], input.value);
      } else {
        deleteCookie(cookieNames[name]);
      }
    });
  }

  // ---- 3. СИНХРОНИЗАЦИЯ СКРЫТЫХ ПОЛЕЙ (С вызовом при старте) ----
  function syncHiddenField(input, fieldName) {
    if (!input || !searchForm) return;

    const update = () => {
      let hidden = searchForm.querySelector(`input[name="${fieldName}"]`);
      if (hidden) {
        hidden.value = input.value;
      }
    };

    input.addEventListener('change', update);
    update(); // Выполняем сразу, чтобы скрытое поле знало о куки или значении сервера
  }

  // Список элементов
  const elements = [
    { el: document.getElementById('folder-select'), name: 'folder' },
    { el: document.getElementById('email-from-input'), name: 'email_from' },
    { el: document.getElementById('email-date-to'), name: 'email_date_to' },
    { el: document.getElementById('email-date-from'), name: 'email_date_from' },
    { el: perPageSelect, name: 'per_page' }
  ];

  elements.forEach(item => {
    if (item.el) {
      restoreValue(item.el, item.name);
      saveOnChange(item.el, item.name);
      syncHiddenField(item.el, item.name);
    }
  });

  // ----- СИНХРОНИЗАЦИЯ ПОИСКА (Q) -----
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