function setCookie(name, value, days = 365) {
    const date = new Date();
    date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
    const expires = "expires=" + date.toUTCString();
    document.cookie = `${name}=${value};${expires};path=/`;
}

// универсальный обработчик сортировки
document.querySelectorAll('.sort-emails-btn, .sort-users-btn, .sort-incidents-btn, .sort-energy-company-btn').forEach(btn => {
    btn.addEventListener('click', function () {
        const sortValue = this.dataset.sort;
        const cookieName = this.dataset.cookie || 'sort_generic';
        const urlParam = this.dataset.param || 'sort';

        // запись cookie
        setCookie(cookieName, sortValue);

        // обновление URL
        const url = new URL(window.location.href);
        url.searchParams.set(urlParam, sortValue);

        window.location.href = url.toString();
    });
});
