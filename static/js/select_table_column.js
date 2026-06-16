document.addEventListener('DOMContentLoaded', function () {
    const trigger = document.querySelector('.column-select-trigger');
    if (!trigger) return; // Если элемента нет, выходим

    const wrapper = trigger.closest('.column-select-wrapper');
    const dropdown = wrapper.querySelector('.column-select-dropdown');
    const checkboxes = dropdown.querySelectorAll('input[type="checkbox"]');
    const table = document.querySelector('.custom-table');

    if (!table || checkboxes.length === 0) return;

    // 1. Генерируем уникальный ключ для текущей страницы (без GET параметров)
    // Используем pathname (например, /planned_work/list/)
    const pageKey = window.location.pathname.replace(/\/$/, ''); // Убираем trailing slash если есть
    const storageKey = `col_settings_${pageKey}`;

    // Функция получения Cookie
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    // Функция установки Cookie
    function setCookie(name, value, days = 365) {
        const expires = new Date();
        expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000);
        // path=/ делает куку доступной на всем сайте, но имя уникально для страницы
        document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/`;
    }

    // 2. Загрузка сохраненного состояния
    let savedState = {};
    const storedData = getCookie(storageKey);
    
    if (storedData) {
        try {
            savedState = JSON.parse(storedData);
        } catch (e) {
            console.warn('Ошибка парсинга настроек колонок:', e);
        }
    }

    // Инициализация чекбоксов и таблицы
    checkboxes.forEach(cb => {
        const col = cb.dataset.col;
        // Если в сохраненных данных нет этого поля, по умолчанию показываем (true)
        const isVisible = savedState[col] !== undefined ? savedState[col] : true;
        
        cb.checked = isVisible;
        updateColumn(col, isVisible, cb);
    });

    // 3. Обработчик изменений
    checkboxes.forEach(cb => {
        cb.addEventListener('change', e => {
            const col = e.target.dataset.col;
            const isVisible = e.target.checked;
            
            // Обновляем таблицу
            updateColumn(col, isVisible, e.target);
            
            // Обновляем сохраненное состояние
            savedState[col] = isVisible;
            
            // Сохраняем в Cookie
            setCookie(storageKey, JSON.stringify(savedState));
        });
    });

    // Функция обновления видимости столбца
    function updateColumn(col, show, checkboxEl) {
        const headers = Array.from(table.querySelectorAll('th'));
        const index = headers.findIndex(th => th.dataset.col === col);
        
        if (index === -1) return;

        // Скрываем/показываем ячейки во всех строках
        table.querySelectorAll('tr').forEach(tr => {
            if (tr.children[index]) {
                tr.children[index].style.display = show ? '' : 'none';
            }
        });

        // Обновляем иконку в чекбоксе
        if (checkboxEl) {
            const icon = checkboxEl.parentNode.querySelector('i');
            if (icon) {
                icon.classList.toggle('bx-check', show);
                icon.classList.toggle('bx-x', !show);
            }
        }
    }

    // Логика открытия/закрытия меню
    trigger.addEventListener('click', e => {
        e.stopPropagation();
        wrapper.classList.toggle('open');
    });

    // Закрытие при клике вне меню
    document.addEventListener('click', e => {
        if (!wrapper.contains(e.target)) {
            wrapper.classList.remove('open');
        }
    });
});