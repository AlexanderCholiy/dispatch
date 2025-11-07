document.addEventListener('DOMContentLoaded', function() {
  const searchForm = document.getElementById('search-form');
  const filterForm = document.getElementById('filter-form');
  const searchInput = document.getElementById('search-input');

  const poleInput = document.getElementById('pole-input');
  const baseStationInput = document.getElementById('base-station-input');
  const statusSelect = document.getElementById('status-select');
  const perPageSelect = document.getElementById('per-page');

  // Обновление скрытого поля q в фильтре при вводе в поиске
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

  // Универсальная функция для обновления скрытых полей в форме поиска
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

  // Привязка событий к фильтрам
  syncHiddenField(poleInput, 'pole');
  syncHiddenField(baseStationInput, 'base_station');
  syncHiddenField(statusSelect, 'status');
  syncHiddenField(perPageSelect, 'per_page');
});
