document.addEventListener('DOMContentLoaded', () => {
    const COOKIE_NAME = 'emails_view_type';
    
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
        expires.setTime(expires.getTime() + (365 * 24 * 60 * 60 * 1000));
        document.cookie = `${name}=${encodeURIComponent(value)};expires=${expires.toUTCString()};path=/`;
    }

    // Получаем текущее значение (для отладки или визуального стиля, если нужно)
    const urlParams = new URLSearchParams(window.location.search);
    let currentType = urlParams.get('emails_view_type') || getCookie(COOKIE_NAME) || 'basic';

    // Находим все кнопки переключения
    const toggleButtons = document.querySelectorAll('.email-three-btn');

    toggleButtons.forEach(btn => {
        const targetType = btn.dataset.viewType; // Цель перехода (например, "simple")

        // Убираем лишнюю логику блокировки. 
        // Эта кнопка всегда предназначена для перехода в targetType.
        // Если targetType совпадает с currentType, значит пользователь уже там, 
        // но в вашей логике HTML такая кнопка просто не должна рендериться.

        btn.addEventListener('click', (e) => {
            e.preventDefault(); // На всякий случай
            
            // 1. Сохраняем новое значение в Cookie
            setCookie(COOKIE_NAME, targetType);

            // 2. Обновляем URL
            const params = new URLSearchParams(window.location.search);
            params.set('emails_view_type', targetType);
            
            // Перенаправляем
            window.location.search = params.toString();
        });
    });
});