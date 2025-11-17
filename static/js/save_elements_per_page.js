document.addEventListener('DOMContentLoaded', function() {
    const perPageSelect = document.getElementById('per-page');
    if (!perPageSelect) return;

    // создаём уникальный ключ per_page_<page>
    const cookieName = getPageCookieName();

    // пытаемся загрузить сохранённое значение
    const savedValue = getCookie(cookieName);
    if (savedValue && perPageSelect.querySelector(`option[value="${savedValue}"]`)) {
        perPageSelect.value = savedValue;
    }

    // сохраняем при изменении
    perPageSelect.addEventListener('change', function() {
        setCookie(cookieName, this.value, 30);
    });

    /**
     * Генерируем безопасное имя для cookie:
     * "/" -> per_page_root
     * "/emails/" -> per_page_emails
     * "/emails/archive/" -> per_page_emails_archive
     */
    function getPageCookieName() {
        let path = window.location.pathname;

        if (path === "/") {
            path = "root";
        } else {
            // делаем из /emails/list/ → emails_list
            path = path.replace(/^\/|\/$/g, "").replace(/\W+/g, "_");
        }

        return "per_page_" + path;
    }

    function setCookie(name, value, days) {
        const expires = new Date();
        expires.setDate(expires.getDate() + days);
        document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
    }

    function getCookie(name) {
        const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
        return match ? decodeURIComponent(match[1]) : null;
    }
});
