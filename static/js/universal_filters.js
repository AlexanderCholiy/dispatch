/**
 * Универсальный обработчик фильтров v2.3 (Общие куки + Очистка пустых)
 * Куки сохраняются без привязки к странице, но очищаются при удалении значения.
 */
(function() {
    if (typeof filtersConfig === 'undefined') {
        console.warn('Universal Filters: Переменная filtersConfig не найдена.');
        return;
    }

    // --- УТИЛИТЫ ДЛЯ КУКИ (БЕЗ ПРЕФИКСА СТРАНИЦЫ) ---
    
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

    /**
     * Удаляет куку по имени (используется при очистке полей)
     */
    function deleteCookie(name) {
        if (!name) return;
        document.cookie = `${name}=;path=/;expires=Thu, 01 Jan 1970 00:00:00 UTC`;
    }

    // --- 1. СОБРАТЬ ВСЕ ДАННЫЕ В ОБЪЕКТ ---
    function getAllFiltersData() {
        const data = {};
        
        filtersConfig.forEach(cfg => {
            let element = document.getElementById(cfg.id);
            if (!element) return;

            let value = '';
            const tagName = element.tagName.toLowerCase();
            const inputType = element.type ? element.type.toLowerCase() : '';

            if (cfg.type === 'multi_select' || (tagName === 'select' && element.multiple)) {
                const options = Array.from(element.selectedOptions)
                                     .map(opt => opt.value.trim())
                                     .filter(v => v !== '');
                value = options.join(',');
            } 
            else if (cfg.type === 'button') {
                const hiddenInput = document.querySelector(`input[name="${cfg.searchFieldName}"]`);
                value = hiddenInput ? hiddenInput.value : (element.getAttribute('data-sort') || '');
            }
            else if ((tagName === 'input' || tagName === 'textarea') && (inputType === 'checkbox' || inputType === 'radio')) {
                if (inputType === 'checkbox') {
                    value = element.checked ? 'true' : 'false';
                } else {
                    value = element.checked ? element.value : '';
                }
            }
            else {
                value = element.value;
            }

            if (value !== '') {
                data[cfg.searchFieldName] = value;
            }
        });

        return data;
    }

    // --- 2. СОХРАНЕНИЕ В КУКИ (ОЧИСТКА ПУСТЫХ) ---
    function saveAllFiltersToCookies() {
        const data = getAllFiltersData();
        filtersConfig.forEach(cfg => {
            const val = data[cfg.searchFieldName];
            
            if (val !== undefined && val !== '') {
                // Значение есть -> сохраняем
                setCookie(cfg.cookieName, val);
            } else {
                // Значения нет или оно пустое -> УДАЛЯЕМ куку!
                deleteCookie(cfg.cookieName);
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

            const tagName = element.tagName.toLowerCase();
            const inputType = element.type ? element.type.toLowerCase() : '';

            if (cfg.type === 'multi_select' || (tagName === 'select' && element.multiple)) {
                const hasSelectedInDOM = Array.from(element.options).some(opt => opt.selected);
                
                if (hasSelectedInDOM) {
                    // Ждем multiple_select.js
                } else {
                    if (savedValue !== '') {
                        const values = savedValue.split(',').map(v => v.trim()).filter(v => v !== '');
                        Array.from(element.options).forEach(opt => opt.selected = false);
                        
                        values.forEach(val => {
                            const opt = element.querySelector(`option[value="${CSS.escape(val)}"]`);
                            if (opt) opt.selected = true;
                        });
                        updateVisualsForReset(cfg.id, element);
                    }
                }
            } 
            else if (inputType === 'checkbox') {
                element.checked = (savedValue === 'true');
            }
            else if (inputType === 'radio') {
                const radios = document.querySelectorAll(`input[type="radio"][name="${cfg.searchFieldName}"]`);
                radios.forEach(radio => {
                    if (radio.value === savedValue) radio.checked = true;
                    else radio.checked = false;
                });
            }
            else {
                element.value = savedValue;
            }
        });
    }

    // --- 4. ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ОБНОВЛЕНИЯ ВИЗУАЛА ---
    function updateVisualsForReset(wrapperId, hiddenSelect) {
        const wrapperIdBase = wrapperId.replace('-hidden', '-wrapper');
        const wrapper = document.getElementById(wrapperIdBase);
        
        if (!wrapper) return;

        const labelSpan = wrapper.querySelector('.selected-label');
        const trigger = wrapper.querySelector('.dropdown-trigger');
        const filterName = trigger ? trigger.getAttribute('data-filter-name') || 'Фильтр' : 'Фильтр';
        
        const options = wrapper.querySelectorAll('.option-item');
        const selectedItems = Array.from(options).filter(item => item.classList.contains('is-selected'));
        const realOptionsCount = Array.from(options).filter(opt => opt.dataset.value !== '').length;
        const selectedRealCount = selectedItems.filter(opt => opt.dataset.value !== '').length;

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
            if (hiddenInput) {
                if (data[cfg.searchFieldName] !== undefined && data[cfg.searchFieldName] !== '') {
                    hiddenInput.value = data[cfg.searchFieldName];
                } else {
                    hiddenInput.value = '';
                }
            }
        });
    }

    // --- 6. НАСТРОЙКА СОБЫТИЙ ---
    function setupEventListeners() {
        filtersConfig.forEach(cfg => {
            const element = document.getElementById(cfg.id);
            if (!element) return;

            const tagName = element.tagName.toLowerCase();
            const inputType = element.type ? element.type.toLowerCase() : '';
            
            let eventType = 'change';
            if (tagName === 'input' && !['checkbox', 'radio'].includes(inputType)) {
                eventType = 'input';
            }

            element.addEventListener(eventType, () => {
                saveAllFiltersToCookies();
                syncSearchFormHiddenFields();
                
                if (cfg.type === 'multi_select' || (tagName === 'select' && element.multiple)) {
                     updateVisualsForReset(cfg.id, element);
                }
            });
        });

        // Слушатели кликов для кастомных множественных выборов
        const multiWrappers = document.querySelectorAll('.multiple-select-wrapper');
        multiWrappers.forEach(wrapper => {
            const options = wrapper.querySelectorAll('.option-item');
            options.forEach(opt => {
                opt.addEventListener('click', () => {
                    setTimeout(() => {
                        const wrapperId = wrapper.id;
                        const hiddenId = wrapperId + '-hidden';
                        const hiddenSelect = document.getElementById(hiddenId);
                        
                        if (hiddenSelect) {
                            const cfg = filtersConfig.find(c => c.id === hiddenId);
                            if (cfg) {
                                saveAllFiltersToCookies();
                                syncSearchFormHiddenFields();
                                updateVisualsForReset(hiddenId, hiddenSelect);
                            }
                        }
                    }, 10);
                });
            });
        });

        // Обработчик формы фильтрации
        const filterForm = document.getElementById('filter-form');
        if (filterForm) {
            filterForm.addEventListener('submit', function(e) {
                e.preventDefault(); 
                
                syncSearchFormHiddenFields();
                saveAllFiltersToCookies();

                const formData = new FormData(filterForm);
                const params = new URLSearchParams();
                
                for (let [key, value] of formData.entries()) {
                    const isMultiField = filtersConfig.some(c => c.searchFieldName === key && (c.type === 'multi_select' || (document.getElementById(c.id)?.multiple)));
                    if (isMultiField) continue;
                    params.append(key, value);
                }

                filtersConfig.forEach(cfg => {
                    const element = document.getElementById(cfg.id);
                    if (element && (cfg.type === 'multi_select' || element.multiple)) {
                        const options = Array.from(element.selectedOptions)
                                             .map(opt => opt.value.trim())
                                             .filter(v => v !== '');
                        
                        if (options.length > 0) {
                            params.append(cfg.searchFieldName, options.join(','));
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
                // 1. Очищаем куки
                filtersConfig.forEach(cfg => {
                    if (cfg.skipOnReset) return;
                    deleteCookie(cfg.cookieName);
                });
                
                // 2. Сбрасываем нативную форму
                const form = document.getElementById('filter-form');
                if (form) form.reset();

                // 3. ЯВНЫЙ СБРОС ПОЛЕЙ INPUT
                filtersConfig.forEach(cfg => {
                    if (cfg.skipOnReset) return;
                    const element = document.getElementById(cfg.id);
                    if (!element) return;
                    
                    const inputType = element.type ? element.type.toLowerCase() : '';
                    
                    if (inputType === 'checkbox') {
                        element.checked = false;
                    } else if (inputType === 'radio') {
                        element.checked = false;
                    } else {
                        element.value = '';
                    }
                });

                // 4. Очистка скрытого Q
                const filterHiddenQ = document.getElementById('filter-hidden-q');
                if (filterHiddenQ) filterHiddenQ.value = '';

                // 5. Сброс всех скрытых полей в search-form
                const searchForm = document.getElementById('search-form');
                if (searchForm) {
                    const hiddenInputs = searchForm.querySelectorAll('input[type="hidden"]');
                    hiddenInputs.forEach(input => {
                        const cfg = filtersConfig.find(c => c.searchFieldName === input.name);
                        if (cfg && cfg.skipOnReset) return;
                        input.value = '';
                    });
                }

                // 6. Сброс визуальной части множественного выбора
                filtersConfig.forEach(cfg => {
                    if (cfg.skipOnReset) return;
                    if (cfg.type === 'multi_select') {
                        const hiddenSelect = document.getElementById(cfg.id);
                        if (!hiddenSelect) return;

                        Array.from(hiddenSelect.options).forEach(opt => opt.selected = false);

                        const wrapperIdBase = cfg.id.replace(/-hidden$/, ''); 
                        const wrapper = document.getElementById(wrapperIdBase);
                        
                        if (wrapper) {
                            const options = wrapper.querySelectorAll('.option-item');
                            options.forEach(opt => opt.classList.remove('is-selected'));
                            
                            const labelSpan = wrapper.querySelector('.selected-label');
                            const trigger = wrapper.querySelector('.dropdown-trigger');
                            const filterName = trigger ? trigger.getAttribute('data-filter-name') || 'Фильтр' : 'Фильтр';
                            
                            labelSpan.textContent = `${filterName}: Все`;
                        }
                    }
                });

                // 7. Очистка видимого поиска
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