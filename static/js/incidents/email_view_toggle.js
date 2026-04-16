document.addEventListener('DOMContentLoaded', () => {
    const COOKIE_NAME = 'emails_view_type';

    // Функция установки куки
    function setCookie(name, value) {
        const expires = new Date();
        expires.setTime(expires.getTime() + (365 * 24 * 60 * 60 * 1000));
        document.cookie = `${name}=${encodeURIComponent(value)};expires=${expires.toUTCString()};path=/`;
    }

    // Находим кнопку по ID
    const btn = document.getElementById('email-three-type');

    if (btn) {
        btn.addEventListener('click', () => {
            // 1. Берем целевое значение из кнопки
            const targetType = btn.dataset.viewType;

            // 2. Сохраняем в Cookie (для надежности и работы без URL)
            setCookie(COOKIE_NAME, targetType);

            // 3. Обновляем URL с новым параметром
            const url = new URL(window.location.href);
            url.searchParams.set('emails_view_type', targetType);
            
            // Переходим по новому URL
            window.location.href = url.toString();
        });
    }
});