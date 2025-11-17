document.addEventListener('DOMContentLoaded', () => {
  const resetButton = document.getElementById('reset-filters');
  const filterForm = document.getElementById('filter-form');
  const searchInput = document.getElementById('search-input');
  const perPageSelect = document.getElementById('per-page');

  if (resetButton && filterForm) {
    resetButton.addEventListener('click', () => {
      // Сохраняем текущее значение per_page
      const perPageValue = perPageSelect ? perPageSelect.value : null;

      // Очищаем текстовые поля фильтра
      const inputs = filterForm.querySelectorAll('input[type="text"]');
      inputs.forEach(input => input.value = '');

      // Сбрасываем статус
      const statusSelect = document.getElementById('status-select');
      if (statusSelect) statusSelect.selectedIndex = 0;

      // Сбрасываем папку
      const folderSelect = document.getElementById('folder-select');
      if (folderSelect) folderSelect.selectedIndex = 0;

      // Сбрасываем статус
      const categorySelect = document.getElementById('category-select');
      if (categorySelect) categorySelect.selectedIndex = 0;

      // Восстанавливаем per_page
      if (perPageSelect && perPageValue) {
        perPageSelect.value = perPageValue;
      }

      // Очищаем поле поиска (в шапке)
      if (searchInput) {
        searchInput.value = '';
      }

      // Очищаем скрытые инпуты в форме поиска
      const hiddenIds = [
        'search-hidden-pole',
        'search-hidden-base-station',
        'search-hidden-status',
        'search-hidden-role',
        'search-hidden-folder',
        'search-hidden-finish',
      ];

      const hiddenInputs = document.querySelectorAll(
        hiddenIds.map(id => `#${id}`).join(', ')
      );
      hiddenInputs.forEach(input => input.value = '');

      // Обновляем скрытое поле q, чтобы запрос был пустым
      const hiddenQ = document.getElementById('filter-hidden-q');
      if (hiddenQ) hiddenQ.value = '';

    });
  }
});
