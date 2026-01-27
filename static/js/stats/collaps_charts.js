// ================== COOKIES ==================
function setCookie(name, value, days = 365) {
    const expires = new Date(Date.now() + days * 24 * 60 * 60 * 1000).toUTCString();
    document.cookie = `${name}=${value}; path=/; expires=${expires}`;
}

function getCookie(name) {
    const matches = document.cookie.match(
        new RegExp('(?:^|; )' + name + '=([^;]*)')
    );
    return matches ? decodeURIComponent(matches[1]) : undefined;
}

// ================== HELPERS ==================
function isCollapsed(containerId) {
    const el = document.getElementById(containerId);
    return el?.classList.contains('collapsed');
}

window.isCollapsed = isCollapsed;

// ================== INIT TOGGLE ==================
document.addEventListener('DOMContentLoaded', () => {

    document.querySelectorAll('.toggle-chart-btn').forEach(btn => {
        const container = btn.parentElement;
        let containerId = container.id;

        if (!containerId) {
            containerId = 'chart-' + Math.random().toString(36).slice(2);
            container.id = containerId;
        }

        const cookieKey = `chart-${containerId}`;
        const saved = getCookie(cookieKey);

        // ⚠️ TEMP раскрываем, если было collapsed
        let shouldCollapseLater = false;
        if (saved === 'collapsed') {
            container.classList.remove('collapsed'); // временно показываем
            shouldCollapseLater = true;
        }

        // Обновляем текст кнопки
        const updateButtonText = () => {
            const collapsed = container.classList.contains('collapsed');
            btn.textContent = collapsed
                ? `▸ ${btn.dataset.baseText}` // свернуто — вправо
                : `▾ ${btn.dataset.baseText}`; // развернуто — вниз
        };

        // сохраняем "базовый текст" без стрелок
        btn.dataset.baseText = btn.textContent.replace(/^Свернуть |^Показать /, '');

        updateButtonText();

        // CLICK
        btn.addEventListener('click', () => {
            container.classList.toggle('collapsed');
            updateButtonText();
            setCookie(cookieKey,
                container.classList.contains('collapsed') ? 'collapsed' : 'expanded'
            );
        });

        // ⏱ После инициализации графиков — снова скрываем
        if (shouldCollapseLater) {
            requestAnimationFrame(() => {
                setTimeout(() => {
                    container.classList.add('collapsed');
                    updateButtonText();
                }, 100); // можно 0–100ms
            });
        }
    });

});
