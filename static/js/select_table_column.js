document.addEventListener('DOMContentLoaded', function () {
    const trigger = document.querySelector('.column-select-trigger');
    const wrapper = trigger.closest('.column-select-wrapper');
    const dropdown = wrapper.querySelector('.column-select-dropdown');
    const checkboxes = dropdown.querySelectorAll('input[type="checkbox"]');
    const table = document.querySelector('.custom-table');

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
        if (visible === null) visible = 'true';
        cb.checked = visible === 'true';
        updateColumn(col, cb.checked, cb);
    });

    // Переключение столбцов
    checkboxes.forEach(cb => {
        cb.addEventListener('change', e => {
            const col = e.target.dataset.col;
            updateColumn(col, e.target.checked, e.target);
            setCookie(`col_${col}`, e.target.checked);
        });
    });

    function updateColumn(col, show, checkboxEl) {
        const index = Array.from(table.querySelectorAll('th')).findIndex(th => th.dataset.col === col);
        if (index === -1) return;
        table.querySelectorAll('tr').forEach(tr => {
            if (tr.children[index]) tr.children[index].style.display = show ? '' : 'none';
        });
        const icon = checkboxEl.parentNode.querySelector('i');
        icon.classList.toggle('bx-check', show);
        icon.classList.toggle('bx-x', !show);
    }

    // Показ/скрытие меню через класс
    trigger.addEventListener('click', e => {
        e.stopPropagation();
        wrapper.classList.toggle('open');
    });

    // Скрытие при клике вне
    document.addEventListener('click', e => {
        if (!wrapper.contains(e.target)) {
            wrapper.classList.remove('open');
        }
    });
});
