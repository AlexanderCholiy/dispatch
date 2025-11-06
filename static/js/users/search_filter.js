document.addEventListener('DOMContentLoaded', function() {
  const searchForm = document.getElementById('search-form');
  const filterForm = document.getElementById('filter-form');
  const searchInput = document.getElementById('search-input');
  const roleSelect = document.getElementById('role-select');

  // Если пользователь меняет поиск — обновляем скрытое поле в форме фильтра
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

  // Если пользователь меняет роль — обновляем скрытое поле в форме поиска
  if (roleSelect && searchForm) {
    roleSelect.addEventListener('change', () => {
      let hiddenRole = searchForm.querySelector('input[name="role"]');
      if (!hiddenRole) {
        hiddenRole = document.createElement('input');
        hiddenRole.type = 'hidden';
        hiddenRole.name = 'role';
        searchForm.appendChild(hiddenRole);
      }
      hiddenRole.value = roleSelect.value;
    });
  }
});