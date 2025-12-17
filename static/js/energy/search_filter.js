document.addEventListener('DOMContentLoaded', function() {
  const searchForm = document.getElementById('search-form');
  const filterForm = document.getElementById('filter-form');

  const searchInput = document.getElementById('search-input');

  const typeSelect = document.getElementById('type-select');
  const companySelect = document.getElementById('company-select');
  const declarantSelect = document.getElementById('declarant-select');

  const perPageSelect = document.getElementById('per-page');

  const cookieNames = {
    type: 'type',
    company: 'company',
    declarant: 'declarant',
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

  restoreValue(typeSelect, 'type');
  restoreValue(companySelect, 'company');
  restoreValue(declarantSelect, 'declarant');

  // ---- СОХРАНЕНИЕ В COOKIE ----
  function saveOnChange(input, name) {
    if (!input) return;
    input.addEventListener('change', () => {
      setCookie(cookieNames[name], input.value);
    });
  }

  saveOnChange(typeSelect, 'type');
  saveOnChange(companySelect, 'company');
  saveOnChange(declarantSelect, 'declarant');

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

  syncHiddenField(typeSelect, 'type');
  syncHiddenField(companySelect, 'company');
  syncHiddenField(declarantSelect, 'declarant');
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
