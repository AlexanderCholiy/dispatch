function toggleAttachments(btn) {
  // Находим общий контейнер
  const wrapper = btn.closest('.email-attachments-wrapper');
  const list = wrapper.querySelector('.email-attachments');
  const body = btn.closest('.email-body'); // Для обновления maxHeight

  if (!list) return;

  const isHidden = list.classList.toggle('hidden');
  btn.textContent = isHidden ? 'Показать вложения' : 'Скрыть вложения';

  // Если письмо раскрыто (есть maxHeight), обновляем его под новый размер
  if (body && body.style.maxHeight) {
    requestAnimationFrame(() => {
      body.style.maxHeight = body.scrollHeight + "px";
    });
  }
}