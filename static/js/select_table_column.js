document.addEventListener('DOMContentLoaded', function () {
    const trigger = document.querySelector('.column-select-trigger');
    const dropdown = document.querySelector('.column-select-dropdown');
    const checkboxes = dropdown.querySelectorAll('input[type="checkbox"]');
    const table = document.querySelector('.custom-table');

    // Получение и установка cookie
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    function setCookie(name, value, days = 30) {
        const expires = new Date();
        expires.setTime(expires.getTime() + days*24*60*60*1000);
        document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/`;
    }

    // Инициализация состояния столбцов
    checkboxes.forEach(cb => {
        const col = cb.dataset.col;
        let visible = getCookie(`col_${col}`);
        if (visible === null) visible = 'true'; // по умолчанию видим
        cb.checked = visible === 'true';
        updateColumn(col, cb.checked, cb);
    });

    // Переключение столбцов
    checkboxes.forEach(cb => {
        cb.addEventListener('change', function(e) {
            const col = e.target.dataset.col;
            updateColumn(col, e.target.checked, e.target);
            setCookie(`col_${col}`, e.target.checked);
        });
    });

    function updateColumn(col, show, checkboxEl) {
        const index = Array.from(table.querySelectorAll('th')).findIndex(th => th.dataset.col === col);
        if (index === -1) return;
        table.querySelectorAll('tr').forEach(tr => {
            if (tr.children[index]) {
                tr.children[index].style.display = show ? '' : 'none';
            }
        });
        const icon = checkboxEl.parentNode.querySelector('i');
        if (show) {
            icon.classList.remove('bx-x');
            icon.classList.add('bx-check');
        } else {
            icon.classList.remove('bx-check');
            icon.classList.add('bx-x');
        }
    }

    // Показ/скрытие меню
    trigger.addEventListener('click', e => {
        e.stopPropagation();
        dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';
    });

    // Скрытие при клике вне
    document.addEventListener('click', e => {
        if (!dropdown.contains(e.target) && !trigger.contains(e.target)) {
            dropdown.style.display = 'none';
        }
    });
});
