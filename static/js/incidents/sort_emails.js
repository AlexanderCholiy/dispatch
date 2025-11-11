document.addEventListener('DOMContentLoaded', () => {
    const savedSort = new URLSearchParams(window.location.search).get('email_sort')
        || localStorage.getItem('email_sort')
        || 'asc';

    document.querySelectorAll('.sort-emails-btn').forEach(btn => {
        btn.disabled = btn.dataset.sort === savedSort;
        btn.addEventListener('click', () => {
            const sort = btn.dataset.sort;
            localStorage.setItem('email_sort', sort);
            const params = new URLSearchParams(window.location.search);
            params.set('email_sort', sort);
            window.location.search = params.toString();
        });
    });
});