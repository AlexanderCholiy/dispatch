document.addEventListener('DOMContentLoaded', () => {
    const btn = document.querySelector('.toggle-status-history');
    const list = document.querySelector('.status-history');
    const key = 'status_history_' + window.location.pathname;

    const isVisible = localStorage.getItem(key) === 'true';

    list.classList.toggle('visible', isVisible);
    btn.textContent = isVisible
        ? 'Скрыть историю статусов'
        : 'Показать историю статусов';

    btn.addEventListener('click', () => {
        const nowVisible = list.classList.toggle('visible');
        localStorage.setItem(key, nowVisible);
        btn.textContent = nowVisible
            ? 'Скрыть историю статусов'
            : 'Показать историю статусов';
    });
});