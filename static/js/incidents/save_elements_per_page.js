document.addEventListener('DOMContentLoaded', function() {
    const perPageSelect = document.getElementById('per-page');

    const savedValue = getCookie('per_page');
    if (savedValue && perPageSelect.querySelector(`option[value="${savedValue}"]`)) {
        perPageSelect.value = savedValue;
    }

    perPageSelect.addEventListener('change', function() {
        setCookie('per_page', this.value, 30);
    });

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