document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll('a[href^="#email-"]').forEach(link => {
    link.addEventListener('click', function (e) {
      e.preventDefault();
      const targetId = this.getAttribute('href').substring(1);
      const target = document.getElementById(targetId);

      if (target) {
        // Плавный скролл
        target.scrollIntoView({ behavior: 'smooth'});

        // Эффект подсветки
        target.classList.add('email-highlight');
        setTimeout(() => target.classList.remove('email-highlight'), 1500);
      }
    });
  });
});