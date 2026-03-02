document.addEventListener('DOMContentLoaded', () => {
  const dropdown = document.querySelector('.dropdown');
  const toggle = dropdown.querySelector('.dropdown-toggle');

  toggle.addEventListener('click', () => {
    dropdown.classList.toggle('open');
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.dropdown')) {
      dropdown.classList.remove('open');
    }
  });
});