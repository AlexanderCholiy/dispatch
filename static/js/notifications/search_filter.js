document.addEventListener('DOMContentLoaded', function() {
  const searchForm = document.getElementById('search-form');
  const filterForm = document.getElementById('filter-form');

  const searchInput = document.getElementById('search-input');
  
  const levelSelect = document.getElementById('level-select');
  const readSelect = document.getElementById('read-select');

  const perPageSelect = document.getElementById('per-page');

  const cookieNames = {
    read: 'read',
    level: 'level',
  };

  // ---- COOKIE HELPERS ----
  function setCookie(name, value, days = 30) {
    const d = new Date();
    d.setTime(d.getTime() + days * 24 * 60 * 60 * 1000);
    document.cookie = `${name}=${value};path=/;expires=${d.toUTCString()}`;
  }

  function getCookie(name) {
    const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : null;
  }

  // ---- ВОССТАНОВЛЕНИЕ ЗНАЧЕНИЙ ИЗ COOKIE ----
  function restoreValue(input, name) {
    if (!input || input.value) return;

    const value = getCookie(cookieNames[name]);
    if (value !== null && value !== undefined) {
      input.value = value;
    }
  }

  restoreValue(readSelect, 'read');
  restoreValue(levelSelect, 'level');

  // ---- СОХРАНЕНИЕ В COOKIE ----
  function saveOnChange(input, name) {
    if (!input) return;
    input.addEventListener('change', () => {
      setCookie(cookieNames[name], input.value);
    });
  }

  saveOnChange(readSelect, 'read');
  saveOnChange(levelSelect, 'level');

  // ----- СИНХРОНИЗАЦИЯ СКРЫТЫХ ПОЛЕЙ В searchForm -----
  function syncHiddenField(input, fieldName) {
    if (!input || !searchForm) return;

    const hidden = searchForm.querySelector(`input[name="${fieldName}"]`);
    if (!hidden) return;

    input.addEventListener('change', () => {
      hidden.value = input.value;
    });
  }

  syncHiddenField(readSelect, 'read');
  syncHiddenField(levelSelect, 'level');
  syncHiddenField(perPageSelect, 'per_page');

  // ----- СИНХРОНИЗАЦИЯ Q -----
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
