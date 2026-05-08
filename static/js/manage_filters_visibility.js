document.addEventListener('DOMContentLoaded', function () {
    const filterWrappers = document.querySelectorAll('.filter-select-wrapper');

    filterWrappers.forEach(wrapper => {
        const trigger = wrapper.querySelector('.filter-select-trigger');
        const dropdown = wrapper.querySelector('.filter-select-dropdown');
        const checkboxes = dropdown.querySelectorAll('input[type="checkbox"]');
        
        function getCookie(name) {
            const value = `; ${document.cookie}`;
            const parts = value.split(`; ${name}=`);
            if (parts.length === 2) return parts.pop().split(';').shift();
            return null;
        }

        function setCookie(name, value, days = 30) {
            const expires = new Date();
            expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000);
            document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/`;
        }

        checkboxes.forEach(cb => {
            const filterName = cb.dataset.filterName;
            if (!filterName) return;
            let visible = getCookie(`filter_visible_${filterName}`);
            if (visible === null) visible = 'true';
            cb.checked = visible === 'true';
            updateFilterVisibility(filterName, cb.checked, cb);
        });

        checkboxes.forEach(cb => {
            cb.addEventListener('change', e => {
                const filterName = e.target.dataset.filterName;
                if (!filterName) return;
                const isVisible = e.target.checked;
                updateFilterVisibility(filterName, isVisible, e.target);
                setCookie(`filter_visible_${filterName}`, isVisible);
            });
        });

        function updateFilterVisibility(filterName, show, checkboxEl) {
            const formElements = document.querySelectorAll(`[name="${filterName}"]`);
            
            formElements.forEach(el => {
                // 1. Ищем стандартную обертку для select
                let targetContainer = el.closest('.select-wrapper');
                
                // 2. Если не нашли, ищем нашу новую обертку для текстовых полей
                if (!targetContainer) {
                    targetContainer = el.closest('.filter-item-wrapper');
                }

                // 3. Если всё еще не нашли (защита), пытаемся найти ближайший div, но не главный контейнер
                if (!targetContainer) {
                    const parent = el.parentElement;
                    // Проверяем, что это не главная форма и не левая панель целиком
                    if (parent && !parent.classList.contains('left-part') && parent.id !== 'filter-form' && parent.id !== 'search-form') {
                        targetContainer = parent;
                    }
                }

                if (targetContainer) {
                    targetContainer.style.display = show ? '' : 'none';
                }
            });

            const icon = checkboxEl.parentNode.querySelector('i');
            if (icon) {
                icon.classList.toggle('bx-check', show);
                icon.classList.toggle('bx-x', !show);
            }
        }

        trigger.addEventListener('click', e => {
            e.stopPropagation();
            wrapper.classList.toggle('open');
        });

        document.addEventListener('click', e => {
            if (!wrapper.contains(e.target)) {
                wrapper.classList.remove('open');
            }
        });
    });
});