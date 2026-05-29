/**
 * Универсальный обработчик фильтров.
 * Ожидает глобальную переменную filtersConfig до загрузки.
 * Примечание: Визуализация множественного выбора делегирована multiple_select.js
 */
(function() {
    if (typeof filtersConfig === 'undefined') {
        console.warn('Universal Filters: Переменная filtersConfig не найдена.');
        return;
    }

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
        
        filtersConfig.forEach(cfg => {
            let element = document.getElementById(cfg.id);
            if (!element) return;

            let value = '';

            if (cfg.type === 'multi_select') {
                const options = Array.from(element.selectedOptions)
                                     .map(opt => opt.value.trim())
                                     .filter(v => v !== '');
                value = options.join(',');
            } 
            else if (cfg.type === 'single_select' || cfg.type === 'text' || cfg.type === 'date') {
                value = element.value;
            }
            else if (cfg.type === 'button') {
                const hiddenInput = document.querySelector(`input[name="${cfg.searchFieldName}"]`);
                value = hiddenInput ? hiddenInput.value : (element.getAttribute('data-sort') || '');
            }

            if (value !== '') {
                data[cfg.searchFieldName] = value;
            }
        });

        return data;
    }

    // --- 2. СОХРАНЕНИЕ В КУКИ ---
    function saveAllFiltersToCookies() {
        const data = getAllFiltersData();
        filtersConfig.forEach(cfg => {
            const val = data[cfg.searchFieldName];
            if (val !== undefined && val !== '') {
                setCookie(cfg.cookieName, val);
            } else if (val === '') {
                setCookie(cfg.cookieName, '');
            }
        });
    }

    // --- 3. ВОССТАНОВЛЕНИЕ ИЗ КУКИ ---
    function restoreFilters() {
        filtersConfig.forEach(cfg => {
            const element = document.getElementById(cfg.id);
            if (!element) return;

            const savedValue = getCookie(cfg.cookieName);
            if (savedValue === null) return;

            if (cfg.type === 'multi_select') {
                const hasSelectedInDOM = Array.from(element.options).some(opt => opt.selected);
                
                if (hasSelectedInDOM) {
                    // Если выбор уже есть в DOM (из шаблона), ждем multiple_select.js
                } else {
                    if (savedValue !== '') {
                        const values = savedValue.split(',').map(v => v.trim()).filter(v => v !== '');
                        Array.from(element.options).forEach(opt => opt.selected = false);
                        
                        values.forEach(val => {
                            const opt = element.querySelector(`option[value="${CSS.escape(val)}"]`);
                            if (opt) opt.selected = true;
                        });
                        
                        // Принудительно обновляем визуал, так как multiple_select.js может еще не успеть отработать на загруженных данных
                        updateVisualsForReset(cfg.id, element);
                    }
                }
            } else if (cfg.type === 'single_select') {
                if (savedValue) element.value = savedValue;
            } else if (cfg.type === 'text' || cfg.type === 'date') {
                if (savedValue) element.value = savedValue;
            } else if (cfg.type === 'button') {
                const hiddenInput = document.querySelector(`input[name="${cfg.searchFieldName}"]`);
                if (hiddenInput && savedValue) hiddenInput.value = savedValue;
            }
        });
    }

    // --- 4. ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ОБНОВЛЕНИЯ ВИЗУАЛА (ТОЛЬКО ДЛЯ СБРОСА/ВОССТАНОВЛЕНИЯ) ---
    // Эта функция используется, когда мы меняем состояние программно (без клика пользователя)
    function updateVisualsForReset(wrapperId, hiddenSelect) {
        const wrapperIdBase = wrapperId.replace('-hidden', '');
        const wrapper = document.getElementById(wrapperIdBase);
        
        if (!wrapper) return;

        const labelSpan = wrapper.querySelector('.selected-label');
        const trigger = wrapper.querySelector('.dropdown-trigger');
        const filterName = trigger ? trigger.getAttribute('data-filter-name') || 'Фильтр' : 'Фильтр';
        
        const options = wrapper.querySelectorAll('.option-item');
        const selectedItems = Array.from(options).filter(item => item.classList.contains('is-selected'));
        const realOptionsCount = Array.from(options).filter(opt => opt.dataset.value !== '').length;
        const selectedRealCount = selectedItems.filter(opt => opt.dataset.value !== '').length;

        // Логика текста лейбла (синхронизирована с multiple_select.js)
        if (selectedRealCount === 0) {
            labelSpan.textContent = `${filterName}: Все`;
        } else if (selectedRealCount === realOptionsCount) {
            labelSpan.textContent = `${filterName}: Все`;
        } else if (selectedRealCount === 1) {
            const singleItem = selectedItems.find(opt => opt.dataset.value !== '');
            if (singleItem) {
                labelSpan.textContent = `${filterName}: ${singleItem.querySelector('span').textContent}`;
            }
        } else {
            labelSpan.textContent = `${filterName}: ${selectedRealCount} шт`;
        }
    }

    // --- 5. СИНХРОНИЗАЦИЯ СКРЫТЫХ ПОЛЕЙ SEARCH-FORM ---
    function syncSearchFormHiddenFields() {
        const searchForm = document.getElementById('search-form');
        if (!searchForm) return;

        const data = getAllFiltersData();

        filtersConfig.forEach(cfg => {
            if (cfg.searchFieldName === 'q') return;

            const hiddenInput = searchForm.querySelector(`input[name="${cfg.searchFieldName}"]`);
            if (hiddenInput && data[cfg.searchFieldName] !== undefined) {
                hiddenInput.value = data[cfg.searchFieldName];
            }
        });
    }

    // --- 6. НАСТРОЙКА СОБЫТИЙ ---
    function setupEventListeners() {
        // Слушаем изменения стандартных элементов (select, input)
        filtersConfig.forEach(cfg => {
            const element = document.getElementById(cfg.id);
            if (!element) return;

            const eventType = (cfg.type === 'text' || cfg.type === 'date') ? 'input' : 'change';

            element.addEventListener(eventType, () => {
                saveAllFiltersToCookies();
                syncSearchFormHiddenFields();
                // Для multi_select здесь ничего не делаем, так как визуал обновляется через click в multiple_select.js
                // Но если изменение произошло программно (например, при восстановлении), можно вызвать обновление
                if (cfg.type === 'multi_select') {
                     updateVisualsForReset(cfg.id, element);
                }
            });
        });

        // !!! УДАЛЕНЫ слушатели кликов по .option-item !!!
        // Теперь этим занимается исключительно multiple_select.js

        // Обработчик формы фильтрации (кнопка "Применить")
        const filterForm = document.getElementById('filter-form');
        if (filterForm) {
            filterForm.addEventListener('submit', function(e) {
                e.preventDefault(); 
                
                syncSearchFormHiddenFields();
                saveAllFiltersToCookies();

                const formData = new FormData(filterForm);
                const params = new URLSearchParams();
                
                for (let [key, value] of formData.entries()) {
                    const isMultiField = filtersConfig.some(c => c.searchFieldName === key && c.type === 'multi_select');
                    if (isMultiField) continue;
                    params.append(key, value);
                }

                // Ручной сбор мульти-полей
                filtersConfig.forEach(cfg => {
                    if (cfg.type === 'multi_select') {
                        const element = document.getElementById(cfg.id);
                        if (element) {
                            const options = Array.from(element.selectedOptions)
                                                 .map(opt => opt.value.trim())
                                                 .filter(v => v !== '');
                            
                            if (options.length > 0) {
                                params.append(cfg.searchFieldName, options.join(','));
                            }
                        }
                    }
                });

                const searchInput = document.getElementById('search-input');
                if (searchInput && searchInput.value) {
                    params.set('q', searchInput.value);
                }

                const currentUrl = new URL(window.location.href);
                currentUrl.search = params.toString();
                window.location.href = currentUrl.toString();
            });
        }

        // Обработчик для формы поиска
        const searchForm = document.getElementById('search-form');
        if (searchForm) {
            searchForm.addEventListener('submit', function(e) {
                syncSearchFormHiddenFields();
                saveAllFiltersToCookies();
            });
        }
        
        // Слушатель для кнопки сброса
        const resetBtn = document.getElementById('reset-filters');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                filtersConfig.forEach(cfg => {
                    setCookie(cfg.cookieName, '', -1);
                });
                
                const form = document.getElementById('filter-form');
                if (form) form.reset();

                const filterHiddenQ = document.getElementById('filter-hidden-q');
                if (filterHiddenQ) filterHiddenQ.value = '';

                // 4. СБРОС ВСЕХ СКРЫТЫХ ПОЛЕЙ В ФОРМЕ ПОИСКА (#search-form)
                // Находим все hidden inputs внутри формы поиска и обнуляем их
                const searchForm = document.getElementById('search-form');
                if (searchForm) {
                    const hiddenInputs = searchForm.querySelectorAll('input[type="hidden"]');
                    hiddenInputs.forEach(input => {
                        input.value = '';
                    });
                }

                // Сброс визуальной части множественного выбора
                filtersConfig.forEach(cfg => {
                    if (cfg.type === 'multi_select') {
                        const hiddenSelect = document.getElementById(cfg.id);
                        if (!hiddenSelect) return;

                        Array.from(hiddenSelect.options).forEach(opt => opt.selected = false);

                        const wrapperIdBase = cfg.id.replace('-hidden', '');
                        const wrapper = document.getElementById(wrapperIdBase);
                        
                        if (wrapper) {
                            const options = wrapper.querySelectorAll('.option-item');
                            options.forEach(opt => opt.classList.remove('is-selected'));
                            updateVisualsForReset(cfg.id, hiddenSelect);
                        }
                    }
                });

                const searchInput = document.getElementById('search-input');
                if (searchInput) searchInput.value = '';

                syncSearchFormHiddenFields();

                const currentUrl = new URL(window.location.href);
                currentUrl.search = ''; 
                window.history.replaceState({}, '', currentUrl.toString());
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    function init() {
        restoreFilters();
        syncSearchFormHiddenFields();
        setupEventListeners();
    }

})();