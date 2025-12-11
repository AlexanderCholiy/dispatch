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
      const inputsToClear = filterForm.querySelectorAll(
        'input[type="text"], input[type="email"], input[type="number"], input[type="search"]'
      );

      inputsToClear.forEach(input => input.value = '');

      // --- Очищаем cookies ---
      function deleteCookie(name) {
        document.cookie = name + "=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT";
      }
      deleteCookie('role');

      deleteCookie('folder');
      deleteCookie('email_from');

      deleteCookie('finish');
      deleteCookie('status');
      deleteCookie('pole');
      deleteCookie('base_station');
      deleteCookie('category')

      // Сбрасываем фильтр завершен ли инцидент
      const finishSelect = document.getElementById('finish-select');
      if (finishSelect) finishSelect.selectedIndex = 0;

      // Сбрасываем статус
      const statusSelect = document.getElementById('status-select');
      if (statusSelect) statusSelect.selectedIndex = 0;

      // Сбрасываем категорию
      const categorySelect = document.getElementById('category-select');
      if (categorySelect) categorySelect.selectedIndex = 0;
      
      // Сбрасываем папку
      const folderSelect = document.getElementById('folder-select');
      if (folderSelect) folderSelect.selectedIndex = 0;

      // Сбрасываем роль
      const roleSelect = document.getElementById('role-select');
      if (roleSelect) roleSelect.selectedIndex = 0;

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
        'search-hidden-finish',
        'search-hidden-status',
        'search-hidden-category',
        'search-hidden-pole',
        'search-hidden-base-station',
        'search-hidden-folder',
        'search-hidden-role',
        'search-hidden-email-from'
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
