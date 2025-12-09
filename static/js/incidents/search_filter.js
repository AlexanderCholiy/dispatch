document.addEventListener('DOMContentLoaded', function() {
  const searchForm = document.getElementById('search-form');
  const filterForm = document.getElementById('filter-form');

  const searchInput = document.getElementById('search-input');

  const finishSelect = document.getElementById('finish-select');
  const statusSelect = document.getElementById('status-select');
  const categorySelect = document.getElementById('category-select');
  const poleInput = document.getElementById('pole-input');
  const baseStationInput = document.getElementById('base-station-input');
  const perPageSelect = document.getElementById('per-page');

  const cookieNames = {
    finish: 'finish',
    status: 'status',
    category: 'category',
    pole: 'pole',
    base_station: 'base_station'
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
    if (!input) return;
    const value = getCookie(cookieNames[name]);
    if (value !== null && value !== undefined) {
      input.value = value;
    }
  }

  restoreValue(finishSelect, 'finish');
  restoreValue(statusSelect, 'status');
  restoreValue(categorySelect, 'category');
  restoreValue(poleInput, 'pole');
  restoreValue(baseStationInput, 'base_station');

  // ---- СОХРАНЕНИЕ В COOKIE ----
  function saveOnChange(input, name) {
    if (!input) return;
    input.addEventListener('change', () => {
      setCookie(cookieNames[name], input.value);
    });
  }

  saveOnChange(finishSelect, 'finish');
  saveOnChange(statusSelect, 'status');
  saveOnChange(categorySelect, 'category');
  saveOnChange(poleInput, 'pole');
  saveOnChange(baseStationInput, 'base_station');

  // ----- СИНХРОНИЗАЦИЯ СКРЫТЫХ ПОЛЕЙ В searchForm -----
  function syncHiddenField(input, fieldName) {
    if (!input || !searchForm) return;
    input.addEventListener('change', () => {
      let hidden = searchForm.querySelector(`input[name="${fieldName}"]`);
      if (!hidden) {
        hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = fieldName;
        searchForm.appendChild(hidden);
      }
      hidden.value = input.value;
    });
  }

  syncHiddenField(finishSelect, 'finish');
  syncHiddenField(statusSelect, 'status');
  syncHiddenField(categorySelect, 'category');
  syncHiddenField(poleInput, 'pole');
  syncHiddenField(baseStationInput, 'base_station');
  syncHiddenField(perPageSelect, 'per_page')

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
