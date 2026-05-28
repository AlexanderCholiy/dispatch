document.addEventListener('DOMContentLoaded', function() {
    // --- КОНФИГУРАЦИЯ ФИЛЬТРОВ ---
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
        // Записываем значение как есть (без encodeURIComponent для запятых), чтобы Python мог легко сплитить
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
        
        // Роль (всегда возвращает строку, даже если пусто)
        const roleSelect = document.getElementById('role-select-hidden');
        if (roleSelect) {
            const roles = Array.from(roleSelect.selectedOptions)
                               .map(opt => opt.value.trim())
                               .filter(v => v !== '');
            // join([]) вернет "" (пустую строку), что критично для очистки куки
            data['role'] = roles.join(',');
        }

        // Per page
        const perPage = document.getElementById('per-page');
        if (perPage) data['per_page'] = perPage.value;

        // Sort
        const sortInput = document.querySelector('input[name="sort_users"]');
        if (sortInput) data['sort_users'] = sortInput.value;

        // Search query
        const qInput = document.getElementById('filter-hidden-q');
        if (qInput) data['q'] = qInput.value;

        return data;
    }

    // --- 2. СОХРАНЕНИЕ В КУКИ (С ОЧИСТКОЙ ПУСТОГО РОЛЕВОГО ФИЛЬТРА) ---
    function saveAllFiltersToCookies() {
        const data = getAllFiltersData();
        
        // Логика для роли: всегда записываем, даже если пусто
        if ('role' in data) {
            if (data.role === '') {
                // Если ролей нет, записываем пустую строку, чтобы перезаписать старую куку
                setCookie('role', ''); 
            } else {
                setCookie('role', data.role);
            }
        }

        if (data.per_page) setCookie('per_page_users', data.per_page);
        if (data.sort_users) setCookie('sort_users', data.sort_users);
    }

    // --- 3. ВОССТАНОВЛЕНИЕ ИЗ КУКИ ---
    function restoreFilters() {
        const roleVal = getCookie('role');
        const perPageVal = getCookie('per_page_users');
        const sortVal = getCookie('sort_users');

        // --- ЛОГИКА ДЛЯ РОЛИ ---
        const roleSelect = document.getElementById('role-select-hidden');
        
        if (roleSelect) {
            // 1. Проверяем, есть ли уже выбранные опции в HTML (от Django)
            const hasSelectedInDOM = Array.from(roleSelect.options).some(opt => opt.selected);

            if (hasSelectedInDOM) {
                // Если в HTML уже есть selected (Django отрисовал "Все" или конкретные роли),
                // мы НЕ трогаем их и просто обновляем визуальный лейбл.
                // Это решает проблему, когда кука пуста, но в HTML все выбрано.
                updateRoleVisuals(roleSelect);
            } else {
                // Если в HTML ничего не выбрано, пробуем восстановить из куки
                if (roleVal !== null && roleVal !== '') {
                    const values = roleVal.split(',').map(v => v.trim()).filter(v => v !== '');
                    
                    // Сбрасываем все selected (на всякий случай)
                    Array.from(roleSelect.options).forEach(opt => opt.selected = false);
                    
                    // Выбираем нужные из куки
                    values.forEach(val => {
                        const opt = roleSelect.querySelector(`option[value="${val}"]`);
                        if (opt) opt.selected = true;
                    });
                    
                    updateRoleVisuals(roleSelect);
                } else {
                    // Если ни в HTML, ни в куке ничего нет - явно сбрасываем визуально
                    Array.from(roleSelect.options).forEach(opt => opt.selected = false);
                    updateRoleVisuals(roleSelect);
                }
            }
        }

        // --- ЛОГИКА ДЛЯ PER_PAGE И SORT (без изменений) ---
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
        
        // Синхронизируем классы .is-selected со скрытым селектом
        Array.from(hiddenSelect.options).forEach(opt => {
            const visualOpt = wrapper.querySelector(`.option-item[data-value="${opt.value}"]`);
            if (visualOpt) {
                if (opt.selected) visualOpt.classList.add('is-selected');
                else visualOpt.classList.remove('is-selected');
            }
        });

        // Пересчитываем текст лейбла
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
        if (data.q) {
            const hiddenQ = searchForm.querySelector('input[name="q"]');
            if (hiddenQ) hiddenQ.value = data.q;
        }
    }

    // --- 6. НАСТРОЙКА РЕАЛЬНОГО СОХРАНЕНИЯ ПРИ ИЗМЕНЕНИИ (REAL-TIME) ---
    function setupRealTimeSaving() {
        // Для селекта пер-страницы
        const perPageSelect = document.getElementById('per-page');
        if (perPageSelect) {
            perPageSelect.addEventListener('change', () => {
                saveAllFiltersToCookies();
                syncSearchFormHiddenFields();
            });
        }

        // Для множественного выбора ролей
        const roleWrapper = document.querySelector('#role-select');
        if (roleWrapper) {
            const options = roleWrapper.querySelectorAll('.option-item');
            options.forEach(opt => {
                opt.addEventListener('click', () => {
                    // Небольшая задержка, чтобы скрытый select успел обновиться вашим основным скриптом
                    setTimeout(() => {
                        saveAllFiltersToCookies();
                        syncSearchFormHiddenFields();
                    }, 10);
                });
            });
        }
    }

    // --- ЗАПУСК И ОБРАБОТЧИКИ СОБЫТИЙ ---
    
    // 1. Восстановление состояния при загрузке
    restoreFilters();
    syncSearchFormHiddenFields();
    
    // 2. Настройка сохранения при кликах (Real-time)
    setupRealTimeSaving();

    const filterForm = document.getElementById('filter-form');
    const searchForm = document.getElementById('search-form');

    // Обработчик для формы фильтрации (кнопка "Применить")
    if (filterForm) {
        filterForm.addEventListener('submit', function(e) {
            e.preventDefault(); 
            
            // Обновляем скрытые поля и куки перед отправкой
            syncSearchFormHiddenFields();
            saveAllFiltersToCookies();

            // Формируем URL вручную, чтобы гарантировать правильность параметров
            const formData = new FormData(filterForm);
            const params = new URLSearchParams();
            
            // Добавляем все данные из формы, кроме role (его добавим вручную корректно)
            for (let [key, value] of formData.entries()) {
                if (key === 'role') continue; 
                params.append(key, value);
            }

            // Добавляем роль как CSV строку
            const roleSelect = document.getElementById('role-select-hidden');
            if (roleSelect) {
                const roles = Array.from(roleSelect.selectedOptions).map(o => o.value).filter(v => v);
                if (roles.length > 0) {
                    params.append('role', roles.join(','));
                }
                // Если roles пуст, мы не добавляем параметр role в URL (или можно добавить role=)
                // Обычно лучше не добавлять пустой параметр, но если нужно сбросить фильтр через URL:
                // if (roles.length === 0) params.append('role', ''); 
            }

            // Формируем итоговый URL
            const currentUrl = new URL(window.location.href);
            currentUrl.search = params.toString();
            
            // Перенаправляем пользователя
            window.location.href = currentUrl.toString();
        });
    }

    // Обработчик для формы поиска (кнопка в шапке)
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            // Перед отправкой поиска убедимся, что скрытые поля актуальны
            syncSearchFormHiddenFields();
            saveAllFiltersToCookies();
            // Стандартная отправка формы продолжится автоматически
        });
    }
});