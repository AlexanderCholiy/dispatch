document.addEventListener('DOMContentLoaded', () => {
  const emailSort = localStorage.getItem('email_sort') || 'asc';
  document.querySelectorAll('.incident-link').forEach(link => {
      const url = new URL(link.href);
      url.searchParams.set('email_sort', emailSort);
      link.href = url.toString();
  });
});