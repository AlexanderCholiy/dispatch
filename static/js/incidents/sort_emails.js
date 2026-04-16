document.addEventListener('DOMContentLoaded', () => {
    const COOKIE_NAME = 'email_sort';
    
    // Функция чтения куки
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Функция установки куки
    function setCookie(name, value) {
        const expires = new Date();
        expires.setTime(expires.getTime() + (365 * 24 * 60 * 60 * 1000)); // 1 год
        document.cookie = `${name}=${encodeURIComponent(value)};expires=${expires.toUTCString()};path=/`;
    }

    // Получаем текущее значение: URL -> Cookie -> Дефолт
    const urlParams = new URLSearchParams(window.location.search);
    const savedSort = urlParams.get('email_sort') || getCookie(COOKIE_NAME) || 'asc';

    document.querySelectorAll('.sort-emails-btn').forEach(btn => {
        // Блокируем кнопку, если она соответствует текущему значению
        btn.disabled = btn.dataset.sort === savedSort;

        btn.addEventListener('click', () => {
            const sort = btn.dataset.sort;
            
            // 1. Сохраняем в Cookie (вместо localStorage)
            setCookie(COOKIE_NAME, sort);

            // 2. Обновляем URL
            const params = new URLSearchParams(window.location.search);
            params.set('email_sort', sort);
            window.location.search = params.toString();
        });
    });
});