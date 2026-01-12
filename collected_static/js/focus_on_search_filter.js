const header = document.getElementById('header');
const searchInput = document.getElementById('search-input');

if (header && searchInput) {
  header.addEventListener('click', (event) => {
    const target = event.target;
    if (
      target.closest('button') ||
      target.closest('a') ||
      (target.closest('form') && !target.closest('#search-form'))
    ) return;

    // Мягкий фокус без скачков
    requestAnimationFrame(() => searchInput.focus());
  });
}
