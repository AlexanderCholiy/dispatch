document.addEventListener('DOMContentLoaded', function() {
    const filtersConfig = [
        { id: 'role-select-hidden', cookieName: 'role', searchFieldName: 'role' },
        { id: 'per-page', cookieName: 'per_page_users', searchFieldName: 'per_page' },
        { id: 'sort-users-btn', cookieName: 'sort_users', searchFieldName: 'sort_users', isButton: true }
    ];

    // --- УТИЛИТЫ ДЛЯ КУКИ ---
    function setCookie(name, value, days = 30) {
        if (!name) return;
        const d = new Date();
        d.setTime(d.getTime() + days * 24 * 60 * 60 * 1000);
        document.cookie = `${name}=${value};path=/;expires=${d.toUTCString()}`;
    }

    function getCookie(name) {
        if (!name) return null;
        const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
        return match ? match[1] : null;
    }

    // --- 1. СОБРАТЬ ВСЕ ДАННЫЕ В ОБЪЕКТ ---
    function getAllFiltersData() {
        const data = {};
        
        // Роль
        const roleSelect = document.getElementById('role-select-hidden');
        if (roleSelect) {
            const roles = Array.from(roleSelect.selectedOptions)
                               .map(opt => opt.value.trim())
                               .filter(v => v !== '');
            data['role'] = roles.join(',');
        }

        // Per page
        const perPage = document.getElementById('per-page');
        if (perPage) data['per_page'] = perPage.value;

        // Sort
        const sortInput = document.querySelector('input[name="sort_users"]');
        if (sortInput) data['sort_users'] = sortInput.value;

        // Search query (ИСПРАВЛЕНО: Берем из ВИДИМОГО поля поиска, если оно есть, иначе из скрытого)
        const searchInput = document.getElementById('search-input');
        const hiddenQInput = document.getElementById('filter-hidden-q');
        
        if (searchInput && searchInput.value) {
            data['q'] = searchInput.value;
        } else if (hiddenQInput) {
            data['q'] = hiddenQInput.value;
        }

        return data;
    }

    // --- 2. СОХРАНЕНИЕ В КУКИ ---
    function saveAllFiltersToCookies() {
        const data = getAllFiltersData();
        
        if ('role' in data) {
            if (data.role === '') setCookie('role', ''); 
            else setCookie('role', data.role);
        }
        if (data.per_page) setCookie('per_page_users', data.per_page);
        if (data.sort_users) setCookie('sort_users', data.sort_users);
    }

    // --- 3. ВОССТАНОВЛЕНИЕ ИЗ КУКИ ---
    function restoreFilters() {
        const roleVal = getCookie('role');
        const perPageVal = getCookie('per_page_users');
        const sortVal = getCookie('sort_users');

        // Логика для роли
        const roleSelect = document.getElementById('role-select-hidden');
        if (roleSelect) {
            const hasSelectedInDOM = Array.from(roleSelect.options).some(opt => opt.selected);
            if (hasSelectedInDOM) {
                updateRoleVisuals(roleSelect);
            } else {
                if (roleVal !== null && roleVal !== '') {
                    const values = roleVal.split(',').map(v => v.trim()).filter(v => v !== '');
                    Array.from(roleSelect.options).forEach(opt => opt.selected = false);
                    values.forEach(val => {
                        const opt = roleSelect.querySelector(`option[value="${val}"]`);
                        if (opt) opt.selected = true;
                    });
                    updateRoleVisuals(roleSelect);
                } else {
                    Array.from(roleSelect.options).forEach(opt => opt.selected = false);
                    updateRoleVisuals(roleSelect);
                }
            }
        }

        // Логика для пер-страницы и сортировки
        const perPageEl = document.getElementById('per-page');
        if (perPageEl && perPageVal) perPageEl.value = perPageVal;

        const sortInput = document.querySelector('input[name="sort_users"]');
        if (sortInput && sortVal) sortInput.value = sortVal;
    }

    // --- 4. ОБНОВЛЕНИЕ ВИЗУАЛА РОЛИ ---
    function updateRoleVisuals(hiddenSelect) {
        const wrapper = document.querySelector('#role-select');
        if (!wrapper) return;
        const labelSpan = wrapper.querySelector('.selected-label');
        const options = wrapper.querySelectorAll('.option-item');
        
        Array.from(hiddenSelect.options).forEach(opt => {
            const visualOpt = wrapper.querySelector(`.option-item[data-value="${opt.value}"]`);
            if (visualOpt) {
                if (opt.selected) visualOpt.classList.add('is-selected');
                else visualOpt.classList.remove('is-selected');
            }
        });

        const selectedItems = Array.from(options).filter(item => item.classList.contains('is-selected'));
        const realOptionsCount = Array.from(options).filter(opt => opt.dataset.value !== '').length;
        const selectedRealCount = selectedItems.filter(opt => opt.dataset.value !== '').length;

        if (selectedRealCount === 0 || (selectedRealCount === 1 && selectedItems[0].dataset.value === '') || selectedRealCount === realOptionsCount) {
            labelSpan.textContent = "Роль: Все";
        } else if (selectedRealCount === 1) {
            const singleItem = selectedItems.find(opt => opt.dataset.value !== '');
            if (singleItem) labelSpan.textContent = "Роль: " + singleItem.querySelector('span').textContent;
        } else {
            labelSpan.textContent = `Роль: выбрано ${selectedRealCount}`;
        }
    }

    // --- 5. СИНХРОНИЗАЦИЯ СКРЫТЫХ ПОЛЕЙ SEARCH-FORM ---
    function syncSearchFormHiddenFields() {
        const searchForm = document.getElementById('search-form');
        if (!searchForm) return;
        const data = getAllFiltersData();

        if (data.role !== undefined) {
            const hiddenRole = searchForm.querySelector('input[name="role"]');
            if (hiddenRole) hiddenRole.value = data.role;
        }
        if (data.per_page) {
            const hiddenPer = searchForm.querySelector('input[name="per_page"]');
            if (hiddenPer) hiddenPer.value = data.per_page;
        }
        if (data.sort_users) {
            const hiddenSort = searchForm.querySelector('input[name="sort_users"]');
            if (hiddenSort) hiddenSort.value = data.sort_users;
        }
        
        // ИСПРАВЛЕНО: Синхронизация поля поиска
        if (data.q !== undefined) {
            const hiddenQ = searchForm.querySelector('input[name="q"]');
            if (hiddenQ) hiddenQ.value = data.q;
            
            // Также обновляем скрытое поле в форме фильтра, чтобы они были одинаковы
            const filterHiddenQ = document.getElementById('filter-hidden-q');
            if (filterHiddenQ) filterHiddenQ.value = data.q;
        }
    }

    // --- 6. НАСТРОЙКА РЕАЛЬНОГО СОХРАНЕНИЯ ПРИ ИЗМЕНЕНИИ ---
    function setupRealTimeSaving() {
        const perPageSelect = document.getElementById('per-page');
        if (perPageSelect) {
            perPageSelect.addEventListener('change', () => {
                saveAllFiltersToCookies();
                syncSearchFormHiddenFields();
            });
        }

        const roleWrapper = document.querySelector('#role-select');
        if (roleWrapper) {
            const options = roleWrapper.querySelectorAll('.option-item');
            options.forEach(opt => {
                opt.addEventListener('click', () => {
                    setTimeout(() => {
                        saveAllFiltersToCookies();
                        syncSearchFormHiddenFields();
                    }, 10);
                });
            });
        }

        // ИСПРАВЛЕНО: Слушаем ввод текста в поиске
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.addEventListener('input', () => {
                // Сразу копируем значение в скрытые поля
                syncSearchFormHiddenFields();
                // Сохраняем в куки (опционально, можно делать только при сабмите)
                saveAllFiltersToCookies();
            });
        }
    }

    // --- ЗАПУСК И ОБРАБОТЧИКИ ---
    
    restoreFilters();
    syncSearchFormHiddenFields();
    setupRealTimeSaving();

    const filterForm = document.getElementById('filter-form');
    const searchForm = document.getElementById('search-form');

    // Обработчик для формы фильтрации (кнопка "Применить")
    if (filterForm) {
        filterForm.addEventListener('submit', function(e) {
            e.preventDefault(); 
            
            syncSearchFormHiddenFields();
            saveAllFiltersToCookies();

            const formData = new FormData(filterForm);
            const params = new URLSearchParams();
            
            for (let [key, value] of formData.entries()) {
                if (key === 'role') continue; 
                params.append(key, value);
            }

            const roleSelect = document.getElementById('role-select-hidden');
            if (roleSelect) {
                const roles = Array.from(roleSelect.selectedOptions).map(o => o.value).filter(v => v);
                if (roles.length > 0) {
                    params.append('role', roles.join(','));
                }
            }

            // Добавляем поиск из видимого поля, если оно отличается от formData
            const searchInput = document.getElementById('search-input');
            if (searchInput && searchInput.value) {
                params.set('q', searchInput.value);
            }

            const currentUrl = new URL(window.location.href);
            currentUrl.search = params.toString();
            window.location.href = currentUrl.toString();
        });
    }

    // Обработчик для формы поиска (кнопка в шапке)
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            // Перед отправкой гарантируем, что все скрытые поля обновлены
            syncSearchFormHiddenFields();
            saveAllFiltersToCookies();
            // Стандартная отправка продолжится
        });
    }
});